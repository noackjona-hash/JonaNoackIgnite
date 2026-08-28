# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
import os

# Repository-Root ermitteln (dieses Spec-File liegt jetzt in installer/), damit
# main.py und icon/ unabhängig vom Aufrufort korrekt gefunden werden.
REPO_ROOT = os.path.dirname(SPECPATH)

datas = [(os.path.join(REPO_ROOT, 'icon'), 'icon')]
hiddenimports = ['matplotlib.backends.backend_tkagg', 'mpl_toolkits.mplot3d']
tmp_ret = collect_all('customtkinter')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    [os.path.join(REPO_ROOT, 'main.py')],
    pathex=[REPO_ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch', 'torchvision', 'torchaudio', 'scipy', 'pandas', 'sympy',
        'IPython', 'notebook', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
        'cuda', 'cudnn', 'triton', 'tensorrt'
    ],
    noarchive=False,
    optimize=0,
)

# Aggressiver Ausschluss von CUDA / PyTorch / LLVM / MKL / ML-Binaries
EXCLUDE_BIN_KEYWORDS = (
    'torch', 'libtorch', 'cuda', 'cudnn', 'cublas', 'cufft', 'curand',
    'cusolver', 'cusparse', 'nccl', 'nvrtc', 'tensorrt', 'llvm', 'triton'
)

a.binaries = [
    b for b in a.binaries
    if not any(k in os.path.basename(b[0]).lower() for k in EXCLUDE_BIN_KEYWORDS)
]

a.datas = [
    d for d in a.datas
    if not any(k in os.path.basename(d[0]).lower() for k in EXCLUDE_BIN_KEYWORDS)
]

pyz = PYZ(a.pure)

import sys
icon_list = [os.path.join(REPO_ROOT, 'icon', 'LogoRund.ico')] if sys.platform.startswith('win') else None

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='IGNITE',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_list,
    version_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='IGNITE',
)
