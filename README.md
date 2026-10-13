# <img src="docs/favicon.svg" alt="" width="32" height="32"> SlicePDF

![Platform](https://img.shields.io/badge/platform-Windows-0078D4)
![Python](https://img.shields.io/badge/python-3.14-3776AB)
![License](https://img.shields.io/badge/license-MIT-green)

A small Windows app for editing PDF pages. It runs on your computer, with no uploads and no tracking.

## Features

- Split by named ranges, one file per range.
- Delete or keep pages, such as `2, 5-7, 12`.
- Reorder pages, such as `3, 1-2, 4`.
- Trim pages from the start or end.
- Split into batches of a set page count.
- Merge two or more PDFs in the order you choose.

Drag a PDF onto the window or pick one from your files. New files go next to the original, or to a folder you choose. The app remembers that folder.

## Install

Download `SlicePDF.exe` from the [latest release](https://github.com/MithunWijayasiri/SlicePDF/releases/latest). It is not code-signed, so Windows SmartScreen shows a warning the first time. Choose **More info**, then **Run anyway**.

To run from source, install Python 3.14, then:

```bash
py -m pip install -r requirements.txt
py slicepdf.py
```

## Good to know

- Page numbers start at 1, and ranges include both ends.
- SlicePDF never changes your original PDF and never overwrites a file. A taken name gets a number, such as `Appendix-2.pdf`.
- Reorder refuses a page listed twice.
- Password-protected PDFs are not supported.

## Development

Run the tests:

```bash
py -m unittest discover --pattern "test_*.py"
```

Build `dist/SlicePDF.exe`:

```bash
py -m pip install pyinstaller
py -m PyInstaller --clean --noconfirm SlicePDF.spec
```

Report bugs or ideas in [GitHub Issues](https://github.com/MithunWijayasiri/SlicePDF/issues).

## License

MIT, see [LICENSE](LICENSE). The app bundles the [Manrope](https://fonts.google.com/specimen/Manrope) font under the SIL Open Font License (`assets/fonts/OFL.txt`).
