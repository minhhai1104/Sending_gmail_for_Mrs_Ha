"""Shared pytest fixtures: FakeClock, FakeSecretStore, FakeMailTransport, InMemoryFileScanner."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, Optional

import pytest

from app.adapters.smtp_mailer import MailTransportError
from app.adapters.sqlite_store import SqliteAppStore
from app.domain.models import (
    GmailSettings,
    MailPlan,
    ScannedFile,
    SendErrorKind,
    SendResult,
)


class FakeClock:
    """Đồng hồ giả lập giúp kiểm thử Pacing, Exponential Backoff, Pause & ETA trong 0ms."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start
        self.sleeps: list[float] = []
        self.waits: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def wait_event(self, event: threading.Event, timeout: float) -> bool:
        self.waits.append(timeout)
        if event.is_set():
            return True
        self.now += timeout
        return event.is_set()


class FakeSecretStore:
    """Kho mật khẩu trong RAM cho unit test (0ms, không chạm đĩa)."""

    def __init__(self) -> None:
        self._passwords: dict[str, str] = {}
        self._gh_token: str = ""

    def save_password(self, sender: str, password: str) -> bool:
        key = sender.strip().lower()
        if not key or not password:
            return False
        self._passwords[key] = password
        return True

    def load_password(self, sender: str) -> str:
        return self._passwords.get(sender.strip().lower(), "")

    def delete_password(self, sender: str) -> bool:
        self._passwords.pop(sender.strip().lower(), None)
        return True

    def has_password(self, sender: str) -> bool:
        return bool(self.load_password(sender))

    def save_github_token(self, token: str) -> bool:
        self._gh_token = token.strip()
        return bool(self._gh_token)

    def load_github_token(self) -> str:
        return self._gh_token

    def delete_github_token(self) -> bool:
        self._gh_token = ""
        return True

    def has_github_token(self) -> bool:
        return bool(self._gh_token)


class FakeMailSession:
    def __init__(
        self,
        sent_log: list[tuple[MailPlan, str]],
        handler: Optional[Callable[[MailPlan, str, int], SendResult]] = None,
    ) -> None:
        self._sent_log = sent_log
        self._handler = handler
        self._attempts: dict[str, int] = {}

    def __enter__(self) -> "FakeMailSession":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def send(self, plan: MailPlan, message_id: str) -> SendResult:
        attempt = self._attempts.get(plan.supplier, 0) + 1
        self._attempts[plan.supplier] = attempt
        self._sent_log.append((plan, message_id))
        if self._handler is not None:
            return self._handler(plan, message_id, attempt)
        return SendResult(
            supplier=plan.supplier,
            ok=True,
            message="Đã gửi thành công (250 OK)",
            error_kind=SendErrorKind.NONE,
            accepted_recipients=tuple(plan.recipients),
            message_id=message_id,
        )


class FakeMailTransport:
    def __init__(
        self,
        *,
        fail_connect: Optional[Exception] = None,
        send_handler: Optional[Callable[[MailPlan, str, int], SendResult]] = None,
    ) -> None:
        self.fail_connect = fail_connect
        self.send_handler = send_handler
        self.sent_log: list[tuple[MailPlan, str]] = []
        self.test_connections = 0

    def test_connection(self, settings: GmailSettings, app_password: str) -> None:
        self.test_connections += 1
        if self.fail_connect is not None:
            raise self.fail_connect
        if app_password != "abcd1234efgh5678":
            raise MailTransportError("Sai mật khẩu ứng dụng.", SendErrorKind.AUTH)

    def open_session(self, settings: GmailSettings, app_password: str) -> FakeMailSession:
        if self.fail_connect is not None:
            raise self.fail_connect
        return FakeMailSession(self.sent_log, self.send_handler)


class InMemoryFileScanner:
    def __init__(self, files: Optional[list[ScannedFile]] = None, subfolders: Optional[list[str]] = None) -> None:
        self.files = list(files or [])
        self.subfolders = list(subfolders or [])

    def scan_directory(self, folder: Path) -> list[ScannedFile]:
        return list(self.files)

    def scan_paths(self, paths: list[Path]) -> list[ScannedFile]:
        return list(self.files)

    def list_period_subfolders(self, root_dir: Path) -> list[str]:
        return list(self.subfolders)

    def inspect_file(self, file_path: Path) -> Optional[ScannedFile]:
        for f in self.files:
            if f.path == file_path:
                return f
        return ScannedFile(
            path=file_path,
            name=file_path.name,
            ext=file_path.suffix.lower(),
            size_bytes=2048,
            sha256="a" * 64,
        )


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def fake_secrets() -> FakeSecretStore:
    return FakeSecretStore()


@pytest.fixture
def store(tmp_path: Path) -> SqliteAppStore:
    return SqliteAppStore(db_path=tmp_path / "app_data.db", seed_defaults=True)
