import csv
import smtplib
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "vendor") not in sys.path:
    sys.path.append(str(ROOT / "vendor"))

from openpyxl import load_workbook  # noqa: E402

from app import config, history, mailer, security  # noqa: E402
from app.planner import (  # noqa: E402
    KIND_DRAFT,
    KIND_FINAL,
    MAX_TOTAL_ATTACHMENT_BYTES,
    build_plans,
)
from app.templating import render, unknown_variables  # noqa: E402


class TemplatingTests(unittest.TestCase):
    def test_render_and_unknown(self):
        self.assertEqual(
            render("A {thang}/{nam} {x}", {"thang": "09", "nam": "2026"}),
            "A 09/2026 {x}",
        )
        self.assertEqual(unknown_variables("{thang} {sai} {nam}"), ["sai"])


class ConfigAndSecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_split_emails_and_validation(self):
        self.assertEqual(
            config.split_emails("a@x.com; b@x.com\nc@x.com, d@x.com"),
            ["a@x.com", "b@x.com", "c@x.com", "d@x.com"],
        )
        self.assertTrue(config.is_valid_email("a.b@x.com"))
        self.assertFalse(config.is_valid_email("a@x"))

    def test_app_password_length_validation(self):
        s_short = config.Settings(
            sender="me@gmail.com",
            display_name="Me",
            app_password="shortpassword",
            attach_dir="Dinh_kem",
        )
        probs = s_short.problems()
        self.assertTrue(any("16 ký tự" in p for p in probs))

        s_valid = config.Settings(
            sender="me@gmail.com",
            display_name="Me",
            app_password="abcdefghijklmnop",
            attach_dir="Dinh_kem",
        )
        self.assertEqual(s_valid.problems(), [])

    def test_hybrid_password_vault_masks_excel_and_reloads(self):
        cfg_path = self.tmp_path / "Cau_hinh.xlsx"
        vault_path = self.tmp_path / ".vault.dat"
        config.create_default_config(cfg_path)

        wb = load_workbook(cfg_path)
        gmail = wb[config.SHEET_GMAIL]
        gmail["B4"] = "me@gmail.com"
        gmail["B6"] = "abcd efgh ijkl mnop"
        wb.save(cfg_path)
        wb.close()

        # Lần đọc đầu tiên: tự động lưu vào vault và che mật khẩu trong file Excel
        cfg1 = config.load_config(cfg_path, vault_path=vault_path)
        self.assertEqual(cfg1.settings.app_password, "abcdefghijklmnop")

        wb_check = load_workbook(cfg_path)
        cell_val = wb_check[config.SHEET_GMAIL]["B6"].value
        wb_check.close()
        self.assertEqual(cell_val, security.SAVED_PLACEHOLDER)

        # Lần đọc thứ hai: dù Excel chỉ chứa placeholder nhưng vẫn nạp đúng mật khẩu từ vault
        cfg2 = config.load_config(cfg_path, vault_path=vault_path)
        self.assertEqual(cfg2.settings.app_password, "abcdefghijklmnop")

    def test_corrupted_excel_raises_friendly_config_error(self):
        bad_path = self.tmp_path / "Broken.xlsx"
        bad_path.write_bytes(b"not a valid zip or xlsx file")
        with self.assertRaises(config.ConfigError) as ctx:
            config.load_config(bad_path)
        self.assertIn("hỏng hoặc không đúng định dạng", str(ctx.exception))

    def test_non_destructive_excel_migration(self):
        cfg_path = self.tmp_path / "Cau_hinh.xlsx"
        config.create_default_config(cfg_path)

        # Giả lập file cấu hình cũ bị thiếu dòng CC chung và có dữ liệu NCC riêng của người dùng
        wb = load_workbook(cfg_path)
        gmail = wb[config.SHEET_GMAIL]
        gmail.delete_rows(8, 1)  # xóa dòng LBL_CC
        sup = wb[config.SHEET_SUPPLIERS]
        sup["B4"] = "NCC_RIENG_CUA_TOI"
        sup["C4"] = "custom@vendor.vn"
        wb.save(cfg_path)
        wb.close()

        migrated = config.migrate_config_if_needed(cfg_path)
        self.assertTrue(migrated)

        cfg = config.load_config(cfg_path, vault_path=self.tmp_path / ".vault.dat")
        self.assertEqual(cfg.suppliers[0].name, "NCC_RIENG_CUA_TOI")
        self.assertEqual(cfg.suppliers[0].recipients, ["custom@vendor.vn"])


class PlanAndMailTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        self.tmp_path = tmp
        self.cfg_path = tmp / "Cau_hinh.xlsx"
        self.vault_path = tmp / ".vault.dat"
        config.create_default_config(self.cfg_path)

        wb = load_workbook(self.cfg_path)
        gmail = wb[config.SHEET_GMAIL]
        gmail["B4"] = "me@gmail.com"
        gmail["B6"] = "abcd efgh ijkl mnop"
        gmail["B7"] = str(tmp / "dk" / "{nam}-{thang}")
        gmail["B8"] = "boss@x.com"
        sup = wb[config.SHEET_SUPPLIERS]
        sup["C4"] = "ace1@x.com; ace2@x.com"   # ACE
        sup["C5"] = "ahc@x.com"                # AHC
        sup["A6"] = "Không"                    # T&T tắt
        wb.save(self.cfg_path)
        wb.close()

        self.attach = tmp / "dk" / "2026-09"
        self.attach.mkdir(parents=True)
        for name in (
            "Bảng phí kiểm tra, phân loại hàng hóa 09.2026 ACE.xlsx",
            "Bảng phí kiểm tra, phân loại hàng hóa 09.2026 AHC.xlsx",
            "PO ACE 09.2026.pdf",
        ):
            (self.attach / name).write_bytes(b"valid attachment content")
        self.cfg = config.load_config(self.cfg_path, vault_path=self.vault_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_load_config(self):
        self.assertEqual(self.cfg.settings.app_password, "abcdefghijklmnop")
        self.assertEqual(len(self.cfg.suppliers), 7)
        self.assertEqual(self.cfg.suppliers[0].recipients, ["ace1@x.com", "ace2@x.com"])
        self.assertFalse(self.cfg.suppliers[2].enabled)
        self.assertEqual(self.cfg.settings.problems(), [])

    def test_draft_attaches_only_excel(self):
        plan = build_plans(self.cfg, 9, 2026, KIND_DRAFT)[0]
        self.assertEqual(
            plan.subject,
            "Bảng phí kiểm tra, phân loại hàng hóa tháng 09 năm 2026 - ACE - Tạm tính",
        )
        self.assertEqual(
            [a.name for a in plan.attachments],
            ["Bảng phí kiểm tra, phân loại hàng hóa 09.2026 ACE.xlsx"],
        )
        self.assertTrue(plan.sendable)
        self.assertIn("tháng 09 năm 2026", plan.body)

    def test_final_attaches_excel_and_pdf(self):
        ace, ahc, tnt, *_ = build_plans(self.cfg, 9, 2026, KIND_FINAL)
        self.assertEqual(
            [a.name for a in ace.attachments],
            [
                "Bảng phí kiểm tra, phân loại hàng hóa 09.2026 ACE.xlsx",
                "PO ACE 09.2026.pdf",
            ],
        )
        self.assertTrue(ace.sendable)
        self.assertFalse(ahc.sendable)  # thiếu PDF của AHC
        self.assertIn("Không tìm thấy file: PO AHC 09.2026.pdf", ahc.errors)
        self.assertEqual(tnt.state, "off")

    def test_missing_recipients_flagged(self):
        plans = build_plans(self.cfg, 9, 2026, KIND_DRAFT)
        diamond = next(p for p in plans if p.supplier == "DiaMond")
        self.assertIn("Chưa điền mail người nhận.", diamond.errors)

    def test_edge_cases_empty_file_oversized_duplicate_and_invalid_supplier_name(self):
        # 1. File rỗng 0 byte
        empty_excel = self.attach / "Bảng phí kiểm tra, phân loại hàng hóa 09.2026 AHC.xlsx"
        empty_excel.write_bytes(b"")
        plans = build_plans(self.cfg, 9, 2026, KIND_DRAFT)
        ahc = next(p for p in plans if p.supplier == "AHC")
        self.assertFalse(ahc.sendable)
        self.assertTrue(any("rỗng (0 KB)" in e for e in ahc.errors))

        # 2. Trùng tên nhà cung cấp & tên chứa ký tự đường dẫn '/'
        self.cfg.suppliers.append(config.Supplier(name="ACE", recipients=["dup@x.com"]))
        self.cfg.suppliers.append(config.Supplier(name="Bad/Supplier", recipients=["bad@x.com"]))
        plans2 = build_plans(self.cfg, 9, 2026, KIND_DRAFT)
        ace_plans = [p for p in plans2 if p.supplier == "ACE"]
        self.assertEqual(len(ace_plans), 2)
        self.assertTrue(any("trùng lặp" in e for e in ace_plans[1].errors))

        bad_plan = next(p for p in plans2 if p.supplier == "Bad/Supplier")
        self.assertTrue(any("ký tự không hợp lệ" in e for e in bad_plan.errors))

        # 3. File vượt quá giới hạn dung lượng đính kèm
        ace_file = self.attach / "Bảng phí kiểm tra, phân loại hàng hóa 09.2026 ACE.xlsx"
        with mock.patch("pathlib.Path.stat") as mock_stat:
            st = mock.MagicMock()
            st.st_size = MAX_TOTAL_ATTACHMENT_BYTES + 1024
            st.st_mode = 0o100644
            mock_stat.return_value = st
            plans3 = build_plans(self.cfg, 9, 2026, KIND_DRAFT)
            ace3 = plans3[0]
            self.assertTrue(any("vượt quá giới hạn" in e for e in ace3.errors))
        self.assertTrue(ace_file.exists())

    def test_build_message(self):
        plan = build_plans(self.cfg, 9, 2026, KIND_FINAL)[0]
        msg = mailer.build_message(self.cfg.settings, plan)
        self.assertEqual(
            [a.addr_spec for a in msg["To"].addresses], ["ace1@x.com", "ace2@x.com"]
        )
        self.assertEqual(msg["Cc"].addresses[0].addr_spec, "boss@x.com")
        self.assertEqual(
            [p.get_filename() for p in msg.iter_attachments()],
            [
                "Bảng phí kiểm tra, phân loại hàng hóa 09.2026 ACE.xlsx",
                "PO ACE 09.2026.pdf",
            ],
        )

    def test_send_plans_uses_smtp_and_continues_after_error(self):
        plans = [p for p in build_plans(self.cfg, 9, 2026, KIND_DRAFT) if p.sendable]
        self.assertEqual([p.supplier for p in plans], ["ACE", "AHC"])
        with mock.patch("smtplib.SMTP_SSL") as smtp:
            server = smtp.return_value
            server.send_message.side_effect = [{}, OSError("boom")]
            results = mailer.send_plans(
                self.cfg.settings, plans, pacing_delay=0.0, max_retries=0
            )
        server.login.assert_called_once_with("me@gmail.com", "abcdefghijklmnop")
        self.assertEqual([r.ok for r in results], [True, False])

    def test_chaos_partial_recipient_refusal_not_marked_as_success(self):
        plans = [p for p in build_plans(self.cfg, 9, 2026, KIND_DRAFT) if p.sendable]
        with mock.patch("smtplib.SMTP_SSL") as smtp:
            server = smtp.return_value
            # send_message trả về dict địa chỉ bị từ chối chứ không raise exception
            server.send_message.return_value = {"ace2@x.com": (550, b"User unknown")}
            results = mailer.send_plans(
                self.cfg.settings, [plans[0]], pacing_delay=0.0
            )
        self.assertFalse(results[0].ok)
        self.assertIn("ace2@x.com", results[0].message)

    def test_chaos_reconnect_failure_does_not_abort_remaining_plans(self):
        plans = [p for p in build_plans(self.cfg, 9, 2026, KIND_DRAFT) if p.sendable]
        with mock.patch("smtplib.SMTP_SSL") as smtp:
            server1 = mock.MagicMock()
            server1.send_message.side_effect = smtplib.SMTPServerDisconnected("lost")
            server2 = mock.MagicMock()
            server2.send_message.return_value = {}
            # Lần 1: connect đầu tiên thành công; Lần 2: reconnect của ACE thất bại; Lần 3: reconnect cho AHC thành công
            smtp.side_effect = [server1, OSError("network still down"), server2]
            results = mailer.send_plans(
                self.cfg.settings, plans, pacing_delay=0.0, max_retries=0
            )
        self.assertEqual(len(results), 2)
        self.assertFalse(results[0].ok)
        self.assertTrue(results[1].ok)

    def test_chaos_missing_attachment_during_send_reports_file_error_not_internet_error(self):
        plan = build_plans(self.cfg, 9, 2026, KIND_DRAFT)[0]
        # Xóa file đính kèm ngay sau khi đã build_plans (giả lập file bị xóa/khóa khi đang ở màn hình Preview)
        plan.attachments[0].path.unlink()
        with mock.patch("smtplib.SMTP_SSL") as smtp:
            server = smtp.return_value
            server.send_message.return_value = {}
            results = mailer.send_plans(
                self.cfg.settings, [plan], pacing_delay=0.0, max_retries=0
            )
        self.assertFalse(results[0].ok)
        self.assertIn("file đính kèm", results[0].message.lower())
        self.assertNotIn("internet", results[0].message.lower())

    def test_chaos_login_failure_closes_ssl_socket(self):
        with mock.patch("smtplib.SMTP_SSL") as smtp:
            server = smtp.return_value
            server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Bad auth")
            with self.assertRaises(mailer.MailError):
                mailer.test_connection(self.cfg.settings)
            server.close.assert_called_once()

    def test_flow_control_cancel_event_stops_batch(self):
        plans = [p for p in build_plans(self.cfg, 9, 2026, KIND_DRAFT) if p.sendable]
        cancel_event = threading.Event()

        def on_result(plan, result):
            cancel_event.set()  # Hủy ngay sau khi gửi xong nhà cung cấp đầu tiên

        with mock.patch("smtplib.SMTP_SSL") as smtp:
            server = smtp.return_value
            server.send_message.return_value = {}
            results = mailer.send_plans(
                self.cfg.settings,
                plans,
                on_result=on_result,
                pacing_delay=0.0,
                cancel_event=cancel_event,
            )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].supplier, "ACE")


class HistorySQLiteAndCSVTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.csv_path = self.tmp_path / "Lich_su_gui.csv"
        self.db_path = self.tmp_path / "history.db"

    def tearDown(self):
        self.tmp.cleanup()

    def _dummy_plan(self, supplier: str = "ACE") -> mailer.MailPlan:
        return mailer.MailPlan(
            supplier=supplier,
            enabled=True,
            recipients=["ace@x.com"],
            cc=[],
            subject="Subject",
            body="Body",
            attachments=[],
        )

    def test_sqlite_record_and_csv_sync(self):
        plan = self._dummy_plan("ACE")
        res = mailer.SendResult("ACE", True, "Đã gửi")
        ok = history.record(
            plan, res, 9, 2026, KIND_DRAFT,
            csv_path=self.csv_path, db_path=self.db_path
        )
        self.assertTrue(ok)
        self.assertTrue(self.db_path.exists())
        self.assertTrue(self.csv_path.exists())
        self.assertEqual(
            history.sent_suppliers(9, 2026, KIND_DRAFT, csv_path=self.csv_path, db_path=self.db_path),
            {"ACE"},
        )

    def test_excel_leading_zero_strip_in_csv_still_recognized(self):
        # Giả lập file CSV bị Microsoft Excel cắt số 0 ở cột Tháng ("09" -> "9") rồi lưu lại
        with open(self.csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(history._COLUMNS)
            writer.writerow([
                "2026-09-30 10:00:00",
                "9",  # Excel tự đổi "09" thành "9"
                "2026",
                KIND_DRAFT,
                "AHC",
                "ahc@x.com",
                "Tiêu đề",
                "file.xlsx",
                "Thành công",
                "Đã gửi",
            ])

        sent = history.sent_suppliers(
            9, 2026, KIND_DRAFT, csv_path=self.csv_path, db_path=self.db_path
        )
        self.assertIn("AHC", sent)

    def test_csv_locked_by_excel_still_saves_to_sqlite_without_data_loss(self):
        plan = self._dummy_plan("Mansa")
        res = mailer.SendResult("Mansa", True, "Đã gửi")
        with mock.patch("app.history._append_csv_row", side_effect=PermissionError("Locked by Excel")):
            ok = history.record(
                plan, res, 9, 2026, KIND_DRAFT,
                csv_path=self.csv_path, db_path=self.db_path
            )
        # Dữ liệu vẫn được bảo toàn 100% trong SQLite history.db
        self.assertTrue(ok)
        sent = history.sent_suppliers(
            9, 2026, KIND_DRAFT, csv_path=self.csv_path, db_path=self.db_path
        )
        self.assertIn("Mansa", sent)


if __name__ == "__main__":
    unittest.main()



class OTAUpdaterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_version_parsing_and_comparison(self):
        from app import updater

        self.assertEqual(updater.parse_version("v1.2.0"), (1, 2, 0))
        self.assertEqual(updater.parse_version("1.10.3-beta"), (1, 10, 3))
        self.assertTrue(updater.is_newer_version("v1.2.0", "1.1.0"))
        self.assertTrue(updater.is_newer_version("2.0.0", "1.9.9"))
        self.assertFalse(updater.is_newer_version("v1.1.0", "1.1.0"))
        self.assertFalse(updater.is_newer_version("1.0.9", "1.1.0"))

    def test_check_for_update_parses_github_release_and_sha256(self):
        import io
        import json

        from app import updater

        expected_hash = "a" * 64
        payload = {
            "tag_name": "v1.3.0",
            "published_at": "2026-11-21T10:00:00Z",
            "body": f"Bản cập nhật mới.\nSHA256: {expected_hash}",
            "assets": [
                {
                    "name": "Gui_mail_nha_cung_cap_v1.3.0.zip",
                    "browser_download_url": "https://github.com/minhhai1104/Sending_gmail_for_Mrs_Ha/releases/download/v1.3.0/Gui_mail_nha_cung_cap_v1.3.0.zip",
                }
            ],
        }
        raw_bytes = json.dumps(payload).encode("utf-8")

        def fake_urlopen(req, timeout=5.0):
            resp = io.BytesIO(raw_bytes)
            resp.status = 200  # type: ignore[attr-defined]
            return resp

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            info = updater.check_for_update("1.2.0")
            self.assertIsNotNone(info)
            assert info is not None
            self.assertEqual(info.version, "1.3.0")
            self.assertEqual(info.sha256, expected_hash)
            self.assertTrue(info.download_url.endswith(".zip"))

            # Nếu phiên bản hiện tại đã bằng hoặc mới hơn thì trả về None
            self.assertIsNone(updater.check_for_update("1.3.0"))
            self.assertIsNone(updater.check_for_update("1.4.0"))

    def test_download_release_asset_verifies_sha256_and_rejects_mismatch(self):
        import hashlib
        import io

        from app import updater

        content = b"binary_zip_payload_for_ota_test"
        good_hash = hashlib.sha256(content).hexdigest()
        bad_hash = "f" * 64

        def fake_urlopen(req, timeout=30.0):
            resp = io.BytesIO(content)
            resp.headers = {"Content-Length": str(len(content))}  # type: ignore[attr-defined]
            return resp

        # 1. Happy path: khớp mã băm SHA-256
        rel_good = updater.ReleaseInfo(
            version="1.3.0",
            download_url="https://github.com/example/release.zip",
            sha256=good_hash,
            release_notes="OK",
            asset_name="release.zip",
        )
        progress_calls: list[tuple[int, int]] = []
        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            dl_path = updater.download_release_asset(
                rel_good,
                self.tmp_path,
                on_progress=lambda cur, total: progress_calls.append((cur, total)),
            )
        self.assertTrue(dl_path.is_file())
        self.assertEqual(dl_path.read_bytes(), content)
        self.assertTrue(len(progress_calls) >= 1)

        # 2. Chaos/Security path: lệch mã băm SHA-256 -> quăng UpdateError và xóa ngay file tạm
        rel_bad = updater.ReleaseInfo(
            version="1.3.0",
            download_url="https://github.com/example/bad_release.zip",
            sha256=bad_hash,
            release_notes="Bad",
            asset_name="bad_release.zip",
        )
        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with self.assertRaises(updater.UpdateError) as ctx:
                updater.download_release_asset(rel_bad, self.tmp_path)
            self.assertIn("SHA-256", str(ctx.exception))
        self.assertFalse((self.tmp_path / "bad_release.zip").exists())

        # 3. Security path: từ chối giao thức không phải HTTPS
        rel_http = updater.ReleaseInfo(
            version="1.3.0",
            download_url="http://insecure.example.com/release.zip",
            sha256=good_hash,
            release_notes="HTTP",
            asset_name="http.zip",
        )
        with self.assertRaises(updater.UpdateError):
            updater.download_release_asset(rel_http, self.tmp_path)

    def test_safe_extract_zip_blocks_zip_slip_and_protected_user_items(self):
        import zipfile

        from app import updater

        # 1. Zip Slip attack
        slip_zip = self.tmp_path / "slip.zip"
        with zipfile.ZipFile(slip_zip, "w") as zf:
            zf.writestr("../../evil.exe", b"malware")
        staging1 = self.tmp_path / "staging1"
        with self.assertRaises(updater.UpdateError) as ctx:
            updater.safe_extract_zip(slip_zip, staging1)
        self.assertIn("không an toàn", str(ctx.exception).lower())

        # 2. Bảo vệ các file dữ liệu người dùng (Cau_hinh.xlsx, history.db, Lich_su_gui.csv)
        mixed_zip = self.tmp_path / "mixed.zip"
        with zipfile.ZipFile(mixed_zip, "w") as zf:
            zf.writestr("Gui_mail_nha_cung_cap.exe", b"new_exe_v1.2")
            zf.writestr("Cau_hinh.xlsx", b"overwrite_attempt")
            zf.writestr("history.db", b"overwrite_db_attempt")
            zf.writestr("Dinh_kem/2026-09/test.xlsx", b"overwrite_attach")
        staging2 = self.tmp_path / "staging2"
        extracted = updater.safe_extract_zip(mixed_zip, staging2)
        extracted_names = [p.name for p in extracted]
        self.assertEqual(extracted_names, ["Gui_mail_nha_cung_cap.exe"])
        self.assertFalse((staging2 / "Cau_hinh.xlsx").exists())
        self.assertFalse((staging2 / "history.db").exists())

    def test_apply_staged_update_preserves_user_data_and_rolls_back_on_error(self):
        from app import updater

        target_dir = self.tmp_path / "app_dir"
        target_dir.mkdir()
        (target_dir / "Gui_mail_nha_cung_cap.exe").write_bytes(b"old_exe_v1.1")
        (target_dir / "Cau_hinh.xlsx").write_bytes(b"user_precious_config")
        (target_dir / "history.db").write_bytes(b"user_precious_history")

        staging_dir = self.tmp_path / "staging"
        staging_dir.mkdir()
        (staging_dir / "Gui_mail_nha_cung_cap.exe").write_bytes(b"new_exe_v1.2")
        (staging_dir / "Cau_hinh.xlsx").write_bytes(b"default_config_should_be_ignored")

        # 1. Happy path: cập nhật binary mới và bảo toàn 100% file người dùng
        updated = updater.apply_staged_update(staging_dir, target_dir)
        self.assertEqual(len(updated), 1)
        self.assertEqual(
            (target_dir / "Gui_mail_nha_cung_cap.exe").read_bytes(), b"new_exe_v1.2"
        )
        self.assertEqual(
            (target_dir / "Cau_hinh.xlsx").read_bytes(), b"user_precious_config"
        )
        self.assertEqual(
            (target_dir / "history.db").read_bytes(), b"user_precious_history"
        )
        self.assertFalse((target_dir / "Gui_mail_nha_cung_cap.exe.bak").exists())

        # 2. Chaos path: lỗi giữa chừng khi copy file thứ 2 -> tự động Rollback file thứ 1 từ .bak
        (staging_dir / "Gui_mail_nha_cung_cap.exe").write_bytes(b"broken_v1.3")
        (staging_dir / "extra_module.dll").write_bytes(b"dll_content")

        orig_replace = Path.replace
        call_count = 0

        def flaky_replace(self_path: Path, target_path: Path) -> Path:
            nonlocal call_count
            if not str(target_path).endswith(".bak") and self_path.name == "extra_module.dll":
                raise OSError("Simulated write failure mid-update")
            call_count += 1
            return orig_replace(self_path, target_path)

        with mock.patch.object(Path, "replace", autospec=True, side_effect=flaky_replace):
            with self.assertRaises(updater.UpdateError):
                updater.apply_staged_update(staging_dir, target_dir)

        # Kiểm tra Gui_mail_nha_cung_cap.exe đã được tự động khôi phục về bản v1.2 trước đó!
        self.assertEqual(
            (target_dir / "Gui_mail_nha_cung_cap.exe").read_bytes(), b"new_exe_v1.2"
        )

    def test_standalone_updater_runner_end_to_end(self):
        import zipfile

        import updater_runner

        target_dir = self.tmp_path / "installed_app"
        target_dir.mkdir()
        (target_dir / "Gui_mail_nha_cung_cap.exe").write_bytes(b"v1.1_binary")
        (target_dir / "Cau_hinh.xlsx").write_bytes(b"my_suppliers_data")

        pkg_zip = self.tmp_path / "update_pkg.zip"
        with zipfile.ZipFile(pkg_zip, "w") as zf:
            zf.writestr("Gui_mail_nha_cung_cap.exe", b"v1.2_binary_updated")
            zf.writestr("Cau_hinh.xlsx", b"should_not_touch")

        ok = updater_runner.execute_update(
            package_path=pkg_zip,
            target_dir=target_dir,
            wait_pid=None,
            relaunch_exe=None,
        )
        self.assertTrue(ok)
        self.assertEqual(
            (target_dir / "Gui_mail_nha_cung_cap.exe").read_bytes(),
            b"v1.2_binary_updated",
        )
        self.assertEqual(
            (target_dir / "Cau_hinh.xlsx").read_bytes(),
            b"my_suppliers_data",
        )



class V2HtmlAndExcelReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_html_email_body_and_inline_logo_cid(self):
        # 1. Kiểm tra chuyển đổi văn bản thuần có chữ ký sang HTML doanh nghiệp
        sample_body = (
            "Kính gửi quý đối tác ACE & T&T,\n"
            "Vui lòng kiểm tra file đính kèm.\n"
            "-------------------\n"
            "Ms. Ngoc Ha\n"
            "Haesung Vina Co., Ltd"
        )
        html_out = mailer.build_html_body(sample_body, logo_cid="test_logo_cid")
        self.assertIn("<html", html_out.lower())
        self.assertIn("ACE &amp; T&amp;T", html_out)
        self.assertIn("Ms. Ngoc Ha", html_out)
        self.assertIn('cid:test_logo_cid', html_out)

        # 2. Kiểm tra build_message có cả text/plain, text/html, logo inline CID và giữ nguyên iter_attachments()
        logo_file = self.tmp_path / "logo.png"
        # Header PNG tối giản hợp lệ
        logo_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

        excel_file = self.tmp_path / "Bang_phi.xlsx"
        excel_file.write_bytes(b"excel_data")

        settings = config.Settings(
            sender="me@gmail.com",
            display_name="Ms. Ngoc Ha",
            app_password="abcdefghijklmnop",
            attach_dir=str(self.tmp_path),
            cc=["boss@x.com"],
            logo_path=str(logo_file),
        )
        from app.planner import Attachment, MailPlan

        plan = MailPlan(
            supplier="ACE",
            enabled=True,
            recipients=["ace@x.com"],
            cc=["boss@x.com"],
            subject="Tiêu đề thử nghiệm v2.0",
            body=sample_body,
            attachments=[Attachment(excel_file, True, 10)],
        )
        msg = mailer.build_message(settings, plan)
        # Danh sách file đính kèm chính thức chỉ gồm file Excel báo cáo (không bị lẫn ảnh logo inline)
        self.assertEqual(
            [p.get_filename() for p in msg.iter_attachments()],
            ["Bang_phi.xlsx"],
        )
        raw_mime = msg.as_string()
        self.assertIn("text/plain", raw_mime)
        self.assertIn("text/html", raw_mime)
        self.assertIn("image/png", raw_mime)

    def test_export_sqlite_to_excel_history_report(self):
        db_path = self.tmp_path / "history.db"
        csv_path = self.tmp_path / "Lich_su_gui.csv"
        xlsx_path = self.tmp_path / "Lich_su_gui.xlsx"

        plan1 = mailer.MailPlan(
            supplier="ACE",
            enabled=True,
            recipients=["ace@x.com"],
            cc=[],
            subject="Báo cáo ACE",
            body="Nội dung",
            attachments=[],
        )
        plan2 = mailer.MailPlan(
            supplier="AHC",
            enabled=True,
            recipients=["ahc@x.com"],
            cc=[],
            subject="Báo cáo AHC",
            body="Nội dung",
            attachments=[],
        )
        history.record(
            plan1,
            mailer.SendResult("ACE", True, "Đã gửi"),
            9,
            2026,
            KIND_DRAFT,
            csv_path=csv_path,
            db_path=db_path,
        )
        history.record(
            plan2,
            mailer.SendResult("AHC", False, "Lỗi kết nối"),
            9,
            2026,
            KIND_FINAL,
            csv_path=csv_path,
            db_path=db_path,
        )

        exported = history.export_sqlite_to_excel(excel_path=xlsx_path, db_path=db_path)
        self.assertTrue(exported)
        self.assertTrue(xlsx_path.is_file())

        wb = load_workbook(xlsx_path)
        try:
            ws = wb.active
            # Dòng 1 là tiêu đề, dòng 2 là ACE, dòng 3 là AHC
            self.assertEqual(ws.cell(row=2, column=2).value, "09")
            self.assertEqual(ws.cell(row=2, column=5).value, "ACE")
            self.assertEqual(ws.cell(row=2, column=9).value, "Thành công")
            self.assertEqual(ws.cell(row=3, column=5).value, "AHC")
            self.assertEqual(ws.cell(row=3, column=9).value, "Lỗi")
        finally:
            wb.close()


    def test_private_repo_ota_token_encryption_and_headers(self):
        import hashlib
        import io
        import json

        from app import updater

        # 1. Mã hóa và giải mã portable OTA token (.ota_token.dat) không lộ plaintext
        token_file = self.tmp_path / ".ota_token.dat"
        sample_token = "ghp_SampleSecretTokenForPrivateRepo12345"
        self.assertTrue(security.save_embedded_ota_token(sample_token, token_file))
        self.assertNotIn(sample_token, token_file.read_text(encoding="utf-8"))
        self.assertEqual(security.load_embedded_ota_token(token_file), sample_token)

        # 2. Kiểm tra gửi header Authorization: Bearer <token> và tải qua api_asset_url
        content = b"private_release_zip_content"
        good_hash = hashlib.sha256(content).hexdigest()
        api_asset_endpoint = "https://api.github.com/repos/minhhai1104/Sending_gmail_for_Mrs_Ha/releases/assets/99999"

        payload = {
            "tag_name": "v2.1.0",
            "published_at": "2026-11-21T10:50:00Z",
            "body": f"Private OTA Release\nSHA256: {good_hash}",
            "assets": [
                {
                    "name": "Gui_mail_nha_cung_cap_v2.1.0.zip",
                    "url": api_asset_endpoint,
                    "browser_download_url": "https://github.com/minhhai1104/Sending_gmail_for_Mrs_Ha/releases/download/v2.1.0/Gui_mail_nha_cung_cap_v2.1.0.zip",
                }
            ],
        }

        captured_headers: list[dict[str, str]] = []

        def fake_urlopen(req, timeout=30.0):
            hdrs = {k.lower(): v for k, v in req.header_items()}
            captured_headers.append(hdrs)
            if req.full_url == api_asset_endpoint:
                resp = io.BytesIO(content)
                resp.headers = {"Content-Length": str(len(content))}  # type: ignore[attr-defined]
                return resp
            resp_json = io.BytesIO(json.dumps(payload).encode("utf-8"))
            resp_json.status = 200  # type: ignore[attr-defined]
            return resp_json

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            info = updater.check_for_update("2.0.0", token=sample_token)
            self.assertIsNotNone(info)
            assert info is not None
            self.assertEqual(info.api_asset_url, api_asset_endpoint)
            self.assertEqual(captured_headers[0].get("authorization"), f"Bearer {sample_token}")

            dl_path = updater.download_release_asset(
                info, self.tmp_path, token=sample_token
            )
            self.assertEqual(dl_path.read_bytes(), content)
            self.assertEqual(captured_headers[1].get("authorization"), f"Bearer {sample_token}")
            self.assertEqual(captured_headers[1].get("accept"), "application/octet-stream")
