# -*- mode: python ; coding: utf-8 -*-
import re
from pathlib import Path

from PyInstaller.utils.hooks import collect_all
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

source = Path(SPECPATH, 'slicepdf.py').read_text(encoding='utf-8')
match = re.search(r'^__version__ = "([^"]+)"', source, re.M)
if not match:
    raise SystemExit('slicepdf.py has no __version__ to build the version resource from.')
version = match.group(1)
# Windows wants four numbers, so a pre-release suffix such as 0.2.0-rc.1 is dropped here.
numbers = [int(part) for part in version.split('-')[0].split('.')]
version_numbers = tuple((numbers + [0, 0, 0, 0])[:4])
if any(number > 0xFFFF for number in version_numbers):
    raise SystemExit(f'Version {version} exceeds the 65535 limit of a Windows version field.')

version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=version_numbers, prodvers=version_numbers),
    kids=[
        StringFileInfo([StringTable('040904B0', [
            StringStruct('CompanyName', 'Mithun Wijayasiri'),
            StringStruct('FileDescription', 'SlicePDF'),
            StringStruct('FileVersion', version),
            StringStruct('InternalName', 'SlicePDF'),
            StringStruct('LegalCopyright', 'MIT License'),
            StringStruct('OriginalFilename', 'SlicePDF.exe'),
            StringStruct('ProductName', 'SlicePDF'),
            StringStruct('ProductVersion', version),
        ])]),
        VarFileInfo([VarStruct('Translation', [0x0409, 1200])]),
    ],
)

datas = [('assets/fonts', 'assets/fonts')]
binaries = []
hiddenimports = []
tmp_ret = collect_all('customtkinter')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
# Collect every tkdnd build, not just the one this machine needs: tkinterdnd2 picks
# win-x64 vs win-x64-tcl9 from the runtime Tcl version.
tmp_ret = collect_all('tkinterdnd2')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['slicepdf.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SlicePDF',
    version=version_info,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
