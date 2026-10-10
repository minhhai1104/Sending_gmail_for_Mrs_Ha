"""Cửa sổ xem trước: kiểm tra từng nhà cung cấp rồi xác nhận gửi."""
import tkinter as tk
from tkinter import ttk

from .config import Settings
from .planner import STATE_ERROR, STATE_OFF, STATE_READY, MailPlan

_STATE_LABEL = {STATE_READY: "✔ Sẵn sàng", STATE_ERROR: "✖ Lỗi", STATE_OFF: "⏸ Không gửi"}
_STATE_COLOR = {STATE_READY: "#1B7F3B", STATE_ERROR: "#C00000", STATE_OFF: "#808080"}
_SENT_LABEL = "↺ Đã gửi rồi"
_SENT_COLOR = "#1F4E78"


class PreviewDialog(tk.Toplevel):
    """Hiển thị bản xem trước. Sau khi đóng: `confirmed` cho biết có xác nhận gửi không,
    `to_send` là danh sách mail sẽ gửi."""

    def __init__(self, parent, settings: Settings, plans: list[MailPlan],
                 period: str, already_sent: set[str]):
        super().__init__(parent)
        self.title("Xem trước trước khi gửi")
        self.geometry("1000x620")
        self.minsize(820, 520)
        self.transient(parent)

        self.confirmed = False
        self.to_send: list[MailPlan] = []
        self._settings = settings
        self._plans = plans
        self._already_sent = {p.supplier for p in plans if p.sendable} & already_sent
        self._skip_sent = tk.BooleanVar(value=True)
        self._problems = settings.problems()

        self._build(period)
        self._refresh_send_button()
        self.grab_set()

    # ------------------------------------------------------------------ giao diện

    def _build(self, period: str) -> None:
        header = ttk.Frame(self, padding=(12, 10, 12, 0))
        header.pack(fill="x")
        ttk.Label(header, text=f"Gửi mail {period}", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ttk.Label(header, text=f"Gửi từ: {self._settings.sender or '(chưa điền)'}").pack(anchor="w")
        for problem in self._problems:
            ttk.Label(header, text="✖ " + problem, foreground="#C00000").pack(anchor="w")

        body = ttk.PanedWindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.add(self._build_list(body), weight=1)
        body.add(self._build_detail(body), weight=2)

        footer = ttk.Frame(self, padding=(12, 0, 12, 12))
        footer.pack(fill="x")
        if self._already_sent:
            ttk.Checkbutton(
                footer, variable=self._skip_sent, command=self._refresh_send_button,
                text=f"Bỏ qua {len(self._already_sent)} nhà cung cấp đã gửi thành công trong kỳ này",
            ).pack(side="left")
        self._send_button = tk.Button(footer, bg="#1B7F3B", fg="white", font=("Segoe UI", 10, "bold"),
                                      padx=14, pady=4, command=self._confirm)
        self._send_button.pack(side="right")
        ttk.Button(footer, text="Hủy", command=self.destroy).pack(side="right", padx=8)

    def _build_list(self, parent) -> ttk.Frame:
        frame = ttk.Frame(parent)
        self._tree = ttk.Treeview(frame, columns=("status", "supplier"), show="headings", selectmode="browse")
        self._tree.heading("status", text="Trạng thái")
        self._tree.heading("supplier", text="Nhà cung cấp")
        self._tree.column("status", width=120, stretch=False)
        self._tree.column("supplier", width=160)
        for state, color in _STATE_COLOR.items():
            self._tree.tag_configure(state, foreground=color)
        self._tree.tag_configure("sent", foreground=_SENT_COLOR)
        for index, plan in enumerate(self._plans):
            sent = plan.supplier in self._already_sent
            self._tree.insert("", "end", iid=str(index), tags=("sent" if sent else plan.state,),
                              values=(_SENT_LABEL if sent else _STATE_LABEL[plan.state], plan.supplier))
        self._tree.pack(fill="both", expand=True)
        self._tree.bind("<<TreeviewSelect>>", self._show_selected)
        return frame

    def _build_detail(self, parent) -> ttk.Frame:
        frame = ttk.Frame(parent)
        self._detail = tk.Text(frame, wrap="word", font=("Segoe UI", 10), padx=10, pady=8)
        scroll = ttk.Scrollbar(frame, command=self._detail.yview)
        self._detail.configure(yscrollcommand=scroll.set, state="disabled")
        self._detail.tag_configure("label", font=("Segoe UI", 10, "bold"))
        self._detail.tag_configure("error", foreground="#C00000")
        self._detail.tag_configure("ok", foreground="#1B7F3B")
        scroll.pack(side="right", fill="y")
        self._detail.pack(side="left", fill="both", expand=True)
        if self._plans:
            self._tree.selection_set("0")
        return frame

    # ------------------------------------------------------------------ xử lý

    def _show_selected(self, _event=None) -> None:
        selection = self._tree.selection()
        if selection:
            self._render_detail(self._plans[int(selection[0])])

    def _render_detail(self, plan: MailPlan) -> None:
        sender = f"{self._settings.display_name} <{self._settings.sender}>".strip()
        text = self._detail
        text.configure(state="normal")
        text.delete("1.0", "end")

        def line(label: str, value: str) -> None:
            text.insert("end", f"{label}: ", "label")
            text.insert("end", value + "\n")

        for error in plan.errors:
            text.insert("end", f"✖ {error}\n", "error")
        if not plan.enabled:
            text.insert("end", "⏸ Nhà cung cấp này đang để 'Gửi? = Không' nên sẽ bị bỏ qua.\n", "error")
        if plan.errors or not plan.enabled:
            text.insert("end", "\n")
        line("Từ", sender)
        line("Đến", "; ".join(plan.recipients) or "(trống)")
        if plan.cc:
            line("CC", "; ".join(plan.cc))
        line("Tiêu đề", plan.subject)
        text.insert("end", "Đính kèm:\n", "label")
        for attachment in plan.attachments:
            mark, tag = ("✔", "ok") if attachment.exists else ("✖", "error")
            text.insert("end", f"   {mark} {attachment.name}\n", tag)
        text.insert("end", "\n" + "─" * 60 + "\n\n" + plan.body)
        text.configure(state="disabled")

    def _selected_to_send(self) -> list[MailPlan]:
        skip = self._skip_sent.get() and bool(self._already_sent)
        return [p for p in self._plans
                if p.sendable and not (skip and p.supplier in self._already_sent)]

    def _refresh_send_button(self) -> None:
        count = len(self._selected_to_send())
        blocked = bool(self._problems) or count == 0
        self._send_button.configure(
            text=f"Xác nhận & Gửi ({count} mail)",
            state="disabled" if blocked else "normal",
            bg="#9E9E9E" if blocked else "#1B7F3B")

    def _confirm(self) -> None:
        self.to_send = self._selected_to_send()
        self.confirmed = True
        self.destroy()
