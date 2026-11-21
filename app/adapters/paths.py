"""Quản lý đường dẫn chuẩn Windows (%LOCALAPPDATA% cho dữ liệu người dùng, tách khỏi thư mục cài app)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

DATA_DIR_NAME = "GmailAutoMailer"


def get_app_dir() -> Path:
    """Thư mục chứa file thực thi (hoặc gốc mã nguồn khi chạy dev)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def get_resource_dir() -> Path:
    """Thư mục chứa tài nguyên đóng gói kèm ứng dụng (web UI, icon)."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent.parent.parent


def get_user_data_dir() -> Path:
    """Thư mục dữ liệu riêng của người dùng Windows (`%LOCALAPPDATA%\\GmailAutoMailer`).

    Tách biệt hoàn toàn khỏi thư mục cài đặt ứng dụng để:
    - Không bị mất dữ liệu khi cài đè hoặc cập nhật OTA.
    - Không bị lỗi thiếu quyền ghi trên Windows.
    - Copy thư mục cài app sang USB/Google Drive không bao giờ mang theo mật khẩu DPAPI.
    """
    override = os.environ.get("GMAIL_MAILER_DATA_DIR", "").strip()
    if override:
        base = Path(override)
    else:
        local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
        if local_app_data:
            base = Path(local_app_data) / DATA_DIR_NAME
        else:
            base = Path.home() / f".{DATA_DIR_NAME.lower()}"
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_db_path() -> Path:
    return get_user_data_dir() / "app_data.db"


def get_vault_path() -> Path:
    return get_user_data_dir() / "vault.dpapi"


def get_webview_storage_dir() -> Path:
    path = get_user_data_dir() / "webview"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_logos_dir() -> Path:
    path = get_user_data_dir() / "logos"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_exports_dir() -> Path:
    path = get_user_data_dir() / "exports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_default_attach_dir() -> Path:
    """Thư mục đính kèm mặc định (ưu tiên Documents\\BaoCao_NCC, gọn gàng thân thiện)."""
    docs = Path.home() / "Documents"
    base = docs if docs.is_dir() else get_user_data_dir()
    return base / "BaoCao_NhaCungCap"


def get_web_ui_dir() -> Path:
    res = get_resource_dir()
    candidate = res / "app" / "ui" / "web"
    if candidate.is_dir():
        return candidate
    return Path(__file__).resolve().parent.parent / "ui" / "web"


def get_icon_path() -> Path:
    res = get_resource_dir()
    for candidate in (
        res / "assets" / "app_icon.ico",
        get_app_dir() / "assets" / "app_icon.ico",
    ):
        if candidate.is_file():
            return candidate
    return res / "assets" / "app_icon.ico"
