"""Các giao diện (Protocol) cho Dependency Injection và kiểm thử Headless 0ms."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Optional, Protocol

from ..domain.models import (
    AppConfig,
    GmailSettings,
    HistoryRecord,
    MailPlan,
    PeriodStats,
    ScannedFile,
    SendResult,
    Supplier,
)


class Clock(Protocol):
    """Giao diện đồng hồ để tiêm FakeClock trong pytest (test Pacing/Backoff/ETA 0ms)."""

    def monotonic(self) -> float: ...

    def sleep(self, seconds: float) -> None: ...

    def wait_event(self, event: threading.Event, timeout: float) -> bool: ...


class SystemClock:
    """Đồng hồ hệ thống thực tế."""

    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)

    def wait_event(self, event: threading.Event, timeout: float) -> bool:
        return event.wait(max(0.0, timeout))


class SecretStore(Protocol):
    """Kho lưu trữ bí mật (Windows DPAPI Vault)."""

    def save_password(self, sender: str, password: str) -> bool: ...

    def load_password(self, sender: str) -> str: ...

    def delete_password(self, sender: str) -> bool: ...

    def has_password(self, sender: str) -> bool: ...

    def save_github_token(self, token: str) -> bool: ...

    def load_github_token(self) -> str: ...

    def delete_github_token(self) -> bool: ...

    def has_github_token(self) -> bool: ...


class ConfigRepository(Protocol):
    """Kho lưu trữ cấu hình ứng dụng SSOT (SQLite WAL)."""

    def load_config(self) -> AppConfig: ...

    def save_settings(self, settings: GmailSettings) -> None: ...

    def save_templates(self, subject: str, body: str, excel_name: str, pdf_name: str) -> None: ...

    def save_prefs(
        self,
        *,
        theme: Optional[str] = None,
        onboarding_completed: Optional[bool] = None,
        last_source_dir: Optional[str] = None,
    ) -> None: ...

    def upsert_supplier(self, supplier: Supplier) -> Supplier: ...

    def delete_supplier(self, supplier_id: int) -> bool: ...

    def set_supplier_enabled(self, supplier_id: int, enabled: bool) -> bool: ...


class HistoryRepository(Protocol):
    """Kho lưu trữ & truy vấn lịch sử gửi email (SQLite WAL)."""

    def record(
        self,
        plan: MailPlan,
        result: SendResult,
        month: int,
        year: int,
        kind: str,
        batch_id: str = "",
    ) -> bool: ...

    def sent_supplier_norms(self, month: int, year: int, kind: str) -> set[str]: ...

    def failed_supplier_norms(self, month: int, year: int, kind: str) -> set[str]: ...

    def query_history(
        self,
        month: Optional[int] = None,
        year: Optional[int] = None,
        kind: Optional[str] = None,
        status: Optional[str] = None,
        keyword: str = "",
        limit: int = 500,
    ) -> list[HistoryRecord]: ...

    def period_stats(self, month: int, year: int, kind: Optional[str] = None) -> PeriodStats: ...

    def export_excel(self, dest_path: Path) -> bool: ...


class FileScanner(Protocol):
    """Trình quét tệp đính kèm trên hệ thống tệp."""

    def scan_directory(self, folder: Path) -> list[ScannedFile]: ...

    def scan_paths(self, paths: list[Path]) -> list[ScannedFile]: ...

    def list_period_subfolders(self, root_dir: Path) -> list[str]: ...

    def inspect_file(self, file_path: Path) -> Optional[ScannedFile]: ...


class MailTransport(Protocol):
    """Kênh vận chuyển SMTP (SMTP SSL 465 / STARTTLS 587 hoặc FakeMailTransport trong test)."""

    def test_connection(self, settings: GmailSettings, app_password: str) -> None: ...

    def open_session(self, settings: GmailSettings, app_password: str) -> "MailSession": ...


class MailSession(Protocol):
    """Phiên gửi SMTP dùng lại trong một đợt gửi."""

    def __enter__(self) -> "MailSession": ...

    def __exit__(self, *exc_info: object) -> None: ...

    def send(self, plan: MailPlan, message_id: str) -> SendResult: ...
