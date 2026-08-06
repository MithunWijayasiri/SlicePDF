---
paths:
  - "slicepdf.py"
  - "test_app.py"
  - "SlicePDF.spec"
  - "assets/fonts/**"
---

# SlicePDF UI — Document desk

Warm paper/document desktop workspace. Hierarchy over decoration, one primary action per screen.
This file is the standing spec — nothing else to consult. Non-technical target user.

## Palette

Every color is a module constant in `slicepdf.py` (`PAPER`…`ERROR`) — those constants are the palette.
No literal hex anywhere else, no color outside them. No blue, purple, gradients, heavy shadows, pure-black
surfaces. Light mode only; no dark theme.

## Typography

`resolve_fonts()` is the source of truth. Manrope only — display headings 800 via the separate
`Manrope ExtraBold` GDI family, body/controls via `Manrope`. Never Segoe UI, never the CustomTkinter
Roboto default. `FONT_FALLBACK` (`Corbel`) fires only when registration failed; a test asserts it doesn't.

## Layout

- Left sidebar is the **only** operation selector: 7 text-first buttons, no dropdown, no icons.
  Active = `SELECTED` bg + `INK` text.
- Workspace, in order: operation title · one description · source panel · drop zone · operation-specific
  fields · output row · single `Run operation` button.
- Show only the fields the selected operation needs. Preserve the chosen source across operation switches.
- Minimum window 760×600 must stay usable. The fields area carries a small requested `height` for exactly
  this reason — grid clips from the bottom (silently dropping the action bar) when requested height exceeds
  the window.

## Do not add

Operation dropdown · recent files · history · settings · statistics or metrics · dark mode · icons or emoji ·
duplicate file selectors · competing primary actions · cards that only repeat what's already on screen.

## Interaction invariants

- PDF work runs off the UI thread; updates marshal back via `self.after()`.
- Run button disabled while working; progress bar gridded only while working.
- Never overwrite: `unique_filename()` + `open(..., "xb")`. Source PDF is read-only.
- Validation dialogs in plain, non-technical language.

## Font packaging

- `register_bundled_fonts()` must run **before** any Tk interpreter exists (`AddFontResourceExW` +
  `FR_PRIVATE`, process-scoped, no install, no admin, no network).
- Assets resolve through `resource_path()` (`sys._MEIPASS` aware); `SlicePDF.spec` ships `assets/fonts`.
- Regenerate statics from `Manrope[wght].ttf` with `fontTools.varLib.instancer`
  (`updateFontNames=True`) — GDI exposes only a variable font's default weight, so a variable font
  would render 800 as a fake synthesized bold. `fonttools` is build-prep only, never a runtime dep.

## Drag and drop

- `TkinterDnD.require(self)` on the CTk root patches `tkinter.BaseWidget`, so every CTk widget gains
  `drop_target_register`/`dnd_bind`. Left uncaught deliberately: a tkdnd load failure kills startup
  rather than silently degrading to click-only.
- Register the drop-zone subtree recursively (`_register_drop_zone`). CTk frames and labels draw on
  internal canvas children that must be registered too, or drops land on an unregistered widget.
- Parse `event.data` only with `self.tk.splitlist` — `%D` is `[list $data]`, and hand-parsing corrupts
  backslash paths. Drops outside the zone are ignored.
- `tkinterdnd2` picks `tkdnd/win-x64` vs `win-x64-tcl9` from the runtime Tcl version, so the spec uses
  `collect_all('tkinterdnd2')` instead of the hook that collects one directory.

## Verifying visually

CustomTkinter scales widgets by display DPI while `geometry()` stays logical, so the window is physically
larger than its requested size. Screenshot tooling must call `SetProcessDpiAwareness` before
`GetWindowRect`/`CopyFromScreen` or the capture clips and looks like a layout bug.
