# SlicePDF

Windows desktop PDF utility for page-level operations: split by named ranges, delete/keep pages, trim start/end, split by page count, reorder pages, merge PDFs. Target user is non-technical → GUI over CLI, minimal friction.

## Files

| File | Role |
|---|---|
| `slicepdf.py` | CustomTkinter GUI (Document desk layout) + operation dispatch. |
| `pdf_operations.py` | Pure page-math/filename helpers; no UI imports. |
| `test_pdf_operations.py` | `unittest` suite for `pdf_operations`. |
| `test_app.py` | GUI-level `unittest` suite: fonts, fields, drops, output, validation. Skips when Tk cannot open a window. |
| `assets/fonts/` | Bundled Manrope statics (400/700/800) + `OFL.txt`. |
| `SlicePDF.bat` | Double-click launcher → `pythonw slicepdf.py` (no console). |
| `SlicePDF.spec` | PyInstaller config; source of truth for builds. |
| `requirements.txt` | Runtime deps: `customtkinter`, `pypdf`, `tkinterdnd2`. |
| `.github/workflows/build.yml` | CI on push + PR: compile, Ruff, PyInstaller build, `SlicePDF.exe` artifact. |
| `README.md` | Public project and user instructions. |
| `docs/plan.md` | Private roadmap; gitignored. |
| `docs/document-desk-ui.md` | UI specification; source of truth for layout, palette, typography. |
| `index.html` | UI direction gallery; `03 · Document desk` is the implemented direction. |

`build/`, `dist/`, `*.pdf`, `.claude/` are gitignored.

## Stack

Python 3.14 · CustomTkinter · tkinterdnd2 · pypdf · PyInstaller.

## Run / build / check

```bash
py slicepdf.py
py -m unittest discover --verbose --pattern "test_*.py"
py -m PyInstaller --clean --noconfirm SlicePDF.spec
py -m ruff check slicepdf.py pdf_operations.py test_pdf_operations.py test_app.py
```

Executable is a frozen snapshot — rebuild after `slicepdf.py` changes.

`test_app.py` opens real (withdrawn) windows and runs the worker body inline — `after()` needs a
mainloop that `unittest` does not provide, so live thread marshalling stays manually verified.

## Behavior

- Page numbers 1-based and inclusive; validated as `1 <= from <= to <= total`.
- Blank named-range rows ignored; at least one named range required.
- Page expressions accept `2, 5-7, 12`; `delete`/`keep` dedupe silently, `reorder` rejects a repeated page (`parse_page_order`).
- Duplicate output names get a numeric suffix (`unique_filename`); files open `"xb"` → never overwrite silently. Source PDF is read-only.
- Output folder defaults to the source PDF folder; a different folder can be selected.
- Errors surface via `messagebox`: unreadable PDF, no file chosen, non-numeric or out-of-range pages, empty name, fewer than two merge inputs.
- Operations run on a daemon thread; UI updates marshalled through `self.after()`. Run button disabled and progress bar shown only while working.

## UI

- Layout, palette, and typography come from `docs/document-desk-ui.md`. Read it before UI changes.
- Left sidebar is the only operation selector; no dropdown.
- Fonts: bundled Manrope statics registered per-process via `AddFontResourceExW` + `FR_PRIVATE` in `register_bundled_fonts()`, called before the Tk root exists; `resolve_fonts()` falls back to `Corbel` if the families are missing. No Segoe UI, no default Roboto.
- Assets resolve through `resource_path()` (handles `sys._MEIPASS`).
- Drag-and-drop: `TkinterDnD.require(self)` on the CTk root (patches `tkinter.BaseWidget`, so every CTk widget gains `drop_target_register`/`dnd_bind`). `_register_drop_zone` recurses the drop-zone subtree — CTk frames/labels draw on internal canvas children that must be registered too. Drops outside the zone are ignored.
- `event.data` is a quoted Tcl list (`%D` = `[list $data]`); parse only with `self.tk.splitlist`. Hand-parsing corrupts backslash paths.
- `tkinterdnd2` picks `tkdnd/win-x64` vs `win-x64-tcl9` from the runtime Tcl version, so the spec uses `collect_all('tkinterdnd2')` rather than relying on the hook that collects one directory.
- Regenerate the statics from `Manrope[wght].ttf` with `fontTools.varLib.instancer` (`updateFontNames=True`) — variable fonts expose only their default weight to GDI. `fonttools` is build-prep only, never a runtime dep.

## Rules

- Dependency-light; UI in `slicepdf.py`, page math in `pdf_operations.py`.
- User-facing text plain and non-technical.
- Long-running PDF work off the UI thread.
- No machine-specific paths in `SlicePDF.spec`.
- No new UI components beyond `docs/document-desk-ui.md`; no icons, emoji, dark mode, history, or metrics.
- Unsigned executable may trigger a SmartScreen warning; signing out of scope.
- Releases are manual; CI never creates them.
