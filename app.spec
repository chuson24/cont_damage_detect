# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Container Damage Detection.

Build with:  pyinstaller app.spec --distpath <dist> --workpath <work> --noconfirm

Bundles a CUDA-enabled torch build so a single package auto-detects and
uses whichever NVIDIA GPU is present (see core/gpu_check.py) and falls
back to CPU when there is none / the GPU turns out unusable.
"""
from PyInstaller.utils.hooks import collect_all

datas = [("weights", "weights")]
binaries = []
hiddenimports = []

for pkg in ("torch", "torchvision", "ultralytics", "cv2", "PyQt6"):
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

a = Analysis(
    ["main.py"],
    pathex=[SPECPATH],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Not used at runtime by this app; jedi in particular vendors huge
    # nested typeshed stub trees (django, etc.) whose paths are long
    # enough to blow past Windows' 260-char MAX_PATH during installer
    # compilation, so keep it (and the notebook stack that pulls it in)
    # out of the bundle entirely.
    excludes=["IPython", "jedi", "notebook", "ipykernel", "ipython_genutils", "jupyter_client", "jupyter_core"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ContainerDamageDetection",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="ContainerDamageDetection",
)
