"""Cửa sổ chính của ứng dụng với bộ điều khiển luồng (Pause/Resume/Cancel), Telemetry & OTA Update."""
import os
import queue
import sys
import tempfile
import threading
import time
import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk
from typing import Any, Callable, Optional

from . import __version__, history, updater
from .config import APP_DIR, CONFIG_PATH, Config, ConfigError, ensure_config_file, load_config
from .mailer import (
    DEFAULT_PACING_SECONDS,
    MailError,
    SendResult,
    send_plans,
    test_connection,
)
from .planner import KIND_DRAFT, KIND_FINAL, MailPlan, build_plans, resolve_attach_dir
from .preview_dialog import PreviewDialog

_KIND_HINT = {
    KIND_DRAFT: "Bản tạm tính: chỉ đính kèm file Excel",
    KIND_FINAL: "Bản chốt: đính kèm file Excel và file PDF",
}
_POLL_MS = 100


class MainWindow(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"Gửi mail hàng loạt cho nhà cung cấp v{__version__} — Haesung Vina")
        self.geometry("820x680")
        self.minsize(740, 560)

        today = date.today()
        self._month = tk.StringVar(value=str(today.month))
        self._year = tk.StringVar(value=str(today.year))
        self._kind = tk.StringVar(value=KIND_DRAFT)
        self._telemetry = tk.StringVar(value="Trạng thái: Sẵn sàng")
        self._events: queue.Queue[tuple[str, Any, Optional[str]]] = queue.Queue()
        self._buttons: list[tk.Widget] = []
        self._busy = False
        self._dark_mode = False
        self._pending_release: Optional[updater.ReleaseInfo] = None

        # Cờ điều khiển luồng gửi (Pause / Cancel)
        self._pause_event = threading.Event()
        self._cancel_event = threading.Event()
        self._total_to_send = 0
        self._sent_count = 0
        self._ok_count = 0
        self._fail_count = 0
        self._batch_start_time = 0.0

        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(_POLL_MS, self._poll_events)
        self.after(200, self._check_first_run)
        self.after(900, lambda: self._start_ota_check(silent=True))

    # ------------------------------------------------------------------ giao diện

    def _build(self) -> None:
        self._root_frame = ttk.Frame(self, padding=14)
        self._root_frame.pack(fill="both", expand=True)

        top_bar = ttk.Frame(self._root_frame)
        top_bar.pack(fill="x", pady=(0, 6))
        ttk.Label(
            top_bar,
            text=f"HỆ THỐNG GỬI EMAIL BÁO CÁO NHÀ CUNG CẤP (v{__version__})",
            font=("Segoe UI", 12, "bold"),
        ).pack(side="left")
        self._theme_btn = ttk.Button(
            top_bar, text="🌙 Giao diện Tối", command=self._toggle_theme
        )
        self._theme_btn.pack(side="right")
        self._ota_check_btn = ttk.Button(
            top_bar,
            text="🔄 Kiểm tra cập nhật",
            command=lambda: self._start_ota_check(silent=False),
        )
        self._ota_check_btn.pack(side="right", padx=(0, 6))
        self._buttons.append(self._ota_check_btn)

        # Thanh thông báo OTA (ẩn mặc định, chỉ hiện khi có bản cập nhật mới trên GitHub Releases)
        self._ota_banner = tk.Frame(self._root_frame, bg="#0078D4", padx=10, pady=6)
        self._ota_label = tk.Label(
            self._ota_banner,
            text="",
            bg="#0078D4",
            fg="white",
            font=("Segoe UI", 9, "bold"),
        )
        self._ota_label.pack(side="left")
        self._ota_apply_btn = tk.Button(
            self._ota_banner,
            text="Cập nhật ngay",
            bg="#FFFFFF",
            fg="#0078D4",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=10,
            pady=2,
            command=self._on_apply_ota_update,
        )
        self._ota_apply_btn.pack(side="right")

        period = ttk.LabelFrame(
            self._root_frame, text=" 1. Chọn kỳ gửi & Chế độ đính kèm ", padding=12
        )
        period.pack(fill="x")
        ttk.Label(period, text="Tháng:").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(
            period, from_=1, to=12, width=5, textvariable=self._month
        ).grid(row=0, column=1, padx=(4, 18))
        ttk.Label(period, text="Năm:").grid(row=0, column=2, sticky="w")
        ttk.Spinbox(
            period, from_=2020, to=2100, width=7, textvariable=self._year
        ).grid(row=0, column=3, padx=4)
        for column, kind in enumerate((KIND_DRAFT, KIND_FINAL)):
            ttk.Radiobutton(
                period,
                text=f"{kind}  ({_KIND_HINT[kind].split(': ')[1]})",
                variable=self._kind,
                value=kind,
            ).grid(
                row=1,
                column=column * 2,
                columnspan=2,
                sticky="w",
                pady=(10, 0),
            )

        send_button = tk.Button(
            self._root_frame,
            text="XEM TRƯỚC & GỬI",
            bg="#107C41",
            fg="white",
            activebackground="#0E6B37",
            activeforeground="white",
            font=("Segoe UI", 13, "bold"),
            pady=8,
            relief="flat",
            command=self._on_preview,
        )
        send_button.pack(fill="x", pady=12)
        self._buttons.append(send_button)

        tools = ttk.Frame(self._root_frame)
        tools.pack(fill="x")
        for text, command in (
            ("Mở file cấu hình", self._open_config),
            ("Mở thư mục đính kèm", self._open_attach_dir),
            ("Kiểm tra kết nối Gmail", self._on_test_connection),
            ("Xem lịch sử gửi", self._open_history),
        ):
            button = ttk.Button(tools, text=text, command=command)
            button.pack(side="left", expand=True, fill="x", padx=2)
            self._buttons.append(button)

        # Phân vùng Telemetry & Điều khiển luồng gửi
        telemetry_frame = ttk.Frame(self._root_frame)
        telemetry_frame.pack(fill="x", pady=(12, 4))

        self._telemetry_label = ttk.Label(
            telemetry_frame,
            textvariable=self._telemetry,
            font=("Segoe UI", 9, "bold"),
        )
        self._telemetry_label.pack(side="left")

        self._cancel_button = ttk.Button(
            telemetry_frame,
            text="⏹ Hủy gửi",
            state="disabled",
            command=self._on_cancel_send,
        )
        self._cancel_button.pack(side="right", padx=(4, 0))

        self._pause_button = ttk.Button(
            telemetry_frame,
            text="⏸ Tạm dừng",
            state="disabled",
            command=self._on_toggle_pause,
        )
        self._pause_button.pack(side="right")

        self._progress = ttk.Progressbar(self._root_frame, mode="determinate")
        self._progress.pack(fill="x", pady=(2, 6))

        self._log = scrolledtext.ScrolledText(
            self._root_frame, height=12, state="disabled", font=("Consolas", 10)
        )
        self._log.pack(fill="both", expand=True)
        self._log.tag_configure("ok", foreground="#107C41")
        self._log.tag_configure("error", foreground="#D83B01")
        self._log.tag_configure("info", foreground="#0078D4")

    # ------------------------------------------------------------------ giao diện Sáng/Tối

    def _toggle_theme(self) -> None:
        self._dark_mode = not self._dark_mode
        style = ttk.Style(self)
        if self._dark_mode:
            bg, fg, log_bg = "#201F1E", "#F3F2F1", "#1B1A19"
            self._theme_btn.configure(text="☀ Giao diện Sáng")
            self._log.tag_configure("ok", foreground="#2BBB72")
            self._log.tag_configure("error", foreground="#F7630C")
            self._log.tag_configure("info", foreground="#2899F5")
        else:
            bg, fg, log_bg = "#F3F2F1", "#201F1E", "#FFFFFF"
            self._theme_btn.configure(text="🌙 Giao diện Tối")
            self._log.tag_configure("ok", foreground="#107C41")
            self._log.tag_configure("error", foreground="#D83B01")
            self._log.tag_configure("info", foreground="#0078D4")

        self.configure(bg=bg)
        style.configure("TFrame", background=bg)
        style.configure("TLabelframe", background=bg, foreground=fg)
        style.configure("TLabelframe.Label", background=bg, foreground=fg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TRadiobutton", background=bg, foreground=fg)
        self._log.configure(bg=log_bg, fg=fg, insertbackground=fg)

    # ------------------------------------------------------------------ tiện ích

    def _write_log(self, text: str, tag: Optional[str] = None) -> None:
        self._log.configure(state="normal")
        if tag:
            self._log.insert("end", text + "\n", tag)
        else:
            self._log.insert("end", text + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")

    def _set_busy(self, busy: bool, is_sending: bool = False) -> None:
        self._busy = busy
        for button in self._buttons:
            button.configure(state="disabled" if busy else "normal")  # type: ignore[call-arg]
        self._ota_apply_btn.configure(state="disabled" if busy else "normal")
        if is_sending and busy:
            self._pause_button.configure(state="normal", text="⏸ Tạm dừng")
            self._cancel_button.configure(state="normal")
        else:
            self._pause_button.configure(state="disabled", text="⏸ Tạm dừng")
            self._cancel_button.configure(state="disabled")

    def _safe_open_path(self, target: Path) -> None:
        try:
            os.startfile(target)  # type: ignore[attr-defined]
        except OSError as exc:
            messagebox.showerror(
                "Không mở được tệp",
                f"Hệ điều hành không mở được '{target.name}':\n{exc}",
            )

    def _read_period(self) -> Optional[tuple[int, int]]:
        try:
            month, year = int(self._month.get()), int(self._year.get())
        except ValueError:
            month = year = 0
        if not (1 <= month <= 12 and 2000 <= year <= 2100):
            messagebox.showwarning(
                "Kỳ gửi chưa đúng",
                "Tháng phải từ 1 đến 12 và năm phải là số hợp lệ.",
            )
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
                "(xem sheet 'Hướng dẫn'), lưu file rồi quay lại app.",
            )
            self._open_config()

    def _on_close(self) -> None:
        if self._busy:
            confirm = messagebox.askyesno(
                "Đang thực hiện tác vụ",
                "Ứng dụng đang kết nối, gửi mail hoặc tải bản cập nhật.\n"
                "Bạn có chắc chắn muốn dừng ngay và thoát ứng dụng không?",
            )
            if not confirm:
                return
            self._cancel_event.set()
            self._pause_event.clear()
        self.destroy()

    # ------------------------------------------------------------------ cập nhật OTA 2 tiến trình

    def _start_ota_check(self, silent: bool = True) -> None:
        if self._busy:
            return
        if not silent:
            self._write_log("Đang kiểm tra bản cập nhật mới trên GitHub Releases...", "info")

        def worker() -> None:
            try:
                rel = updater.check_for_update(__version__)
                self._events.put(("ota_checked", (rel, silent), None))
            except updater.UpdateError as exc:
                if not silent:
                    self._events.put(("log", f"✖ {exc}", "error"))

        threading.Thread(target=worker, daemon=True).start()

    def _handle_ota_checked(self, release: Optional[updater.ReleaseInfo], silent: bool) -> None:
        if release is not None:
            self._pending_release = release
            self._ota_label.configure(
                text=f"🚀 Đã có phiên bản mới v{release.version} trên GitHub Releases!"
            )
            self._ota_banner.pack(fill="x", pady=(0, 8), after=self._root_frame.winfo_children()[0])
            self._write_log(
                f"🚀 Phát hiện phiên bản mới v{release.version}. Bấm 'Cập nhật ngay' để nâng cấp tự động.",
                "info",
            )
            if not silent:
                self._on_apply_ota_update()
        elif not silent:
            self._write_log(f"✔ Bạn đang sử dụng phiên bản mới nhất (v{__version__}).", "ok")
            messagebox.showinfo(
                "Kiểm tra cập nhật",
                f"Bạn đang sử dụng phiên bản mới nhất (v{__version__}).",
            )

    def _on_apply_ota_update(self) -> None:
        if self._busy or self._pending_release is None:
            return
        rel = self._pending_release
        notes = rel.release_notes or "Nâng cấp hiệu năng và bảo mật."
        confirm = messagebox.askyesno(
            f"Cập nhật lên phiên bản v{rel.version}",
            f"Đã có phiên bản mới v{rel.version} (hiện tại: v{__version__}).\n\n"
            f"Nội dung cập nhật:\n{notes[:400]}\n\n"
            "Dữ liệu cấu hình (Cau_hinh.xlsx), lịch sử gửi và file đính kèm của bạn "
            "được giữ nguyên 100%.\n"
            "Bạn có muốn tải và tự động cập nhật ngay bây giờ không?",
        )
        if not confirm:
            return

        self._progress.configure(maximum=100, value=0)
        self._telemetry.set(f"Đang tải bản cập nhật v{rel.version}...")
        self._write_log(f"Đang tải gói cập nhật {rel.asset_name}...", "info")
        self._run_in_background(lambda: self._ota_download_worker(rel), is_sending=False)

    def _ota_download_worker(self, rel: updater.ReleaseInfo) -> None:
        def on_progress(downloaded: int, total: int) -> None:
            if total > 0:
                pct = min(100, int((downloaded / total) * 100))
                self._events.put(("ota_progress", (pct, rel.version), None))

        try:
            temp_dir = Path(tempfile.gettempdir()) / "GmailAutoMailer_OTA"
            pkg_path = updater.download_release_asset(
                rel, temp_dir, on_progress=on_progress
            )
            self._events.put(("ota_ready_to_swap", (pkg_path, rel.version), None))
        except updater.UpdateError as exc:
            self._events.put(("log", f"✖ Cập nhật thất bại: {exc}", "error"))
            self._events.put(("telemetry", "Trạng thái: Lỗi tải bản cập nhật ✖", None))
            self._events.put(("finished", None, None))

    def _handle_ota_ready_to_swap(self, pkg_path: Path, new_version: str) -> None:
        self._write_log(
            f"✔ Đã tải và xác thực SHA-256 bản v{new_version}. Đang khởi chạy tiến trình Updater...",
            "ok",
        )
        relaunch_target: Optional[Path] = None
        if getattr(sys, "frozen", False):
            relaunch_target = Path(sys.executable).resolve()
        else:
            exe_candidate = APP_DIR / "Gui_mail_nha_cung_cap.exe"
            if exe_candidate.is_file():
                relaunch_target = exe_candidate

        try:
            updater.spawn_standalone_updater(
                package_path=pkg_path,
                target_dir=APP_DIR,
                current_pid=os.getpid(),
                relaunch_exe=relaunch_target,
            )
            self._busy = False
            self.destroy()
        except OSError as exc:
            self._set_busy(False)
            self._write_log(f"✖ Không khởi chạy được tiến trình Updater: {exc}", "error")

    # ------------------------------------------------------------------ nút bấm

    def _open_config(self) -> None:
        if not CONFIG_PATH.exists():
            self._check_first_run()
        if CONFIG_PATH.exists():
            self._safe_open_path(CONFIG_PATH)

    def _open_attach_dir(self) -> None:
        cfg, period = self._load_config(), self._read_period()
        if cfg and period:
            folder = resolve_attach_dir(cfg, *period)
            try:
                folder.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                messagebox.showerror("Lỗi thư mục", f"Không tạo được thư mục đính kèm:\n{exc}")
                return
            self._safe_open_path(folder)

    def _open_history(self) -> None:
        if history.DB_PATH.exists():
            history.export_sqlite_to_excel()
            history.export_sqlite_to_csv()
        if history.EXCEL_HISTORY_PATH.exists():
            self._safe_open_path(history.EXCEL_HISTORY_PATH)
        elif history.HISTORY_PATH.exists():
            self._safe_open_path(history.HISTORY_PATH)
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
        self._telemetry.set("Trạng thái: Đang kiểm tra kết nối Gmail...")
        self._write_log("Đang kiểm tra kết nối Gmail...", "info")
        self._run_in_background(lambda: self._test_worker(cfg), is_sending=False)

    def _on_preview(self) -> None:
        period = self._read_period()
        cfg = self._load_config()  # đọc lại mỗi lần để nhận thay đổi mới nhất trong file Excel
        if not (period and cfg):
            return
        month, year = period
        kind = self._kind.get()
        plans = build_plans(cfg, month, year, kind)
        if not plans:
            messagebox.showwarning(
                "Chưa có nhà cung cấp", "Sheet 'Nhà cung cấp' đang trống."
            )
            return

        dialog = PreviewDialog(
            self,
            cfg.settings,
            plans,
            f"tháng {month:02d}/{year} - {kind}",
            history.sent_suppliers(month, year, kind),
        )
        self.wait_window(dialog)
        if dialog.confirmed and dialog.to_send:
            self._pause_event.clear()
            self._cancel_event.clear()
            self._total_to_send = len(dialog.to_send)
            self._sent_count = 0
            self._ok_count = 0
            self._fail_count = 0
            self._batch_start_time = time.monotonic()
            self._progress.configure(maximum=self._total_to_send, value=0)
            self._telemetry.set(
                f"Đang gửi: 0/{self._total_to_send} (0%)  |  Thành công: 0  |  Lỗi: 0"
            )
            self._write_log(
                f"=== Bắt đầu gửi tháng {month:02d}/{year} - {kind}: {self._total_to_send} mail ===",
                "info",
            )
            self._run_in_background(
                lambda: self._send_worker(cfg, dialog.to_send, month, year, kind),
                is_sending=True,
            )

    def _on_toggle_pause(self) -> None:
        if not self._busy:
            return
        if self._pause_event.is_set():
            self._pause_event.clear()
            self._pause_button.configure(text="⏸ Tạm dừng")
            self._write_log("▶ Tiếp tục gửi các nhà cung cấp còn lại...", "info")
        else:
            self._pause_event.set()
            self._pause_button.configure(text="▶ Tiếp tục")
            self._telemetry.set(
                f"⏸ ĐANG TẠM DỪNG ({self._sent_count}/{self._total_to_send} mail)"
            )
            self._write_log("⏸ Đã tạm dừng đợt gửi. Bấm 'Tiếp tục' để gửi tiếp.", "info")

    def _on_cancel_send(self) -> None:
        if not self._busy:
            return
        if messagebox.askyesno(
            "Xác nhận hủy gửi",
            "Bạn có chắc chắn muốn HỦY đợt gửi đang chạy không?\n"
            "(Các nhà cung cấp đã gửi xong trước đó vẫn được lưu vào lịch sử).",
        ):
            self._cancel_event.set()
            self._pause_event.clear()
            self._pause_button.configure(state="disabled")
            self._cancel_button.configure(state="disabled")
            self._write_log("⏹ Đang dừng đợt gửi theo yêu cầu người dùng...", "error")

    # ------------------------------------------------------------------ luồng nền

    def _run_in_background(
        self, target: Callable[[], None], is_sending: bool = False
    ) -> None:
        self._set_busy(True, is_sending=is_sending)
        threading.Thread(target=target, daemon=True).start()

    def _test_worker(self, cfg: Config) -> None:
        try:
            test_connection(cfg.settings)
            self._events.put(("log", "✔ Kết nối Gmail thành công.", "ok"))
            self._events.put(("telemetry", "Trạng thái: Kết nối Gmail thành công ✔", None))
        except MailError as exc:
            self._events.put(("log", f"✖ {exc}", "error"))
            self._events.put(("telemetry", "Trạng thái: Lỗi kết nối Gmail ✖", None))
        self._events.put(("finished", None, None))

    def _send_worker(
        self,
        cfg: Config,
        plans: list[MailPlan],
        month: int,
        year: int,
        kind: str,
    ) -> None:
        def on_result(plan: MailPlan, result: SendResult) -> None:
            self._events.put(("result", (plan, result, month, year, kind), None))

        try:
            send_plans(
                cfg.settings,
                plans,
                on_result=on_result,
                pacing_delay=DEFAULT_PACING_SECONDS,
                max_retries=1,
                pause_event=self._pause_event,
                cancel_event=self._cancel_event,
            )
        except MailError as exc:
            self._events.put(("log", f"✖ {exc}", "error"))
        self._events.put(("finished", "send", None))

    def _poll_events(self) -> None:
        """Nhận kết quả từ luồng nền và cập nhật giao diện (chỉ luồng chính được đụng vào Tkinter)."""
        while True:
            try:
                kind, payload, tag = self._events.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self._write_log(payload, tag)
            elif kind == "telemetry":
                self._telemetry.set(payload)
            elif kind == "result":
                self._handle_result(*payload)
            elif kind == "ota_checked":
                self._handle_ota_checked(*payload)
            elif kind == "ota_progress":
                pct, ver = payload
                self._progress.configure(value=pct)
                self._telemetry.set(f"Đang tải bản cập nhật v{ver}: {pct}%...")
            elif kind == "ota_ready_to_swap":
                self._handle_ota_ready_to_swap(*payload)
            elif kind == "finished":
                self._handle_finished(payload)
        self.after(_POLL_MS, self._poll_events)

    def _handle_result(
        self,
        plan: MailPlan,
        result: SendResult,
        month: int,
        year: int,
        kind: str,
    ) -> None:
        self._progress.step(1)
        self._sent_count += 1
        if result.ok:
            self._ok_count += 1
            icon, tag = "✔", "ok"
        else:
            self._fail_count += 1
            icon, tag = "✖", "error"

        pct = int((self._sent_count / max(1, self._total_to_send)) * 100)
        elapsed = max(0.1, time.monotonic() - self._batch_start_time)
        avg_sec = elapsed / self._sent_count
        rate_per_min = (self._sent_count / elapsed) * 60.0
        remaining = max(0, int((self._total_to_send - self._sent_count) * avg_sec))
        self._telemetry.set(
            f"Tiến độ: {self._sent_count}/{self._total_to_send} ({pct}%)  |  "
            f"Tốc độ: {rate_per_min:.1f} mail/phút  |  "
            f"Thành công: {self._ok_count}  |  Lỗi: {self._fail_count}  |  "
            f"ETA: {remaining}s"
        )

        self._write_log(f"{icon} {plan.supplier}: {result.message}", tag)
        if not history.record(plan, result, month, year, kind):
            self._write_log(
                "   (Cảnh báo: Không ghi được lịch sử gửi.)",
                "error",
            )

    def _handle_finished(self, mode: Optional[str]) -> None:
        self._set_busy(False)
        if mode == "send":
            if self._cancel_event.is_set():
                summary = (
                    f"⏹ Đã hủy đợt gửi ({self._sent_count}/{self._total_to_send} mail  |  "
                    f"Thành công: {self._ok_count}  |  Lỗi: {self._fail_count})"
                )
                self._telemetry.set(summary)
                self._write_log(f"=== {summary} ===", "error")
            else:
                summary = (
                    f"✔ Hoàn tất đợt gửi: {self._ok_count}/{self._total_to_send} thành công, "
                    f"{self._fail_count} lỗi"
                )
                self._telemetry.set(summary)
                self._write_log(f"=== {summary} ===", "ok" if self._fail_count == 0 else "error")
