# -*- mode: python ; coding: utf-8 -*-
"""Đặc tả đóng gói PyInstaller cho tiến trình cập nhật OTA độc lập updater.exe (thuần stdlib)."""
from pathlib import Path

_icon_file = 'assets/app_icon.ico' if Path('assets/app_icon.ico').is_file() else None
_version_file = 'build/version_info.txt' if Path('build/version_info.txt').is_file() else None

a = Analysis(
    ['updater_runner.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        '_tkinter',
        'openpyxl',
        'sqlite3',
        'webview',
        'pythonnet',
        'clr_loader',
        'nh3',
        'ssl',
        '_ssl',
        'hashlib',
        '_hashlib',
        'decimal',
        'unicodedata',
        'pyexpat',
        'lzma',
        'bz2',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'pytest',
        'unittest',
        'pydoc',
    ],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='updater',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon_file,
    version=_version_file,
)
