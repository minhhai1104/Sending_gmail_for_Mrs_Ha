"""Cửa sổ xem trước v2.0: kiểm tra, tìm kiếm nhanh, chọn lọc từng nhà cung cấp rồi xác nhận gửi."""
import tkinter as tk
from tkinter import ttk
from typing import Any, Optional

from .config import Settings
from .planner import STATE_ERROR, STATE_OFF, STATE_READY, MailPlan

_STATE_LABEL = {
    STATE_READY: "✔ Sẵn sàng",
    STATE_ERROR: "✖ Lỗi",
    STATE_OFF: "⏸ Không gửi",
}
_STATE_COLOR = {
    STATE_READY: "#107C41",
    STATE_ERROR: "#D83B01",
    STATE_OFF: "#605E5C",
}
_SENT_LABEL = "↺ Đã gửi rồi"
_SENT_COLOR = "#0078D4"


def _format_size(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "0 KB"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.2f} MB"


class PreviewDialog(tk.Toplevel):
    """Hiển thị bản xem trước. Sau khi đóng: `confirmed` cho biết có xác nhận gửi không,
    `to_send` là danh sách mail sẽ gửi."""

    def __init__(
        self,
        parent: tk.Tk,
        settings: Settings,
        plans: list[MailPlan],
        period: str,
        already_sent: set[str],
    ) -> None:
        super().__init__(parent)
        self.title("Xem trước & Kiểm duyệt trước khi gửi (v2.0)")
        self.geometry("1060x670")
        self.minsize(860, 560)
        self.transient(parent)

        self.confirmed = False
        self.to_send: list[MailPlan] = []
        self._settings = settings
        self._plans = plans
        self._already_sent = {p.supplier for p in plans if p.sendable} & already_sent
        self._skip_sent = tk.BooleanVar(value=True)
        self._filter_var = tk.StringVar(value="")
        self._problems = settings.problems()

        # Tập hợp chỉ số (index) các kế hoạch được tick chọn gửi
        self._checked_indices: set[int] = {
            idx
            for idx, p in enumerate(plans)
            if p.sendable and p.supplier not in self._already_sent
        }

        self._build(period)
        self._refresh_tree_checks()
        self._refresh_send_button()
        self._filter_var.trace_add("write", lambda *_: self._refresh_tree_checks())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.grab_set()

    # ------------------------------------------------------------------ giao diện

    def _build_summary_text(self) -> str:
        total = len(self._plans)
        ready = sum(1 for p in self._plans if p.state == STATE_READY and p.supplier not in self._already_sent)
        sent = len(self._already_sent)
        errors = sum(1 for p in self._plans if p.state == STATE_ERROR)
        off = sum(1 for p in self._plans if p.state == STATE_OFF)
        return (
            f"Tổng: {total} NCC   |   ✔ Sẵn sàng mới: {ready}   |   "
            f"↺ Đã gửi trong kỳ: {sent}   |   ✖ Lỗi thiếu file/mail: {errors}   |   "
            f"⏸ Tạm tắt: {off}"
        )

    def _build(self, period: str) -> None:
        header = ttk.Frame(self, padding=(14, 12, 14, 4))
        header.pack(fill="x")
        ttk.Label(
            header,
            text=f"Kiểm duyệt đợt gửi mail {period}",
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            header,
            text=self._build_summary_text(),
            font=("Segoe UI", 9, "bold"),
            foreground="#0078D4",
        ).pack(anchor="w", pady=(2, 0))
        ttk.Label(
            header,
            text=f"Tài khoản gửi: {self._settings.sender or '(chưa điền)'}  |  "
            "Định dạng: HTML Doanh nghiệp + Plaintext  |  "
            "Mẹo: Nhấp đúp dòng NCC để Chọn (☑) hoặc Bỏ chọn (☐).",
        ).pack(anchor="w", pady=(2, 0))
        for problem in self._problems:
            ttk.Label(header, text="✖ " + problem, foreground="#D83B01").pack(
                anchor="w", pady=(2, 0)
            )

        body = ttk.PanedWindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=14, pady=10)
        body.add(self._build_list(body), weight=1)
        body.add(self._build_detail(body), weight=2)

        footer = ttk.Frame(self, padding=(14, 0, 14, 14))
        footer.pack(fill="x")

        ttk.Button(
            footer, text="Chọn tất cả hợp lệ", command=self._select_all_valid
        ).pack(side="left", padx=(0, 6))
        ttk.Button(footer, text="Bỏ chọn tất cả", command=self._deselect_all).pack(
            side="left", padx=(0, 12)
        )

        if self._already_sent:
            ttk.Checkbutton(
                footer,
                variable=self._skip_sent,
                command=self._on_toggle_skip_sent,
                text=f"Bỏ qua {len(self._already_sent)} nhà cung cấp đã gửi thành công trong kỳ này",
            ).pack(side="left")

        self._send_button = tk.Button(
            footer,
            bg="#107C41",
            fg="white",
            activebackground="#0E6B37",
            activeforeground="white",
            font=("Segoe UI", 10, "bold"),
            padx=16,
            pady=5,
            relief="flat",
            command=self._confirm,
        )
        self._send_button.pack(side="right")
        ttk.Button(footer, text="Hủy (Esc)", command=self.destroy).pack(
            side="right", padx=8
        )

    def _build_list(self, parent: tk.Misc) -> ttk.Frame:
        frame = ttk.Frame(parent)

        search_bar = ttk.Frame(frame)
        search_bar.pack(fill="x", pady=(0, 6))
        ttk.Label(search_bar, text="🔍 Lọc NCC:").pack(side="left")
        search_entry = ttk.Entry(search_bar, textvariable=self._filter_var)
        search_entry.pack(side="left", fill="x", expand=True, padx=(6, 0))

        tree_container = ttk.Frame(frame)
        tree_container.pack(fill="both", expand=True)

        self._tree = ttk.Treeview(
            tree_container,
            columns=("pick", "status", "supplier"),
            show="headings",
            selectmode="browse",
        )
        self._tree.heading("pick", text="Gửi")
        self._tree.heading("status", text="Trạng thái")
        self._tree.heading("supplier", text="Nhà cung cấp")
        self._tree.column("pick", width=44, anchor="center", stretch=False)
        self._tree.column("status", width=120, stretch=False)
        self._tree.column("supplier", width=165)

        for state, color in _STATE_COLOR.items():
            self._tree.tag_configure(state, foreground=color)
        self._tree.tag_configure("sent", foreground=_SENT_COLOR)

        scroll = ttk.Scrollbar(
            tree_container, orient="vertical", command=self._tree.yview
        )
        self._tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self._tree.pack(side="left", fill="both", expand=True)
        self._tree.bind("<<TreeviewSelect>>", self._show_selected)
        self._tree.bind("<Double-1>", self._on_double_click_row)
        self._tree.bind("<space>", self._on_double_click_row)
        return frame

    def _build_detail(self, parent: tk.Misc) -> ttk.Frame:
        frame = ttk.Frame(parent)
        self._detail = tk.Text(
            frame, wrap="word", font=("Segoe UI", 10), padx=12, pady=10
        )
        scroll = ttk.Scrollbar(frame, command=self._detail.yview)
        self._detail.configure(yscrollcommand=scroll.set, state="disabled")
        self._detail.tag_configure("label", font=("Segoe UI", 10, "bold"))
        self._detail.tag_configure("error", foreground="#D83B01")
        self._detail.tag_configure("ok", foreground="#107C41")
        scroll.pack(side="right", fill="y")
        self._detail.pack(side="left", fill="both", expand=True)
        return frame

    # ------------------------------------------------------------------ xử lý chọn

    def _refresh_tree_checks(self) -> None:
        keyword = self._filter_var.get().strip().lower()
        current_sel = self._tree.selection()
        selected_iid = current_sel[0] if current_sel else None

        self._tree.delete(*self._tree.get_children())
        first_iid: Optional[str] = None

        for index, plan in enumerate(self._plans):
            if keyword and keyword not in plan.supplier.lower():
                continue
            iid = str(index)
            if first_iid is None:
                first_iid = iid
            sent = plan.supplier in self._already_sent
            mark = (
                "☑"
                if index in self._checked_indices
                else ("☐" if plan.sendable else "—")
            )
            self._tree.insert(
                "",
                "end",
                iid=iid,
                tags=("sent" if sent else plan.state,),
                values=(
                    mark,
                    _SENT_LABEL if sent else _STATE_LABEL[plan.state],
                    plan.supplier,
                ),
            )

        target_iid = (
            selected_iid
            if selected_iid and self._tree.exists(selected_iid)
            else first_iid
        )
        if target_iid is not None:
            self._tree.selection_set(target_iid)

    def _on_double_click_row(self, _event: Optional[Any] = None) -> None:
        selection = self._tree.selection()
        if not selection:
            return
        idx = int(selection[0])
        plan = self._plans[idx]
        if not plan.sendable:
            return
        if idx in self._checked_indices:
            self._checked_indices.remove(idx)
        else:
            self._checked_indices.add(idx)
        self._refresh_tree_checks()
        self._refresh_send_button()

    def _on_toggle_skip_sent(self) -> None:
        skip = self._skip_sent.get()
        for idx, plan in enumerate(self._plans):
            if plan.sendable and plan.supplier in self._already_sent:
                if skip:
                    self._checked_indices.discard(idx)
                else:
                    self._checked_indices.add(idx)
        self._refresh_tree_checks()
        self._refresh_send_button()

    def _select_all_valid(self) -> None:
        skip = self._skip_sent.get()
        self._checked_indices = {
            idx
            for idx, p in enumerate(self._plans)
            if p.sendable and not (skip and p.supplier in self._already_sent)
        }
        self._refresh_tree_checks()
        self._refresh_send_button()

    def _deselect_all(self) -> None:
        self._checked_indices.clear()
        self._refresh_tree_checks()
        self._refresh_send_button()

    def _show_selected(self, _event: Optional[Any] = None) -> None:
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
            text.insert(
                "end",
                "⏸ Nhà cung cấp này đang để 'Gửi? = Không' nên sẽ bị bỏ qua.\n",
                "error",
            )
        if plan.errors or not plan.enabled:
            text.insert("end", "\n")
        line("Từ", sender)
        line("Đến", "; ".join(plan.recipients) or "(trống)")
        if plan.cc:
            line("CC", "; ".join(plan.cc))
        line("Tiêu đề", plan.subject)
        text.insert("end", "Đính kèm:\n", "label")
        for attachment in plan.attachments:
            mark, tag = (
                ("✔", "ok")
                if attachment.exists and attachment.size_bytes > 0
                else ("✖", "error")
            )
            size_info = (
                f" ({_format_size(attachment.size_bytes)})"
                if attachment.exists
                else ""
            )
            text.insert("end", f"   {mark} {attachment.name}{size_info}\n", tag)
        text.insert("end", "\n" + "─" * 60 + "\n\n" + plan.body)
        text.configure(state="disabled")

    def _selected_to_send(self) -> list[MailPlan]:
        return [
            plan
            for idx, plan in enumerate(self._plans)
            if idx in self._checked_indices and plan.sendable
        ]

    def _refresh_send_button(self) -> None:
        count = len(self._selected_to_send())
        blocked = bool(self._problems) or count == 0
        self._send_button.configure(
            text=f"Xác nhận & Gửi ({count} mail)",
            state="disabled" if blocked else "normal",
            bg="#9E9E9E" if blocked else "#107C41",
        )

    def _confirm(self) -> None:
        self.to_send = self._selected_to_send()
        self.confirmed = True
        self.destroy()
