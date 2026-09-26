"""GUI-level tests: font packaging, workspace wiring, dropped files, and written output."""
import logging
import os
import tempfile
import tkinter
import unittest
from unittest import mock

from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Link
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, NumberObject

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


def make_linked_pdf(directory: str, name: str) -> str:
    """Write a 6-page PDF where page 1 links to page 5, with outline Chapter 1 (p1) > Section 1.1 (p2), Chapter 5 (p5)."""
    path = os.path.join(directory, name)
    writer = PdfWriter()
    for offset in range(6):
        writer.add_blank_page(width=200 + offset, height=200)
    source_page, target_page = writer.pages[0], writer.pages[4]
    annotation = DictionaryObject()
    annotation[NameObject("/Type")] = NameObject("/Annot")
    annotation[NameObject("/Subtype")] = NameObject("/Link")
    annotation[NameObject("/Rect")] = ArrayObject(NumberObject(value) for value in (0, 0, 100, 100))
    annotation[NameObject("/Dest")] = ArrayObject([target_page.indirect_reference, NameObject("/Fit")])
    source_page[NameObject("/Annots")] = ArrayObject([writer._add_object(annotation)])
    chapter_one = writer.add_outline_item("Chapter 1", 0)
    writer.add_outline_item("Section 1.1", 1, parent=chapter_one)
    writer.add_outline_item("Chapter 5", 4)
    with open(path, "wb") as handle:
        writer.write(handle)
    return path


def make_encrypted_pdf(directory: str, name: str, user_password: str = "pw", owner_password: str = "owner") -> str:
    """Write a password-protected PDF. An empty user password leaves it openable by any viewer."""
    path = os.path.join(directory, name)
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt(user_password, owner_password=owner_password)
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
        patcher = mock.patch.object(slicepdf, "FOLDER_FILE", os.path.join(self.work, "settings", "output-folder.txt"))
        patcher.start()
        self.addCleanup(patcher.stop)

        self.app = slicepdf.App()
        self.app.withdraw()
        self.addCleanup(self.close_app)

    def close_app(self):
        """Cancel CustomTkinter's pending after() callbacks so teardown stays quiet."""
        # With its callbacks cancelled, an open CTkToplevel breaks the root's destroy.
        if self.app.about_window is not None:
            self.app.about_window.destroy()
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

    def hint(self):
        self.app._update_hint()
        return self.app.outcome_hint.cget("text")

    def fill_range(self, index, start, end, name="Part"):
        while len(self.app.rows) <= index:
            self.app.add_row()
        self.app.rows[index].name_entry.insert(0, name)
        self.app.rows[index].from_entry.insert(0, start)
        self.app.rows[index].to_entry.insert(0, end)

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
        self.assertEqual(self.app.source_meta.cget("text"), "")
        self.assertEqual(self.app.drop_headline.cget("text"), "Place a PDF on the desk")

    def test_drop_zone_offers_to_replace_a_loaded_source(self):
        self.load(self.source)
        self.assertEqual(self.app.drop_headline.cget("text"), "Drop another PDF to replace this one")
        self.app.change_operation("merge")
        self.assertEqual(self.app.drop_headline.cget("text"), "Drop other PDFs to replace these")

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

    def test_hint_stays_empty_until_a_source_is_chosen(self):
        self.app.change_operation("count")
        self.fill("count", "4")
        self.assertEqual(self.hint(), "")

    def test_count_hint_reports_the_files_it_would_write(self):
        self.app.change_operation("count")
        self.load(self.source)
        self.fill("count", "4")
        self.assertEqual(self.hint(), "6 pages → 2 files.")

    def test_count_hint_reads_as_singular_for_one_file(self):
        self.app.change_operation("count")
        self.load(self.source)
        self.fill("count", "6")
        self.assertEqual(self.hint(), "6 pages → 1 file.")

    def test_keep_hint_counts_the_pages_kept(self):
        self.app.change_operation("keep")
        self.load(self.source)
        self.fill("pages", "1-3, 5")
        self.assertEqual(self.hint(), "6 pages → 4 pages.")

    def test_delete_hint_counts_the_pages_left(self):
        self.app.change_operation("delete")
        self.load(self.source)
        self.fill("pages", "2, 5-6")
        self.assertEqual(self.hint(), "6 pages → 3 pages.")

    def test_trim_hint_waits_until_something_is_removed(self):
        self.app.change_operation("trim")
        self.load(self.source)
        self.assertEqual(self.hint(), "")
        self.fill("start", "1")
        self.fill("end", "2")
        self.assertEqual(self.hint(), "6 pages → 3 pages.")

    def test_named_hint_counts_files_and_the_pages_they_use(self):
        self.app.change_operation("named")
        self.load(self.source)
        self.fill_range(0, "1", "2")
        self.fill_range(1, "3", "6")
        self.assertEqual(self.hint(), "2 files → 6 of 6 pages.")

    def test_named_hint_ignores_a_range_that_is_still_blank(self):
        self.app.change_operation("named")
        self.load(self.source)
        self.fill_range(0, "1", "2")
        self.app.add_row()
        self.assertEqual(self.hint(), "1 file → 2 of 6 pages.")

    def test_named_hint_waits_for_an_output_name(self):
        self.app.change_operation("named")
        self.load(self.source)
        self.fill_range(0, "1", "2", name="")
        self.assertEqual(self.hint(), "")

    def test_hint_stays_empty_while_the_input_is_unusable(self):
        self.app.change_operation("keep")
        self.load(self.source)
        self.fill("pages", "1-")
        self.assertEqual(self.hint(), "")
        self.fill("pages", "9")
        self.assertEqual(self.hint(), "")

    def test_merge_has_no_outcome_hint(self):
        self.app.change_operation("merge")
        self.load(self.source, self.source)
        self.assertIsNone(self.app.outcome_hint)

    def test_file_button_wording_matches_the_operation(self):
        self.app.change_operation("merge")
        self.assertEqual(self.app.file_button.cget("text"), "Choose PDFs…")
        self.app.change_operation("keep")
        self.assertEqual(self.app.file_button.cget("text"), "Choose PDF…")

    def test_progress_is_hidden_until_an_operation_runs(self):
        self.assertEqual(self.app.progress.grid_info(), {})
        self.assertEqual(self.app.cancel_button.grid_info(), {})

    def test_chosen_output_folder_is_remembered_for_the_next_launch(self):
        folder = tempfile.mkdtemp(dir=self.work)
        with mock.patch.object(slicepdf.filedialog, "askdirectory", return_value=folder):
            self.app.choose_output()
        self.close_app()
        self.app = slicepdf.App()
        self.app.withdraw()
        self.assertEqual(self.app.out_dir, folder)
        self.assertTrue(self.app.out_label.cget("text").endswith(os.path.basename(folder)))

    def test_long_output_folder_keeps_its_last_folder_names(self):
        self.assertEqual(slicepdf.short_path("D:/Reports/Split"), r"D:\Reports\Split")
        long = r"C:\Users\someone\OneDrive - Company\Documents\Clients\2026\Reports"
        self.assertEqual(slicepdf.short_path(long), r"…\Documents\Clients\2026\Reports")

    def test_about_window_links_to_the_project(self):
        self.app.show_about()
        buttons = {child.cget("text"): child for child in self.app.about_window.winfo_children() if isinstance(child, slicepdf.ctk.CTkButton)}
        self.assertEqual(list(buttons), list(slicepdf.LINKS))
        with mock.patch.object(slicepdf.webbrowser, "open") as opened:
            buttons["Releases"].invoke()
        opened.assert_called_once_with("https://github.com/MithunWijayasiri/SlicePDF/releases")

    def test_about_opens_only_one_window(self):
        self.app.show_about()
        first = self.app.about_window
        self.app.show_about()
        self.assertIs(self.app.about_window, first)

    def test_remembered_folder_that_no_longer_exists_is_ignored(self):
        os.makedirs(os.path.dirname(slicepdf.FOLDER_FILE))
        with open(slicepdf.FOLDER_FILE, "w", encoding="utf-8") as handle:
            handle.write(os.path.join(self.work, "gone"))
        self.assertIsNone(slicepdf.remembered_folder())

    def test_unreadable_remembered_folder_file_is_ignored(self):
        os.makedirs(os.path.dirname(slicepdf.FOLDER_FILE))
        with open(slicepdf.FOLDER_FILE, "wb") as handle:
            handle.write(b"\xff\xfe\x00bad")
        self.assertIsNone(slicepdf.remembered_folder())

    def test_unreadable_source_is_reported_and_not_adopted(self):
        broken = os.path.join(self.work, "broken.pdf")
        with open(broken, "wb") as handle:
            handle.write(b"not really a pdf")
        self.load(broken)
        self.assertEqual(self.app.pdf_paths, [])
        self.assertIn("Could not read PDF", self.dialogs[0])

    def test_empty_pdf_is_rejected_at_load(self):
        self.load(make_pdf(self.work, "empty.pdf", 0))
        self.assertEqual(self.app.pdf_paths, [])
        self.assertIn("empty.pdf has no pages.", self.dialogs[0])

    def test_password_protected_pdf_is_rejected_at_load(self):
        self.load(make_encrypted_pdf(self.work, "locked.pdf"))
        self.assertEqual(self.app.pdf_paths, [])
        self.assertIn("locked.pdf is password-protected. SlicePDF cannot open it.", self.dialogs[0])

    def test_pdf_openable_with_an_empty_password_is_still_adopted(self):
        restricted = make_encrypted_pdf(self.work, "print-restricted.pdf", user_password="")
        self.load(restricted)
        self.assertEqual(self.app.pdf_paths, [restricted])
        self.assertEqual(self.app.total_pages, 1)
        self.assertEqual(self.dialogs, [])

    def test_one_bad_file_rejects_the_whole_merge_selection(self):
        self.app.change_operation("merge")
        self.load(self.source)
        self.load(self.source, make_pdf(self.work, "empty.pdf", 0))
        self.assertEqual(self.app.pdf_paths, [self.source])
        self.assertIn("empty.pdf has no pages.", self.dialogs[0])


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


class OperationTestCase(AppTestCase):
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


class OperationOutputTests(OperationTestCase):
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

    def test_failure_partway_leaves_a_complete_file_on_disk(self):
        directory = tempfile.mkdtemp(dir=self.work)
        real_write = PdfWriter.write
        writes = []

        def fail_on_the_second(writer, stream):
            writes.append(stream)
            if len(writes) > 1:
                raise OSError("The disk is full.")
            return real_write(writer, stream)

        with mock.patch.object(PdfWriter, "write", fail_on_the_second):
            self.run_operation("count", (2, "batch"), destination=directory)
        self.assertIn("The disk is full.", self.dialogs[-1])
        self.assertIn(f"Stopped after writing 1 file. It is still in {directory}.", self.dialogs[-1])
        self.assertEqual(len(PdfReader(os.path.join(directory, "batch-1.pdf")).pages), 2)
        self.assertEqual(os.listdir(directory), ["batch-1.pdf"])

    def test_failure_later_names_every_file_and_the_folder(self):
        directory = tempfile.mkdtemp(dir=self.work)
        with mock.patch.object(PdfWriter, "write", side_effect=[None, None, OSError("The disk is full.")]):
            self.run_operation("count", (2, "batch"), destination=directory)
        self.assertIn(f"Stopped after writing 2 files. They are still in {directory}.", self.dialogs[-1])

    def test_cancel_before_the_first_file_writes_nothing(self):
        self.app.cancel_requested.set()
        out = self.run_operation("count", (2, "batch"))
        self.assertEqual(os.listdir(out), [])
        self.assertEqual(self.app.message.cget("text"), "Cancelled — 0 files saved.")
        self.assertEqual(self.app.run_button.cget("state"), "normal")

    def test_cancel_stops_after_the_current_file_and_keeps_it(self):
        real_write = PdfWriter.write

        def write_then_cancel(writer, stream):
            real_write(writer, stream)
            self.app.cancel_operation()

        with mock.patch.object(PdfWriter, "write", write_then_cancel):
            out = self.run_operation("count", (2, "batch"))
        self.assertEqual(self.page_counts(out), {"batch-1.pdf": 2})
        self.assertEqual(self.app.message.cget("text"), "Cancelled — 1 file saved.")

    def test_failure_before_any_write_does_not_claim_partial_files(self):
        self.app.out_dir = tempfile.mkdtemp(dir=self.work)
        self.run_inline("keep", [os.path.join(self.work, "missing.pdf")], ("1-2", "kept.pdf"))
        self.assertIn("Error", self.dialogs[-1])
        self.assertNotIn("Stopped after writing", self.dialogs[-1])


class LinksAndBookmarksTests(OperationTestCase):
    """Internal links and bookmarks follow their pages; ones pointing at a missing page are dropped."""

    def setUp(self):
        super().setUp()
        self.linked = make_linked_pdf(self.work, "linked.pdf")

    def outline_pages(self, directory, name):
        """(title, zero-based target page index) for every outline entry, depth-first."""
        reader = PdfReader(os.path.join(directory, name))

        def walk(items):
            for item in items:
                if isinstance(item, list):
                    yield from walk(item)
                else:
                    yield item.title, reader.get_destination_page_number(item)

        return list(walk(reader.outline))

    def link_target(self, directory, name, page_index):
        """Zero-based target page index of the link annotation on one page, or None."""
        reader = PdfReader(os.path.join(directory, name))
        for annotation in reader.pages[page_index].get("/Annots", []):
            annotation = annotation.get_object()
            if annotation.get("/Subtype") == "/Link":
                target = annotation["/Dest"][0]
                return next(i for i, page in enumerate(reader.pages) if page.indirect_reference == target)
        return None

    def test_keep_subset_including_the_link_target_remaps_it(self):
        out = self.run_operation("keep", ("1, 2, 5", "kept.pdf"), paths=[self.linked])
        self.assertEqual(self.link_target(out, "kept.pdf", 0), 2)

    def test_keep_subset_excluding_the_link_target_drops_it(self):
        out = self.run_operation("keep", ("1, 2, 3", "kept.pdf"), paths=[self.linked])
        self.assertIsNone(self.link_target(out, "kept.pdf", 0))

    def test_reorder_carries_the_link_and_bookmarks_to_their_new_pages(self):
        out = self.run_operation("reorder", ("5, 1", "order.pdf"), paths=[self.linked])
        self.assertEqual(self.outline_pages(out, "order.pdf"), [("Chapter 1", 1), ("Chapter 5", 0)])
        self.assertEqual(self.link_target(out, "order.pdf", 1), 0)

    def test_count_split_gives_each_file_only_its_own_bookmarks(self):
        out = self.run_operation("count", (4, "batch"), paths=[self.linked])
        self.assertEqual(self.outline_pages(out, "batch-1.pdf"), [("Chapter 1", 0), ("Section 1.1", 1)])
        self.assertEqual(self.outline_pages(out, "batch-2.pdf"), [("Chapter 5", 0)])
        self.assertIsNone(self.link_target(out, "batch-1.pdf", 0))

    def test_merge_offsets_the_second_files_link_and_bookmarks(self):
        out = self.run_operation("merge", "all.pdf", paths=[self.linked, self.linked])
        self.assertEqual(
            self.outline_pages(out, "all.pdf"),
            [("Chapter 1", 0), ("Section 1.1", 1), ("Chapter 5", 4),
             ("Chapter 1", 6), ("Section 1.1", 7), ("Chapter 5", 10)],
        )
        self.assertEqual(self.link_target(out, "all.pdf", 0), 4)
        self.assertEqual(self.link_target(out, "all.pdf", 6), 10)

    def test_link_written_as_a_bare_page_number_is_remapped(self):
        # pypdf's Link helper writes a page number, not a page reference; append drops it before pypdf 6.16.
        path = os.path.join(self.work, "numbered.pdf")
        writer = PdfWriter()
        for offset in range(6):
            writer.add_blank_page(width=200 + offset, height=200)
        writer.add_annotation(page_number=0, annotation=Link(rect=(0, 0, 100, 100), target_page_index=4))
        with open(path, "wb") as handle:
            writer.write(handle)
        out = self.run_operation("keep", ("1, 5", "kept.pdf"), paths=[path])
        self.assertEqual(self.link_target(out, "kept.pdf", 0), 1)

    def test_dropped_parent_bookmark_stays_as_a_heading_over_surviving_children(self):
        out = self.run_operation("keep", ("2-6", "kept.pdf"), paths=[self.linked])
        self.assertEqual(self.outline_pages(out, "kept.pdf"), [("Chapter 1", None), ("Section 1.1", 0), ("Chapter 5", 3)])


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
