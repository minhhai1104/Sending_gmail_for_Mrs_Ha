"""Kho bảo mật thông tin đăng nhập bằng Windows DPAPI thuần (Zero Plaintext Secrets).

Sử dụng trực tiếp `ctypes.windll.crypt32.CryptProtectData` & `CryptUnprotectData` của hệ điều hành
Windows — gắn chặt với Master Key tài khoản Windows cục bộ:
- Không phụ thuộc `keyring` bên thứ 3 (không bao giờ lỗi thiếu hiddenimports khi đóng gói .exe).
- Không có bất kỳ khóa mã hóa tĩnh (hardcoded secret) nào trong mã nguồn.
- Lưu tại `%LOCALAPPDATA%\\GmailAutoMailer\\vault.dpapi` (tách biệt hoàn toàn khỏi thư mục cài App).
"""

from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes as wintypes
import json
import os
import sys
from pathlib import Path
from typing import Optional

from ..domain.validation import normalize_app_password
from .paths import get_vault_path

_GITHUB_TOKEN_KEY = "__github_ota_token__"
_CRYPTPROTECT_UI_FORBIDDEN = 0x01


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def _dpapi_protect(plaintext: bytes) -> bytes:
    """Mã hóa byte bằng Windows DPAPI (Current User Scope, không bật UI)."""
    if sys.platform != "win32":
        raise RuntimeError("Windows DPAPI chỉ khả dụng trên hệ điều hành Windows.")

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        wintypes.LPCWSTR,
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p

    buf = ctypes.create_string_buffer(plaintext, len(plaintext))
    blob_in = _DataBlob(len(plaintext), buf)
    blob_out = _DataBlob()

    ok = crypt32.CryptProtectData(
        ctypes.byref(blob_in),
        "GmailAutoMailerVault",
        None,
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(blob_out),
    )
    if not ok:
        raise OSError("CryptProtectData thất bại khi mã hóa kho mật khẩu.")

    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(blob_out.pbData)


def _dpapi_unprotect(ciphertext: bytes) -> bytes:
    """Giải mã byte bằng Windows DPAPI (Current User Scope)."""
    if sys.platform != "win32":
        raise RuntimeError("Windows DPAPI chỉ khả dụng trên hệ điều hành Windows.")

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p

    buf = ctypes.create_string_buffer(ciphertext, len(ciphertext))
    blob_in = _DataBlob(len(ciphertext), buf)
    blob_out = _DataBlob()

    ok = crypt32.CryptUnprotectData(
        ctypes.byref(blob_in),
        None,
        None,
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(blob_out),
    )
    if not ok:
        raise OSError("CryptUnprotectData thất bại (kho mật khẩu hỏng hoặc thuộc tài khoản Windows khác).")

    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(blob_out.pbData)


class DpapiSecretStore:
    """Triển khai SecretStore chuẩn Windows DPAPI với ghi nguyên tử (Atomic Write)."""

    def __init__(self, vault_path: Optional[Path] = None) -> None:
        self._vault_path = vault_path if vault_path is not None else get_vault_path()

    @property
    def vault_path(self) -> Path:
        return self._vault_path

    def _read_records(self) -> dict[str, str]:
        if not self._vault_path.is_file():
            return {}
        try:
            raw_b64 = self._vault_path.read_text(encoding="utf-8").strip()
            if not raw_b64:
                return {}
            cipher = base64.b64decode(raw_b64.encode("ascii"))
            plain = _dpapi_unprotect(cipher)
            data = json.loads(plain.decode("utf-8"))
            return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _write_records(self, records: dict[str, str]) -> bool:
        try:
            self._vault_path.parent.mkdir(parents=True, exist_ok=True)
            plain = json.dumps(records, ensure_ascii=False).encode("utf-8")
            cipher = _dpapi_protect(plain)
            encoded = base64.b64encode(cipher).decode("ascii")
            tmp_path = self._vault_path.with_suffix(".dpapi.tmp")
            tmp_path.write_text(encoded, encoding="utf-8")
            os.replace(tmp_path, self._vault_path)
            return True
        except Exception:
            return False

    def save_password(self, sender: str, password: str) -> bool:
        key = (sender or "").strip().lower()
        clean = normalize_app_password(password)
        if not key or not clean:
            return False
        records = self._read_records()
        records[f"gmail::{key}"] = clean
        return self._write_records(records)

    def load_password(self, sender: str) -> str:
        key = (sender or "").strip().lower()
        if not key:
            return ""
        records = self._read_records()
        return records.get(f"gmail::{key}", "")

    def delete_password(self, sender: str) -> bool:
        key = (sender or "").strip().lower()
        if not key:
            return False
        records = self._read_records()
        full_key = f"gmail::{key}"
        if full_key not in records:
            return True
        del records[full_key]
        return self._write_records(records)

    def has_password(self, sender: str) -> bool:
        return bool(self.load_password(sender))

    def save_github_token(self, token: str) -> bool:
        clean = (token or "").strip()
        if not clean:
            return False
        records = self._read_records()
        records[_GITHUB_TOKEN_KEY] = clean
        return self._write_records(records)

    def load_github_token(self) -> str:
        records = self._read_records()
        return records.get(_GITHUB_TOKEN_KEY, "")

    def delete_github_token(self) -> bool:
        records = self._read_records()
        if _GITHUB_TOKEN_KEY not in records:
            return True
        del records[_GITHUB_TOKEN_KEY]
        return self._write_records(records)

    def has_github_token(self) -> bool:
        return bool(self.load_github_token())
