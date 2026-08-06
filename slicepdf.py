"""SlicePDF: perform common page-level PDF operations."""
import os
import threading
from collections.abc import Callable
from tkinter import filedialog, messagebox

import customtkinter as ctk
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

from pdf_operations import (
    parse_page_expression,
    safe_filename,
    split_by_count,
    trim_pages,
    unique_filename,
)

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")
ACCENT = "#4457d8"
ACCENT_HOVER = "#3547c0"
INK = "#20242b"
MUTED = "#8a919c"
LINE = "#e2e2df"
BG = "#fbfbfa"
WHITE = "#ffffff"
OPERATIONS = {
    "Split by named ranges": "named",
    "Delete selected pages": "delete",
    "Trim start/end": "trim",
    "Split by page count": "count",
    "Keep selected pages": "keep",
    "Reorder pages": "reorder",
    "Merge PDFs": "merge",
}


def slugify(name: str) -> str:
    """Convert a chapter name to a filename-safe slug."""
    import re
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")


class ChapterRow:
    def __init__(self, master, on_remove: Callable[["ChapterRow"], None]):
        self.frame = ctk.CTkFrame(master, fg_color="transparent")
        self.frame.grid_columnconfigure(0, weight=1)
        self.name_entry = ctk.CTkEntry(self.frame, placeholder_text="Output name", border_color=LINE, fg_color=WHITE)
        self.name_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8), pady=3)
        self.from_entry = ctk.CTkEntry(self.frame, width=72, placeholder_text="From", border_color=LINE, fg_color=WHITE, justify="center")
        self.from_entry.grid(row=0, column=1, padx=4, pady=3)
        self.to_entry = ctk.CTkEntry(self.frame, width=72, placeholder_text="To", border_color=LINE, fg_color=WHITE, justify="center")
        self.to_entry.grid(row=0, column=2, padx=4, pady=3)
        ctk.CTkButton(self.frame, text="✕", width=30, fg_color="transparent", text_color=MUTED, hover_color="#f0f0ee", command=lambda: on_remove(self)).grid(row=0, column=3, padx=(4, 0), pady=3)

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
        self.title("SlicePDF")
        self.geometry("650x650")
        self.minsize(580, 560)
        self.configure(fg_color=BG)
        self.pdf_path = None
        self.pdf_paths: list[str] = []
        self.total_pages = 0
        self.out_dir = None
        self.rows: list[ChapterRow] = []
        self.controls: dict[str, ctk.CTkEntry] = {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 6))
        top.grid_columnconfigure(1, weight=1)
        self.choose_button = ctk.CTkButton(top, text="Choose PDF…", command=self.choose_file, fg_color=ACCENT, hover_color=ACCENT_HOVER, width=120)
        self.choose_button.grid(row=0, column=0)
        self.file_label = ctk.CTkLabel(top, text="No file selected", text_color=MUTED, anchor="w")
        self.file_label.grid(row=0, column=1, sticky="w", padx=12)
        ctk.CTkFrame(self, height=1, fg_color=LINE).grid(row=1, column=0, sticky="ew", padx=20, pady=6)

        operation = ctk.CTkFrame(self, fg_color="transparent")
        operation.grid(row=2, column=0, sticky="ew", padx=20, pady=(2, 0))
        ctk.CTkLabel(operation, text="Operation", text_color=MUTED).pack(side="left")
        self.operation_menu = ctk.CTkOptionMenu(operation, values=list(OPERATIONS), command=self.change_operation, fg_color=ACCENT, button_color=ACCENT_HOVER, width=230)
        self.operation_menu.pack(side="left", padx=12)
        self.operation_hint = ctk.CTkLabel(operation, text="", text_color=MUTED)
        self.operation_hint.pack(side="left")

        self.form = ctk.CTkScrollableFrame(self, fg_color=WHITE, border_color=LINE, border_width=1)
        self.form.grid(row=3, column=0, sticky="nsew", padx=20, pady=8)
        self.form.grid_columnconfigure(0, weight=1)
        self.add_btn = ctk.CTkButton(self, text="+  Add range", command=self.add_row, fg_color="transparent", text_color=ACCENT, hover_color="#eef0fb", border_width=1, border_color="#c3c9e8")
        self.add_btn.grid(row=4, column=0, sticky="ew", padx=20)
        ctk.CTkFrame(self, height=1, fg_color=LINE).grid(row=5, column=0, sticky="ew", padx=20, pady=8)

        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.grid(row=6, column=0, sticky="ew", padx=20)
        foot.grid_columnconfigure(0, weight=1)
        self.out_label = ctk.CTkLabel(foot, text="Output: (same folder as PDF)", text_color=MUTED, anchor="w")
        self.out_label.grid(row=0, column=0, sticky="w")
        ctk.CTkButton(foot, text="Change", width=70, command=self.choose_output, fg_color="transparent", text_color=ACCENT, hover_color="#eef0fb", border_width=1, border_color="#c3c9e8").grid(row=0, column=1, padx=8)
        self.run_btn = ctk.CTkButton(foot, text="Run", command=self.start_operation, fg_color=ACCENT, hover_color=ACCENT_HOVER, width=120)
        self.run_btn.grid(row=0, column=2)
        self.progress = ctk.CTkProgressBar(self, progress_color=ACCENT)
        self.progress.set(0)
        self.progress.grid(row=7, column=0, sticky="ew", padx=20, pady=(12, 2))
        self.status = ctk.CTkLabel(self, text="", text_color=MUTED)
        self.status.grid(row=8, column=0, pady=(2, 12))
        self.change_operation("Split by named ranges")

    def entry(self, key, placeholder, width=None):
        entry = ctk.CTkEntry(self.form, placeholder_text=placeholder, border_color=LINE, fg_color=WHITE, width=width or 0)
        entry.grid(sticky="ew", padx=12, pady=10)
        self.controls[key] = entry
        return entry

    def change_operation(self, label):
        for row in self.rows:
            row.destroy()
        self.rows = []
        self.controls = {}
        for child in self.form.winfo_children():
            child.destroy()
        mode = OPERATIONS[label]
        hints = {"named": "Each range becomes a separate PDF.", "delete": "Example: 2, 5-7, 12", "keep": "Example: 1-3, 8, 10-12", "reorder": "Example: 3, 1-2, 4", "trim": "Remove pages from either end.", "count": "Each output contains at most this many pages.", "merge": "Choose two or more PDFs to combine."}
        self.operation_hint.configure(text=hints[mode])
        self.add_btn.grid_remove()
        self.choose_button.configure(text="Choose PDFs…" if mode == "merge" else "Choose PDF…")
        if mode == "named":
            headers = ctk.CTkLabel(self.form, text="OUTPUT NAME                         FROM             TO", text_color=MUTED)
            headers.grid(sticky="w", padx=12, pady=(10, 0))
            self.add_btn.grid()
            self.add_row()
        elif mode in ("delete", "keep", "reorder"):
            self.entry("pages", "Page numbers or ranges")
            self.entry("filename", "Output filename (optional)")
        elif mode == "trim":
            self.entry("start", "Pages to remove from start", 220)
            self.entry("end", "Pages to remove from end", 220)
            self.entry("filename", "Output filename (optional)")
        elif mode == "count":
            self.entry("count", "Pages per output file", 220)
            self.entry("filename", "Output filename prefix (optional)")
        elif mode == "merge":
            self.entry("filename", "Output filename (optional)")

    def add_row(self):
        row = ChapterRow(self.form, self.remove_row)
        row.grid(sticky="ew", padx=8, pady=2)
        self.rows.append(row)

    def remove_row(self, row):
        row.destroy()
        self.rows.remove(row)
        if not self.rows:
            self.add_row()

    def choose_file(self):
        paths = filedialog.askopenfilenames(title="Choose PDFs", filetypes=[("PDF files", "*.pdf")])
        if not paths:
            return
        try:
            readers = [PdfReader(path) for path in paths]
            self.total_pages = len(readers[0].pages)
        except (OSError, PdfReadError) as error:
            messagebox.showerror("Error", f"Could not read PDF:\n{error}")
            return
        self.pdf_paths = list(paths)
        self.pdf_path = paths[0]
        if OPERATIONS[self.operation_menu.get()] == "merge":
            self.file_label.configure(text=f"{len(paths)} PDFs selected", text_color=INK)
        else:
            self.file_label.configure(text=f"{os.path.basename(paths[0])}   ·   {self.total_pages} pages", text_color=INK)
        self.set_status("")

    def choose_output(self):
        directory = filedialog.askdirectory(title="Choose output folder")
        if directory:
            self.out_dir = directory
            self.out_label.configure(text=f"Output: {directory}", text_color=INK)

    def collect_chapters(self):
        chapters = []
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
            chapters.append((name, start, end))
        if not chapters:
            raise ValueError("Add at least one named range.")
        return chapters

    def form_value(self, key, default=""):
        return self.controls[key].get().strip() or default

    def start_operation(self):
        if not self.pdf_paths:
            messagebox.showwarning("No file", "Choose a PDF first.")
            return
        mode = OPERATIONS[self.operation_menu.get()]
        try:
            if mode == "named":
                payload = self.collect_chapters()
            elif mode in ("delete", "keep", "reorder"):
                payload = (self.form_value("pages"), self.form_value("filename"))
                parse_page_expression(payload[0], self.total_pages)
            elif mode == "trim":
                payload = (int(self.form_value("start", "0")), int(self.form_value("end", "0")), self.form_value("filename"))
                trim_pages(self.total_pages, payload[0], payload[1])
            elif mode == "count":
                payload = (int(self.form_value("count")), self.form_value("filename"))
                split_by_count(self.total_pages, payload[0])
            else:
                if len(self.pdf_paths) < 2:
                    raise ValueError("Choose at least two PDFs to merge.")
                payload = self.form_value("filename")
        except (ValueError, TypeError) as error:
            messagebox.showerror("Check the operation", str(error))
            return
        self.run_btn.configure(state="disabled")
        self.progress.set(0)
        threading.Thread(target=self._run, args=(mode, list(self.pdf_paths), payload), daemon=True, name="slicepdf-worker").start()

    def _run(self, mode, paths, payload):
        try:
            readers = [PdfReader(path) for path in paths]
            destination = self.out_dir or os.path.dirname(paths[0])
            used = set()
            outputs = []
            if mode == "merge":
                pages = [(reader, page) for reader in readers for page in range(len(reader.pages))]
                outputs = [(pages, safe_filename(payload or f"{os.path.splitext(os.path.basename(paths[0]))[0]}-merged.pdf", "merged"))]
            elif mode == "named":
                outputs = [([page for page in range(start - 1, end)], safe_filename(name, f"chapter-{index}")) for index, (name, start, end) in enumerate(payload, 1)]
            elif mode == "count":
                prefix = payload[1] or f"{os.path.splitext(os.path.basename(paths[0]))[0]}-part"
                outputs = [(pages, safe_filename(f"{prefix}-{index}", "part")) for index, pages in enumerate(split_by_count(len(readers[0].pages), payload[0]), 1)]
            else:
                if mode == "trim":
                    pages = trim_pages(len(readers[0].pages), payload[0], payload[1])
                else:
                    selected = parse_page_expression(payload[0], len(readers[0].pages))
                    pages = [page for page in range(len(readers[0].pages)) if page not in selected] if mode == "delete" else selected
                outputs = [(pages, safe_filename(payload[-1] or f"{os.path.splitext(os.path.basename(paths[0]))[0]}-output.pdf", "output"))]
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
        except (OSError, PdfReadError, ValueError) as error:
            self.after(0, self._fail, str(error))

    def set_status(self, text, color=MUTED):
        self.status.configure(text=text, text_color=color)

    def _tick(self, fraction, filename):
        self.progress.set(fraction)
        self.set_status(f"Wrote {filename}")

    def _done(self, count, directory):
        self.run_btn.configure(state="normal")
        self.set_status(f"Done — {count} files saved.", INK)
        if messagebox.askyesno("Finished", f"Created {count} files in:\n{directory}\n\nOpen the folder?"):
            os.startfile(directory)

    def _fail(self, message):
        self.run_btn.configure(state="normal")
        self.set_status("Failed.", "#c0392b")
        messagebox.showerror("Error", message)


if __name__ == "__main__":
    App().mainloop()
