"""Điểm khởi động ứng dụng gửi mail hàng loạt."""
import ctypes
import sys
import traceback
from pathlib import Path

# Ưu tiên thư viện hệ thống; nếu máy chưa cài openpyxl thì dùng bản đóng gói sẵn trong vendor/
_VENDOR_DIR = str(Path(__file__).resolve().parent / "vendor")
if _VENDOR_DIR not in sys.path:
    sys.path.append(_VENDOR_DIR)


def _enable_high_dpi() -> None:
    """Kích hoạt hiển thị sắc nét (High-DPI Awareness) trên màn hình Windows 10/11."""
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass


def main() -> None:
    _enable_high_dpi()
    try:
        from app.main_window import MainWindow
        MainWindow().mainloop()
    except Exception:  # noqa: BLE001 - chạy bằng pythonw không có console nên phải hiện lỗi bằng hộp thoại
        import tkinter
        from tkinter import messagebox
        root = tkinter.Tk()
        root.withdraw()
        messagebox.showerror("Lỗi khởi động ứng dụng", traceback.format_exc())


if __name__ == "__main__":
    main()
