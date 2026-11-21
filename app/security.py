"""Quản lý bảo mật Mật khẩu ứng dụng Gmail (Hybrid Zero-Plaintext Vault)."""
import base64
import hashlib
import hmac
import json
import os
import platform
import re
import secrets
from pathlib import Path
from typing import Optional

SAVED_PLACEHOLDER = "******** (Đã lưu an toàn trên máy)"
KEYRING_SERVICE = "GmailAutoMailer_HaesungVina"
_APP_PASS_RE = re.compile(r"^[A-Za-z0-9]{16}$")


def normalize_app_password(raw: str) -> str:
    """Xóa toàn bộ khoảng trắng trong chuỗi mật khẩu ứng dụng."""
    if not raw or raw.strip() == SAVED_PLACEHOLDER:
        return ""
    return re.sub(r"\s+", "", raw)


def is_valid_app_password(password: str) -> bool:
    """Mật khẩu ứng dụng Gmail chuẩn gồm đúng 16 ký tự chữ/số (sau khi bỏ khoảng trắng)."""
    return bool(_APP_PASS_RE.match(password))


def _machine_secret() -> bytes:
    """Khóa dẫn xuất gắn với tài khoản hệ điều hành và tên máy tính hiện tại."""
    user = os.environ.get("USERNAME") or os.environ.get("USER") or "default_user"
    node = platform.node() or "default_node"
    seed = f"GmailAutoMailer::{node}::{user}::HaesungVina".encode("utf-8")
    return hashlib.sha256(seed).digest()


def _xor_keystream(data: bytes, key: bytes, nonce: bytes) -> bytes:
    """Mã hóa/giải mã dòng bằng SHA-256 CTR chuẩn thư viện gốc Python (không cần pip install)."""
    out = bytearray(len(data))
    block_count = (len(data) + 31) // 32
    for counter in range(block_count):
        block = hashlib.sha256(key + nonce + counter.to_bytes(4, "big")).digest()
        start = counter * 32
        end = min(start + 32, len(data))
        for i in range(start, end):
            out[i] = data[i] ^ block[i - start]
    return bytes(out)


def _encrypt_payload(plaintext: str) -> str:
    secret = _machine_secret()
    nonce = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", secret, nonce, 10_000)
    cipher = _xor_keystream(plaintext.encode("utf-8"), key, nonce)
    mac = hmac.new(key, nonce + cipher, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(nonce + mac + cipher).decode("ascii")


def _decrypt_payload(token: str) -> str:
    raw = base64.urlsafe_b64decode(token.encode("ascii"))
    if len(raw) < 48:
        raise ValueError("Invalid vault token")
    nonce, mac, cipher = raw[:16], raw[16:48], raw[48:]
    secret = _machine_secret()
    key = hashlib.pbkdf2_hmac("sha256", secret, nonce, 10_000)
    expected_mac = hmac.new(key, nonce + cipher, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expected_mac):
        raise ValueError("Vault integrity check failed")
    return _xor_keystream(cipher, key, nonce).decode("utf-8")


def _read_vault(vault_path: Path) -> dict[str, str]:
    if not vault_path.is_file():
        return {}
    try:
        token = vault_path.read_text(encoding="utf-8").strip()
        if not token:
            return {}
        data = json.loads(_decrypt_payload(token))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_vault(vault_path: Path, data: dict[str, str]) -> bool:
    try:
        token = _encrypt_payload(json.dumps(data, ensure_ascii=False))
        vault_path.write_text(token, encoding="utf-8")
        return True
    except OSError:
        return False


def save_password(
    sender: str,
    password: str,
    vault_path: Optional[Path] = None,
    use_os_keyring: bool = False,
) -> bool:
    """Lưu mật khẩu ứng dụng an toàn cho tài khoản `sender`."""
    sender_key = sender.strip().lower()
    clean_pw = normalize_app_password(password)
    if not sender_key or not clean_pw:
        return False

    saved = False
    if vault_path is not None:
        records = _read_vault(vault_path)
        records[sender_key] = clean_pw
        saved = _write_vault(vault_path, records)

    if use_os_keyring:
        try:
            import keyring
            keyring.set_password(KEYRING_SERVICE, sender_key, clean_pw)
            saved = True
        except Exception:
            pass
    return saved


def load_password(
    sender: str,
    vault_path: Optional[Path] = None,
    use_os_keyring: bool = False,
) -> str:
    """Đọc mật khẩu ứng dụng đã lưu của tài khoản `sender`."""
    sender_key = sender.strip().lower()
    if not sender_key:
        return ""

    if vault_path is not None:
        records = _read_vault(vault_path)
        if sender_key in records:
            return records[sender_key]

    if use_os_keyring:
        try:
            import keyring
            pw = keyring.get_password(KEYRING_SERVICE, sender_key)
            if pw:
                return normalize_app_password(pw)
        except Exception:
            pass
    return ""
