"""GUI-level tests: font packaging, workspace wiring, dropped files, and written output."""
import logging
import os
import tempfile
import tkinter
import unittest
from unittest import mock

from pypdf import PdfReader, PdfWriter

import slicepdf

# Private font registration must happen before any Tk interpreter reads the family list.
slicepdf.register_bundled_fonts()

# Tests feed pypdf deliberately broken files; its warnings are the expected outcome.
logging.getLogger("pypdf").setLevel(logging.ERROR)


def tk_available() -> bool:
    """Report whether this machine can open a Tk window at all."""
    try:
        root = tkinter.Tk()
    except tkinter.TclError:
        return False
    root.destroy()
    return True


TK_AVAILABLE = tk_available()


def make_pdf(directory: str, name: str, pages: int, first_width: int = 200) -> str:
    """Write a blank PDF and return its path. Page widths ascend so page identity is checkable."""
    path = os.path.join(directory, name)
    writer = PdfWriter()
    for offset in range(pages):
        writer.add_blank_page(width=first_width + offset, height=200)
    with open(path, "wb") as handle:
        writer.write(handle)
    return path


@unittest.skipUnless(TK_AVAILABLE, "Tk cannot open a window in this environment")
class AppTestCase(unittest.TestCase):
    """A hidden App instance with dialogs captured instead of shown."""

    def setUp(self):
        self.dialogs: list[str] = []
        for name in ("showerror", "showwarning"):
            patcher = mock.patch.object(slicepdf.messagebox, name, self.record_dialog)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(slicepdf.messagebox, "askyesno", return_value=False)
        patcher.start()
        self.addCleanup(patcher.stop)

        # PdfReader holds its source open, which can block temp cleanup on Windows.
        directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(directory.cleanup)
        self.work = directory.name
        self.source = make_pdf(self.work, "source.pdf", 6)
        self.second = make_pdf(self.work, "appendix.pdf", 2, first_width=300)

        self.app = slicepdf.App()
        self.app.withdraw()
        self.addCleanup(self.close_app)

    def close_app(self):
        """Cancel CustomTkinter's pending after() callbacks so teardown stays quiet."""
        for after_id in self.app.tk.splitlist(self.app.tk.call("after", "info")):
            self.app.after_cancel(after_id)
        self.app.destroy()

    def record_dialog(self, title, message):
        self.dialogs.append(f"{title}: {message}")

    def load(self, *paths):
        """Adopt sources the way choosing or dropping them does."""
        self.app._load_paths(list(paths))

    def fill(self, key, value):
        self.app.controls[key].delete(0, "end")
        self.app.controls[key].insert(0, value)

    def drop_payload(self, *paths):
        """Build the string tkdnd delivers as %D: a quoted Tcl list of paths."""
        return self.app.tk.call("format", "%s", self.app.tk.call("list", *paths))

    def subtree(self, widget):
        yield widget
        for child in widget.winfo_children():
            yield from self.subtree(child)

    def bindings(self, widget):
        """Sequences bound on this exact widget path; CTk's bind() override hides them."""
        return widget.tk.splitlist(widget.tk.call("bind", str(widget)))


class FontPackagingTests(AppTestCase):
    def test_bundled_manrope_is_used_not_a_fallback(self):
        self.assertEqual(self.app.fonts["body"][0], "Manrope")
        self.assertEqual(self.app.fonts["small"][0], "Manrope")
        self.assertEqual(self.app.fonts["display"][0], "Manrope ExtraBold")

    def test_no_font_is_segoe_ui_or_roboto(self):
        families = {font[0] for font in self.app.fonts.values()}
        self.assertNotIn("Segoe UI", families)
        self.assertNotIn("Roboto", families)
        self.assertNotIn(slicepdf.FONT_FALLBACK, families)

    def test_font_files_ship_beside_the_app(self):
        directory = slicepdf.resource_path("assets", "fonts")
        for name in ("Manrope-Regular.ttf", "Manrope-Bold.ttf", "Manrope-ExtraBold.ttf"):
            self.assertTrue(os.path.isfile(os.path.join(directory, name)), name)


class WorkspaceTests(AppTestCase):
    def test_sidebar_offers_every_operation(self):
        self.assertEqual(len(self.app.operation_buttons), 7)
        self.assertEqual(set(self.app.operation_buttons), set(slicepdf.OPERATIONS.values()))

    def test_selected_operation_is_the_only_highlighted_one(self):
        self.app.change_operation("trim")
        highlighted = [mode for mode, button in self.app.operation_buttons.items()
                       if button.cget("fg_color") == slicepdf.SELECTED]
        self.assertEqual(highlighted, ["trim"])

    def test_each_operation_exposes_only_its_own_fields(self):
        expected = {
            "named": set(),
            "delete": {"pages", "filename"},
            "keep": {"pages", "filename"},
            "reorder": {"pages", "filename"},
            "trim": {"start", "end", "filename"},
            "count": {"count", "filename"},
            "merge": {"filename"},
        }
        for mode, keys in expected.items():
            self.app.change_operation(mode)
            self.assertEqual(set(self.app.controls), keys, mode)

    def test_title_and_description_follow_the_operation(self):
        self.app.change_operation("merge")
        self.assertEqual(self.app.title_label.cget("text"), "Merge PDFs")
        self.assertEqual(self.app.description.cget("text"), slicepdf.DESCRIPTIONS["merge"])

    def test_named_ranges_start_with_one_row_and_grow(self):
        self.app.change_operation("named")
        self.assertEqual(len(self.app.rows), 1)
        self.app.add_row()
        self.assertEqual(len(self.app.rows), 2)

    def test_removing_the_last_named_row_leaves_one_behind(self):
        self.app.change_operation("named")
        self.app.remove_row(self.app.rows[0])
        self.assertEqual(len(self.app.rows), 1)

    def test_empty_source_panel_state(self):
        self.assertEqual(self.app.source_name.cget("text"), "Nothing on the desk yet")
        self.assertEqual(self.app.source_meta.cget("text"), "PDF · — pages")

    def test_loaded_source_panel_shows_name_and_page_count(self):
        self.load(self.source)
        self.assertEqual(self.app.source_name.cget("text"), "source.pdf")
        self.assertEqual(self.app.source_meta.cget("text"), "PDF · 6 pages")

    def test_merge_source_panel_counts_files(self):
        self.app.change_operation("merge")
        self.load(self.source, self.second)
        self.assertEqual(self.app.source_name.cget("text"), "2 PDFs selected")
        self.load(self.source)
        self.assertEqual(self.app.source_name.cget("text"), "1 PDF selected")

    def test_switching_operation_keeps_the_chosen_source(self):
        self.load(self.source)
        self.app.change_operation("count")
        self.assertEqual(self.app.pdf_paths, [self.source])
        self.assertEqual(self.app.total_pages, 6)

    def test_batch_hint_appears_once_source_and_count_are_valid(self):
        self.app.change_operation("count")
        self.assertEqual(self.app.batch_hint.cget("text"), "")
        self.load(self.source)
        self.fill("count", "4")
        self.app._update_batch_hint()
        self.assertEqual(self.app.batch_hint.cget("text"), "6 pages → 2 files.")

    def test_file_button_wording_matches_the_operation(self):
        self.app.change_operation("merge")
        self.assertEqual(self.app.file_button.cget("text"), "Choose PDFs…")
        self.app.change_operation("keep")
        self.assertEqual(self.app.file_button.cget("text"), "Choose PDF…")

    def test_progress_is_hidden_until_an_operation_runs(self):
        self.assertEqual(self.app.progress.grid_info(), {})

    def test_unreadable_source_is_reported_and_not_adopted(self):
        broken = os.path.join(self.work, "broken.pdf")
        with open(broken, "wb") as handle:
            handle.write(b"not really a pdf")
        self.load(broken)
        self.assertEqual(self.app.pdf_paths, [])
        self.assertIn("Could not read PDF", self.dialogs[0])


class DropZoneTests(AppTestCase):
    def test_every_widget_in_the_drop_zone_accepts_drops(self):
        widgets = list(self.subtree(self.app.drop_zone))
        self.assertGreater(len(widgets), 1)
        for widget in widgets:
            self.assertIn("<<Drop>>", self.bindings(widget), str(widget))

    def test_nothing_outside_the_drop_zone_accepts_drops(self):
        panel = self.app.source_name.master
        for widget in self.subtree(panel):
            self.assertNotIn("<<Drop>>", self.bindings(widget), str(widget))

    def test_dropped_path_containing_spaces_survives_parsing(self):
        spaced = make_pdf(self.work, "quarterly report final.pdf", 5)
        self.app._on_drop(mock.Mock(data=self.drop_payload(spaced)))
        self.assertEqual(self.app.pdf_paths, [spaced])
        self.assertEqual(self.app.total_pages, 5)
        self.assertEqual(self.dialogs, [])

    def test_single_file_operation_takes_the_first_dropped_pdf(self):
        self.app.change_operation("keep")
        self.app._on_drop(mock.Mock(data=self.drop_payload(self.source, self.second)))
        self.assertEqual(self.app.pdf_paths, [self.source])

    def test_merge_keeps_every_dropped_pdf_in_drop_order(self):
        self.app.change_operation("merge")
        self.app._on_drop(mock.Mock(data=self.drop_payload(self.second, self.source)))
        self.assertEqual(self.app.pdf_paths, [self.second, self.source])

    def test_drop_without_a_pdf_is_refused(self):
        other = os.path.join(self.work, "notes.txt")
        open(other, "w").close()
        self.app._on_drop(mock.Mock(data=self.drop_payload(other)))
        self.assertEqual(self.app.pdf_paths, [])
        self.assertIn("Place a PDF file on the desk", self.dialogs[0])

    def test_failed_drop_leaves_the_previous_source_in_place(self):
        self.load(self.source)
        broken = os.path.join(self.work, "broken.pdf")
        with open(broken, "wb") as handle:
            handle.write(b"not really a pdf")
        self.app._on_drop(mock.Mock(data=self.drop_payload(broken)))
        self.assertEqual(self.app.pdf_paths, [self.source])
        self.assertIn("Could not read PDF", self.dialogs[0])


class OperationOutputTests(AppTestCase):
    """The worker body runs inline here: after() needs a mainloop unittest does not run."""

    def run_inline(self, mode, paths, payload):
        """Run the worker body on this thread, with after() calling straight through."""
        def immediate(_delay, callback=None, *args):
            if callback:
                callback(*args)

        with mock.patch.object(self.app, "after", immediate):
            self.app._run(mode, paths, payload)

    def run_operation(self, mode, payload, paths=None, destination=None):
        self.app.change_operation(mode)
        self.app.pdf_paths = paths or [self.source]
        self.app.total_pages = 6
        self.app.out_dir = destination or tempfile.mkdtemp(dir=self.work)
        self.run_inline(mode, self.app.pdf_paths, payload)
        return self.app.out_dir

    def page_counts(self, directory):
        return {name: len(PdfReader(os.path.join(directory, name)).pages)
                for name in sorted(os.listdir(directory))}

    def page_widths(self, directory, name):
        """Page widths of one output, which identify the source pages and their order."""
        return [int(page.mediabox.width) for page in PdfReader(os.path.join(directory, name)).pages]

    def test_named_ranges_write_one_file_each(self):
        out = self.run_operation("named", [("Intro", 1, 2), ("Body", 3, 6)])
        self.assertEqual(self.page_counts(out), {"Body.pdf": 4, "Intro.pdf": 2})

    def test_delete_keeps_the_remaining_pages(self):
        out = self.run_operation("delete", ("2, 5-6", "kept.pdf"))
        self.assertEqual(self.page_counts(out), {"kept.pdf": 3})

    def test_keep_writes_only_the_selected_pages(self):
        out = self.run_operation("keep", ("1-3", "keep.pdf"))
        self.assertEqual(self.page_counts(out), {"keep.pdf": 3})

    def test_reorder_writes_the_requested_order(self):
        out = self.run_operation("reorder", ("3, 1-2", "order.pdf"))
        self.assertEqual(self.page_widths(out, "order.pdf"), [202, 200, 201])

    def test_trim_removes_pages_from_both_ends(self):
        out = self.run_operation("trim", (1, 2, "trim.pdf"))
        self.assertEqual(self.page_counts(out), {"trim.pdf": 3})

    def test_split_by_count_writes_batches(self):
        out = self.run_operation("count", (4, "batch"))
        self.assertEqual(self.page_counts(out), {"batch-1.pdf": 4, "batch-2.pdf": 2})

    def test_merge_joins_sources_in_order(self):
        out = self.run_operation("merge", "all.pdf", paths=[self.source, self.second])
        self.assertEqual(self.page_widths(out, "all.pdf"), [200, 201, 202, 203, 204, 205, 300, 301])

    def test_existing_output_is_never_overwritten(self):
        destination = tempfile.mkdtemp(dir=self.work)
        with open(os.path.join(destination, "keep.pdf"), "wb") as handle:
            handle.write(b"original bytes")
        self.run_operation("keep", ("1-2", "keep.pdf"), destination=destination)
        with open(os.path.join(destination, "keep.pdf"), "rb") as handle:
            self.assertEqual(handle.read(), b"original bytes")
        self.assertTrue(os.path.exists(os.path.join(destination, "keep-2.pdf")))

    def test_output_lands_beside_the_source_when_no_folder_is_chosen(self):
        folder = tempfile.mkdtemp(dir=self.work)
        source = make_pdf(folder, "beside.pdf", 4)
        self.app.out_dir = None
        self.run_inline("keep", [source], ("1-2", "kept.pdf"))
        self.assertEqual(self.page_counts(folder), {"beside.pdf": 4, "kept.pdf": 2})

    def test_source_pdf_is_left_untouched(self):
        self.run_operation("count", (2, "batch"))
        self.assertEqual(len(PdfReader(self.source).pages), 6)


class ValidationTests(AppTestCase):
    """start_operation must reject bad input before any worker thread starts."""

    def start(self, mode, fields=None, paths=None):
        self.app.change_operation(mode)
        if paths is not None:
            self.load(*paths)
        for key, value in (fields or {}).items():
            self.fill(key, value)
        self.app.out_dir = tempfile.mkdtemp(dir=self.work)
        self.app.start_operation()
        return self.app.out_dir

    def assertRejected(self, out_dir, fragment):
        self.assertTrue(self.dialogs, "expected a dialog")
        self.assertIn(fragment, self.dialogs[-1])
        self.assertEqual(os.listdir(out_dir), [])
        self.assertEqual(self.app.run_button.cget("state"), "normal")

    def test_running_without_a_source_warns(self):
        out = self.start("keep", {"pages": "1-2"})
        self.assertRejected(out, "Choose a PDF first")

    def test_reorder_rejects_a_repeated_page(self):
        out = self.start("reorder", {"pages": "3, 1-3"}, paths=[self.source])
        self.assertRejected(out, "listed more than once")

    def test_pages_outside_the_document_are_rejected(self):
        out = self.start("keep", {"pages": "5-9"}, paths=[self.source])
        self.assertRejected(out, "between 1 and 6")

    def test_trim_may_not_remove_every_page(self):
        out = self.start("trim", {"start": "3", "end": "3"}, paths=[self.source])
        self.assertRejected(out, "at least one page")

    def test_batch_size_must_be_positive(self):
        out = self.start("count", {"count": "0"}, paths=[self.source])
        self.assertRejected(out, "positive whole number")

    def test_empty_batch_size_is_reported_in_plain_words(self):
        out = self.start("count", {}, paths=[self.source])
        self.assertRejected(out, "Pages per output file must be a whole number.")

    def test_non_numeric_trim_input_is_reported_in_plain_words(self):
        out = self.start("trim", {"start": "two"}, paths=[self.source])
        self.assertRejected(out, "Pages to remove from the beginning must be a whole number.")

    def test_merge_needs_two_sources(self):
        out = self.start("merge", {}, paths=[self.source])
        self.assertRejected(out, "at least two PDFs")

    def test_named_range_needs_a_name(self):
        self.app.change_operation("named")
        self.load(self.source)
        self.app.rows[0].from_entry.insert(0, "1")
        self.app.rows[0].to_entry.insert(0, "2")
        self.app.out_dir = tempfile.mkdtemp(dir=self.work)
        self.app.start_operation()
        self.assertRejected(self.app.out_dir, "output name is empty")

    def test_named_range_ending_before_it_starts_is_rejected(self):
        self.app.change_operation("named")
        self.load(self.source)
        self.app.rows[0].name_entry.insert(0, "Intro")
        self.app.rows[0].from_entry.insert(0, "5")
        self.app.rows[0].to_entry.insert(0, "2")
        self.app.out_dir = tempfile.mkdtemp(dir=self.work)
        self.app.start_operation()
        self.assertRejected(self.app.out_dir, "From cannot come after To")

    def test_at_least_one_named_range_is_required(self):
        out = self.start("named", {}, paths=[self.source])
        self.assertRejected(out, "at least one named range")


if __name__ == "__main__":
    unittest.main()
