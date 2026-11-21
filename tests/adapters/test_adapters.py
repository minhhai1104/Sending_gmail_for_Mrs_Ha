"""Kiểm thử tầng Adapters: Windows DPAPI, SQLite WAL, OsFileScanner, SMTP 465/587, OTA Hardening."""

from __future__ import annotations

import io
import json
import smtplib
import sqlite3
import sys
import zipfile
from contextlib import closing
from pathlib import Path
from unittest.mock import MagicMock, patch

import openpyxl
import pytest

from app.adapters.dpapi_vault import DpapiSecretStore
from app.adapters.fs_scanner import OsFileScanner, compute_file_sha256
from app.adapters.ota_updater import (
    UpdateError,
    apply_staged_update,
    compute_sha256,
    download_release_asset,
    is_newer_version,
    safe_extract_zip,
    validate_https_github_url,
    verify_sha256,
)
from app.adapters.smtp_mailer import (
    GmailSmtpTransport,
    MailTransportError,
    build_email_message,
    generate_message_id,
)
from app.adapters.sqlite_store import STATUS_FAIL, STATUS_OK, SqliteAppStore
from app.domain.models import (
    AttachmentMatch,
    FileType,
    GmailSettings,
    MailPlan,
    MatchStatus,
    ReleaseInfo,
    ScannedFile,
    SendErrorKind,
    SendResult,
    Supplier,
)


class TestDpapiVault:
    @pytest.mark.skipif(sys.platform != "win32", reason="Windows DPAPI only")
    def test_dpapi_roundtrip_and_no_plaintext_on_disk(self, tmp_path: Path) -> None:
        vault = DpapiSecretStore(tmp_path / "vault.dpapi")
        assert vault.save_password("Ha@Haesung.vn", "abcd efgh ijkl mnop") is True
        assert vault.has_password("ha@haesung.vn") is True
        assert vault.load_password("HA@HAESUNG.VN") == "abcdefghijklmnop"

        # File trên đĩa tuyệt đối không chứa chuỗi mật khẩu plaintext
        raw_disk = vault.vault_path.read_text(encoding="utf-8")
        assert "abcdefghijklmnop" not in raw_disk
        assert "ha@haesung.vn" not in raw_disk

        assert vault.save_github_token("github_pat_secret_123456") is True
        assert vault.load_github_token() == "github_pat_secret_123456"
        assert vault.delete_github_token() is True
        assert vault.has_github_token() is False

        assert vault.delete_password("ha@haesung.vn") is True
        assert vault.load_password("ha@haesung.vn") == ""

    def test_dpapi_corrupt_file_fails_safely(self, tmp_path: Path) -> None:
        vp = tmp_path / "vault.dpapi"
        vp.write_text("NOT_VALID_BASE64!!!", encoding="utf-8")
        vault = DpapiSecretStore(vp)
        assert vault.load_password("a@b.com") == ""


class TestSqliteAppStore:
    def test_wal_migrations_crud_and_legacy_history_import(self, tmp_path: Path) -> None:
        db_file = tmp_path / "app_data.db"
        store = SqliteAppStore(db_file, seed_defaults=True)

        # Xác nhận WAL & schema_migrations
        with closing(sqlite3.connect(str(db_file))) as conn:
            mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
            assert mode.lower() == "wal"
            ver = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
            assert ver == 1

        cfg = store.load_config()
        assert len(cfg.suppliers) == 7

        # Upsert + Toggle + Delete Supplier
        added = store.upsert_supplier(Supplier(None, "NewCo", ["n@co.com"], aliases=["NC"], note="VIP"))
        assert added.id is not None
        assert store.set_supplier_enabled(added.id, False) is True
        assert store.delete_supplier(added.id) is True

        # Kế thừa history.db từ v2.0
        legacy_db = tmp_path / "history.db"
        with closing(sqlite3.connect(str(legacy_db))) as lconn:
            lconn.execute(
                """CREATE TABLE send_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, sent_at TEXT, month INTEGER, year INTEGER,
                    kind TEXT, supplier TEXT, recipients TEXT, subject TEXT, attachments TEXT,
                    status TEXT, detail TEXT)"""
            )
            lconn.execute(
                "INSERT INTO send_history (sent_at, month, year, kind, supplier, recipients, subject, attachments, status, detail) "
                "VALUES ('2026-09-01 10:00:00', 9, 2026, 'Tạm tính', 'DiaMond', 'd@x.com', 'Sub', 'f.xlsx', 'Thành công', 'OK')"
            )
            lconn.commit()

        assert store.import_legacy_history_db(legacy_db) == 1
        assert store.import_legacy_history_db(legacy_db) == 0  # Idempotent
        # Case-insensitive sent check ("diamond" khớp "DiaMond")
        assert "diamond" in store.sent_supplier_norms(9, 2026, "Tạm tính")

    def test_failed_suppliers_and_excel_export_formula_safety(self, tmp_path: Path) -> None:
        store = SqliteAppStore(tmp_path / "app.db", seed_defaults=False)
        plan_fail = MailPlan(1, "=CMD|evil", True, ["a@x.com"], [], "=1+1", "body")
        plan_ok = MailPlan(2, "ACE", True, ["b@x.com"], [], "Sub", "body")

        store.record(plan_fail, SendResult("=CMD|evil", False, "Timeout", SendErrorKind.TRANSIENT_NETWORK), 9, 2026, "Chốt")
        store.record(plan_ok, SendResult("ACE", False, "Timeout"), 9, 2026, "Chốt")
        store.record(plan_ok, SendResult("ACE", True, "OK"), 9, 2026, "Chốt")

        # ACE đã gửi lại thành công nên KHÔNG còn trong failed_supplier_norms
        assert store.failed_supplier_norms(9, 2026, "Chốt") == {"=cmd|evil"}

        stats = store.period_stats(9, 2026, "Chốt")
        assert stats.total == 3 and stats.ok_count == 1 and stats.fail_count == 2

        xlsx_out = tmp_path / "Lich_su_gui.xlsx"
        assert store.export_excel(xlsx_out) is True
        wb = openpyxl.load_workbook(xlsx_out)
        try:
            ws = wb.active
            assert ws["B2"].value == "09"
            assert ws["B2"].number_format == "@"
            # Chống Formula Injection
            assert str(ws["E2"].value).startswith("'")
            assert str(ws["G2"].value).startswith("'")
            assert ws["I2"].value == STATUS_FAIL
            assert ws["I4"].value == STATUS_OK
        finally:
            wb.close()


class TestOsFileScannerAndSmtp:
    def test_scanner_excludes_junk_and_computes_sha(self, tmp_path: Path) -> None:
        (tmp_path / "2026-09").mkdir()
        f1 = tmp_path / "2026-09" / "ACE.xlsx"
        f1.write_bytes(b"excel-data")
        (tmp_path / "2026-09" / "~$ACE.xlsx").write_bytes(b"lock")

        scanner = OsFileScanner()
        assert scanner.list_period_subfolders(tmp_path) == ["2026-09"]
        scanned = scanner.scan_paths([tmp_path / "2026-09"])
        assert len(scanned) == 1
        assert scanned[0].sha256 == compute_file_sha256(f1)

    def test_toctou_hash_mismatch_blocks_send(self, tmp_path: Path) -> None:
        f = tmp_path / "ACE.xlsx"
        f.write_bytes(b"original-fee-sheet")
        sf = ScannedFile(f, f.name, ".xlsx", f.stat().st_size, sha256=compute_file_sha256(f))
        plan = MailPlan(
            1,
            "ACE",
            True,
            ["ace@x.com"],
            [],
            "Sub",
            "Body",
            attachments=[AttachmentMatch(FileType.EXCEL, f.name, MatchStatus.EXACT, file=sf)],
        )
        # File bị thay đổi nội dung SAU KHI người dùng xem trước!
        f.write_bytes(b"tampered-fee-sheet-for-other-vendor")

        settings = GmailSettings(sender="me@gmail.com", display_name="Me")
        with pytest.raises(MailTransportError) as exc_info:
            build_email_message(settings, plan, message_id=generate_message_id("me@gmail.com"))
        assert exc_info.value.kind == SendErrorKind.ATTACHMENT_CHANGED

    def test_smtp_ssl_fallback_to_starttls_and_partial_refusal(self, tmp_path: Path) -> None:
        f = tmp_path / "ACE.xlsx"
        f.write_bytes(b"excel-content")
        logo = tmp_path / "logo.png"
        logo.write_bytes(b"\x89PNG\r\n\x1a\n1234")
        sf = ScannedFile(f, f.name, ".xlsx", f.stat().st_size, sha256=compute_file_sha256(f))
        settings = GmailSettings(sender="me@gmail.com", display_name="Me", logo_path=str(logo))
        plan = MailPlan(
            1,
            "ACE",
            True,
            ["ok@ace.com", "bad@ace.com"],
            [],
            "Sub",
            "Hello\n---\nSig",
            attachments=[AttachmentMatch(FileType.EXCEL, f.name, MatchStatus.EXACT, file=sf)],
            logo_path=logo,
        )

        mock_tls = MagicMock()
        mock_tls.noop.return_value = (250, b"OK")
        mock_tls.send_message.return_value = {"bad@ace.com": (550, b"User unknown")}

        with (
            patch("smtplib.SMTP_SSL", side_effect=OSError("Port 465 blocked by firewall")),
            patch("smtplib.SMTP", return_value=mock_tls) as smtp_cls,
        ):
            transport = GmailSmtpTransport()
            with transport.open_session(settings, "abcd1234efgh5678") as sess:
                res = sess.send(plan, message_id=generate_message_id("me@gmail.com"))

        smtp_cls.assert_called_once()
        mock_tls.starttls.assert_called_once()
        assert res.ok is False
        assert res.error_kind == SendErrorKind.PARTIAL_REFUSED
        assert res.accepted_recipients == ("ok@ace.com",)
        assert res.refused_recipients == ("bad@ace.com",)

    def test_smtp_auth_error_closes_socket(self) -> None:
        mock_ssl = MagicMock()
        mock_ssl.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Bad credentials")
        settings = GmailSettings(sender="me@gmail.com")
        with patch("smtplib.SMTP_SSL", return_value=mock_ssl):
            with pytest.raises(MailTransportError) as exc_info:
                GmailSmtpTransport().test_connection(settings, "wrong")
        assert exc_info.value.kind == SendErrorKind.AUTH
        assert mock_ssl.quit.called or mock_ssl.close.called


class TestOtaHardening:
    def test_mandatory_sha256_and_domain_allowlist(self, tmp_path: Path) -> None:
        sample = tmp_path / "pkg.zip"
        sample.write_bytes(b"hello")
        good_hash = compute_sha256(sample)

        # Rỗng hoặc sai độ dài -> PHẢI trả False
        assert verify_sha256(sample, "") is False
        assert verify_sha256(sample, "short") is False
        assert verify_sha256(sample, good_hash) is True
        assert is_newer_version("3.0.0", "2.0.0") is True

        # Khóa domain allowlist
        validate_https_github_url("https://github.com/minhhai1104/Sending_gmail_for_Mrs_Ha/releases/download/v3.0.0/app.zip")
        with pytest.raises(UpdateError):
            validate_https_github_url("http://github.com/evil.zip")
        with pytest.raises(UpdateError):
            validate_https_github_url("https://evil.example.com/app.zip")

        # Từ chối tải nếu thiếu SHA-256
        rel_no_sha = ReleaseInfo("3.1.0", "https://github.com/a/b.zip", "", "notes", "b.zip")
        with pytest.raises(UpdateError, match="SHA-256"):
            download_release_asset(rel_no_sha, tmp_path)

    def test_zip_slip_protected_items_and_rollback(self, tmp_path: Path) -> None:
        evil_zip = tmp_path / "evil.zip"
        with zipfile.ZipFile(evil_zip, "w") as zf:
            zf.writestr("../../outside.exe", b"pwned")
        with pytest.raises(UpdateError, match="Zip Slip"):
            safe_extract_zip(evil_zip, tmp_path / "stage1")

        good_zip = tmp_path / "good.zip"
        with zipfile.ZipFile(good_zip, "w") as zf:
            zf.writestr("Gui_mail_nha_cung_cap.exe", b"new-bin")
            zf.writestr("app_data.db", b"should-be-ignored")
            zf.writestr("vault.dpapi", b"should-be-ignored")

        stage = tmp_path / "stage2"
        extracted = safe_extract_zip(good_zip, stage)
        assert [p.name for p in extracted] == ["Gui_mail_nha_cung_cap.exe"]

        target = tmp_path / "install"
        target.mkdir()
        (target / "Gui_mail_nha_cung_cap.exe").write_bytes(b"old-bin")
        (target / "app_data.db").write_bytes(b"user-data")
        apply_staged_update(stage, target)
        assert (target / "Gui_mail_nha_cung_cap.exe").read_bytes() == b"new-bin"
        assert (target / "app_data.db").read_bytes() == b"user-data"

    def test_check_for_update_and_download_verified_sha256(self, tmp_path: Path) -> None:
        from app.adapters.ota_updater import check_for_update, spawn_standalone_updater

        pkg_bytes = b"PK\x03\x04dummy-zip-payload"
        pkg_file = tmp_path / "expected.zip"
        pkg_file.write_bytes(pkg_bytes)
        expected_sha = compute_sha256(pkg_file)

        api_payload = {
            "tag_name": "v3.1.0",
            "published_at": "2026-12-01T00:00:00Z",
            "body": f"Release notes\nSHA256: {expected_sha}",
            "assets": [
                {
                    "name": "Gui_mail_nha_cung_cap_v3.1.0.zip",
                    "browser_download_url": "https://github.com/minhhai1104/Sending_gmail_for_Mrs_Ha/releases/download/v3.1.0/pkg.zip",
                    "url": "https://api.github.com/repos/minhhai1104/Sending_gmail_for_Mrs_Ha/releases/assets/99",
                }
            ],
        }

        class _FakeResp(io.BytesIO):
            def __init__(self, data: bytes, headers: dict[str, str] | None = None) -> None:
                super().__init__(data)
                self.headers = headers or {"Content-Length": str(len(data))}

            def __enter__(self) -> "_FakeResp":
                return self

            def __exit__(self, *args: object) -> None:
                self.close()

        with patch(
            "urllib.request.urlopen",
            return_value=_FakeResp(json.dumps(api_payload).encode("utf-8")),
        ):
            rel = check_for_update("3.0.0", token="ghp_testtoken1234567890")
            assert rel is not None and rel.version == "3.1.0" and rel.sha256 == expected_sha

        progress_ticks: list[tuple[int, int]] = []
        with patch("urllib.request.urlopen", return_value=_FakeResp(pkg_bytes)):
            downloaded = download_release_asset(
                rel, tmp_path / "dl", on_progress=lambda a, b: progress_ticks.append((a, b))
            )
            assert downloaded.is_file() and progress_ticks[-1][0] == len(pkg_bytes)

        # Kiểm tra lệch SHA-256 bị xóa và báo lỗi
        bad_rel = ReleaseInfo("3.1.0", rel.download_url, "0" * 64, "notes", "bad.zip")
        with patch("urllib.request.urlopen", return_value=_FakeResp(pkg_bytes)):
            with pytest.raises(UpdateError, match="SHA-256"):
                download_release_asset(bad_rel, tmp_path / "dl_bad")
            assert not (tmp_path / "dl_bad" / "bad.zip").exists()

        # Kiểm tra spawn_standalone_updater dùng Popen mock (copy updater.exe ra %TEMP%)
        app_dir = tmp_path / "appdir"
        app_dir.mkdir()
        (app_dir / "updater.exe").write_bytes(b"fake-exe")
        with patch("subprocess.Popen") as popen_mock:
            spawn_standalone_updater(downloaded, target_dir=app_dir, current_pid=1234, relaunch_exe=app_dir / "main.exe")
            popen_mock.assert_called_once()
            spawned_args = popen_mock.call_args[0][0]
            assert "updater_exec.exe" in spawned_args[0]
            assert "--relaunch" in spawned_args

    def test_paths_module_env_override(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.adapters import paths

        monkeypatch.setenv("GMAIL_MAILER_DATA_DIR", str(tmp_path / "custom_data"))
        assert paths.get_user_data_dir() == tmp_path / "custom_data"
        assert paths.get_db_path().name == "app_data.db"
        assert paths.get_vault_path().name == "vault.dpapi"
        assert paths.get_webview_storage_dir().is_dir()
        assert paths.get_logos_dir().is_dir()
        assert paths.get_exports_dir().is_dir()
        assert paths.get_web_ui_dir().name == "web"
        assert paths.get_icon_path().name == "app_icon.ico"

    def test_smtp_error_classifications_and_scanner_edges(self, tmp_path: Path) -> None:
        from app.adapters.smtp_mailer import classify_smtp_error

        scanner = OsFileScanner()
        assert scanner.scan_directory(tmp_path / "missing_dir") == []
        assert scanner.list_period_subfolders(tmp_path / "missing_dir") == []
        assert scanner.inspect_file(tmp_path / "nope.xlsx") is None

        single = tmp_path / "one.pdf"
        single.write_bytes(b"%PDF-1.4")
        assert len(scanner.scan_paths([single, tmp_path / "nope.pdf"])) == 1

        k1, _ = classify_smtp_error(smtplib.SMTPRecipientsRefused({"x@y.com": (550, b"no")}))
        assert k1 == SendErrorKind.RECIPIENT_REFUSED
        k2, _ = classify_smtp_error(smtplib.SMTPException("temp"))
        assert k2 == SendErrorKind.TRANSIENT_NETWORK
        k3, _ = classify_smtp_error(OSError("net down"))
        assert k3 == SendErrorKind.TRANSIENT_NETWORK
        k4, _ = classify_smtp_error(ValueError("weird"))
        assert k4 == SendErrorKind.UNKNOWN

        # Missing attachment file raises ATTACHMENT_IO
        missing_sf = ScannedFile(tmp_path / "gone.xlsx", "gone.xlsx", ".xlsx", 100, "a" * 64)
        plan = MailPlan(
            1,
            "ACE",
            True,
            ["a@v.com"],
            ["cc@v.com"],
            "Sub",
            "Body",
            attachments=[AttachmentMatch(FileType.EXCEL, "gone.xlsx", MatchStatus.EXACT, file=missing_sf)],
        )
        with pytest.raises(MailTransportError) as ei:
            build_email_message(GmailSettings(sender="me@gmail.com"), plan, generate_message_id("me@gmail.com"))
        assert ei.value.kind == SendErrorKind.ATTACHMENT_IO

