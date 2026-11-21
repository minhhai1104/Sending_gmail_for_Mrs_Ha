"""Khởi chạy cửa sổ PyWebView (Microsoft Edge WebView2) với Dark Titlebar, Drag & Drop & AppUserModelID."""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path
from typing import Any

import webview
from webview.dom import DOMEventHandler

from .. import APP_NAME, APP_USER_MODEL_ID, __version__
from ..adapters.dpapi_vault import DpapiSecretStore
from ..adapters.fs_scanner import OsFileScanner
from ..adapters.paths import (
    get_app_dir,
    get_db_path,
    get_icon_path,
    get_vault_path,
    get_web_ui_dir,
    get_webview_storage_dir,
)
from ..adapters.smtp_mailer import GmailSmtpTransport
from ..adapters.sqlite_store import SqliteAppStore
from ..application.app_service import AppService
from ..application.batch_runner import BatchRunner
from ..application.dispatch_service import DispatchService
from .bridge import UiBridge


def _configure_windows_shell() -> None:
    """Kích hoạt High-DPI Per-Monitor V2 và AppUserModelID cho icon Taskbar Windows sắc nét."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass
    try:
        # Per-Monitor DPI Aware V2 (-4)
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass


def _is_windows_dark_theme() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return int(val) == 0
    except Exception:
        return False


def _apply_win32_dark_titlebar(window: webview.Window, dark: bool) -> None:
    """Đồng bộ màu thanh tiêu đề Windows 10/11 với chế độ Sáng/Tối của ứng dụng."""
    if sys.platform != "win32":
        return
    try:
        hwnd = 0
        native = getattr(window, "native", None)
        if native is not None and hasattr(native, "Handle"):
            hwnd = int(native.Handle.ToInt64())
        if not hwnd:
            hwnd = int(ctypes.windll.user32.FindWindowW(None, window.title))
        if not hwnd:
            return
        value = ctypes.c_int(1 if dark else 0)
        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20 (Win11 / Win10 2004+) hoặc 19 (Win10 1903)
        for attr in (20, 19):
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                ctypes.c_void_p(hwnd),
                ctypes.c_int(attr),
                ctypes.byref(value),
                ctypes.sizeof(value),
            )
        # Buộc Windows vẽ lại khung tiêu đề (non-client area) ngay lập tức
        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0027)
    except Exception:
        pass


def launch_app(debug: bool = False) -> None:
    """Điểm khởi động chính của ứng dụng Desktop Gmail Auto Mailer v3.0."""
    _configure_windows_shell()

    store = SqliteAppStore(db_path=get_db_path(), seed_defaults=True)
    # Tự động kế thừa lịch sử gửi từ history.db cũ (nếu nâng cấp từ v2.0)
    legacy_history = get_app_dir() / "history.db"
    if legacy_history.is_file():
        store.import_legacy_history_db(legacy_history)

    secret_store = DpapiSecretStore(vault_path=get_vault_path())
    scanner = OsFileScanner()
    transport = GmailSmtpTransport()

    app_service = AppService(store, store, secret_store, transport)
    dispatch_service = DispatchService(store, store, secret_store, scanner, transport)
    batch_runner = BatchRunner(transport, store)

    cfg = store.load_config()
    initial_dark = (
        True
        if cfg.prefs.theme == "dark"
        else (False if cfg.prefs.theme == "light" else _is_windows_dark_theme())
    )
    window_ref: list[webview.Window] = []

    def _on_theme_change(theme_name: str) -> None:
        if not window_ref:
            return
        is_dark = (
            True
            if theme_name == "dark"
            else (False if theme_name == "light" else _is_windows_dark_theme())
        )
        _apply_win32_dark_titlebar(window_ref[0], is_dark)

    bridge = UiBridge(
        app_service=app_service,
        dispatch_service=dispatch_service,
        batch_runner=batch_runner,
        secret_store=secret_store,
        on_theme_change=_on_theme_change,
    )

    index_path = get_web_ui_dir() / "index.html"
    icon_path = get_icon_path()
    bg_hex = "#111317" if initial_dark else "#F6F8FA"

    window = webview.create_window(
        title=f"{APP_NAME} v{__version__} — Haesung Vina",
        url=str(index_path),
        js_api=bridge,
        width=1240,
        height=790,
        min_size=(980, 650),
        resizable=True,
        background_color=bg_hex,
        text_select=True,
        confirm_close=False,
    )
    if window is None:
        raise RuntimeError("Không khởi tạo được cửa sổ PyWebView.")

    window_ref.append(window)
    bridge.attach_window(window)

    def _on_closing() -> bool:
        if bridge.is_busy:
            bridge.shutdown()
        return True

    def _on_loaded() -> None:
        _apply_win32_dark_titlebar(window, initial_dark)
        # Đăng ký native Drag & Drop ở tầng Python để lấy đường dẫn tuyệt đối chuẩn Windows
        try:
            def _on_drop(event: Any) -> None:
                dt = event.get("dataTransfer") if isinstance(event, dict) else None
                files = dt.get("files") if isinstance(dt, dict) else None
                if not files:
                    return
                paths: list[Path] = []
                for f in files:
                    full_path = f.get("pywebviewFullPath") if isinstance(f, dict) else None
                    if full_path:
                        paths.append(Path(str(full_path)))
                if paths:
                    bridge.handle_native_dropped_paths(paths)

            window.dom.document.events.dragenter += DOMEventHandler(  # type: ignore[arg-type]
                lambda _e: None, prevent_default=True
            )
            window.dom.document.events.dragover += DOMEventHandler(  # type: ignore[arg-type]
                lambda _e: None, prevent_default=True
            )
            window.dom.document.events.drop += DOMEventHandler(  # type: ignore[arg-type]
                _on_drop, prevent_default=True
            )
        except Exception:
            pass

        # Kiểm tra bản cập nhật OTA âm thầm ở nền
        bridge.check_ota_update(silent=True)

    window.events.closing += _on_closing
    window.events.loaded += _on_loaded

    webview.start(
        gui="edgechromium",
        debug=debug,
        http_server=True,
        private_mode=False,
        storage_path=str(get_webview_storage_dir()),
        icon=str(icon_path) if icon_path.is_file() else None,
    )
