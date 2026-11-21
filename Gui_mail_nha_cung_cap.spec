# -*- mode: python ; coding: utf-8 -*-
"""Đặc tả đóng gói PyInstaller cho ứng dụng Gui_mail_nha_cung_cap.exe (kèm .ota_token.dat mã hóa)."""
from pathlib import Path

_ota_datas = [('.ota_token.dat', '.')] if Path('.ota_token.dat').is_file() else []

a = Analysis(
    ['main.py'],
    pathex=['.', 'vendor'],
    binaries=[],
    datas=_ota_datas,
    hiddenimports=['openpyxl', 'et_xmlfile', 'sqlite3'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
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
    name='Gui_mail_nha_cung_cap',
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
