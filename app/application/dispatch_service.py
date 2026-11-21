"""Headless Dispatch ViewModel: Workspace gửi mail, Smart Match, Override, Filter-Safe & Test-to-Self."""

from __future__ import annotations

import mimetypes
from datetime import date
from pathlib import Path
from typing import Any, Optional

from ..adapters.smtp_mailer import generate_message_id
from ..domain.matching import (
    detect_send_kind,
    extract_period_from_text,
    match_files_for_suppliers,
    suggest_period,
)
from ..domain.models import (
    DiscoveredSupplier,
    FileType,
    MailPlan,
    PlanState,
    ScannedFile,
    SendKind,
)
from ..domain.templating import build_html_body, build_logo_data_uri, render, unknown_variables
from ..domain.validation import (
    detect_duplicate_emails_across_suppliers,
    is_valid_email,
    normalize_name,
    redact_secrets,
    validate_gmail_settings,
)
from ..ports.protocols import (
    ConfigRepository,
    FileScanner,
    HistoryRepository,
    MailTransport,
    SecretStore,
)


def _format_size(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "0 KB"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.2f} MB"


class DispatchService:
    """Quản lý trạng thái Workspace Gửi Mail hoàn toàn độc lập với lớp GUI."""

    def __init__(
        self,
        config_repo: ConfigRepository,
        history_repo: HistoryRepository,
        secret_store: SecretStore,
        file_scanner: FileScanner,
        mail_transport: MailTransport,
    ) -> None:
        self._config_repo = config_repo
        self._history_repo = history_repo
        self._secret_store = secret_store
        self._file_scanner = file_scanner
        self._mail_transport = mail_transport

        self._month: int = date.today().month
        self._year: int = date.today().year
        self._kind: SendKind = SendKind.DRAFT
        self._source_paths: list[Path] = []
        self._source_label: str = ""
        self._scanned_files: list[ScannedFile] = []
        self._manual_overrides: dict[tuple[int, FileType], ScannedFile] = {}
        self._plans: list[MailPlan] = []
        self._discovered: list[DiscoveredSupplier] = []
        self._partial_pdf_warning: bool = False
        self._period_reason: str = ""

    @property
    def current_plans(self) -> list[MailPlan]:
        return list(self._plans)

    @property
    def current_period(self) -> tuple[int, int, SendKind]:
        return self._month, self._year, self._kind

    def init_workspace(self, today: Optional[date] = None) -> dict[str, Any]:
        """Khởi tạo Workspace thông minh: tự gợi ý kỳ gửi + quét thư mục mặc định nếu có."""
        cfg = self._config_repo.load_config()
        root_dir = Path(cfg.settings.attach_dir) if cfg.settings.attach_dir else None
        subfolders = (
            self._file_scanner.list_period_subfolders(root_dir)
            if root_dir is not None
            else []
        )
        suggestion = suggest_period([], known_subfolders=subfolders, today=today)
        self._month = suggestion.month
        self._year = suggestion.year
        self._period_reason = suggestion.reason

        if suggestion.source_dir and root_dir is not None:
            candidate_dir = root_dir / suggestion.source_dir
            if candidate_dir.is_dir():
                return self.load_from_paths([candidate_dir], auto_detect=True)

        if cfg.prefs.last_source_dir:
            last_dir = Path(cfg.prefs.last_source_dir)
            if last_dir.is_dir():
                return self.load_from_paths([last_dir], auto_detect=True)

        return self.refresh_workspace()

    def set_period_and_kind(
        self,
        month: int,
        year: int,
        kind_value: str,
    ) -> dict[str, Any]:
        if not (1 <= int(month) <= 12 and 2000 <= int(year) <= 2100):
            return {"ok": False, "message": "Tháng phải từ 1 đến 12 và năm phải hợp lệ."}
        self._month = int(month)
        self._year = int(year)
        self._kind = SendKind.FINAL if kind_value == SendKind.FINAL.value else SendKind.DRAFT
        self._period_reason = ""
        # Nếu đang chưa trỏ thư mục ngoài, thử quét thư mục con YYYY-MM của kỳ mới chọn
        cfg = self._config_repo.load_config()
        if not self._source_paths and cfg.settings.attach_dir:
            period_dir = Path(cfg.settings.attach_dir) / f"{self._year}-{self._month:02d}"
            if period_dir.is_dir():
                self._scanned_files = self._file_scanner.scan_directory(period_dir)
                self._source_label = str(period_dir)
        return self.refresh_workspace()

    def load_from_paths(self, paths: list[Path], auto_detect: bool = True) -> dict[str, Any]:
        """Nạp 1 thư mục hoặc cụm file (từ Drag & Drop / Folder Picker) và tự khớp thông minh."""
        clean_paths = [p for p in paths if p is not None]
        if not clean_paths:
            return {"ok": False, "message": "Chưa chọn thư mục hoặc tệp đính kèm nào."}

        self._source_paths = clean_paths
        self._manual_overrides.clear()
        self._scanned_files = self._file_scanner.scan_paths(clean_paths)

        folder_name = ""
        if len(clean_paths) == 1 and clean_paths[0].is_dir():
            folder_name = clean_paths[0].name
            self._source_label = str(clean_paths[0])
            self._config_repo.save_prefs(last_source_dir=str(clean_paths[0]))
        else:
            parent_dir = clean_paths[0].parent
            folder_name = parent_dir.name
            self._source_label = f"{len(self._scanned_files)} tệp từ {parent_dir.name}"

        if auto_detect and self._scanned_files:
            suggestion = suggest_period(self._scanned_files, folder_name=folder_name)
            self._month = suggestion.month
            self._year = suggestion.year
            self._period_reason = suggestion.reason
            detected_kind, partial_warn = detect_send_kind(self._scanned_files)
            self._kind = detected_kind
            self._partial_pdf_warning = partial_warn
        else:
            _, partial_warn = detect_send_kind(self._scanned_files)
            self._partial_pdf_warning = partial_warn if self._kind == SendKind.FINAL else False

        return self.refresh_workspace()

    def clear_source(self) -> dict[str, Any]:
        self._source_paths = []
        self._source_label = ""
        self._scanned_files = []
        self._manual_overrides.clear()
        self._partial_pdf_warning = False
        return self.refresh_workspace()

    def approve_suggested_match(
        self,
        supplier_id: int,
        file_type_value: str,
        save_alias: bool = False,
    ) -> dict[str, Any]:
        """Người dùng bấm duyệt tường minh một gợi ý Tầng Vàng (`NEEDS_REVIEW`)."""
        ftype = FileType.PDF if file_type_value == FileType.PDF.value else FileType.EXCEL
        plan = next((p for p in self._plans if p.supplier_id == supplier_id), None)
        if plan is None:
            return {"ok": False, "message": "Không tìm thấy nhà cung cấp."}
        att = next((a for a in plan.attachments if a.file_type == ftype), None)
        if att is None or att.file is None:
            return {"ok": False, "message": "Không có file gợi ý để duyệt."}

        self._manual_overrides[(supplier_id, ftype)] = att.file

        if save_alias:
            # Rút tên ngắn từ file để lưu làm bí danh giúp tháng sau tự khớp 100%
            cfg = self._config_repo.load_config()
            sup = next((s for s in cfg.suppliers if s.id == supplier_id), None)
            if sup is not None:
                from ..domain.matching import _extract_vendor_residual

                residual = _extract_vendor_residual(att.file.name)
                if residual and normalize_name(residual) != normalize_name(sup.name):
                    if all(normalize_name(a) != normalize_name(residual) for a in sup.aliases):
                        sup.aliases.append(residual)
                        self._config_repo.upsert_supplier(sup)

        return self.refresh_workspace()

    def override_attachment(
        self,
        supplier_id: int,
        file_type_value: str,
        file_path: Path,
    ) -> dict[str, Any]:
        """Gắn bù / thay thế file đính kèm trực tiếp cho 1 NCC trên dòng bị thiếu hoặc xung đột."""
        ftype = FileType.PDF if file_type_value == FileType.PDF.value else FileType.EXCEL
        scanned = self._file_scanner.inspect_file(file_path)
        if scanned is None:
            return {"ok": False, "message": "Không đọc được tệp đã chọn."}
        if scanned.file_type != ftype:
            expected_lbl = "Excel (.xlsx/.xls)" if ftype == FileType.EXCEL else "PDF (.pdf)"
            return {"ok": False, "message": f"Tệp '{scanned.name}' không đúng định dạng {expected_lbl}."}
        if scanned.size_bytes <= 0:
            return {"ok": False, "message": f"Tệp '{scanned.name}' bị rỗng (0 KB)."}

        self._manual_overrides[(supplier_id, ftype)] = scanned
        # Nếu tệp chọn tay nằm ngoài thư mục nguồn, thêm vào danh sách file đã biết để kiểm tra trùng 1-1
        if all(f.path != scanned.path for f in self._scanned_files):
            self._scanned_files.append(scanned)
        return self.refresh_workspace()

    def refresh_workspace(self) -> dict[str, Any]:
        """Dựng lại toàn bộ `MailPlan` theo cấu hình mới nhất + file đã quét + lịch sử SQLite."""
        cfg = self._config_repo.load_config()
        has_pw = self._secret_store.has_password(cfg.settings.sender)
        gmail_problems = validate_gmail_settings(cfg.settings, has_pw)
        dup_emails = detect_duplicate_emails_across_suppliers(cfg.suppliers)
        already_sent_norms = self._history_repo.sent_supplier_norms(
            self._month, self._year, self._kind.value
        )
        failed_norms = self._history_repo.failed_supplier_norms(
            self._month, self._year, self._kind.value
        )

        # Kiểm tra logo cấu hình rõ ràng & tính dung lượng cộng dồn vào giới hạn 18 MB
        logo_path: Optional[Path] = None
        logo_size = 0
        if cfg.settings.logo_path:
            lp = Path(cfg.settings.logo_path)
            if lp.is_file():
                logo_path = lp
                try:
                    logo_size = lp.stat().st_size
                except OSError:
                    logo_size = 0

        # Kiểm tra lỗi biến mẫu toàn cục
        bad_vars = sorted(
            {
                v
                for tpl in (
                    cfg.templates.subject,
                    cfg.templates.body,
                    cfg.templates.excel_name,
                    cfg.templates.pdf_name,
                )
                for v in unknown_variables(tpl)
            }
        )
        shared_errors = [f"Biến mẫu không hợp lệ: {{{v}}}" for v in bad_vars]

        # Ánh xạ manual_overrides theo supplier_id -> chỉ số index trong cfg.suppliers
        id_to_idx = {s.id: idx for idx, s in enumerate(cfg.suppliers) if s.id is not None}
        idx_overrides: dict[tuple[int, FileType], ScannedFile] = {}
        for (sup_id, ftype), sfile in self._manual_overrides.items():
            if sup_id in id_to_idx:
                idx_overrides[(id_to_idx[sup_id], ftype)] = sfile

        matches_by_idx, discovered = match_files_for_suppliers(
            suppliers=cfg.suppliers,
            scanned_files=self._scanned_files,
            month=self._month,
            year=self._year,
            kind=self._kind,
            excel_template=cfg.templates.excel_name,
            pdf_template=cfg.templates.pdf_name,
            manual_overrides=idx_overrides,
            logo_size_bytes=logo_size,
        )
        self._discovered = discovered

        plans: list[MailPlan] = []
        for idx, sup in enumerate(cfg.suppliers):
            values = {
                "thang": f"{self._month:02d}",
                "nam": str(self._year),
                "nha_cung_cap": sup.name,
                "loai": self._kind.value,
            }
            errors = list(shared_errors)
            warnings: list[str] = []

            if not sup.recipients:
                errors.append("Chưa nhập email người nhận.")
            else:
                for addr in sup.recipients:
                    if not is_valid_email(addr):
                        errors.append(f"Email người nhận không hợp lệ: {addr}")
                    elif addr.lower() in dup_emails:
                        others = [n for n in dup_emails[addr.lower()] if n != sup.name]
                        warnings.append(
                            f"Email '{addr}' đang trùng với NCC khác ({', '.join(others)}) — "
                            "hãy kiểm tra kỹ để tránh gửi nhầm bảng phí!"
                        )

            sup_matches = matches_by_idx.get(idx, [])
            for att in sup_matches:
                if att.is_blocked and att.note:
                    errors.append(att.note)
                elif att.needs_review and att.note:
                    warnings.append(att.note)
                elif att.file is not None:
                    fp = extract_period_from_text(att.file.name)
                    if fp is not None and fp != (self._month, self._year):
                        warnings.append(
                            f"Lưu ý: file '{att.file.name}' có ký hiệu kỳ {fp[0]:02d}/{fp[1]} "
                            f"khác kỳ đang gửi {self._month:02d}/{self._year}."
                        )

            plan = MailPlan(
                supplier_id=sup.id,
                supplier=sup.name,
                enabled=sup.enabled,
                recipients=list(sup.recipients),
                cc=list(cfg.settings.cc),
                subject=render(cfg.templates.subject, values),
                body=render(cfg.templates.body, values),
                attachments=sup_matches,
                errors=errors,
                warnings=warnings,
                already_sent=normalize_name(sup.name) in already_sent_norms,
                logo_path=logo_path,
                logo_size_bytes=logo_size,
            )
            plans.append(plan)

        self._plans = plans
        return self._serialize_workspace(
            gmail_problems=gmail_problems,
            dup_emails=dup_emails,
            failed_norms=failed_norms,
            sender=cfg.settings.sender,
            display_name=cfg.settings.display_name,
            logo_path=logo_path,
        )

    def _serialize_workspace(
        self,
        *,
        gmail_problems: list[str],
        dup_emails: dict[str, list[str]],
        failed_norms: set[str],
        sender: str,
        display_name: str,
        logo_path: Optional[Path],
    ) -> dict[str, Any]:
        logo_uri = ""
        if logo_path is not None and logo_path.is_file():
            try:
                mime = mimetypes.guess_type(logo_path.name)[0] or "image/png"
                logo_uri = build_logo_data_uri(logo_path.read_bytes(), mime_type=mime)
            except OSError:
                logo_uri = ""

        ready_new = sum(1 for p in self._plans if p.state == PlanState.READY and not p.already_sent)
        sent_cnt = sum(1 for p in self._plans if p.already_sent and p.enabled)
        review_cnt = sum(1 for p in self._plans if p.state == PlanState.REVIEW)
        error_cnt = sum(1 for p in self._plans if p.state == PlanState.ERROR)
        off_cnt = sum(1 for p in self._plans if p.state == PlanState.OFF)

        plan_dtos: list[dict[str, Any]] = []
        for p in self._plans:
            html_preview = build_html_body(p.body, logo_src=logo_uri or None, for_preview=True)
            plan_dtos.append(
                {
                    "supplier_id": p.supplier_id,
                    "supplier": p.supplier,
                    "enabled": p.enabled,
                    "state": p.state.value,
                    "sendable": p.sendable,
                    "already_sent": p.already_sent,
                    "last_failed": normalize_name(p.supplier) in failed_norms,
                    "default_checked": p.sendable and not p.already_sent,
                    "recipients": p.recipients,
                    "cc": p.cc,
                    "from_display": f"{display_name} <{sender}>".strip() if sender else "(Chưa cài Gmail)",
                    "subject": p.subject,
                    "body_text": p.body,
                    "body_html": html_preview,
                    "total_bytes": p.total_bytes,
                    "total_size_label": _format_size(p.total_bytes),
                    "errors": p.errors,
                    "warnings": p.warnings,
                    "attachments": [
                        {
                            "file_type": att.file_type.value,
                            "expected_name": att.expected_name,
                            "status": att.status.value,
                            "is_ready": att.is_ready,
                            "needs_review": att.needs_review,
                            "is_blocked": att.is_blocked,
                            "file_name": att.file.name if att.file else "",
                            "file_path": str(att.file.path) if att.file else "",
                            "size_bytes": att.file.size_bytes if att.file else 0,
                            "size_label": _format_size(att.file.size_bytes) if att.file else "",
                            "note": att.note,
                            "score": round(att.score * 100),
                            "candidates": [
                                {
                                    "name": c.name,
                                    "path": str(c.path),
                                    "size_label": _format_size(c.size_bytes),
                                }
                                for c in att.candidates
                            ],
                        }
                        for att in p.attachments
                    ],
                }
            )

        return {
            "ok": True,
            "period": {
                "month": self._month,
                "year": self._year,
                "kind": self._kind.value,
                "reason": self._period_reason,
            },
            "source": {
                "label": self._source_label,
                "scanned_count": len(self._scanned_files),
                "partial_pdf_warning": self._partial_pdf_warning,
            },
            "gmail_ready": len(gmail_problems) == 0,
            "gmail_problems": gmail_problems,
            "duplicate_emails": dup_emails,
            "summary": {
                "total": len(self._plans),
                "ready_new": ready_new,
                "sent": sent_cnt,
                "review": review_cnt,
                "error": error_cnt,
                "off": off_cnt,
                "failed_in_period": len(failed_norms),
            },
            "plans": plan_dtos,
            "discovered": [
                {
                    "suggested_name": d.suggested_name,
                    "files": [f.name for f in d.files],
                }
                for d in self._discovered
            ],
        }

    # ------------------------------------------------------------------ Filter-Safe Selection

    def resolve_selected_plans(
        self,
        selected_supplier_ids: list[int],
        visible_supplier_ids: Optional[list[int]] = None,
        only_visible: bool = False,
    ) -> dict[str, Any]:
        """Kiểm tra an toàn trước khi gửi — chống bẫy 'bộ lọc ẩn NCC vẫn gửi nhầm'."""
        selected_set = set(selected_supplier_ids)
        visible_set = set(visible_supplier_ids) if visible_supplier_ids is not None else None

        all_sendable = [
            p for p in self._plans if p.supplier_id in selected_set and p.sendable
        ]
        hidden_checked = (
            [p for p in all_sendable if p.supplier_id not in visible_set]
            if visible_set is not None
            else []
        )
        final_plans = (
            [p for p in all_sendable if p.supplier_id in visible_set]
            if (only_visible and visible_set is not None)
            else all_sendable
        )
        return {
            "plans": final_plans,
            "total_selected": len(all_sendable),
            "hidden_count": len(hidden_checked),
            "hidden_suppliers": [p.supplier for p in hidden_checked],
            "needs_filter_confirm": len(hidden_checked) > 0 and not only_visible,
        }

    def get_failed_plans_for_retry(self) -> list[MailPlan]:
        """Lấy danh sách `MailPlan` của các NCC đang lỗi trong kỳ hiện tại (và đủ điều kiện gửi)."""
        failed_norms = self._history_repo.failed_supplier_norms(
            self._month, self._year, self._kind.value
        )
        return [
            p
            for p in self._plans
            if p.sendable and normalize_name(p.supplier) in failed_norms
        ]

    # ------------------------------------------------------------------ Gửi thử an toàn (Test-to-Self)

    def send_test_to_self(
        self,
        supplier_id: Optional[int] = None,
        override_test_email: str = "",
    ) -> dict[str, Any]:
        """Gửi 1 email thử về chính hộp thư người gửi: ép `cc=[]`, tiền tố `[GỬI THỬ]`, KHÔNG ghi lịch sử."""
        cfg = self._config_repo.load_config()
        pw = self._secret_store.load_password(cfg.settings.sender)
        problems = validate_gmail_settings(cfg.settings, bool(pw))
        if problems:
            return {"ok": False, "message": problems[0]}

        target_email = (override_test_email or "").strip() or cfg.settings.sender
        if not is_valid_email(target_email):
            return {"ok": False, "message": f"Email nhận thư thử không hợp lệ: {target_email}"}

        source_plan = (
            next((p for p in self._plans if p.supplier_id == supplier_id), None)
            if supplier_id is not None
            else (self._plans[0] if self._plans else None)
        )

        logo_path = Path(cfg.settings.logo_path) if cfg.settings.logo_path else None
        if logo_path is not None and not logo_path.is_file():
            logo_path = None

        if source_plan is not None:
            ready_atts = [att for att in source_plan.attachments if att.is_ready and att.file is not None]
            test_plan = MailPlan(
                supplier_id=source_plan.supplier_id,
                supplier=source_plan.supplier,
                enabled=True,
                recipients=[target_email],
                cc=[],  # TUYỆT ĐỐI XÓA CC để không bao giờ bắn nhầm cho sếp/đối tác
                subject=f"[GỬI THỬ] {source_plan.subject}",
                body=source_plan.body,
                attachments=ready_atts,
                logo_path=logo_path,
            )
        else:
            values = {
                "thang": f"{self._month:02d}",
                "nam": str(self._year),
                "nha_cung_cap": "ACE",
                "loai": self._kind.value,
            }
            test_plan = MailPlan(
                supplier_id=None,
                supplier="Mẫu thử nghiệm",
                enabled=True,
                recipients=[target_email],
                cc=[],
                subject=f"[GỬI THỬ] {render(cfg.templates.subject, values)}",
                body=render(cfg.templates.body, values),
                attachments=[],
                logo_path=logo_path,
            )

        msg_id = generate_message_id(cfg.settings.sender)
        try:
            with self._mail_transport.open_session(cfg.settings, pw) as session:
                res = session.send(test_plan, message_id=msg_id)
        except Exception as exc:
            return {"ok": False, "message": redact_secrets(str(exc), (pw,))}

        if not res.ok:
            return {"ok": False, "message": redact_secrets(res.message, (pw,))}
        return {
            "ok": True,
            "message": f"Đã gửi email thử nghiệm tới {target_email} (không ghi vào lịch sử gửi thật).",
        }
