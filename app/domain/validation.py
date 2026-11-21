"""Các hàm chuẩn hóa, kiểm tra hợp lệ và lọc thông tin nhạy cảm (Pure Domain)."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from typing import Iterable

from .models import GmailSettings, Supplier

_EMAIL_RE = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$")
_APP_PASS_RE = re.compile(r"^[A-Za-z0-9]{16}$")
_INVALID_SUPPLIER_CHARS = set('/\\:*?"<>|')
_SECRET_PATTERNS = (
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"gho_[A-Za-z0-9]{20,}"),
    re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]{10,}", re.IGNORECASE),
)

GOOGLE_2FA_URL = "https://myaccount.google.com/security"
GOOGLE_APP_PASSWORD_URL = "https://myaccount.google.com/apppasswords"


def normalize_name(name: str) -> str:
    """Chuẩn hóa tên NCC đồng nhất toàn hệ thống (NFC + strip + lower + gộp khoảng trắng)."""
    nfc = unicodedata.normalize("NFC", name or "")
    return re.sub(r"\s+", " ", nfc.strip()).lower()


def normalize_unicode(text: str) -> str:
    """Chuẩn hóa chuỗi sang Unicode NFC."""
    return unicodedata.normalize("NFC", text or "")


def split_emails(text: str) -> list[str]:
    """Tách danh sách email theo ; , khoảng trắng, xuống dòng và khử trùng lặp giữ thứ tự."""
    seen: set[str] = set()
    result: list[str] = []
    for raw in re.split(r"[;,\s]+", text or ""):
        clean = raw.strip()
        if not clean:
            continue
        key = clean.lower()
        if key not in seen:
            seen.add(key)
            result.append(clean)
    return result


def is_valid_email(address: str) -> bool:
    return bool(_EMAIL_RE.match((address or "").strip()))


def normalize_app_password(raw: str) -> str:
    """Loại bỏ toàn bộ khoảng trắng và dấu gạch ngang khi người dùng dán App Password."""
    return re.sub(r"[\s\-]+", "", raw or "")


def is_valid_app_password(password: str) -> bool:
    """Mật khẩu ứng dụng Google gồm đúng 16 ký tự chữ/số không dấu."""
    return bool(_APP_PASS_RE.match(normalize_app_password(password)))


def diagnose_app_password(raw: str) -> tuple[bool, str, str]:
    """Chẩn đoán tức thì chuỗi App Password người dùng dán vào.

    Trả về `(hợp_lệ, chuỗi_đã_làm_sạch, thông_báo_hướng_dẫn)`.
    """
    cleaned = normalize_app_password(raw)
    if not cleaned:
        return False, "", "Chưa nhập Mật khẩu ứng dụng Gmail."
    if not cleaned.isascii() or not cleaned.isalnum():
        return (
            False,
            cleaned,
            "Mật khẩu ứng dụng của Google chỉ gồm 16 chữ cái và chữ số (không có ký tự đặc biệt). "
            "Có vẻ bạn đang nhập mật khẩu đăng nhập Gmail thường.",
        )
    if len(cleaned) != 16:
        return (
            False,
            cleaned,
            f"Mật khẩu ứng dụng Gmail cần đúng 16 ký tự (hiện có {len(cleaned)}/16 ký tự).",
        )
    return True, cleaned, "Định dạng Mật khẩu ứng dụng hợp lệ (16/16 ký tự)."


def validate_supplier(
    name: str,
    recipients: list[str],
    existing_norm_names: set[str],
) -> list[str]:
    """Kiểm tra hợp lệ cho một nhà cung cấp khi thêm/sửa."""
    errors: list[str] = []
    clean_name = normalize_unicode(name).strip()
    if not clean_name:
        errors.append("Tên nhà cung cấp không được để trống.")
        return errors

    if any(ch in _INVALID_SUPPLIER_CHARS for ch in clean_name):
        errors.append('Tên nhà cung cấp chứa ký tự cấm (/ \\ : * ? " < > |).')

    if normalize_name(clean_name) in existing_norm_names:
        errors.append(f"Tên nhà cung cấp bị trùng lặp: {clean_name}")

    if not recipients:
        errors.append("Chưa nhập địa chỉ email người nhận.")
    else:
        for mail in recipients:
            if not is_valid_email(mail):
                errors.append(f"Địa chỉ email không hợp lệ: {mail}")
    return errors


def validate_gmail_settings(settings: GmailSettings, has_password: bool) -> list[str]:
    """Kiểm tra các lỗi cấu hình Gmail khiến không thể gửi mail."""
    issues: list[str] = []
    if not is_valid_email(settings.sender):
        issues.append("Chưa điền hoặc điền sai địa chỉ Gmail dùng để gửi.")
    if not has_password:
        issues.append("Chưa thiết lập Mật khẩu ứng dụng Gmail (16 ký tự).")
    for cc in settings.cc:
        if not is_valid_email(cc):
            issues.append(f"Email CC chung không hợp lệ: {cc}")
    if not (0.0 <= settings.pacing_seconds <= 30.0):
        issues.append("Thời gian giãn cách gửi (Pacing) phải nằm trong khoảng 0 đến 30 giây.")
    if not (0 <= settings.max_retries <= 5):
        issues.append("Số lần tự thử lại khi rớt mạng phải từ 0 đến 5.")
    return issues


def detect_duplicate_emails_across_suppliers(suppliers: list[Supplier]) -> dict[str, list[str]]:
    """Phát hiện địa chỉ email xuất hiện ở >= 2 nhà cung cấp khác nhau (nguy cơ gửi nhầm bảng phí).

    Trả về `{email_lower: [tên_NCC_1, tên_NCC_2, ...]}`.
    """
    email_owners: dict[str, list[str]] = defaultdict(list)
    for sup in suppliers:
        if not sup.enabled:
            continue
        seen_in_sup: set[str] = set()
        for addr in sup.recipients:
            key = addr.strip().lower()
            if key and key not in seen_in_sup:
                seen_in_sup.add(key)
                email_owners[key].append(sup.name)
    return {email: owners for email, owners in email_owners.items() if len(owners) >= 2}


def redact_secrets(text: str, extra_secrets: Iterable[str] = ()) -> str:
    """Che toàn bộ token/mật khẩu nhạy cảm trước khi hiển thị lên UI hoặc ghi log."""
    if not text:
        return ""
    out = text
    for secret in extra_secrets:
        clean = (secret or "").strip()
        if len(clean) >= 6:
            out = out.replace(clean, "[REDACTED]")
    for pattern in _SECRET_PATTERNS:
        if pattern.groups:
            out = pattern.sub(r"\1[REDACTED]", out)
        else:
            out = pattern.sub("[REDACTED]", out)
    return out
