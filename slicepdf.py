"""SlicePDF: split a PDF into named files using page ranges."""
import os
import re
import threading
from collections.abc import Callable
from tkinter import filedialog, messagebox

import customtkinter as ctk
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

ACCENT = "#4457d8"
ACCENT_HOVER = "#3547c0"
INK = "#20242b"
MUTED = "#8a919c"
LINE = "#e2e2df"
BG = "#fbfbfa"
WHITE = "#ffffff"


def slugify(name: str) -> str:
    """Convert a chapter name to a filename-safe slug."""
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")


def output_filename(
    stem: str, name: str, index: int, used: dict[str, int], destination: str
) -> str:
    slug = slugify(name) or f"chapter-{index}"
    count = used.get(slug, 0)
    while True:
        count += 1
        candidate_slug = slug if count == 1 else f"{slug}-{count}"
        filename = f"{stem}-split-{candidate_slug}.pdf"
        if not os.path.exists(os.path.join(destination, filename)):
            used[slug] = count
            return filename


class ChapterRow:
    def __init__(self, master, on_remove: Callable[["ChapterRow"], None]):
        self.frame = ctk.CTkFrame(master, fg_color="transparent")
        self.frame.grid_columnconfigure(0, weight=1)

        self.name_entry = ctk.CTkEntry(
            self.frame, placeholder_text="Chapter name", border_color=LINE, fg_color=WHITE
        )
        self.name_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8), pady=3)
        self.from_entry = ctk.CTkEntry(
            self.frame, width=72, placeholder_text="From", border_color=LINE,
            fg_color=WHITE, justify="center"
        )
        self.from_entry.grid(row=0, column=1, padx=4, pady=3)
        self.to_entry = ctk.CTkEntry(
            self.frame, width=72, placeholder_text="To", border_color=LINE,
            fg_color=WHITE, justify="center"
        )
        self.to_entry.grid(row=0, column=2, padx=4, pady=3)
        remove_button = ctk.CTkButton(
            self.frame, text="✕", width=30, fg_color="transparent", text_color=MUTED,
            hover_color="#f0f0ee", command=lambda: on_remove(self)
        )
        remove_button.grid(row=0, column=3, padx=(4, 0), pady=3)

    def grid(self, **kwargs):
        self.frame.grid(**kwargs)

    def destroy(self):
        self.frame.destroy()

    def values(self) -> tuple[str, str, str]:
        return (
            self.name_entry.get().strip(),
            self.from_entry.get().strip(),
            self.to_entry.get().strip(),
        )

    def is_blank(self) -> bool:
        return not any(self.values())


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SlicePDF")
        self.geometry("620x600")
        self.minsize(560, 520)
        self.configure(fg_color=BG)

        self.pdf_path = None
        self.total_pages = 0
        self.out_dir = None
        self.rows: list[ChapterRow] = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # --- Source row ---
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 6))
        top.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(top, text="Choose PDF…", command=self.choose_file,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER, width=120).grid(row=0, column=0)
        self.file_label = ctk.CTkLabel(top, text="No file selected", text_color=MUTED, anchor="w")
        self.file_label.grid(row=0, column=1, sticky="w", padx=12)

        ctk.CTkFrame(self, height=1, fg_color=LINE).grid(row=1, column=0, sticky="ew", padx=20, pady=6)

        # --- Column headers ---
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=2, column=0, sticky="ew", padx=20, pady=(2, 0))
        head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(head, text="CHAPTER NAME", text_color=MUTED,
                     font=("Segoe UI", 11, "bold"), anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(head, text="FROM", text_color=MUTED, font=("Segoe UI", 11, "bold"),
                     width=72).grid(row=0, column=1, padx=4)
        ctk.CTkLabel(head, text="TO", text_color=MUTED, font=("Segoe UI", 11, "bold"),
                     width=72).grid(row=0, column=2, padx=4)
        ctk.CTkLabel(head, text="", width=30).grid(row=0, column=3, padx=(4, 0))

        # --- Scrollable chapter rows ---
        self.rowbox = ctk.CTkScrollableFrame(self, fg_color="#ffffff", border_color=LINE,
                                             border_width=1)
        self.rowbox.grid(row=3, column=0, sticky="nsew", padx=20, pady=8)
        self.rowbox.grid_columnconfigure(0, weight=1)

        self.add_btn = ctk.CTkButton(self, text="+  Add chapter", command=self.add_row,
                                     fg_color="transparent", text_color=ACCENT,
                                     hover_color="#eef0fb", border_width=1, border_color="#c3c9e8")
        self.add_btn.grid(row=4, column=0, sticky="ew", padx=20)

        ctk.CTkFrame(self, height=1, fg_color=LINE).grid(row=5, column=0, sticky="ew", padx=20, pady=8)

        # --- Output + action ---
        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.grid(row=6, column=0, sticky="ew", padx=20)
        foot.grid_columnconfigure(0, weight=1)
        self.out_label = ctk.CTkLabel(foot, text="Output: (same folder as PDF)",
                                      text_color=MUTED, anchor="w")
        self.out_label.grid(row=0, column=0, sticky="w")
        ctk.CTkButton(foot, text="Change", width=70, command=self.choose_output,
                      fg_color="transparent", text_color=ACCENT, hover_color="#eef0fb",
                      border_width=1, border_color="#c3c9e8").grid(row=0, column=1, padx=8)
        self.split_btn = ctk.CTkButton(foot, text="Split", command=self.start_split,
                                       fg_color=ACCENT, hover_color=ACCENT_HOVER, width=120)
        self.split_btn.grid(row=0, column=2)

        self.progress = ctk.CTkProgressBar(self, progress_color=ACCENT)
        self.progress.set(0)
        self.progress.grid(row=7, column=0, sticky="ew", padx=20, pady=(12, 2))
        self.status = ctk.CTkLabel(self, text="", text_color=MUTED)
        self.status.grid(row=8, column=0, pady=(2, 12))

        self.add_row()  # start with one blank row

    # --- Row management ---
    def add_row(self):
        row = ChapterRow(self.rowbox, self.remove_row)
        row.grid(sticky="ew", padx=8, pady=2)
        self.rows.append(row)

    def remove_row(self, row):
        row.destroy()
        self.rows.remove(row)
        if not self.rows:
            self.add_row()

    # --- File pickers ---
    def choose_file(self):
        path = filedialog.askopenfilename(title="Choose a PDF", filetypes=[("PDF files", "*.pdf")])
        if not path:
            return
        try:
            self.total_pages = len(PdfReader(path).pages)
        except (OSError, PdfReadError) as e:
            messagebox.showerror("Error", f"Could not read PDF:\n{e}")
            return
        self.pdf_path = path
        self.file_label.configure(
            text=f"{os.path.basename(path)}   ·   {self.total_pages} pages", text_color=INK)
        self.set_status("")

    def choose_output(self):
        d = filedialog.askdirectory(title="Choose output folder")
        if d:
            self.out_dir = d
            self.out_label.configure(text=f"Output: {d}", text_color=INK)

    # --- Validation + split ---
    def collect_chapters(self) -> list[tuple[str, int, int]]:
        chapters: list[tuple[str, int, int]] = []
        for i, row in enumerate(self.rows, 1):
            if row.is_blank():
                continue
            name, frm, to = row.values()
            if not name:
                raise ValueError(f"Row {i}: chapter name is empty.")
            try:
                a, b = int(frm), int(to)
            except ValueError as error:
                raise ValueError(f"'{name}': From/To must be whole numbers.") from error
            if not (1 <= a <= b <= self.total_pages):
                raise ValueError(
                    f"'{name}': pages must be between 1 and {self.total_pages}, with From ≤ To.")
            chapters.append((name, a, b))
        if not chapters:
            raise ValueError("Add at least one chapter with a name and page range.")
        return chapters

    def start_split(self):
        if not self.pdf_path:
            messagebox.showwarning("No file", "Choose a PDF first.")
            return
        try:
            chapters = self.collect_chapters()
        except ValueError as e:
            messagebox.showerror("Check the chapters", str(e))
            return
        self.split_btn.configure(state="disabled")
        self.progress.set(0)
        pdf_path = self.pdf_path
        out_dir = self.out_dir
        threading.Thread(
            target=self._split,
            args=(pdf_path, out_dir, chapters),
            daemon=True,
            name="slicepdf-worker",
        ).start()

    def _split(self, pdf_path: str, out_dir: str | None,
               chapters: list[tuple[str, int, int]]) -> None:
        try:
            reader = PdfReader(pdf_path)
            stem = os.path.splitext(os.path.basename(pdf_path))[0]
            destination = out_dir or os.path.dirname(pdf_path)
            used: dict[str, int] = {}
            for index, (name, start, end) in enumerate(chapters, 1):
                writer = PdfWriter()
                for page in range(start - 1, end):  # Convert inclusive 1-based range.
                    writer.add_page(reader.pages[page])
                filename = output_filename(stem, name, index, used, destination)
                with open(os.path.join(destination, filename), "xb") as output_file:
                    writer.write(output_file)
                self.after(0, self._tick, index / len(chapters), filename)
            self.after(0, self._done, len(chapters), destination)
        except (OSError, PdfReadError) as error:
            self.after(0, self._fail, str(error))

    def set_status(self, text, color=MUTED):
        self.status.configure(text=text, text_color=color)

    def _tick(self, frac, fname):
        self.progress.set(frac)
        self.set_status(f"Wrote {fname}")

    def _done(self, n, out_dir):
        self.split_btn.configure(state="normal")
        self.set_status(f"Done — {n} files saved.", INK)
        if messagebox.askyesno("Finished", f"Created {n} files in:\n{out_dir}\n\nOpen the folder?"):
            os.startfile(out_dir)

    def _fail(self, msg):
        self.split_btn.configure(state="normal")
        self.set_status("Failed.", "#c0392b")
        messagebox.showerror("Error", msg)


if __name__ == "__main__":
    App().mainloop()
