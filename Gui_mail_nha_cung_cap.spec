# -*- mode: python ; coding: utf-8 -*-
"""Đặc tả đóng gói PyInstaller (--onedir) cho Gmail Auto Mailer v3.0 (Haesung Vina).

Ưu điểm `--onedir` kết hợp bộ cài 1-Click Setup.exe:
- Khởi động nhanh gấp 3 lần (không giải nén hàng chục MB vào %TEMP% mỗi lần mở).
- Giảm cảnh báo nhầm Antivirus/Defender (tắt UPX, nhúng đầy đủ Icon & Windows Version Info).
- Đóng gói gọn tài nguyên Web UI tĩnh (app/ui/web) & PyWebView EdgeChromium.
"""
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

_icon_file = 'assets/app_icon.ico' if Path('assets/app_icon.ico').is_file() else None
_version_file = 'build/version_info.txt' if Path('build/version_info.txt').is_file() else None

_datas = [
    ('app/ui/web/index.html', 'app/ui/web'),
    ('app/ui/web/styles.css', 'app/ui/web'),
    ('app/ui/web/app.js', 'app/ui/web'),
]
if _icon_file:
    _datas.append(('assets/app_icon.ico', 'assets'))

_datas += collect_data_files('webview')
_datas += collect_data_files('clr_loader')
_datas += collect_data_files('pythonnet')

_hidden = [
    'openpyxl',
    'et_xmlfile',
    'sqlite3',
    'nh3',
    'webview',
    'webview.platforms.edgechromium',
    'webview.platforms.winforms',
    'clr',
    'pythonnet',
    'bottle',
] + collect_submodules('webview.platforms')

a = Analysis(
    ['main.py'],
    pathex=['.', 'vendor'],
    binaries=[],
    datas=_datas,
    hiddenimports=_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        '_tkinter',
        'tcl',
        'tk',
        'PIL',
        'customtkinter',
        'cryptography',
        'bcrypt',
        'setuptools',
        'pkg_resources',
        'tomli',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'pytest',
        'unittest',
        'pydoc',
        'webview.platforms.cocoa',
        'webview.platforms.gtk',
        'webview.platforms.qt',
        'webview.platforms.android',
    ],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Gui_mail_nha_cung_cap',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon_file,
    version=_version_file,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Gui_mail_nha_cung_cap',
)
