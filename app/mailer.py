"""Dựng mail (Multipart Plaintext + HTML doanh nghiệp + Logo CID) và gửi qua Gmail (SMTP SSL)."""
import html
import mimetypes
import re
import smtplib
import ssl
import threading
import time
from dataclasses import dataclass
from email.headerregistry import Address
from email.message import EmailMessage
from pathlib import Path
from typing import Callable, Optional

from .config import APP_DIR, Settings
from .planner import MailPlan

GMAIL_HOST = "smtp.gmail.com"
GMAIL_PORT = 465
TIMEOUT_SECONDS = 60
DEFAULT_PACING_SECONDS = 1.5
_HTML_TAG_RE = re.compile(r"<\s*(?:html|body|p|div|br|table|span|strong|b|a)\b", re.IGNORECASE)
_SIG_SEP_RE = re.compile(r"^-{3,}\s*$", re.MULTILINE)


class MailError(Exception):
    """Lỗi gửi mail với thông báo dễ hiểu bằng tiếng Việt."""


@dataclass
class SendResult:
    supplier: str
    ok: bool
    message: str


def friendly_error(exc: Exception) -> str:
    if isinstance(exc, MailError):
        return str(exc)
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return (
            "Gmail từ chối đăng nhập. Hãy kiểm tra lại Gmail và 'Mật khẩu ứng dụng' "
            "(không dùng mật khẩu đăng nhập thường)."
        )
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return "Gmail từ chối địa chỉ người nhận: " + ", ".join(exc.recipients)
    if isinstance(exc, smtplib.SMTPException):  # xét trước OSError vì SMTPException kế thừa OSError
        return f"Lỗi gửi mail: {exc}"
    if isinstance(exc, OSError):
        return "Không kết nối được tới Gmail. Hãy kiểm tra Internet."
    return f"Lỗi gửi mail: {exc}"


def _resolve_logo_path(settings: Settings) -> Optional[Path]:
    """Xác định đường dẫn ảnh logo chữ ký (nếu được cấu hình hoặc có sẵn logo.png cạnh app)."""
    raw = (settings.logo_path or "").strip()
    if raw:
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = APP_DIR / candidate
        return candidate if candidate.is_file() else None
    default_logo = APP_DIR / "logo.png"
    return default_logo if default_logo.is_file() else None


def build_html_body(body_text: str, logo_cid: Optional[str] = None) -> str:
    """Chuyển đổi nội dung thư sang HTML chuẩn doanh nghiệp kèm chữ ký và logo CID tùy chọn."""
    logo_html = (
        f'<div style="margin-top:10px;">'
        f'<img src="cid:{html.escape(logo_cid)}" alt="Company Logo" '
        f'style="max-height:56px;width:auto;display:block;" />'
        f"</div>"
        if logo_cid
        else ""
    )

    if _HTML_TAG_RE.search(body_text or ""):
        # Người dùng tự viết mã HTML trong ô Nội dung mail
        if "<html" in body_text.lower():
            return body_text
        return (
            '<!DOCTYPE html><html><head><meta charset="utf-8"></head>'
            '<body style="font-family:\'Segoe UI\',Arial,sans-serif;font-size:14px;'
            'line-height:1.6;color:#201F1E;">'
            f"{body_text}{logo_html}</body></html>"
        )

    parts = _SIG_SEP_RE.split(body_text or "", maxsplit=1)
    main_text = parts[0].strip()
    sig_text = parts[1].strip() if len(parts) > 1 else ""

    main_paragraphs = [
        f'<p style="margin:0 0 10px 0;">{html.escape(line)}</p>' if line.strip() else "<br/>"
        for line in main_text.splitlines()
    ]
    main_html = "\n".join(main_paragraphs)

    sig_block = ""
    if sig_text or logo_html:
        sig_lines = []
        for idx, line in enumerate(sig_text.splitlines()):
            escaped = html.escape(line)
            if idx == 0:
                sig_lines.append(
                    f'<div style="font-weight:bold;color:#1F4E78;font-size:14px;">{escaped}</div>'
                )
            else:
                sig_lines.append(f'<div style="color:#595959;font-size:13px;">{escaped}</div>')
        sig_inner = "\n".join(sig_lines)
        sig_block = (
            '<div style="margin-top:18px;padding-top:12px;border-top:1px solid #D2D0CE;">'
            f"{sig_inner}{logo_html}</div>"
        )

    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8"></head>'
        '<body style="font-family:\'Segoe UI\',Arial,sans-serif;font-size:14px;'
        'line-height:1.6;color:#201F1E;margin:0;padding:12px;">'
        f"{main_html}{sig_block}</body></html>"
    )


def build_message(settings: Settings, plan: MailPlan) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = Address(settings.display_name, addr_spec=settings.sender)
    msg["To"] = [Address(addr_spec=mail) for mail in plan.recipients]
    if plan.cc:
        msg["Cc"] = [Address(addr_spec=mail) for mail in plan.cc]
    msg["Subject"] = plan.subject

    logo_file = _resolve_logo_path(settings)
    logo_cid = "company_logo_haesung" if logo_file is not None else None

    msg.set_content(plan.body)
    html_content = build_html_body(plan.body, logo_cid=logo_cid)
    msg.add_alternative(html_content, subtype="html")

    if logo_file is not None and logo_cid is not None:
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
                    cid=f"<{logo_cid}>",
                )
        except OSError:
            pass

    for attachment in plan.attachments:
        mime_type = mimetypes.guess_type(attachment.name)[0] or "application/octet-stream"
        main_type, _, sub_type = mime_type.partition("/")
        try:
            payload = attachment.path.read_bytes()
        except OSError as exc:
            raise MailError(
                f"Không đọc được file đính kèm '{attachment.name}' "
                "(file đã bị xóa hoặc đang bị khóa)."
            ) from exc
        msg.add_attachment(
            payload,
            maintype=main_type,
            subtype=sub_type,
            filename=attachment.name,
        )
    return msg


class GmailSession:
    """Một phiên đăng nhập Gmail dùng chung cho cả đợt gửi."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._server: Optional[smtplib.SMTP_SSL] = None

    def __enter__(self) -> "GmailSession":
        self._connect()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _connect(self) -> None:
        self.close()
        server: Optional[smtplib.SMTP_SSL] = None
        try:
            server = smtplib.SMTP_SSL(
                GMAIL_HOST,
                GMAIL_PORT,
                timeout=TIMEOUT_SECONDS,
                context=ssl.create_default_context(),
            )
            server.login(self._settings.sender, self._settings.app_password)
        except (smtplib.SMTPException, OSError) as exc:
            if server is not None:
                try:
                    server.close()
                except Exception:
                    pass
            raise MailError(friendly_error(exc)) from exc
        self._server = server

    def close(self) -> None:
        if self._server is not None:
            try:
                self._server.quit()
            except (smtplib.SMTPException, OSError):
                try:
                    self._server.close()
                except Exception:
                    pass
            self._server = None

    def send(self, plan: MailPlan) -> None:
        msg = build_message(self._settings, plan)
        if self._server is None:
            self._connect()
        assert self._server is not None
        try:
            refused = self._server.send_message(msg)
        except smtplib.SMTPServerDisconnected:
            # Mất kết nối giữa chừng: đăng nhập lại và thử 1 lần nữa
            self._connect()
            assert self._server is not None
            refused = self._server.send_message(msg)

        if isinstance(refused, dict) and refused:
            refused_addrs = ", ".join(refused.keys())
            raise MailError(f"Gmail từ chối một số địa chỉ người nhận: {refused_addrs}")


def test_connection(settings: Settings) -> None:
    """Đăng nhập thử vào Gmail; raise MailError nếu thất bại."""
    with GmailSession(settings):
        pass


def _wait_if_paused(
    pause_event: Optional[threading.Event],
    cancel_event: Optional[threading.Event],
) -> bool:
    """Chờ nếu đang ở trạng thái Tạm dừng (pause_event.is_set()). Trả về True nếu bị Hủy."""
    while pause_event is not None and pause_event.is_set():
        if cancel_event is not None and cancel_event.is_set():
            return True
        time.sleep(0.1)
    return bool(cancel_event is not None and cancel_event.is_set())


def send_plans(
    settings: Settings,
    plans: list[MailPlan],
    on_result: Optional[Callable[[MailPlan, SendResult], None]] = None,
    pacing_delay: float = 0.0,
    max_retries: int = 0,
    pause_event: Optional[threading.Event] = None,
    cancel_event: Optional[threading.Event] = None,
) -> list[SendResult]:
    """Gửi lần lượt từng mail kèm Pacing, Exponential Backoff Retry và kiểm soát Pause/Cancel."""
    results: list[SendResult] = []
    with GmailSession(settings) as session:
        for index, plan in enumerate(plans):
            if _wait_if_paused(pause_event, cancel_event):
                break

            attempt = 0
            result: Optional[SendResult] = None
            while True:
                try:
                    session.send(plan)
                    result = SendResult(plan.supplier, True, "Đã gửi")
                    break
                except (MailError, smtplib.SMTPException, OSError) as exc:
                    err_msg = friendly_error(exc)
                    # Không retry nếu là lỗi thiếu file đính kèm hoặc từ chối địa chỉ nhận
                    is_transient = (
                        not isinstance(
                            exc,
                            (smtplib.SMTPRecipientsRefused, smtplib.SMTPAuthenticationError),
                        )
                        and "file đính kèm" not in err_msg.lower()
                        and "địa chỉ người nhận" not in err_msg.lower()
                    )

                    if attempt < max_retries and is_transient:
                        attempt += 1
                        backoff = min(4.0, 1.0 * (2 ** (attempt - 1)))
                        if cancel_event is not None:
                            if cancel_event.wait(backoff):
                                break
                        else:
                            time.sleep(backoff)
                        continue
                    result = SendResult(plan.supplier, False, err_msg)
                    break

            if result is None:
                break

            results.append(result)
            if on_result:
                on_result(plan, result)

            if _wait_if_paused(pause_event, cancel_event):
                break

            # Giãn cách Pacing thông minh chống Gmail chặn spam giữa các mail liên tiếp
            if pacing_delay > 0 and index < len(plans) - 1:
                if cancel_event is not None:
                    if cancel_event.wait(pacing_delay):
                        break
                else:
                    time.sleep(pacing_delay)

    return results
