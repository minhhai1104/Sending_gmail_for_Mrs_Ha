"""Nội suy biến mẫu email, làm sạch HTML bằng nh3 (chống XSS) và dựng HTML doanh nghiệp."""

from __future__ import annotations

import base64
import html
import re
from typing import Optional

import nh3

VARIABLES: dict[str, str] = {
    "thang": "Tháng gồm 2 chữ số, ví dụ 09",
    "nam": "Năm gồm 4 chữ số, ví dụ 2026",
    "nha_cung_cap": "Tên nhà cung cấp, ví dụ ACE",
    "loai": "Chế độ gửi: Tạm tính hoặc Chốt",
}

VARIABLE_CHIPS: tuple[dict[str, str], ...] = (
    {"key": "thang", "token": "{thang}", "label": "Tháng (09)", "example": "09"},
    {"key": "nam", "token": "{nam}", "label": "Năm (2026)", "example": "2026"},
    {"key": "nha_cung_cap", "token": "{nha_cung_cap}", "label": "Tên NCC", "example": "ACE"},
    {"key": "loai", "token": "{loai}", "label": "Loại gửi", "example": "Tạm tính"},
)

_TYPO_MAP: dict[str, str] = {
    "tháng": "thang",
    "month": "thang",
    "năm": "nam",
    "year": "nam",
    "ncc": "nha_cung_cap",
    "nhacungcap": "nha_cung_cap",
    "nhà cung cấp": "nha_cung_cap",
    "supplier": "nha_cung_cap",
    "loại": "loai",
    "type": "loai",
    "kind": "loai",
}

# Chỉ bắt biến dạng {ten_bien} không chứa dấu : ; < > (tránh bắt nhầm CSS { color: red; })
_VAR_PATTERN = re.compile(r"\{([^{}:;<>\"'\n]{1,40})\}")
_HTML_TAG_RE = re.compile(r"<\s*(?:html|body|p|div|br|table|span|strong|b|i|u|ul|ol|li|a|h[1-6])\b", re.IGNORECASE)
_SIG_SEP_RE = re.compile(r"^[-_]{3,}\s*$", re.MULTILINE)

_ALLOWED_HTML_TAGS: set[str] = {
    "p",
    "br",
    "div",
    "span",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "ul",
    "ol",
    "li",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "h1",
    "h2",
    "h3",
    "h4",
    "hr",
    "a",
    "img",
}
_ALLOWED_HTML_ATTRS: dict[str, set[str]] = {
    "p": {"style"},
    "div": {"style"},
    "span": {"style"},
    "table": {"style", "cellpadding", "cellspacing", "border"},
    "th": {"style", "colspan", "rowspan"},
    "td": {"style", "colspan", "rowspan"},
    "a": {"href", "style"},
    "img": {"src", "alt", "style", "width", "height"},
    "hr": {"style"},
}
_ALLOWED_URL_SCHEMES: set[str] = {"https", "http", "mailto", "cid", "data"}


def render(template: str, values: dict[str, str]) -> str:
    """Thay thế các biến hợp lệ trong `{...}` bằng giá trị tương ứng."""
    return _VAR_PATTERN.sub(lambda m: values.get(m.group(1).strip(), m.group(0)), template or "")


def unknown_variables(template: str) -> list[str]:
    """Danh sách tên biến không tồn tại (bỏ qua khối CSS có dấu `:` hoặc `;`)."""
    found = {name.strip() for name in _VAR_PATTERN.findall(template or "")}
    return sorted(name for name in found if name and name not in VARIABLES)


def suggest_variable_fix(bad_name: str) -> Optional[str]:
    """Gợi ý biến đúng nếu người dùng gõ có dấu tiếng Việt hoặc tiếng Anh."""
    key = (bad_name or "").strip().lower()
    return _TYPO_MAP.get(key)


def sanitize_html_fragment(raw_html: str, allow_external_images: bool = False) -> str:
    """Làm sạch HTML bằng `nh3` (Rust Ammonia) để triệt tiêu 100% XSS/script/event handler."""
    cleaned = nh3.clean(
        raw_html or "",
        tags=_ALLOWED_HTML_TAGS,
        attributes=_ALLOWED_HTML_ATTRS,
        url_schemes=_ALLOWED_URL_SCHEMES,
        strip_comments=True,
    )
    if not allow_external_images:
        # Chặn tải ảnh từ URL http/https bên ngoài trong khung preview (chống tracking/leak IP)
        cleaned = re.sub(
            r'(<img\b[^>]*\bsrc\s*=\s*["\'])(?:https?://[^"\']*)(["\'])',
            r"\1\2",
            cleaned,
            flags=re.IGNORECASE,
        )
    return cleaned


def build_logo_data_uri(logo_bytes: bytes, mime_type: str = "image/png") -> str:
    """Chuyển ảnh logo thành Data URI để hiển thị trực tiếp trong Live HTML Preview."""
    b64 = base64.b64encode(logo_bytes).decode("ascii")
    safe_mime = mime_type if mime_type.startswith("image/") else "image/png"
    return f"data:{safe_mime};base64,{b64}"


def build_html_body(
    body_text: str,
    logo_src: Optional[str] = None,
    for_preview: bool = False,
) -> str:
    """Dựng tài liệu HTML hoàn chỉnh chuẩn doanh nghiệp (đã sanitize chống XSS).

    - Khi gửi SMTP: truyền `logo_src="cid:company_logo_haesung"`.
    - Khi xem trước trên Web UI: truyền `logo_src="data:image/png;base64,..."` và `for_preview=True`.
    """
    logo_html = (
        f'<div style="margin-top:12px;">'
        f'<img src="{html.escape(logo_src, quote=True)}" alt="Company Logo" '
        f'style="max-height:56px;width:auto;display:block;" />'
        f"</div>"
        if logo_src
        else ""
    )

    text = body_text or ""
    if _HTML_TAG_RE.search(text):
        inner = sanitize_html_fragment(text, allow_external_images=not for_preview)
        body_inner = f"{inner}{logo_html}"
    else:
        parts = _SIG_SEP_RE.split(text, maxsplit=1)
        main_text = parts[0].strip()
        sig_text = parts[1].strip() if len(parts) > 1 else ""

        main_paragraphs = [
            f'<p style="margin:0 0 10px 0;">{html.escape(line)}</p>' if line.strip() else "<br/>"
            for line in main_text.splitlines()
        ]
        main_html = "\n".join(main_paragraphs)

        sig_block = ""
        if sig_text or logo_html:
            sig_lines: list[str] = []
            for idx, line in enumerate(sig_text.splitlines()):
                escaped = html.escape(line)
                if idx == 0:
                    sig_lines.append(
                        f'<div style="font-weight:600;color:#0F4C81;font-size:14px;">{escaped}</div>'
                    )
                else:
                    sig_lines.append(
                        f'<div style="color:#475569;font-size:13px;">{escaped}</div>'
                    )
            sig_inner = "\n".join(sig_lines)
            sig_block = (
                '<div style="margin-top:18px;padding-top:12px;border-top:1px solid #CBD5E1;">'
                f"{sig_inner}{logo_html}</div>"
            )
        body_inner = f"{main_html}{sig_block}"

    csp_meta = (
        "<meta http-equiv=\"Content-Security-Policy\" "
        "content=\"default-src 'none'; img-src data: cid:; style-src 'unsafe-inline';\">"
        if for_preview
        else ""
    )
    return (
        f'<!DOCTYPE html><html><head><meta charset="utf-8">{csp_meta}</head>'
        '<body style="font-family:\'Segoe UI\',Arial,sans-serif;font-size:14px;'
        'line-height:1.6;color:#0F172A;background:#FFFFFF;margin:0;padding:16px;">'
        f"{body_inner}</body></html>"
    )
