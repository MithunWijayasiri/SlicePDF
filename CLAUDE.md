# SlicePDF

Windows desktop PDF utility. Current feature: split one PDF into named files by inclusive page ranges. Target user is non-technical → GUI over CLI, minimal friction.

## Files

| File | Role |
|---|---|
| `slicepdf.py` | Single-file CustomTkinter GUI + split workflow. |
| `SlicePDF.bat` | Double-click launcher → `pythonw slicepdf.py` (no console). |
| `SlicePDF.spec` | PyInstaller config; source of truth for builds. |
| `requirements.txt` | Runtime deps: `customtkinter`, `pypdf`. |
| `.github/workflows/build.yml` | CI on push + PR: compile, Ruff, PyInstaller build, `SlicePDF.exe` artifact. |
| `README.md` | Public project and user instructions. |
| `docs/plan.md` | Private roadmap; gitignored. |

`build/`, `dist/`, `*.pdf`, `.claude/` are gitignored.

## Stack

Python 3.14 · CustomTkinter · pypdf · PyInstaller.

## Run / build / check

```bash
py slicepdf.py
py -m PyInstaller --clean --noconfirm SlicePDF.spec
py -m ruff check slicepdf.py
```

Executable is a frozen snapshot — rebuild after `slicepdf.py` changes.

## Behavior

- Page numbers 1-based and inclusive; validated as `1 <= from <= to <= total`.
- Blank rows ignored; at least one named range required.
- Output name `<source>-split-<slug>.pdf`; duplicate slugs get numeric suffix; name with no alphanumerics → `chapter-N`.
- Output folder defaults to the source PDF folder; a different folder can be selected.
- Errors surface via `messagebox`: unreadable PDF, no file chosen, non-numeric or out-of-range pages, empty name, no chapters.
- Split runs on a daemon thread; UI updates marshalled through `self.after()`.

## Rules

- Dependency-light and single-file until a second operation justifies extraction.
- User-facing text plain and non-technical.
- Long-running PDF work off the UI thread.
- No machine-specific paths in `SlicePDF.spec`.
- Add tests before extracting shared page-operation logic.
- Unsigned executable triggers SmartScreen; signing out of scope.
- Releases are manual; CI never creates them.

## Planned

Custom output names · delete selected pages · trim start/end · split by page count · keep/reorder pages · merge PDFs.
