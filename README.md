# SlicePDF

![Platform](https://img.shields.io/badge/platform-Windows-0078D4)
![Python](https://img.shields.io/badge/python-3.14-3776AB)
![License](https://img.shields.io/badge/license-MIT-green)

SlicePDF is a small Windows app for making everyday PDF page edits without the hassle. Split, trim, reorder, or merge your files in a few clicks. Everything stays on your computer — there are no uploads and no tracking.

## What it does

- **Split by named ranges** — create separate files by naming each range, such as `Introduction` or `Appendix`.
- **Delete or keep pages** — enter pages or ranges such as `2, 5-7, 12`.
- **Reorder pages** — arrange them in the order you want, such as `3, 1-2, 4`.
- **Trim the beginning or end** — remove unwanted pages from either side of a document.
- **Split by page count** — break a PDF into evenly sized batches.
- **Merge PDFs** — combine two or more files in the order you choose.

Drag a PDF onto the window or choose one from your files. Results are saved beside the original unless you pick another folder, and large files are processed without freezing the window.

## Install and run

### Executable

Windows builds will be published on the [Releases page](https://github.com/MithunWijayasiri/SlicePDF/releases). The executable is unsigned, so Windows may show a SmartScreen warning on first launch — select **More info** → **Run anyway**.

### From source

Requires Python 3.14.

```bash
py -m pip install -r requirements.txt
py slicepdf.py
```

## Example

Split by named ranges, with these rows:

| Name | From | To |
|---|---:|---:|
| Introduction | 1 | 10 |
| Main content | 11 | 80 |
| Appendix | 81 | 95 |

Produces:

```text
Introduction.pdf
Main content.pdf
Appendix.pdf
```

## Good to know

- Page numbers are 1-based and inclusive.
- Ranges may overlap; each output gets the pages from its own range. Blank rows are ignored.
- Existing files are never overwritten. A repeated name gets a numeric suffix: `Appendix-2.pdf`.
- Characters Windows forbids in filenames are replaced with `-`.
- Reordering rejects a page listed twice, so nothing is silently dropped.
- Your source PDF is only ever read, never modified.

## Build the executable

```bash
py -m PyInstaller --clean --noconfirm SlicePDF.spec
```

The result is `dist/SlicePDF.exe`.

## Roadmap

Page previews, remembered output folders, batch processing, and cancellation.

## Contributing

Bug reports and suggestions are welcome through [GitHub Issues](https://github.com/MithunWijayasiri/SlicePDF/issues). For code changes, open a pull request with verification steps and run the tests first:

```bash
py -m unittest discover --pattern "test_*.py"
```

## License

MIT — see [LICENSE](LICENSE). Bundles the [Manrope](https://github.com/sharanda/manrope) typeface under the SIL Open Font License (`assets/fonts/OFL.txt`).
