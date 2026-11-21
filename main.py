"""Điểm khởi động ứng dụng Desktop Gmail Auto Mailer v3.0 (Haesung Vina)."""

from __future__ import annotations

import ctypes
import sys
import traceback
from pathlib import Path

# Ưu tiên thư viện hệ thống; giữ tương thích fallback nếu chạy từ mã nguồn có thư mục vendor/
_VENDOR_DIR = str(Path(__file__).resolve().parent / "vendor")
if Path(_VENDOR_DIR).is_dir() and _VENDOR_DIR not in sys.path:
    sys.path.append(_VENDOR_DIR)


def _show_fatal_error(title: str, message: str) -> None:
    """Hiển thị hộp thoại lỗi native Windows (không phụ thuộc Tkinter)."""
    if sys.platform == "win32":
        try:
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
            return
        except Exception:
            pass
    print(f"{title}:\n{message}", file=sys.stderr)


def main() -> None:
    try:
        from app.ui.window import launch_app

        launch_app(debug=False)
    except Exception:  # noqa: BLE001
        _show_fatal_error(
            "Lỗi khởi động Gmail Auto Mailer",
            "Không thể khởi động ứng dụng. Vui lòng kiểm tra máy đã có Microsoft Edge WebView2 Runtime.\n\n"
            + traceback.format_exc(),
        )


if __name__ == "__main__":
    main()
