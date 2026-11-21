"""Lõi gửi mail Gmail SMTP (SSL 465 -> STARTTLS 587 fallback), TOCTOU SHA-256, HTML + Logo CID."""

from __future__ import annotations

import hmac
import mimetypes
import smtplib
import ssl
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path
from typing import Optional

from ..domain.models import GmailSettings, MailPlan, SendErrorKind, SendResult
from ..domain.templating import build_html_body
from ..domain.validation import redact_secrets
from .fs_scanner import compute_file_sha256

GMAIL_HOST = "smtp.gmail.com"
GMAIL_SSL_PORT = 465
GMAIL_STARTTLS_PORT = 587
TIMEOUT_SECONDS = 45
LOGO_CID = "company_logo_haesung"


class MailTransportError(Exception):
    """Lỗi vận chuyển SMTP kèm phân loại tường minh `SendErrorKind`."""

    def __init__(self, message: str, kind: SendErrorKind) -> None:
        super().__init__(message)
        self.kind = kind


def generate_message_id(sender: str) -> str:
    """Tạo `Message-ID` chuẩn RFC cố định cho mỗi email (chống gửi trùng khi retry)."""
    domain = sender.split("@")[-1] if "@" in sender else "haesungvina.local"
    return make_msgid(domain=domain)


def classify_smtp_error(exc: Exception, active_secrets: tuple[str, ...] = ()) -> tuple[SendErrorKind, str]:
    """Chuyển đổi exception sang cặp `(SendErrorKind, thông_báo_tiếng_Việt_đã_che_secret)`."""
    if isinstance(exc, MailTransportError):
        return exc.kind, redact_secrets(str(exc), active_secrets)
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return (
            SendErrorKind.AUTH,
            "Gmail từ chối đăng nhập. Hãy kiểm tra lại địa chỉ Gmail và Mật khẩu ứng dụng (16 ký tự).",
        )
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        addrs = ", ".join(exc.recipients.keys())
        return SendErrorKind.RECIPIENT_REFUSED, f"Gmail từ chối toàn bộ người nhận: {addrs}"
    if isinstance(exc, (smtplib.SMTPServerDisconnected, TimeoutError, ConnectionError, OSError)):
        return (
            SendErrorKind.TRANSIENT_NETWORK,
            "Kết nối tới máy chủ Gmail bị gián đoạn. Hãy kiểm tra mạng Internet hoặc tường lửa.",
        )
    if isinstance(exc, smtplib.SMTPException):
        safe = redact_secrets(str(exc), active_secrets)
        return SendErrorKind.TRANSIENT_NETWORK, f"Lỗi máy chủ SMTP Gmail: {safe}"
    safe = redact_secrets(str(exc), active_secrets)
    return SendErrorKind.UNKNOWN, f"Lỗi gửi mail không xác định: {safe}"


def _resolve_explicit_logo(settings: GmailSettings, plan: MailPlan) -> Optional[Path]:
    """Chỉ dùng logo khi người dùng cấu hình rõ ràng (tuyệt đối không tự nhúng logo.png âm thầm)."""
    if plan.logo_path is not None and plan.logo_path.is_file():
        return plan.logo_path
    raw = (settings.logo_path or "").strip()
    if raw:
        candidate = Path(raw)
        if candidate.is_file():
            return candidate
    return None


def build_email_message(
    settings: GmailSettings,
    plan: MailPlan,
    message_id: str,
    verify_toctou: bool = True,
) -> EmailMessage:
    """Dựng MIME Multipart (Plaintext + HTML đã sanitize + Logo CID tùy chọn + Đính kèm đã xác thực TOCTOU)."""
    msg = EmailMessage()
    msg["From"] = Address(settings.display_name, addr_spec=settings.sender)
    msg["To"] = [Address(addr_spec=mail) for mail in plan.recipients]
    if plan.cc:
        msg["Cc"] = [Address(addr_spec=mail) for mail in plan.cc]
    msg["Subject"] = plan.subject
    msg["Message-ID"] = message_id

    logo_file = _resolve_explicit_logo(settings, plan)
    logo_src = f"cid:{LOGO_CID}" if logo_file is not None else None

    msg.set_content(plan.body)
    html_content = build_html_body(plan.body, logo_src=logo_src, for_preview=False)
    msg.add_alternative(html_content, subtype="html")

    if logo_file is not None:
        try:
            logo_bytes = logo_file.read_bytes()
            mime_type = mimetypes.guess_type(logo_file.name)[0] or "image/png"
            main_type, _, sub_type = mime_type.partition("/")
            html_part = msg.get_body(preferencelist=("html",))
            if html_part is not None:
                html_part.add_related(  # type: ignore[attr-defined]
                    logo_bytes,
                    maintype=main_type,
                    subtype=sub_type,
                    cid=f"<{LOGO_CID}>",
                )
        except OSError as exc:
            raise MailTransportError(
                f"Không đọc được ảnh logo chữ ký '{logo_file.name}'.",
                SendErrorKind.ATTACHMENT_IO,
            ) from exc

    for att in plan.attachments:
        if att.file is None:
            raise MailTransportError(
                f"Thiếu file đính kèm bắt buộc '{att.expected_name}'.",
                SendErrorKind.ATTACHMENT_IO,
            )
        file_path = att.file.path
        if not file_path.is_file():
            raise MailTransportError(
                f"File đính kèm '{att.file.name}' không còn tồn tại trên đĩa.",
                SendErrorKind.ATTACHMENT_IO,
            )

        # Kiểm tra TOCTOU: đối chiếu SHA-256 thực tế ngay trước khi gửi so với lúc người dùng duyệt
        if verify_toctou and att.file.sha256:
            try:
                actual_hash = compute_file_sha256(file_path)
            except OSError as exc:
                raise MailTransportError(
                    f"Không đọc được file đính kèm '{att.file.name}' (file đang bị khóa).",
                    SendErrorKind.ATTACHMENT_IO,
                ) from exc
            if not hmac.compare_digest(actual_hash, att.file.sha256.lower()):
                raise MailTransportError(
                    f"File đính kèm '{att.file.name}' vừa bị thay đổi nội dung sau khi bạn xem trước. "
                    "Đã dừng gửi để bảo vệ an toàn dữ liệu — vui lòng quét lại trước khi gửi.",
                    SendErrorKind.ATTACHMENT_CHANGED,
                )

        try:
            payload = file_path.read_bytes()
        except OSError as exc:
            raise MailTransportError(
                f"Không đọc được file đính kèm '{att.file.name}' (file đang bị khóa hoặc đã xóa).",
                SendErrorKind.ATTACHMENT_IO,
            ) from exc

        mime_type = mimetypes.guess_type(att.file.name)[0] or "application/octet-stream"
        main_type, _, sub_type = mime_type.partition("/")
        msg.add_attachment(
            payload,
            maintype=main_type,
            subtype=sub_type,
            filename=att.file.name,
        )

    return msg


class SmtpMailSession:
    """Phiên SMTP hỗ trợ tự động Fallback Port 465 (SSL) -> 587 (STARTTLS) và kiểm tra NOOP."""

    def __init__(self, settings: GmailSettings, app_password: str) -> None:
        self._settings = settings
        self._password = app_password
        self._server: Optional[smtplib.SMTP] = None

    def __enter__(self) -> "SmtpMailSession":
        self._connect()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _connect_ssl(self) -> smtplib.SMTP:
        server = smtplib.SMTP_SSL(
            GMAIL_HOST,
            GMAIL_SSL_PORT,
            timeout=TIMEOUT_SECONDS,
            context=ssl.create_default_context(),
        )
        try:
            server.login(self._settings.sender, self._password)
        except Exception:
            self._safe_close(server)
            raise
        return server

    def _connect_starttls(self) -> smtplib.SMTP:
        server = smtplib.SMTP(GMAIL_HOST, GMAIL_STARTTLS_PORT, timeout=TIMEOUT_SECONDS)
        try:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
            server.login(self._settings.sender, self._password)
        except Exception:
            self._safe_close(server)
            raise
        return server

    def _connect(self) -> None:
        self.close()
        try:
            self._server = self._connect_ssl()
            return
        except smtplib.SMTPAuthenticationError as exc:
            kind, msg = classify_smtp_error(exc, (self._password,))
            raise MailTransportError(msg, kind) from exc
        except (OSError, smtplib.SMTPException):
            # Fallback sang Port 587 STARTTLS (rất hữu ích khi tường lửa văn phòng chặn port 465)
            try:
                self._server = self._connect_starttls()
                return
            except Exception as exc2:
                kind, msg = classify_smtp_error(exc2, (self._password,))
                raise MailTransportError(msg, kind) from exc2

    @staticmethod
    def _safe_close(server: Optional[smtplib.SMTP]) -> None:
        if server is None:
            return
        try:
            server.quit()
        except Exception:
            try:
                server.close()
            except Exception:
                pass

    def close(self) -> None:
        self._safe_close(self._server)
        self._server = None

    def _ensure_alive(self) -> None:
        """Kiểm tra kết nối bằng `NOOP` TRƯỚC KHI gửi DATA để giảm thiểu nguy cơ retry trùng lặp."""
        if self._server is None:
            self._connect()
            return
        try:
            code, _ = self._server.noop()
            if code != 250:
                self._connect()
        except (smtplib.SMTPException, OSError):
            self._connect()

    def send(self, plan: MailPlan, message_id: str) -> SendResult:
        msg = build_email_message(self._settings, plan, message_id=message_id, verify_toctou=True)
        self._ensure_alive()
        assert self._server is not None

        try:
            refused = self._server.send_message(msg)
        except Exception as exc:
            kind, err_msg = classify_smtp_error(exc, (self._password,))
            raise MailTransportError(err_msg, kind) from exc

        all_targets = list(plan.recipients) + list(plan.cc)
        if isinstance(refused, dict) and refused:
            refused_set = {addr.lower() for addr in refused.keys()}
            refused_list = tuple(refused.keys())
            accepted_list = tuple(a for a in all_targets if a.lower() not in refused_set)
            if accepted_list:
                return SendResult(
                    supplier=plan.supplier,
                    ok=False,
                    message=(
                        f"Gửi được 1 phần ({len(accepted_list)}/{len(all_targets)}). "
                        f"Gmail từ chối: {', '.join(refused_list)}"
                    ),
                    error_kind=SendErrorKind.PARTIAL_REFUSED,
                    refused_recipients=refused_list,
                    accepted_recipients=accepted_list,
                    message_id=message_id,
                )
            return SendResult(
                supplier=plan.supplier,
                ok=False,
                message=f"Gmail từ chối toàn bộ địa chỉ nhận: {', '.join(refused_list)}",
                error_kind=SendErrorKind.RECIPIENT_REFUSED,
                refused_recipients=refused_list,
                accepted_recipients=(),
                message_id=message_id,
            )

        return SendResult(
            supplier=plan.supplier,
            ok=True,
            message="Đã gửi thành công (250 OK)",
            error_kind=SendErrorKind.NONE,
            accepted_recipients=tuple(all_targets),
            message_id=message_id,
        )


class GmailSmtpTransport:
    """Triển khai `MailTransport` thực tế qua Gmail SMTP."""

    def test_connection(self, settings: GmailSettings, app_password: str) -> None:
        with SmtpMailSession(settings, app_password):
            pass

    def open_session(self, settings: GmailSettings, app_password: str) -> SmtpMailSession:
        return SmtpMailSession(settings, app_password)
