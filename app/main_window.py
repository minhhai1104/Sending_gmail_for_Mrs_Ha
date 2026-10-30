"""Cửa sổ chính của ứng dụng."""
import os
import queue
import threading
import tkinter as tk
from datetime import date
from tkinter import messagebox, scrolledtext, ttk
from typing import Callable, Optional

from . import __version__, history
from .config import CONFIG_PATH, Config, ConfigError, ensure_config_file, load_config
from .mailer import MailError, SendResult, send_plans, test_connection
from .planner import KIND_DRAFT, KIND_FINAL, MailPlan, build_plans, resolve_attach_dir
from .preview_dialog import PreviewDialog

_KIND_HINT = {
    KIND_DRAFT: "Bản tạm tính: chỉ đính kèm file Excel",
    KIND_FINAL: "Bản chốt: đính kèm file Excel và file PDF",
}
_POLL_MS = 100


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Gửi mail hàng loạt cho nhà cung cấp v{__version__}")
        self.geometry("780x620")
        self.minsize(700, 520)

        today = date.today()
        self._month = tk.StringVar(value=str(today.month))
        self._year = tk.StringVar(value=str(today.year))
        self._kind = tk.StringVar(value=KIND_DRAFT)
        self._events: queue.Queue = queue.Queue()
        self._buttons: list[tk.Widget] = []
        self._busy = False

        self._build()
        self.after(_POLL_MS, self._poll_events)
        self.after(200, self._check_first_run)

    # ------------------------------------------------------------------ giao diện

    def _build(self) -> None:
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)

        period = ttk.LabelFrame(root, text=" 1. Chọn kỳ gửi ", padding=12)
        period.pack(fill="x")
        ttk.Label(period, text="Tháng:").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(period, from_=1, to=12, width=5, textvariable=self._month).grid(row=0, column=1, padx=(4, 18))
        ttk.Label(period, text="Năm:").grid(row=0, column=2, sticky="w")
        ttk.Spinbox(period, from_=2020, to=2100, width=7, textvariable=self._year).grid(row=0, column=3, padx=4)
        for column, kind in enumerate((KIND_DRAFT, KIND_FINAL)):
            ttk.Radiobutton(period, text=f"{kind}  ({_KIND_HINT[kind].split(': ')[1]})",
                            variable=self._kind, value=kind).grid(row=1, column=column * 2, columnspan=2,
                                                                  sticky="w", pady=(10, 0))

        send_button = tk.Button(root, text="XEM TRƯỚC & GỬI", bg="#1B7F3B", fg="white",
                                font=("Segoe UI", 13, "bold"), pady=8, command=self._on_preview)
        send_button.pack(fill="x", pady=12)
        self._buttons.append(send_button)

        tools = ttk.Frame(root)
        tools.pack(fill="x")
        for text, command in (("Mở file cấu hình", self._open_config),
                              ("Mở thư mục đính kèm", self._open_attach_dir),
                              ("Kiểm tra kết nối Gmail", self._on_test_connection),
                              ("Xem lịch sử gửi", self._open_history)):
            button = ttk.Button(tools, text=text, command=command)
            button.pack(side="left", expand=True, fill="x", padx=2)
            self._buttons.append(button)

        self._progress = ttk.Progressbar(root, mode="determinate")
        self._progress.pack(fill="x", pady=(12, 4))
        self._log = scrolledtext.ScrolledText(root, height=12, state="disabled", font=("Consolas", 10))
        self._log.pack(fill="both", expand=True)
        self._log.tag_configure("ok", foreground="#1B7F3B")
        self._log.tag_configure("error", foreground="#C00000")

    # ------------------------------------------------------------------ tiện ích

    def _write_log(self, text: str, tag: Optional[str] = None) -> None:
        self._log.configure(state="normal")
        self._log.insert("end", text + "\n", tag)
        self._log.see("end")
        self._log.configure(state="disabled")

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        for button in self._buttons:
            button.configure(state="disabled" if busy else "normal")

    def _read_period(self) -> Optional[tuple[int, int]]:
        try:
            month, year = int(self._month.get()), int(self._year.get())
        except ValueError:
            month = year = 0
        if not (1 <= month <= 12 and 2000 <= year <= 2100):
            messagebox.showwarning("Kỳ gửi chưa đúng", "Tháng phải từ 1 đến 12 và năm phải là số hợp lệ.")
            return None
        return month, year

    def _load_config(self) -> Optional[Config]:
        try:
            return load_config()
        except ConfigError as exc:
            messagebox.showerror("Lỗi file cấu hình", str(exc))
            return None

    def _check_first_run(self) -> None:
        try:
            created = ensure_config_file()
        except OSError as exc:
            messagebox.showerror("Lỗi", f"Không tạo được file cấu hình: {exc}")
            return
        if created:
            messagebox.showinfo(
                "Chào mừng!",
                f"Đây là lần chạy đầu tiên. App đã tạo file '{CONFIG_PATH.name}'.\n\n"
                "Hãy điền Gmail, Mật khẩu ứng dụng và mail người nhận từng nhà cung cấp "
                "(xem sheet 'Hướng dẫn'), lưu file rồi quay lại app.")
            self._open_config()

    # ------------------------------------------------------------------ nút bấm

    def _open_config(self) -> None:
        if not CONFIG_PATH.exists():
            self._check_first_run()
        if CONFIG_PATH.exists():
            os.startfile(CONFIG_PATH)

    def _open_attach_dir(self) -> None:
        cfg, period = self._load_config(), self._read_period()
        if cfg and period:
            folder = resolve_attach_dir(cfg, *period)
            folder.mkdir(parents=True, exist_ok=True)
            os.startfile(folder)

    def _open_history(self) -> None:
        if history.HISTORY_PATH.exists():
            os.startfile(history.HISTORY_PATH)
        else:
            messagebox.showinfo("Lịch sử gửi", "Chưa có lịch sử gửi mail nào.")

    def _on_test_connection(self) -> None:
        cfg = self._load_config()
        if not cfg:
            return
        problems = cfg.settings.problems()
        if problems:
            messagebox.showwarning("Chưa điền đủ thông tin Gmail", "\n".join(problems))
            return
        self._write_log("Đang kiểm tra kết nối Gmail...")
        self._run_in_background(lambda: self._test_worker(cfg))

    def _on_preview(self) -> None:
        period = self._read_period()
        cfg = self._load_config()  # đọc lại mỗi lần để nhận thay đổi mới nhất trong file Excel
        if not (period and cfg):
            return
        month, year = period
        kind = self._kind.get()
        plans = build_plans(cfg, month, year, kind)
        if not plans:
            messagebox.showwarning("Chưa có nhà cung cấp", "Sheet 'Nhà cung cấp' đang trống.")
            return

        dialog = PreviewDialog(self, cfg.settings, plans, f"tháng {month:02d}/{year} - {kind}",
                               history.sent_suppliers(month, year, kind))
        self.wait_window(dialog)
        if dialog.confirmed:
            self._progress.configure(maximum=len(dialog.to_send), value=0)
            self._write_log(f"=== Bắt đầu gửi tháng {month:02d}/{year} - {kind}: {len(dialog.to_send)} mail ===")
            self._run_in_background(lambda: self._send_worker(cfg, dialog.to_send, month, year, kind))

    # ------------------------------------------------------------------ luồng nền

    def _run_in_background(self, target: Callable[[], None]) -> None:
        self._set_busy(True)
        threading.Thread(target=target, daemon=True).start()

    def _test_worker(self, cfg: Config) -> None:
        try:
            test_connection(cfg.settings)
            self._events.put(("log", "✔ Kết nối Gmail thành công.", "ok"))
        except MailError as exc:
            self._events.put(("log", f"✖ {exc}", "error"))
        self._events.put(("finished", None, None))

    def _send_worker(self, cfg: Config, plans: list[MailPlan], month: int, year: int, kind: str) -> None:
        def on_result(plan: MailPlan, result: SendResult) -> None:
            self._events.put(("result", (plan, result, month, year, kind), None))

        try:
            send_plans(cfg.settings, plans, on_result)
        except MailError as exc:
            self._events.put(("log", f"✖ {exc}", "error"))
        self._events.put(("finished", None, None))

    def _poll_events(self) -> None:
        """Nhận kết quả từ luồng nền và cập nhật giao diện (chỉ luồng chính được đụng vào Tkinter)."""
        while True:
            try:
                kind, payload, tag = self._events.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self._write_log(payload, tag)
            elif kind == "result":
                self._handle_result(*payload)
            elif kind == "finished":
                self._set_busy(False)
        self.after(_POLL_MS, self._poll_events)

    def _handle_result(self, plan: MailPlan, result: SendResult, month: int, year: int, kind: str) -> None:
        self._progress.step(1)
        icon, tag = ("✔", "ok") if result.ok else ("✖", "error")
        self._write_log(f"{icon} {plan.supplier}: {result.message}", tag)
        if not history.record(plan, result, month, year, kind):
            self._write_log("   (Không ghi được lịch sử. Hãy đóng file Lich_su_gui.csv nếu đang mở.)", "error")
