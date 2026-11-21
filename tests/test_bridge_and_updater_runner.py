"""Kiểm thử lớp UiBridge (6 rào chắn bảo mật QA) & tiến trình cập nhật độc lập updater_runner.py."""

from __future__ import annotations

import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import updater_runner
from app.adapters.sqlite_store import SqliteAppStore
from app.application.app_service import AppService
from app.application.batch_runner import BatchRunner
from app.application.dispatch_service import DispatchService
from app.domain.models import GmailSettings, ScannedFile, Supplier
from app.ui.bridge import UiBridge
from tests.conftest import FakeClock, FakeMailTransport, FakeSecretStore, InMemoryFileScanner


class TestUiBridgeSecurityAndFlow:
    def test_bridge_write_only_secrets_url_allowlist_and_native_drop(
        self, store: SqliteAppStore, fake_secrets: FakeSecretStore, fake_clock: FakeClock
    ) -> None:
        fake_secrets.save_password("ha@haesung.vn", "abcd1234efgh5678")
        fake_secrets.save_github_token("ghp_supersecret1234567890")
        store.save_settings(GmailSettings(sender="ha@haesung.vn", display_name="Ms. Ha"))

        for s in store.load_config().suppliers:
            if s.id is not None:
                store.delete_supplier(s.id)
        ace = store.upsert_supplier(Supplier(None, "ACE", ["ace@v.com"]))

        f_ace = ScannedFile(
            Path("C:/drop/Bảng phí kiểm tra, phân loại hàng hóa 09.2026 ACE.xlsx"),
            "Bảng phí kiểm tra, phân loại hàng hóa 09.2026 ACE.xlsx",
            ".xlsx",
            4096,
            "a" * 64,
        )
        scanner = InMemoryFileScanner(files=[f_ace])
        transport = FakeMailTransport()
        app_svc = AppService(store, store, fake_secrets, transport)
        disp_svc = DispatchService(store, store, fake_secrets, scanner, transport)
        runner = BatchRunner(transport, store, clock=fake_clock)

        bridge = UiBridge(app_svc, disp_svc, runner, fake_secrets)
        mock_win = MagicMock()
        bridge.attach_window(mock_win)

        # 1. Write-Only: get_initial_data tuyệt đối không chứa mật khẩu hay token
        init = bridge.get_initial_data()
        init_dump = str(init)
        assert "abcd1234efgh5678" not in init_dump
        assert "ghp_supersecret" not in init_dump
        assert init["settings"]["has_app_password"] is True
        assert init["settings"]["has_github_token"] is True

        # 2. External URL Allowlist
        with patch("webbrowser.open") as wb_open:
            assert bridge.open_external_url("google_app_password")["ok"] is True
            wb_open.assert_called_once()
            assert bridge.open_external_url("https://evil.com")["ok"] is False

        # 3. Native Drag & Drop đẩy sự kiện workspace:updated về JS
        bridge.handle_native_dropped_paths([Path("C:/drop")])
        assert mock_win.evaluate_js.called
        assert "workspace:updated" in mock_win.evaluate_js.call_args[0][0]

        # 4. Candidate index out of bounds bị chặn
        assert bridge.select_candidate_file(ace.id or 1, "excel", 99)["ok"] is False

        # 5. Filter-safe check & Theme toggle
        chk = bridge.check_send_selection([ace.id or 1], [ace.id or 1])
        assert chk["total_selected"] == 1 and chk["needs_filter_confirm"] is False
        assert bridge.set_theme("dark")["theme"] == "dark"


class TestPureStdlibUpdaterRunner:
    def test_execute_update_protects_user_data_and_blocks_zip_slip(self, tmp_path: Path) -> None:
        # Zip Slip bị chặn
        evil_zip = tmp_path / "evil.zip"
        with zipfile.ZipFile(evil_zip, "w") as zf:
            zf.writestr("../escape.exe", b"bad")
        with pytest.raises(RuntimeError, match="Zip Slip"):
            updater_runner.safe_extract_zip(evil_zip, tmp_path / "st")

        # Gói hợp lệ cập nhật --onedir và bỏ qua file dữ liệu người dùng
        pkg = tmp_path / "v3.zip"
        with zipfile.ZipFile(pkg, "w") as zf:
            zf.writestr("Gui_mail_nha_cung_cap.exe", b"NEW_EXE")
            zf.writestr("_internal/app.bin", b"NEW_DLL")
            zf.writestr("app_data.db", b"OVERWRITE_ATTEMPT")
            zf.writestr("vault.dpapi", b"OVERWRITE_ATTEMPT")

        target = tmp_path / "installed"
        target.mkdir()
        (target / "Gui_mail_nha_cung_cap.exe").write_bytes(b"OLD_EXE")
        (target / "app_data.db").write_bytes(b"KEEP_DB")

        ok = updater_runner.execute_update(pkg, target, wait_pid=None, relaunch_exe=None)
        assert ok is True
        assert (target / "Gui_mail_nha_cung_cap.exe").read_bytes() == b"NEW_EXE"
        assert (target / "_internal" / "app.bin").read_bytes() == b"NEW_DLL"
        assert (target / "app_data.db").read_bytes() == b"KEEP_DB"
        assert not (target / "vault.dpapi").exists()
        assert not pkg.exists()
