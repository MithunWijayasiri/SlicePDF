# SlicePDF

Windows desktop PDF page utility. Current feature: split one PDF into named files using inclusive page ranges. Target user is non-technical — GUI over CLI, minimal friction.

## Files

| File | Role |
|---|---|
| `slicepdf.py` | Single-file CustomTkinter GUI and split workflow. |
| `SlicePDF.bat` | Double-click launcher → `pythonw slicepdf.py` (no console). |
| `README.md` | Public project and user instructions. |
| `dist/SlicePDF.exe` | Existing portable binary; rebuild after source changes. |
| `SlicePDF.spec` | PyInstaller configuration. |
| `build/` | PyInstaller build artifacts; do not publish as source. |
| `docs/plan.md` | Private product roadmap and GitHub workflow; excluded from Git. |

## Stack

- Python 3.14.
- CustomTkinter for GUI.
- `pypdf` for PDF read/write.
- PyInstaller for Windows executable builds.

## Run / build

```bash
py slicepdf.py
py -m PyInstaller --onefile --windowed --name "SlicePDF" slicepdf.py
```

Rebuild the executable after changes to `slicepdf.py`; the executable is a frozen snapshot.

## Current behavior

- Select a PDF; page count appears in the window.
- Add one or more named page ranges.
- Page numbers are 1-based and inclusive.
- Blank rows are ignored.
- Each valid range becomes a separate PDF.
- Output defaults to the source PDF folder; a different folder can be selected.
- Output names use `<source>-split-<chapter-name>.pdf`.
- Duplicate chapter names receive numeric suffixes.
- Empty names fall back to `chapter-N`.
- Invalid ranges, missing names, unreadable PDFs, and missing input files show errors.
- PDF work runs on a background thread; UI updates use `after()`.

## Engineering rules

- Keep the app dependency-light and single-file until a second operation justifies extraction.
- Keep user-facing text plain and non-technical.
- Keep long-running PDF operations off the UI thread.
- Add tests before extracting shared page-operation logic.
- Avoid machine-specific paths in public build configuration.
- Unsigned Windows executables may trigger SmartScreen; signing is out of scope.

## Planned features

Priorities: custom output names, delete selected pages, trim start/end, split by page count, keep/reorder pages, and merge PDFs.
