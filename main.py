"""Điểm khởi động ứng dụng gửi mail hàng loạt."""
import sys
import traceback
from pathlib import Path

# openpyxl được đóng gói sẵn trong thư mục vendor/ nên máy khác chỉ cần có Python là chạy được
sys.path.insert(0, str(Path(__file__).resolve().parent / "vendor"))


def main() -> None:
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
