"""Lõi gửi mail Gmail SMTP (SSL 465 -> STARTTLS 587 fallback), TOCTOU SHA-256, HTML + Logo CID."""

from __future__ import annotations

import base64
import email.policy
import hmac
import mimetypes
import smtplib
import ssl
import unicodedata
from email import encoders
from email.header import Header
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid
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

# Dùng compat32 với max_line_length=0 để smtplib.send_message (BytesGenerator)
# KHÔNG tự bẻ tham số tên file sang RFC 2231 (filename*0*= / filename*1*=),
# tránh lỗi đảo ngược mảnh tên & mất đuôi .xlsx/.pdf trên mail domain (DaouOffice, Outlook cũ, Hiworks...).
_NO_WRAP_COMPAT_POLICY = email.policy.compat32.clone(max_line_length=0)

# Bản đồ MIME tường minh cho file văn phòng & ảnh logo (tránh lệ thuộc Windows Registry bị thiếu/sai).
_EXPLICIT_MIME_TYPES: dict[str, str] = {
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12",
    ".csv": "text/csv",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


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


def _guess_mime_type(filename: str) -> tuple[str, str]:
    """Xác định `(maintype, subtype)` ưu tiên bảng chuẩn Office/PDF trước `mimetypes.guess_type`."""
    ext = Path(filename).suffix.lower()
    mime_type = (
        _EXPLICIT_MIME_TYPES.get(ext) or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    )
    main_type, sep, sub_type = mime_type.partition("/")
    if not sep or not main_type or not sub_type:
        return "application", "octet-stream"
    return main_type, sub_type


def encode_mime_filename(filename: str) -> str:
    """Mã hóa tên file đính kèm an toàn tương thích 100% Gmail, Outlook và Mail Domain (DaouOffice/Hiworks/Exchange).

    - Chuẩn hóa NFC (tránh lỗi dấu tiếng Việt tách rời từ macOS) và loại bỏ ký tự điều khiển chống Header Injection.
    - Tên thuần ASCII an toàn (không chứa `"`, `\\`, `=?`) giữ nguyên nguyên vẹn.
    - Tên có dấu tiếng Việt / tiếng Hàn / Unicode được mã hóa RFC 2047 UTF-8 Base64 (`=?UTF-8?B?...?=`),
      mỗi encoded-word <= 75 ký tự, cắt đúng ranh giới ký tự UTF-8, KHÔNG dùng RFC 2231 `filename*0*=`.
    """
    clean = unicodedata.normalize("NFC", filename.replace("\r", "").replace("\n", "").replace("\x00", ""))
    if (
        clean
        and all(32 <= ord(ch) <= 126 for ch in clean)
        and '"' not in clean
        and "\\" not in clean
        and "=?" not in clean
        and len(clean) <= 900
    ):
        return clean

    prefix = "=?UTF-8?B?"
    suffix = "?="
    # 75 - 12 = 63 ký tự base64 -> tối đa 60 ký tự base64 = 45 byte UTF-8 -> mỗi từ tối đa 72 <= 75 ký tự
    max_raw_bytes = ((75 - len(prefix) - len(suffix)) // 4) * 3
    words: list[str] = []
    chunk = bytearray()
    for ch in clean:
        ch_bytes = ch.encode("utf-8")
        if chunk and len(chunk) + len(ch_bytes) > max_raw_bytes:
            b64 = base64.b64encode(bytes(chunk)).decode("ascii")
            words.append(f"{prefix}{b64}{suffix}")
            chunk = bytearray()
        chunk.extend(ch_bytes)
    if chunk:
        b64 = base64.b64encode(bytes(chunk)).decode("ascii")
        words.append(f"{prefix}{b64}{suffix}")

    # Giữ các encoded-word cách nhau bằng 1 dấu cách trên 1 dòng (tránh lỗi gãy dấu ngoặc kép trên Outlook/Apple Mail),
    # chỉ xuống dòng khi độ dài tiến sát giới hạn 998 ký tự/dòng của RFC 5322.
    lines: list[str] = []
    current = ""
    for word in words:
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= 900:
            current = f"{current} {word}"
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return "\n ".join(lines)


def _format_sender_header(display_name: str, sender: str) -> str:
    """Định dạng header `From:` chuẩn RFC 5322 / RFC 2047."""
    clean_name = unicodedata.normalize(
        "NFC", (display_name or "").replace("\r", "").replace("\n", "").strip()
    )
    if not clean_name:
        return sender
    if all(32 <= ord(ch) <= 126 for ch in clean_name):
        return formataddr((clean_name, sender))
    return formataddr((Header(clean_name, "utf-8", maxlinelen=75).encode(), sender))


def _format_address_list(addresses: list[str]) -> str:
    """Nối danh sách địa chỉ To/Cc có gấp dòng sạch để không bao giờ vượt 998 ký tự/dòng."""
    lines: list[str] = []
    current = ""
    for addr in addresses:
        if not current:
            current = addr
        elif len(current) + 2 + len(addr) <= 76:
            current = f"{current}, {addr}"
        else:
            lines.append(f"{current},")
            current = addr
    if current:
        lines.append(current)
    return "\n ".join(lines)


def _build_binary_part(
    payload: bytes,
    filename: str,
    disposition: str,
    content_id: Optional[str] = None,
) -> MIMEBase:
    """Tạo MIME part nhị phân Base64 với cả `Content-Type; name=` và `Content-Disposition; filename=` chuẩn RFC 2047."""
    main_type, sub_type = _guess_mime_type(filename)
    part = MIMEBase(main_type, sub_type, policy=_NO_WRAP_COMPAT_POLICY)
    del part["MIME-Version"]
    part.set_payload(payload)
    encoders.encode_base64(part)

    encoded_name = encode_mime_filename(filename)
    part.replace_header("Content-Type", f'{main_type}/{sub_type};\n name="{encoded_name}"')
    part.add_header("Content-Disposition", f'{disposition};\n filename="{encoded_name}"')
    if content_id:
        part["Content-ID"] = f"<{content_id}>"
    return part


def build_email_message(
    settings: GmailSettings,
    plan: MailPlan,
    message_id: str,
    verify_toctou: bool = True,
) -> MIMEMultipart:
    """Dựng MIME Multipart (Plaintext + HTML đã sanitize + Logo CID tùy chọn + Đính kèm đã xác thực TOCTOU)."""
    msg = MIMEMultipart("mixed", policy=_NO_WRAP_COMPAT_POLICY)
    msg["From"] = _format_sender_header(settings.display_name, settings.sender)
    msg["To"] = _format_address_list(plan.recipients)
    if plan.cc:
        msg["Cc"] = _format_address_list(plan.cc)
    msg["Subject"] = Header(plan.subject, "utf-8", maxlinelen=75).encode()
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = message_id

    logo_file = _resolve_explicit_logo(settings, plan)
    logo_src = f"cid:{LOGO_CID}" if logo_file is not None else None

    alt = MIMEMultipart("alternative", policy=_NO_WRAP_COMPAT_POLICY)
    del alt["MIME-Version"]

    plain_part = MIMEText(plan.body, "plain", "utf-8", policy=_NO_WRAP_COMPAT_POLICY)
    del plain_part["MIME-Version"]
    alt.attach(plain_part)

    html_content = build_html_body(plan.body, logo_src=logo_src, for_preview=False)
    html_part = MIMEText(html_content, "html", "utf-8", policy=_NO_WRAP_COMPAT_POLICY)
    del html_part["MIME-Version"]

    if logo_file is not None:
        try:
            logo_bytes = logo_file.read_bytes()
        except OSError as exc:
            raise MailTransportError(
                f"Không đọc được ảnh logo chữ ký '{logo_file.name}'.",
                SendErrorKind.ATTACHMENT_IO,
            ) from exc
        rel = MIMEMultipart("related", policy=_NO_WRAP_COMPAT_POLICY)
        del rel["MIME-Version"]
        rel.attach(html_part)
        rel.attach(_build_binary_part(logo_bytes, logo_file.name, disposition="inline", content_id=LOGO_CID))
        alt.attach(rel)
    else:
        alt.attach(html_part)

    msg.attach(alt)

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

        msg.attach(_build_binary_part(payload, att.file.name, disposition="attachment"))

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
