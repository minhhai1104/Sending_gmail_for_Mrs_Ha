"""Headless Application Service: Onboarding, Settings (Write-Only), Suppliers, Templates & History."""

from __future__ import annotations

import mimetypes
import shutil
from datetime import date
from pathlib import Path
from typing import Any, Optional

from ..adapters.paths import get_exports_dir, get_logos_dir
from ..adapters.smtp_mailer import MailTransportError
from ..domain.models import (
    DEFAULT_BODY,
    DEFAULT_EXCEL_TEMPLATE,
    DEFAULT_PDF_TEMPLATE,
    DEFAULT_SUBJECT,
    AppConfig,
    GmailSettings,
    HistoryRecord,
    PeriodStats,
    SendKind,
    Supplier,
)
from ..domain.templating import (
    VARIABLE_CHIPS,
    build_html_body,
    build_logo_data_uri,
    render,
    suggest_variable_fix,
    unknown_variables,
)
from ..domain.validation import (
    GOOGLE_2FA_URL,
    GOOGLE_APP_PASSWORD_URL,
    detect_duplicate_emails_across_suppliers,
    diagnose_app_password,
    is_valid_email,
    normalize_name,
    redact_secrets,
    split_emails,
    validate_gmail_settings,
    validate_supplier,
)
from ..ports.protocols import ConfigRepository, HistoryRepository, MailTransport, SecretStore

_ALLOWED_LOGO_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_MAX_LOGO_BYTES = 2 * 1024 * 1024  # 2 MB


class AppService:
    """Điều phối toàn bộ cấu hình In-App (không bao giờ trả mật khẩu/token ra lớp UI)."""

    def __init__(
        self,
        config_repo: ConfigRepository,
        history_repo: HistoryRepository,
        secret_store: SecretStore,
        mail_transport: MailTransport,
        logos_dir: Optional[Path] = None,
        exports_dir: Optional[Path] = None,
    ) -> None:
        self._config_repo = config_repo
        self._history_repo = history_repo
        self._secret_store = secret_store
        self._mail_transport = mail_transport
        self._logos_dir = logos_dir
        self._exports_dir = exports_dir

    def _get_logos_dir(self) -> Path:
        target = self._logos_dir if self._logos_dir is not None else get_logos_dir()
        target.mkdir(parents=True, exist_ok=True)
        return target

    def _get_exports_dir(self) -> Path:
        target = self._exports_dir if self._exports_dir is not None else get_exports_dir()
        target.mkdir(parents=True, exist_ok=True)
        return target

    # ------------------------------------------------------------------ Trạng thái tổng quan

    def load_config(self) -> AppConfig:
        return self._config_repo.load_config()

    def get_bootstrap_state(self) -> dict[str, Any]:
        """Trả về dữ liệu khởi tạo an toàn cho UI (Write-Only: tuyệt đối không trả mật khẩu)."""
        cfg = self._config_repo.load_config()
        has_pw = self._secret_store.has_password(cfg.settings.sender)
        has_gh = self._secret_store.has_github_token()
        gmail_problems = validate_gmail_settings(cfg.settings, has_pw)
        dup_emails = detect_duplicate_emails_across_suppliers(cfg.suppliers)
        logo_uri = self.get_logo_data_uri(cfg.settings.logo_path)

        return {
            "needs_onboarding": not cfg.prefs.onboarding_completed or not has_pw or not is_valid_email(cfg.settings.sender),
            "settings": {
                "sender": cfg.settings.sender,
                "display_name": cfg.settings.display_name,
                "attach_dir": cfg.settings.attach_dir,
                "cc": cfg.settings.cc,
                "logo_path": cfg.settings.logo_path,
                "logo_data_uri": logo_uri,
                "pacing_seconds": cfg.settings.pacing_seconds,
                "max_retries": cfg.settings.max_retries,
                "has_app_password": has_pw,
                "has_github_token": has_gh,
                "gmail_ready": len(gmail_problems) == 0,
                "gmail_problems": gmail_problems,
            },
            "templates": {
                "subject": cfg.templates.subject,
                "body": cfg.templates.body,
                "excel_name": cfg.templates.excel_name,
                "pdf_name": cfg.templates.pdf_name,
                "variable_chips": list(VARIABLE_CHIPS),
            },
            "prefs": {
                "theme": cfg.prefs.theme,
                "onboarding_completed": cfg.prefs.onboarding_completed,
                "last_source_dir": cfg.prefs.last_source_dir,
            },
            "suppliers": [self._serialize_supplier(s) for s in cfg.suppliers],
            "duplicate_emails": dup_emails,
            "links": {
                "google_2fa": GOOGLE_2FA_URL,
                "google_app_password": GOOGLE_APP_PASSWORD_URL,
            },
        }

    @staticmethod
    def _serialize_supplier(s: Supplier) -> dict[str, Any]:
        return {
            "id": s.id,
            "name": s.name,
            "recipients": s.recipients,
            "aliases": s.aliases,
            "note": s.note,
            "enabled": s.enabled,
            "sort_order": s.sort_order,
        }

    # ------------------------------------------------------------------ Cài đặt & Bảo mật (Write-Only)

    def test_and_save_gmail(
        self,
        sender: str,
        display_name: str,
        raw_app_password: str = "",
        verify_connection: bool = True,
    ) -> dict[str, Any]:
        """Kiểm tra & lưu tài khoản Gmail (hỗ trợ giữ nguyên mật khẩu cũ nếu để trống ô mật khẩu)."""
        clean_sender = (sender or "").strip()
        clean_name = (display_name or "").strip()
        if not is_valid_email(clean_sender):
            return {"ok": False, "message": "Địa chỉ Gmail không đúng định dạng (ví dụ: ten@gmail.com)."}

        cfg = self._config_repo.load_config()
        raw_pw = (raw_app_password or "").strip()
        if raw_pw:
            valid, clean_pw, diag = diagnose_app_password(raw_pw)
            if not valid:
                return {"ok": False, "message": diag}
        else:
            clean_pw = self._secret_store.load_password(clean_sender)
            if not clean_pw:
                return {
                    "ok": False,
                    "message": "Chưa có Mật khẩu ứng dụng cho Gmail này. Vui lòng nhập 16 ký tự từ Google.",
                }

        candidate_settings = GmailSettings(
            sender=clean_sender,
            display_name=clean_name or cfg.settings.display_name,
            attach_dir=cfg.settings.attach_dir,
            cc=cfg.settings.cc,
            logo_path=cfg.settings.logo_path,
            pacing_seconds=cfg.settings.pacing_seconds,
            max_retries=cfg.settings.max_retries,
        )

        if verify_connection:
            try:
                self._mail_transport.test_connection(candidate_settings, clean_pw)
            except MailTransportError as exc:
                return {"ok": False, "message": redact_secrets(str(exc), (clean_pw,))}
            except Exception as exc:
                return {
                    "ok": False,
                    "message": redact_secrets(f"Không kết nối được Gmail: {exc}", (clean_pw,)),
                }

        if raw_pw:
            if not self._secret_store.save_password(clean_sender, clean_pw):
                return {
                    "ok": False,
                    "message": "Không lưu được Mật khẩu ứng dụng vào kho bảo mật Windows DPAPI.",
                }

        self._config_repo.save_settings(candidate_settings)
        return {
            "ok": True,
            "message": "Kết nối Gmail thành công và đã lưu bảo mật bằng Windows DPAPI.",
        }

    def test_current_gmail(self) -> dict[str, Any]:
        cfg = self._config_repo.load_config()
        pw = self._secret_store.load_password(cfg.settings.sender)
        problems = validate_gmail_settings(cfg.settings, bool(pw))
        if problems:
            return {"ok": False, "message": problems[0]}
        try:
            self._mail_transport.test_connection(cfg.settings, pw)
            return {"ok": True, "message": f"Kết nối thành công tới Gmail ({cfg.settings.sender})."}
        except Exception as exc:
            return {"ok": False, "message": redact_secrets(str(exc), (pw,))}

    def clear_app_password(self) -> dict[str, Any]:
        cfg = self._config_repo.load_config()
        self._secret_store.delete_password(cfg.settings.sender)
        return {"ok": True, "message": "Đã xóa Mật khẩu ứng dụng khỏi kho bảo mật máy này."}

    def save_general_settings(
        self,
        *,
        sender: Optional[str] = None,
        display_name: Optional[str] = None,
        attach_dir: Optional[str] = None,
        cc_list: Optional[list[str]] = None,
        pacing_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
        theme: Optional[str] = None,
    ) -> dict[str, Any]:
        cfg = self._config_repo.load_config()
        s = cfg.settings

        new_sender = s.sender if sender is None else sender.strip()
        new_name = s.display_name if display_name is None else display_name.strip()
        new_dir = s.attach_dir if attach_dir is None else attach_dir.strip()
        new_cc = s.cc if cc_list is None else split_emails(";".join(cc_list))
        new_pacing = s.pacing_seconds if pacing_seconds is None else float(pacing_seconds)
        new_retries = s.max_retries if max_retries is None else int(max_retries)

        for cc in new_cc:
            if not is_valid_email(cc):
                return {"ok": False, "message": f"Email CC không hợp lệ: {cc}"}
        if new_sender and not is_valid_email(new_sender):
            return {"ok": False, "message": f"Địa chỉ Gmail không hợp lệ: {new_sender}"}
        if not (0.0 <= new_pacing <= 30.0):
            return {"ok": False, "message": "Giãn cách gửi (Pacing) phải từ 0 đến 30 giây."}
        if not (0 <= new_retries <= 5):
            return {"ok": False, "message": "Số lần tự thử lại phải từ 0 đến 5."}

        updated = GmailSettings(
            sender=new_sender,
            display_name=new_name,
            attach_dir=new_dir,
            cc=new_cc,
            logo_path=s.logo_path,
            pacing_seconds=new_pacing,
            max_retries=new_retries,
        )
        self._config_repo.save_settings(updated)
        if theme is not None:
            self._config_repo.save_prefs(theme=theme)
        return {"ok": True, "message": "Đã lưu cài đặt."}

    def set_theme(self, theme: str) -> dict[str, Any]:
        clean = theme if theme in {"light", "dark", "system"} else "system"
        self._config_repo.save_prefs(theme=clean)
        return {"ok": True, "theme": clean}

    def save_github_token(self, token: str) -> dict[str, Any]:
        clean = (token or "").strip()
        if not clean:
            self._secret_store.delete_github_token()
            return {"ok": True, "message": "Đã xóa GitHub Token."}
        if not self._secret_store.save_github_token(clean):
            return {"ok": False, "message": "Không lưu được GitHub Token vào Windows DPAPI."}
        return {"ok": True, "message": "Đã lưu GitHub Token an toàn bằng Windows DPAPI."}

    def complete_onboarding(self) -> dict[str, Any]:
        cfg = self._config_repo.load_config()
        has_pw = self._secret_store.has_password(cfg.settings.sender)
        problems = validate_gmail_settings(cfg.settings, has_pw)
        if problems:
            return {"ok": False, "message": problems[0]}
        self._config_repo.save_prefs(onboarding_completed=True)
        return {"ok": True, "message": "Thiết lập ban đầu hoàn tất!"}

    # ------------------------------------------------------------------ Quản lý Nhà cung cấp

    def upsert_supplier(
        self,
        *,
        supplier_id: Optional[int],
        name: str,
        recipients_raw: str | list[str],
        aliases_raw: str | list[str] = "",
        note: str = "",
        enabled: bool = True,
    ) -> dict[str, Any]:
        cfg = self._config_repo.load_config()
        existing_norms = {
            normalize_name(s.name)
            for s in cfg.suppliers
            if supplier_id is None or s.id != supplier_id
        }
        recipients = (
            split_emails(";".join(recipients_raw))
            if isinstance(recipients_raw, list)
            else split_emails(recipients_raw)
        )
        aliases = (
            [a.strip() for a in aliases_raw if a.strip()]
            if isinstance(aliases_raw, list)
            else [a.strip() for a in aliases_raw.replace(";", ",").split(",") if a.strip()]
        )

        errors = validate_supplier(name, recipients, existing_norms)
        if errors:
            return {"ok": False, "message": errors[0], "errors": errors}

        saved = self._config_repo.upsert_supplier(
            Supplier(
                id=supplier_id,
                name=name.strip(),
                recipients=recipients,
                aliases=aliases,
                note=(note or "").strip(),
                enabled=bool(enabled),
            )
        )
        new_cfg = self._config_repo.load_config()
        return {
            "ok": True,
            "supplier": self._serialize_supplier(saved),
            "duplicate_emails": detect_duplicate_emails_across_suppliers(new_cfg.suppliers),
        }

    def delete_supplier(self, supplier_id: int) -> dict[str, Any]:
        deleted = self._config_repo.delete_supplier(int(supplier_id))
        if not deleted:
            return {"ok": False, "message": "Không tìm thấy nhà cung cấp cần xóa."}
        return {"ok": True, "message": "Đã xóa nhà cung cấp."}

    def toggle_supplier(self, supplier_id: int, enabled: bool) -> dict[str, Any]:
        ok = self._config_repo.set_supplier_enabled(int(supplier_id), bool(enabled))
        if not ok:
            return {"ok": False, "message": "Không tìm thấy nhà cung cấp."}
        return {"ok": True}

    def add_supplier_alias(self, supplier_id: int, alias: str) -> dict[str, Any]:
        clean_alias = (alias or "").strip()
        if not clean_alias:
            return {"ok": False, "message": "Bí danh không được để trống."}
        cfg = self._config_repo.load_config()
        target = next((s for s in cfg.suppliers if s.id == supplier_id), None)
        if target is None:
            return {"ok": False, "message": "Không tìm thấy nhà cung cấp."}
        norm_new = normalize_name(clean_alias)
        if norm_new != normalize_name(target.name) and all(
            normalize_name(a) != norm_new for a in target.aliases
        ):
            target.aliases.append(clean_alias)
            self._config_repo.upsert_supplier(target)
        return {"ok": True, "aliases": target.aliases}

    # ------------------------------------------------------------------ Mẫu Email, Chữ ký & Logo

    def save_templates(
        self,
        subject: str,
        body: str,
        excel_name: str,
        pdf_name: str,
    ) -> dict[str, Any]:
        all_bad: list[str] = []
        for field_val in (subject, body, excel_name, pdf_name):
            for bad in unknown_variables(field_val):
                fix = suggest_variable_fix(bad)
                hint = f" (ý bạn là {{{fix}}}?)" if fix else ""
                all_bad.append(f"Biến không hợp lệ {{{bad}}}{hint}")
        if all_bad:
            return {"ok": False, "message": "; ".join(sorted(set(all_bad)))}
        if not (subject or "").strip():
            return {"ok": False, "message": "Tiêu đề mail không được để trống."}
        if not (excel_name or "").strip():
            return {"ok": False, "message": "Mẫu tên file Excel không được để trống."}
        if not (pdf_name or "").strip():
            return {"ok": False, "message": "Mẫu tên file PDF không được để trống."}

        self._config_repo.save_templates(subject, body, excel_name, pdf_name)
        return {"ok": True, "message": "Đã lưu mẫu email và quy tắc tên file."}

    def reset_default_templates(self) -> dict[str, Any]:
        self._config_repo.save_templates(
            DEFAULT_SUBJECT,
            DEFAULT_BODY,
            DEFAULT_EXCEL_TEMPLATE,
            DEFAULT_PDF_TEMPLATE,
        )
        return {
            "ok": True,
            "templates": {
                "subject": DEFAULT_SUBJECT,
                "body": DEFAULT_BODY,
                "excel_name": DEFAULT_EXCEL_TEMPLATE,
                "pdf_name": DEFAULT_PDF_TEMPLATE,
            },
        }

    def set_logo_from_file(self, source_path: Path) -> dict[str, Any]:
        """Sao chép an toàn ảnh logo vào `%LOCALAPPDATA%\\GmailAutoMailer\\logos`."""
        try:
            src = source_path.resolve()
        except OSError:
            return {"ok": False, "message": "Đường dẫn ảnh logo không hợp lệ."}
        if not src.is_file():
            return {"ok": False, "message": "Không tìm thấy file ảnh đã chọn."}
        ext = src.suffix.lower()
        if ext not in _ALLOWED_LOGO_EXTS:
            return {"ok": False, "message": "Chỉ hỗ trợ ảnh logo định dạng PNG, JPG, WEBP hoặc GIF."}
        size = src.stat().st_size
        if size <= 0:
            return {"ok": False, "message": "File ảnh logo bị rỗng (0 KB)."}
        if size > _MAX_LOGO_BYTES:
            return {"ok": False, "message": "Ảnh logo quá lớn (> 2 MB). Hãy chọn ảnh nhẹ hơn."}

        dest = self._get_logos_dir() / f"company_logo{ext}"
        try:
            shutil.copy2(src, dest)
        except OSError as exc:
            return {"ok": False, "message": f"Không lưu được ảnh logo: {exc}"}

        cfg = self._config_repo.load_config()
        cfg.settings.logo_path = str(dest)
        self._config_repo.save_settings(cfg.settings)
        return {
            "ok": True,
            "logo_path": str(dest),
            "logo_data_uri": self.get_logo_data_uri(str(dest)),
            "message": "Đã cập nhật ảnh logo chữ ký.",
        }

    def clear_logo(self) -> dict[str, Any]:
        cfg = self._config_repo.load_config()
        cfg.settings.logo_path = ""
        self._config_repo.save_settings(cfg.settings)
        return {"ok": True, "message": "Đã gỡ ảnh logo chữ ký."}

    def get_logo_data_uri(self, logo_path: str) -> str:
        clean = (logo_path or "").strip()
        if not clean:
            return ""
        p = Path(clean)
        if not p.is_file():
            return ""
        try:
            mime = mimetypes.guess_type(p.name)[0] or "image/png"
            return build_logo_data_uri(p.read_bytes(), mime_type=mime)
        except OSError:
            return ""

    def render_live_template_preview(
        self,
        *,
        subject: str,
        body: str,
        excel_name: str,
        pdf_name: str,
        supplier_name: str = "ACE",
        month: Optional[int] = None,
        year: Optional[int] = None,
        kind: str = SendKind.FINAL.value,
    ) -> dict[str, Any]:
        """Kết xuất xem trước trực tiếp (HTML đã sanitize + Logo Data URI + tên file mẫu)."""
        today = date.today()
        m = month if month is not None else today.month
        y = year if year is not None else today.year
        values = {
            "thang": f"{m:02d}",
            "nam": str(y),
            "nha_cung_cap": supplier_name or "ACE",
            "loai": kind,
        }
        cfg = self._config_repo.load_config()
        logo_uri = self.get_logo_data_uri(cfg.settings.logo_path)
        rendered_subject = render(subject, values)
        rendered_body = render(body, values)
        rendered_html = build_html_body(
            rendered_body,
            logo_src=logo_uri or None,
            for_preview=True,
        )
        return {
            "subject": rendered_subject,
            "body_text": rendered_body,
            "body_html": rendered_html,
            "excel_example": render(excel_name, values),
            "pdf_example": render(pdf_name, values),
        }

    # ------------------------------------------------------------------ Lịch sử gửi In-App

    def query_history(
        self,
        *,
        month: Optional[int] = None,
        year: Optional[int] = None,
        kind: Optional[str] = None,
        status: Optional[str] = None,
        keyword: str = "",
        limit: int = 500,
    ) -> dict[str, Any]:
        rows: list[HistoryRecord] = self._history_repo.query_history(
            month=month, year=year, kind=kind, status=status, keyword=keyword, limit=limit
        )
        stats: Optional[PeriodStats] = None
        if month is not None and year is not None:
            stats = self._history_repo.period_stats(month, year, kind or None)
        else:
            ok_cnt = sum(1 for r in rows if r.status == "Thành công")
            fail_cnt = len(rows) - ok_cnt
            rate = round((ok_cnt / len(rows)) * 100.0, 1) if rows else 0.0
            stats = PeriodStats(total=len(rows), ok_count=ok_cnt, fail_count=fail_cnt, success_rate=rate)

        return {
            "stats": {
                "total": stats.total,
                "ok_count": stats.ok_count,
                "fail_count": stats.fail_count,
                "success_rate": stats.success_rate,
            },
            "records": [
                {
                    "id": r.id,
                    "batch_id": r.batch_id,
                    "sent_at": r.sent_at,
                    "month": f"{r.month:02d}",
                    "year": r.year,
                    "kind": r.kind,
                    "supplier": r.supplier,
                    "recipients": r.recipients,
                    "subject": r.subject,
                    "attachments": r.attachments,
                    "status": r.status,
                    "detail": r.detail,
                }
                for r in rows
            ],
        }

    def export_history_excel(self, dest_path: Optional[Path] = None) -> dict[str, Any]:
        target = dest_path if dest_path is not None else (self._get_exports_dir() / "Lich_su_gui.xlsx")
        ok = self._history_repo.export_excel(target)
        if not ok:
            return {
                "ok": False,
                "message": "Chưa có dữ liệu lịch sử gửi hoặc file Excel đích đang mở bị khóa ghi.",
            }
        return {"ok": True, "path": str(target), "message": f"Đã xuất báo cáo tại {target.name}"}
