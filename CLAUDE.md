# SlicePDF

Windows desktop PDF utility for page-level operations: split by named ranges, delete/keep pages, trim start/end, split by page count, reorder pages, merge PDFs. Target user is non-technical → GUI over CLI, minimal friction.

## Files

| File | Role |
|---|---|
| `slicepdf.py` | CustomTkinter GUI + operation dispatch. |
| `pdf_operations.py` | Pure page-math/filename helpers; no UI imports. |
| `test_pdf_operations.py` | `unittest` suite for `pdf_operations`. |
| `test_app.py` | GUI-level `unittest` suite; skips when Tk cannot open a window. |
| `assets/fonts/` | Bundled Manrope statics (400/700/800) + `OFL.txt`. |
| `SlicePDF.bat` | Double-click launcher → `pythonw slicepdf.py` (no console). |
| `SlicePDF.spec` | PyInstaller config; source of truth for builds. |
| `.github/workflows/build.yml` | CI on push + PR: compile, tests, Ruff, build, `SlicePDF.exe` artifact. |
| `.github/workflows/release.yml` | Manual `workflow_dispatch` release: stamps the version, checks, tags, publishes. |
| `docs/plan.md` | Private roadmap. |

UI, font, and drag-and-drop specifics live in `.claude/rules/ui-design.md`, which loads automatically with `slicepdf.py`.

`build/`, `dist/`, `*.pdf` are gitignored. `docs/` is **not** — keep the roadmap out of commits by staging explicit paths.

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

`test_app.py` opens real (withdrawn) windows and runs the worker body inline: `after()` needs a mainloop `unittest` does not provide, so live thread marshalling stays manually verified.

## Behavior

- Page numbers 1-based and inclusive; validated as `1 <= from <= to <= total`.
- Page expressions accept `2, 5-7, 12`. `delete`/`keep` dedupe silently; `reorder` rejects a repeated page (`parse_page_order`).
- Blank named-range rows ignored; at least one named range required.
- Never overwrite: `unique_filename()` + `open(..., "xb")`. Source PDF is read-only.
- Output folder defaults to the source PDF folder; another can be chosen.
- `__version__` in `slicepdf.py` is the single version source: shown in the window title, read by `SlicePDF.spec` for the exe's Windows file properties, and rewritten by the release workflow.
- Errors surface via `messagebox`; operations run on a daemon thread with updates marshalled through `self.after()`.

## Rules

- Dependency-light; UI in `slicepdf.py`, page math in `pdf_operations.py`.
- User-facing text plain and non-technical.
- Long-running PDF work off the UI thread.
- No machine-specific paths in `SlicePDF.spec`.
- Unsigned executable may trigger a SmartScreen warning; signing out of scope.
- Releases run only from the manual `Release` workflow; `build.yml` never publishes one.
