"""SlicePDF: perform common page-level PDF operations."""
import ctypes
import os
import sys
import threading
import tkinter.font
from collections.abc import Callable
from tkinter import filedialog, messagebox

import customtkinter as ctk
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError
from tkinterdnd2 import DND_FILES, TkinterDnD

from pdf_operations import (
    parse_page_expression,
    parse_page_order,
    safe_filename,
    split_by_count,
    trim_pages,
    unique_filename,
)

ctk.set_appearance_mode("light")

PAPER = "#f7f3eb"
SIDEBAR = "#eee9df"
SURFACE = "#fffdf9"
INK = "#332b25"
MUTED = "#7b7168"
LINE = "#ddd3c5"
ACCENT = "#9a5529"
ACCENT_DARK = "#7d3e1d"
SELECTED = "#dfc5af"
SUCCESS = "#4f7b62"
ERROR = "#a04435"

FR_PRIVATE = 0x10
FONT_FALLBACK = "Corbel"

OPERATIONS = {
    "Split by named ranges": "named",
    "Delete selected pages": "delete",
    "Trim start/end": "trim",
    "Split by page count": "count",
    "Keep selected pages": "keep",
    "Reorder pages": "reorder",
    "Merge PDFs": "merge",
}
DESCRIPTIONS = {
    "named": "Divide a PDF into named files using inclusive page ranges.",
    "delete": "Remove selected pages and keep everything else.",
    "trim": "Remove pages from the beginning, the end, or both.",
    "count": "Create evenly sized batches from one PDF.",
    "keep": "Create a PDF containing only the pages you select.",
    "reorder": "Arrange selected pages in the order you enter.",
    "merge": "Combine two or more PDFs in the order you choose.",
}
PAGE_FIELDS = {
    "delete": ("PAGES TO DELETE", "Example: 2, 5-7, 12"),
    "keep": ("PAGES TO KEEP", "Example: 1-3, 8, 10-12"),
    "reorder": ("PAGE ORDER", "Example: 3, 1-2, 4"),
}
ENTRY_STYLE = {
    "border_color": LINE,
    "border_width": 1,
    "corner_radius": 4,
    "fg_color": SURFACE,
    "text_color": INK,
    "placeholder_text_color": MUTED,
    "height": 36,
}


def resource_path(*parts: str) -> str:
    """Resolve a bundled asset path for both source and PyInstaller runs."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def register_bundled_fonts() -> None:
    """Register the bundled Manrope faces for this process only. Call before Tk starts."""
    directory = resource_path("assets", "fonts")
    if sys.platform != "win32" or not os.path.isdir(directory):
        return
    for name in sorted(os.listdir(directory)):
        if name.lower().endswith(".ttf"):
            ctypes.windll.gdi32.AddFontResourceExW(os.path.join(directory, name), FR_PRIVATE, 0)


def resolve_fonts() -> dict[str, tuple]:
    """Pick font families once a Tk root exists, falling back if Manrope is unavailable."""
    families = set(tkinter.font.families())
    body = "Manrope" if "Manrope" in families else FONT_FALLBACK
    heavy = "Manrope ExtraBold" if "Manrope ExtraBold" in families else body
    weight = () if heavy != body else ("bold",)
    return {
        "display": (heavy, 26, *weight),
        "brand": (heavy, 23, *weight),
        "body": (body, 13),
        "strong": (body, 13, "bold"),
        "small": (body, 12),
        "label": (body, 10, "bold"),
    }


class RangeRow:
    """One output name plus its inclusive From/To page range."""

    def __init__(self, master, fonts: dict[str, tuple], on_remove: Callable[["RangeRow"], None]):
        self.frame = ctk.CTkFrame(master, fg_color="transparent")
        self.frame.grid_columnconfigure(0, weight=1)
        self.name_entry = ctk.CTkEntry(self.frame, placeholder_text="Output name", font=fonts["body"], **ENTRY_STYLE)
        self.name_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.from_entry = ctk.CTkEntry(self.frame, width=78, placeholder_text="From", justify="center", font=fonts["body"], **ENTRY_STYLE)
        self.from_entry.grid(row=0, column=1, padx=4)
        self.to_entry = ctk.CTkEntry(self.frame, width=78, placeholder_text="To", justify="center", font=fonts["body"], **ENTRY_STYLE)
        self.to_entry.grid(row=0, column=2, padx=4)
        ctk.CTkButton(self.frame, text="×", width=30, height=36, corner_radius=3, fg_color="transparent", text_color=MUTED, hover_color=LINE, font=fonts["body"], command=lambda: on_remove(self)).grid(row=0, column=3, padx=(4, 0))

    def grid(self, **kwargs):
        self.frame.grid(**kwargs)

    def destroy(self):
        self.frame.destroy()

    def values(self) -> tuple[str, str, str]:
        return self.name_entry.get().strip(), self.from_entry.get().strip(), self.to_entry.get().strip()

    def is_blank(self) -> bool:
        return not any(self.values())


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        TkinterDnD.require(self)
        self.fonts = resolve_fonts()
        self.title("SlicePDF")
        self.geometry("940x720")
        self.minsize(760, 600)
        self.configure(fg_color=PAPER)
        self.pdf_paths: list[str] = []
        self.total_pages = 0
        self.out_dir = None
        self.mode = "named"
        self.rows: list[RangeRow] = []
        self.controls: dict[str, ctk.CTkEntry] = {}
        self.operation_buttons: dict[str, ctk.CTkButton] = {}
        self.batch_hint: ctk.CTkLabel | None = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_workspace()
        self.change_operation("named")

    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, width=270, corner_radius=0, fg_color=SIDEBAR)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        ctk.CTkLabel(sidebar, text="SlicePDF", text_color=INK, font=self.fonts["brand"], anchor="w").pack(fill="x", padx=24, pady=(28, 0))
        ctk.CTkLabel(sidebar, text="YOUR DOCUMENT DESK", text_color=ACCENT, font=self.fonts["label"], anchor="w").pack(fill="x", padx=25, pady=(2, 30))
        ctk.CTkLabel(sidebar, text="CHOOSE AN ACTION", text_color=MUTED, font=self.fonts["label"], anchor="w").pack(fill="x", padx=25, pady=(0, 8))
        for label, mode in OPERATIONS.items():
            button = ctk.CTkButton(sidebar, text=label, anchor="w", height=38, corner_radius=4, fg_color="transparent", hover_color=LINE, text_color=MUTED, font=self.fonts["body"], command=lambda selected=mode: self.change_operation(selected))
            button.pack(fill="x", padx=16, pady=2)
            self.operation_buttons[mode] = button

    def _build_workspace(self):
        space = ctk.CTkFrame(self, corner_radius=0, fg_color=PAPER)
        space.grid(row=0, column=1, sticky="nsew")
        space.grid_columnconfigure(0, weight=1)
        space.grid_rowconfigure(4, weight=1)

        head = ctk.CTkFrame(space, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=30, pady=(26, 0))
        head.grid_columnconfigure(0, weight=1)
        self.title_label = ctk.CTkLabel(head, text="", text_color=INK, font=self.fonts["display"], anchor="w")
        self.title_label.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(head, text="PRIVATE WORKFLOW", text_color=SUCCESS, font=self.fonts["label"], anchor="e").grid(row=0, column=1, sticky="e", pady=(10, 0))
        self.description = ctk.CTkLabel(space, text="", text_color=MUTED, font=self.fonts["body"], anchor="w")
        self.description.grid(row=1, column=0, sticky="ew", padx=30, pady=(2, 18))

        panel = ctk.CTkFrame(space, fg_color=SURFACE, border_color=LINE, border_width=1, corner_radius=4)
        panel.grid(row=2, column=0, sticky="ew", padx=30)
        panel.grid_columnconfigure(0, weight=1)
        self.source_name = ctk.CTkLabel(panel, text="", text_color=INK, font=self.fonts["strong"], anchor="w")
        self.source_name.grid(row=0, column=0, sticky="w", padx=16, pady=14)
        self.source_meta = ctk.CTkLabel(panel, text="", text_color=MUTED, font=self.fonts["small"], anchor="e")
        self.source_meta.grid(row=0, column=1, sticky="e", padx=16, pady=14)

        drop = ctk.CTkFrame(space, fg_color=SURFACE, border_color=LINE, border_width=1, corner_radius=4)
        drop.grid(row=3, column=0, sticky="ew", padx=30, pady=16)
        drop.grid_columnconfigure(0, weight=1)
        headline = ctk.CTkLabel(drop, text="Place a PDF on the desk", text_color=INK, font=self.fonts["strong"])
        headline.grid(row=0, column=0, pady=(20, 2))
        hint = ctk.CTkLabel(drop, text="Drag it here or choose one from your files", text_color=MUTED, font=self.fonts["small"])
        hint.grid(row=1, column=0)
        self.file_button = ctk.CTkButton(drop, text="Choose PDF…", width=140, height=34, corner_radius=3, fg_color="transparent", text_color=ACCENT, hover_color=LINE, border_width=1, border_color=ACCENT, font=self.fonts["body"], command=self.choose_file)
        self.file_button.grid(row=2, column=0, pady=(14, 20))
        for widget in (drop, headline, hint):
            widget.bind("<Button-1>", lambda _event: self.choose_file())
        self.drop_zone = drop
        self._register_drop_zone(drop)

        # Small requested height so the action bar still fits at the 760x600 minimum.
        self.fields = ctk.CTkScrollableFrame(space, height=130, fg_color="transparent", corner_radius=0, scrollbar_button_color=LINE, scrollbar_button_hover_color=SELECTED)
        self.fields.grid(row=4, column=0, sticky="nsew", padx=22)
        self.fields.grid_columnconfigure(0, weight=1)

        ctk.CTkFrame(space, height=1, corner_radius=0, fg_color=LINE).grid(row=5, column=0, sticky="ew", padx=30, pady=(14, 0))
        actions = ctk.CTkFrame(space, fg_color="transparent")
        actions.grid(row=6, column=0, sticky="ew", padx=30, pady=14)
        actions.grid_columnconfigure(0, weight=1)
        self.out_label = ctk.CTkLabel(actions, text="Save beside the original PDF", text_color=MUTED, font=self.fonts["small"], anchor="w")
        self.out_label.grid(row=0, column=0, sticky="w")
        ctk.CTkButton(actions, text="Choose folder", width=130, height=36, corner_radius=3, fg_color="transparent", text_color=ACCENT, hover_color=LINE, border_width=1, border_color=ACCENT, font=self.fonts["body"], command=self.choose_output).grid(row=0, column=1, padx=10)
        self.run_button = ctk.CTkButton(actions, text="Run operation", width=150, height=36, corner_radius=3, fg_color=ACCENT, hover_color=ACCENT_DARK, text_color=SURFACE, font=self.fonts["strong"], command=self.start_operation)
        self.run_button.grid(row=0, column=2)

        self.progress = ctk.CTkProgressBar(space, height=6, corner_radius=3, fg_color=LINE, progress_color=ACCENT)
        self.message = ctk.CTkLabel(space, text="", text_color=MUTED, font=self.fonts["small"], anchor="w")
        self.message.grid(row=8, column=0, sticky="ew", padx=30, pady=(0, 14))
        self._update_source_panel()

    def _field_label(self, text):
        ctk.CTkLabel(self.fields, text=text, text_color=MUTED, font=self.fonts["label"], anchor="w").grid(sticky="w", padx=8, pady=(14, 5))

    def _field_entry(self, key, placeholder, value=""):
        entry = ctk.CTkEntry(self.fields, placeholder_text=placeholder, font=self.fonts["body"], **ENTRY_STYLE)
        if value:
            entry.insert(0, value)
        entry.grid(sticky="ew", padx=8)
        self.controls[key] = entry
        return entry

    def change_operation(self, mode):
        self.mode = mode
        for item_mode, button in self.operation_buttons.items():
            active = item_mode == mode
            button.configure(fg_color=SELECTED if active else "transparent", text_color=INK if active else MUTED)
        self.title_label.configure(text=next(name for name, value in OPERATIONS.items() if value == mode))
        self.description.configure(text=DESCRIPTIONS[mode])
        self.file_button.configure(text="Choose PDFs…" if mode == "merge" else "Choose PDF…")
        self._build_fields(mode)
        self._update_source_panel()

    def _build_fields(self, mode):
        for row in self.rows:
            row.destroy()
        self.rows = []
        self.controls = {}
        self.batch_hint = None
        for child in self.fields.winfo_children():
            child.destroy()

        if mode == "named":
            self._field_label("NAME EACH OUTPUT FILE AND SET ITS PAGE RANGE")
            self.rows_frame = ctk.CTkFrame(self.fields, fg_color="transparent")
            self.rows_frame.grid(sticky="ew", pady=(0, 0))
            self.rows_frame.grid_columnconfigure(0, weight=1)
            ctk.CTkButton(self.fields, text="＋  Add another range", height=36, corner_radius=3, fg_color="transparent", text_color=ACCENT, hover_color=LINE, border_width=1, border_color=ACCENT, font=self.fonts["body"], command=self.add_row).grid(sticky="ew", padx=8, pady=(10, 0))
            self.add_row()
        elif mode in PAGE_FIELDS:
            label, example = PAGE_FIELDS[mode]
            self._field_label(label)
            self._field_entry("pages", example)
            self._field_label("OUTPUT FILENAME (OPTIONAL)")
            self._field_entry("filename", "Example: selected-pages.pdf")
        elif mode == "trim":
            self._field_label("PAGES TO REMOVE FROM THE BEGINNING")
            self._field_entry("start", "0", "0")
            self._field_label("PAGES TO REMOVE FROM THE END")
            self._field_entry("end", "0", "0")
            self._field_label("OUTPUT FILENAME (OPTIONAL)")
            self._field_entry("filename", "Example: trimmed.pdf")
        elif mode == "count":
            self._field_label("PAGES PER OUTPUT FILE")
            self._field_entry("count", "Example: 10").bind("<KeyRelease>", self._update_batch_hint)
            self.batch_hint = ctk.CTkLabel(self.fields, text="", text_color=MUTED, font=self.fonts["small"], anchor="w")
            self.batch_hint.grid(sticky="w", padx=8, pady=(6, 0))
            self._field_label("OUTPUT FILENAME PREFIX (OPTIONAL)")
            self._field_entry("filename", "Example: batch")
            self._update_batch_hint()
        else:
            self._field_label("OUTPUT FILENAME (OPTIONAL)")
            self._field_entry("filename", "Example: combined.pdf")

    def add_row(self):
        row = RangeRow(self.rows_frame, self.fonts, self.remove_row)
        row.grid(sticky="ew", padx=8, pady=3)
        self.rows.append(row)

    def remove_row(self, row):
        row.destroy()
        self.rows.remove(row)
        if not self.rows:
            self.add_row()

    def _update_source_panel(self):
        if not self.pdf_paths:
            self.source_name.configure(text="Nothing on the desk yet")
            self.source_meta.configure(text="PDF · — pages")
        elif self.mode == "merge":
            count = len(self.pdf_paths)
            self.source_name.configure(text=f"{count} PDF{'' if count == 1 else 's'} selected")
            self.source_meta.configure(text=f"PDF · {count} file{'' if count == 1 else 's'}")
        else:
            self.source_name.configure(text=os.path.basename(self.pdf_paths[0]))
            self.source_meta.configure(text=f"PDF · {self.total_pages} pages")

    def _update_batch_hint(self, _event=None):
        if self.batch_hint is None:
            return
        value = self.form_value("count")
        text = ""
        if self.total_pages and value.isdigit() and int(value) > 0:
            text = f"{self.total_pages} pages → {len(split_by_count(self.total_pages, int(value)))} files."
        self.batch_hint.configure(text=text)

    def _register_drop_zone(self, widget):
        """Accept dropped PDFs on the drop zone and every widget drawn inside it."""
        widget.drop_target_register(DND_FILES)
        widget.dnd_bind("<<Drop>>", self._on_drop)
        for child in widget.winfo_children():
            self._register_drop_zone(child)

    def _on_drop(self, event):
        paths = [path for path in self.tk.splitlist(event.data) if path.lower().endswith(".pdf")]
        if not paths:
            messagebox.showwarning("Not a PDF", "Place a PDF file on the desk.")
            return
        self._load_paths(paths if self.mode == "merge" else paths[:1])

    def choose_file(self):
        if self.mode == "merge":
            paths = list(filedialog.askopenfilenames(title="Choose PDFs", filetypes=[("PDF files", "*.pdf")]))
        else:
            path = filedialog.askopenfilename(title="Choose a PDF", filetypes=[("PDF files", "*.pdf")])
            paths = [path] if path else []
        if paths:
            self._load_paths(paths)

    def _load_paths(self, paths):
        """Adopt chosen or dropped PDFs after checking every one can be read."""
        try:
            self.total_pages = len(PdfReader(paths[0]).pages)
            for path in paths[1:]:
                PdfReader(path)
        except (OSError, PdfReadError) as error:
            messagebox.showerror("Could not read PDF", str(error))
            return
        self.pdf_paths = list(paths)
        self._update_source_panel()
        self._update_batch_hint()
        self.set_message("")

    def choose_output(self):
        directory = filedialog.askdirectory(title="Choose output folder")
        if directory:
            self.out_dir = directory
            self.out_label.configure(text=f"Save to {directory}", text_color=INK)

    def collect_ranges(self):
        ranges = []
        for index, row in enumerate(self.rows, 1):
            if row.is_blank():
                continue
            name, start, end = row.values()
            if not name:
                raise ValueError(f"Row {index}: output name is empty.")
            try:
                start, end = int(start), int(end)
            except ValueError as error:
                raise ValueError(f"'{name}': From/To must be whole numbers.") from error
            if not (1 <= start <= end <= self.total_pages):
                raise ValueError(f"'{name}': pages must be between 1 and {self.total_pages}, with From ≤ To.")
            ranges.append((name, start, end))
        if not ranges:
            raise ValueError("Add at least one named range.")
        return ranges

    def form_value(self, key, default=""):
        return self.controls[key].get().strip() or default

    def form_number(self, key, label, default=""):
        """Return a whole number from a form field, refusing anything else in plain words."""
        value = self.form_value(key, default)
        if not value.isdigit():
            raise ValueError(f"{label} must be a whole number.")
        return int(value)

    def start_operation(self):
        if not self.pdf_paths:
            messagebox.showwarning("No file", "Choose a PDF first.")
            return
        try:
            if self.mode == "named":
                payload = self.collect_ranges()
            elif self.mode in PAGE_FIELDS:
                payload = (self.form_value("pages"), self.form_value("filename"))
                self._select_pages(self.mode, payload[0], self.total_pages)
            elif self.mode == "trim":
                payload = (self.form_number("start", "Pages to remove from the beginning", "0"),
                           self.form_number("end", "Pages to remove from the end", "0"),
                           self.form_value("filename"))
                trim_pages(self.total_pages, payload[0], payload[1])
            elif self.mode == "count":
                payload = (self.form_number("count", "Pages per output file"), self.form_value("filename"))
                split_by_count(self.total_pages, payload[0])
            else:
                if len(self.pdf_paths) < 2:
                    raise ValueError("Choose at least two PDFs to merge.")
                payload = self.form_value("filename")
        except (ValueError, TypeError) as error:
            messagebox.showerror("Check the operation", str(error))
            return
        self.run_button.configure(state="disabled")
        self.progress.set(0)
        self.progress.grid(row=7, column=0, sticky="ew", padx=30, pady=(0, 8))
        self.set_message("Working…")
        threading.Thread(target=self._run, args=(self.mode, list(self.pdf_paths), payload), daemon=True, name="slicepdf-worker").start()

    @staticmethod
    def _select_pages(mode, expression, total_pages):
        """Return the zero-based pages a page-expression operation writes out."""
        if mode == "reorder":
            return parse_page_order(expression, total_pages)
        selected = parse_page_expression(expression, total_pages)
        if mode == "keep":
            return selected
        return [page for page in range(total_pages) if page not in selected]

    def _run(self, mode, paths, payload):
        try:
            readers = [PdfReader(path) for path in paths]
            total_pages = len(readers[0].pages)
            destination = self.out_dir or os.path.dirname(paths[0])
            stem = os.path.splitext(os.path.basename(paths[0]))[0]
            used = set()
            if mode == "merge":
                pages = [(reader, page) for reader in readers for page in range(len(reader.pages))]
                outputs = [(pages, safe_filename(payload or f"{stem}-merged.pdf", "merged"))]
            elif mode == "named":
                outputs = [(list(range(start - 1, end)), safe_filename(name, f"chapter-{index}")) for index, (name, start, end) in enumerate(payload, 1)]
            elif mode == "count":
                prefix = payload[1] or f"{stem}-part"
                outputs = [(pages, safe_filename(f"{prefix}-{index}", "part")) for index, pages in enumerate(split_by_count(total_pages, payload[0]), 1)]
            elif mode == "trim":
                outputs = [(trim_pages(total_pages, payload[0], payload[1]), safe_filename(payload[2] or f"{stem}-output.pdf", "output"))]
            else:
                outputs = [(self._select_pages(mode, payload[0], total_pages), safe_filename(payload[1] or f"{stem}-output.pdf", "output"))]
            for index, (pages, filename) in enumerate(outputs, 1):
                writer = PdfWriter()
                for page in pages:
                    reader, page_index = page if mode == "merge" else (readers[0], page)
                    writer.add_page(reader.pages[page_index])
                filename = unique_filename(filename, destination, used)
                with open(os.path.join(destination, filename), "xb") as output_file:
                    writer.write(output_file)
                self.after(0, self._tick, index / len(outputs), filename)
            self.after(0, self._done, len(outputs), destination)
        # Blind on purpose: an escaped exception would leave the run button disabled for good.
        except Exception as error:  # noqa: BLE001
            self.after(0, self._fail, str(error) or error.__class__.__name__)

    def set_message(self, text, color=MUTED):
        self.message.configure(text=text, text_color=color)

    def _tick(self, fraction, filename):
        self.progress.set(fraction)
        self.set_message(f"Wrote {filename}")

    def _finish(self):
        self.progress.grid_remove()
        self.run_button.configure(state="normal")

    def _done(self, count, directory):
        self._finish()
        files = f"{count} file{'' if count == 1 else 's'}"
        self.set_message(f"Done — {files} saved.", SUCCESS)
        if messagebox.askyesno("Finished", f"Created {files} in:\n{directory}\n\nOpen the folder?"):
            os.startfile(directory)

    def _fail(self, message):
        self._finish()
        self.set_message("The operation did not finish.", ERROR)
        messagebox.showerror("Error", message)


if __name__ == "__main__":
    register_bundled_fonts()
    App().mainloop()
