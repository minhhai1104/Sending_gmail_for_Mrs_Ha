import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "vendor"))

from openpyxl import load_workbook  # noqa: E402

from app import config, mailer  # noqa: E402
from app.planner import KIND_DRAFT, KIND_FINAL, build_plans  # noqa: E402
from app.templating import render, unknown_variables  # noqa: E402


class TemplatingTests(unittest.TestCase):
    def test_render_and_unknown(self):
        self.assertEqual(render("A {thang}/{nam} {x}", {"thang": "09", "nam": "2026"}), "A 09/2026 {x}")
        self.assertEqual(unknown_variables("{thang} {sai} {nam}"), ["sai"])


class ConfigTests(unittest.TestCase):
    def test_split_emails(self):
        self.assertEqual(config.split_emails("a@x.com; b@x.com\nc@x.com, d@x.com"),
                         ["a@x.com", "b@x.com", "c@x.com", "d@x.com"])
        self.assertTrue(config.is_valid_email("a.b@x.com"))
        self.assertFalse(config.is_valid_email("a@x"))


class PlanAndMailTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        self.cfg_path = tmp / "Cau_hinh.xlsx"
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

        self.attach = tmp / "dk" / "2026-09"
        self.attach.mkdir(parents=True)
        for name in ("Bảng phí kiểm tra, phân loại hàng hóa 09.2026 ACE.xlsx",
                     "Bảng phí kiểm tra, phân loại hàng hóa 09.2026 AHC.xlsx",
                     "PO ACE 09.2026.pdf"):
            (self.attach / name).write_bytes(b"data")
        self.cfg = config.load_config(self.cfg_path)

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
        self.assertEqual(plan.subject,
                         "Bảng phí kiểm tra, phân loại hàng hóa tháng 09 năm 2026 - ACE - Tạm tính")
        self.assertEqual([a.name for a in plan.attachments],
                         ["Bảng phí kiểm tra, phân loại hàng hóa 09.2026 ACE.xlsx"])
        self.assertTrue(plan.sendable)
        self.assertIn("tháng 09 năm 2026", plan.body)

    def test_final_attaches_excel_and_pdf(self):
        ace, ahc, tnt, *_ = build_plans(self.cfg, 9, 2026, KIND_FINAL)
        self.assertEqual([a.name for a in ace.attachments],
                         ["Bảng phí kiểm tra, phân loại hàng hóa 09.2026 ACE.xlsx", "PO ACE 09.2026.pdf"])
        self.assertTrue(ace.sendable)
        self.assertFalse(ahc.sendable)  # thiếu PDF của AHC
        self.assertIn("Không tìm thấy file: PO AHC 09.2026.pdf", ahc.errors)
        self.assertEqual(tnt.state, "off")

    def test_missing_recipients_flagged(self):
        plans = build_plans(self.cfg, 9, 2026, KIND_DRAFT)
        diamond = next(p for p in plans if p.supplier == "DiaMond")
        self.assertIn("Chưa điền mail người nhận.", diamond.errors)

    def test_build_message(self):
        plan = build_plans(self.cfg, 9, 2026, KIND_FINAL)[0]
        msg = mailer.build_message(self.cfg.settings, plan)
        self.assertEqual([a.addr_spec for a in msg["To"].addresses], ["ace1@x.com", "ace2@x.com"])
        self.assertEqual(msg["Cc"].addresses[0].addr_spec, "boss@x.com")
        self.assertEqual([p.get_filename() for p in msg.iter_attachments()],
                         ["Bảng phí kiểm tra, phân loại hàng hóa 09.2026 ACE.xlsx", "PO ACE 09.2026.pdf"])

    def test_send_plans_uses_smtp_and_continues_after_error(self):
        plans = [p for p in build_plans(self.cfg, 9, 2026, KIND_DRAFT) if p.sendable]
        self.assertEqual([p.supplier for p in plans], ["ACE", "AHC"])
        with mock.patch("smtplib.SMTP_SSL") as smtp:
            server = smtp.return_value
            server.send_message.side_effect = [None, OSError("boom")]
            results = mailer.send_plans(self.cfg.settings, plans)
        server.login.assert_called_once_with("me@gmail.com", "abcdefghijklmnop")
        self.assertEqual([r.ok for r in results], [True, False])


if __name__ == "__main__":
    unittest.main()
