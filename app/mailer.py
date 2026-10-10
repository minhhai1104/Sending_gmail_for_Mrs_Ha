"""Dựng mail và gửi qua Gmail (SMTP SSL)."""
import mimetypes
import smtplib
import ssl
from dataclasses import dataclass
from email.headerregistry import Address
from email.message import EmailMessage
from typing import Callable, Optional

from .config import Settings
from .planner import MailPlan

GMAIL_HOST = "smtp.gmail.com"
GMAIL_PORT = 465
TIMEOUT_SECONDS = 60


class MailError(Exception):
    """Lỗi gửi mail với thông báo dễ hiểu bằng tiếng Việt."""


@dataclass
class SendResult:
    supplier: str
    ok: bool
    message: str


def friendly_error(exc: Exception) -> str:
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return ("Gmail từ chối đăng nhập. Hãy kiểm tra lại Gmail và 'Mật khẩu ứng dụng' "
                "(không dùng mật khẩu đăng nhập thường).")
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return "Gmail từ chối địa chỉ người nhận: " + ", ".join(exc.recipients)
    if isinstance(exc, smtplib.SMTPException):  # phải xét trước OSError vì SMTPException kế thừa OSError
        return f"Lỗi gửi mail: {exc}"
    if isinstance(exc, OSError):
        return "Không kết nối được tới Gmail. Hãy kiểm tra Internet."
    return f"Lỗi gửi mail: {exc}"


def build_message(settings: Settings, plan: MailPlan) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = Address(settings.display_name, addr_spec=settings.sender)
    msg["To"] = [Address(addr_spec=mail) for mail in plan.recipients]
    if plan.cc:
        msg["Cc"] = [Address(addr_spec=mail) for mail in plan.cc]
    msg["Subject"] = plan.subject
    msg.set_content(plan.body)
    for attachment in plan.attachments:
        mime_type = mimetypes.guess_type(attachment.name)[0] or "application/octet-stream"
        main_type, _, sub_type = mime_type.partition("/")
        msg.add_attachment(attachment.path.read_bytes(), maintype=main_type,
                           subtype=sub_type, filename=attachment.name)
    return msg


class GmailSession:
    """Một phiên đăng nhập Gmail dùng chung cho cả đợt gửi."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._server: Optional[smtplib.SMTP_SSL] = None

    def __enter__(self) -> "GmailSession":
        self._connect()
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def _connect(self) -> None:
        self.close()
        try:
            server = smtplib.SMTP_SSL(GMAIL_HOST, GMAIL_PORT, timeout=TIMEOUT_SECONDS,
                                      context=ssl.create_default_context())
            server.login(self._settings.sender, self._settings.app_password)
        except (smtplib.SMTPException, OSError) as exc:
            raise MailError(friendly_error(exc)) from exc
        self._server = server

    def close(self) -> None:
        if self._server is not None:
            try:
                self._server.quit()
            except (smtplib.SMTPException, OSError):
                pass
            self._server = None

    def send(self, plan: MailPlan) -> None:
        msg = build_message(self._settings, plan)
        try:
            self._server.send_message(msg)
        except smtplib.SMTPServerDisconnected:  # mất kết nối giữa chừng: đăng nhập lại và thử 1 lần nữa
            self._connect()
            self._server.send_message(msg)


def test_connection(settings: Settings) -> None:
    """Đăng nhập thử vào Gmail; raise MailError nếu thất bại."""
    with GmailSession(settings):
        pass


def send_plans(settings: Settings, plans: list[MailPlan],
               on_result: Optional[Callable[[MailPlan, SendResult], None]] = None) -> list[SendResult]:
    """Gửi lần lượt từng mail. Lỗi ở một nhà cung cấp không làm dừng cả đợt."""
    results = []
    with GmailSession(settings) as session:
        for plan in plans:
            try:
                session.send(plan)
                result = SendResult(plan.supplier, True, "Đã gửi")
            except (smtplib.SMTPException, OSError) as exc:
                result = SendResult(plan.supplier, False, friendly_error(exc))
            results.append(result)
            if on_result:
                on_result(plan, result)
    return results
