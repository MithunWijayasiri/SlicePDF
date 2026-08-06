# SlicePDF

![Platform](https://img.shields.io/badge/platform-Windows-0078D4)
![Python](https://img.shields.io/badge/python-3.14-3776AB)
![License](https://img.shields.io/badge/license-MIT-green)

A simple Windows desktop tool for dividing PDFs into smaller, named files by page range.

SlicePDF processes files locally. It does not upload documents or use telemetry.

## Current features

- Choose a PDF and view its page count.
- Add multiple named page ranges.
- Use 1-based inclusive page numbers.
- Choose an output folder, or save beside the original PDF.
- Process large PDFs without freezing the window.
- Receive clear errors for invalid ranges and unreadable files.

The current release focuses on splitting PDFs by named page ranges. Other page operations listed in the roadmap are not available yet.

## Use the app

### Windows executable

A downloadable executable will be published through GitHub Releases. Until the first release is available, run the application from source as described below.

When using a released executable:

1. Download and open `SlicePDF.exe`.
2. If Windows shows a SmartScreen warning, select **More info** → **Run anyway**.
3. Click **Choose PDF…**.
4. Add a chapter for each output file.
5. Enter a name and the first and last page for each range.
6. Optionally choose an output folder.
7. Click **Split**.

Example:

| Name | From | To |
|---|---:|---:|
| Introduction | 1 | 10 |
| Main content | 11 | 80 |
| Appendix | 81 | 95 |

Generated files:

```text
Original-split-introduction.pdf
Original-split-main-content.pdf
Original-split-appendix.pdf
```

### Run from source

Requirements: Python 3.14, `customtkinter`, `pypdf`, and PyInstaller for building the Windows executable.

```bash
py -m pip install customtkinter pypdf pyinstaller
py slicepdf.py
```

## Download

Official Windows executables will be published on the [GitHub Releases page](https://github.com/MithunWijayasiri/SlicePDF/releases).

## Build the Windows executable

```bash
py -m PyInstaller --clean --noconfirm SlicePDF.spec
```

The executable is created in `dist/`.

## Notes

- Page ranges may overlap; each output receives the pages specified in its own range.
- Blank rows are ignored.
- Names are converted to safe filename slugs.
- Duplicate names receive numeric suffixes.
- If no output folder is selected, files are saved beside the source PDF.
- The executable is unsigned. Windows may display a SmartScreen warning on first launch.
- PDF files stay on your computer; SlicePDF does not upload them.

## Roadmap

Planned page operations include custom output names, deleting selected pages, trimming pages from the beginning or end, splitting by page count, keeping selected pages, reordering pages, and merging PDFs.

## Contributing

Bug reports and feature suggestions are welcome through [GitHub Issues](https://github.com/MithunWijayasiri/SlicePDF/issues). For code changes, open a pull request with a focused description and include verification steps.

## License

SlicePDF is released under the [MIT License](LICENSE).

