# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

APP_NAME = "Transparentor"
APP_VERSION = "1.1.0"

spec_dir = Path(SPECPATH).resolve()
script_path = spec_dir / "Transparentor.pyw"
icon_path = spec_dir / "transparentoricon.ico"
version_info_path = spec_dir / "Transparentor.version.txt"

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

# Ensure all modules and data files from tkinterdnd2, rembg, and onnxruntime are fully collected
hiddenimports = collect_submodules("tkinterdnd2") + collect_submodules("rembg") + collect_submodules("onnxruntime")
datas = collect_data_files("tkinterdnd2") + collect_data_files("rembg") + collect_data_files("onnxruntime")
datas += copy_metadata("pymatting") + copy_metadata("rembg")
datas.append((str(icon_path), "."))

a = Analysis(
    [str(script_path)],
    pathex=[str(spec_dir)],
    binaries=[],
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
    name=APP_NAME,
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
    icon=str(icon_path) if icon_path.exists() else None,
    version=str(version_info_path) if version_info_path.exists() else None,
)
