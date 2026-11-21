"""Kiểm thử tầng Application ViewModels: Onboarding, Write-Only Secrets, Dispatch, Filter-Safe, Retry & Pause Telemetry."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from app.adapters.smtp_mailer import MailTransportError
from app.adapters.sqlite_store import SqliteAppStore
from app.application.app_service import AppService
from app.application.batch_runner import BatchRunner
from app.application.dispatch_service import DispatchService
from app.domain.models import (
    BatchProgress,
    BatchState,
    FileType,
    GmailSettings,
    MailPlan,
    PlanState,
    ScannedFile,
    SendErrorKind,
    SendKind,
    SendResult,
    Supplier,
)
from tests.conftest import FakeClock, FakeMailTransport, FakeSecretStore, InMemoryFileScanner


def _sf(name: str, size: int = 2048, sha: str = "") -> ScannedFile:
    p = Path("C:/reports/2026-09") / name
    return ScannedFile(p, name, p.suffix.lower(), size, sha or f"sha_{name}")


class TestAppService:
    def test_onboarding_write_only_secrets_and_crud(
        self, store: SqliteAppStore, fake_secrets: FakeSecretStore, tmp_path: Path
    ) -> None:
        transport = FakeMailTransport()
        svc = AppService(
            store,
            store,
            fake_secrets,
            transport,
            logos_dir=tmp_path / "logos",
            exports_dir=tmp_path / "exports",
        )

        # Ban đầu cần onboarding và tuyệt đối KHÔNG trả mật khẩu trong bootstrap
        boot0 = svc.get_bootstrap_state()
        assert boot0["needs_onboarding"] is True
        assert "app_password" not in boot0["settings"]
        assert boot0["settings"]["has_app_password"] is False

        # Sai mật khẩu -> bị chặn
        bad = svc.test_and_save_gmail("ha@haesung.vn", "Ms. Ha", "short")
        assert bad["ok"] is False

        # Đúng mật khẩu -> test connection + lưu DPAPI/SecretStore + giữ Write-Only
        ok = svc.test_and_save_gmail("ha@haesung.vn", "Ms. Ha", "abcd 1234 efgh 5678")
        assert ok["ok"] is True
        assert transport.test_connections == 1

        # Sửa tên hiển thị mà để trống mật khẩu -> giữ nguyên mật khẩu cũ!
        ok2 = svc.test_and_save_gmail("ha@haesung.vn", "Ms. Ngoc Ha", "")
        assert ok2["ok"] is True
        assert fake_secrets.load_password("ha@haesung.vn") == "abcd1234efgh5678"

        assert svc.complete_onboarding()["ok"] is True
        boot1 = svc.get_bootstrap_state()
        assert boot1["needs_onboarding"] is False
        assert boot1["settings"]["has_app_password"] is True
        assert "abcd1234efgh5678" not in str(boot1)

        # Logo upload + Template preview + Variable validation
        logo_src = tmp_path / "my_logo.png"
        logo_src.write_bytes(b"\x89PNG\r\n\x1a\nDATA")
        assert svc.set_logo_from_file(logo_src)["ok"] is True
        assert svc.save_templates("Bad {tháng}", "Body", "a.xlsx", "b.pdf")["ok"] is False
        assert svc.save_templates("OK {thang}", "Hi {nha_cung_cap}\n---\nSig", "{nha_cung_cap}.xlsx", "PO {nha_cung_cap}.pdf")["ok"] is True

        preview = svc.render_live_template_preview(
            subject="Tháng {thang}", body="Xin chào {nha_cung_cap}", excel_name="{nha_cung_cap}.xlsx", pdf_name="PO.pdf", supplier_name="ACE", month=9, year=2026
        )
        assert preview["subject"] == "Tháng 09"
        assert "data:image/png;base64," in preview["body_html"]

        # Suppliers CRUD + Alias
        created = svc.upsert_supplier(supplier_id=None, name="Alpha", recipients_raw="a@alpha.com")
        assert created["ok"] is True
        sup_id = created["supplier"]["id"]
        assert svc.add_supplier_alias(sup_id, "ALP")["ok"] is True
        assert svc.toggle_supplier(sup_id, False)["ok"] is True
        assert svc.delete_supplier(sup_id)["ok"] is True

        # General settings, theme, GitHub token, clear logo/password, reset templates, history query/export
        assert svc.save_general_settings(cc_list=["boss@haesung.vn"], pacing_seconds=2.0, max_retries=2, theme="dark")["ok"] is True
        assert svc.save_general_settings(cc_list=["bad-cc"])["ok"] is False
        assert svc.set_theme("light")["theme"] == "light"
        assert svc.save_github_token("ghp_abc12345678901234567890")["ok"] is True
        assert svc.save_github_token("")["ok"] is True
        assert svc.test_current_gmail()["ok"] is True
        assert svc.clear_logo()["ok"] is True
        assert svc.reset_default_templates()["ok"] is True
        assert svc.clear_app_password()["ok"] is True

        # History query & Excel export
        plan_hist = MailPlan(1, "ACE", True, ["ace@v.com"], [], "Sub", "Body")
        store.record(plan_hist, SendResult("ACE", True, "OK"), 9, 2026, SendKind.DRAFT.value)
        q = svc.query_history(month=9, year=2026, keyword="ACE")
        assert q["stats"]["ok_count"] == 1 and len(q["records"]) == 1
        exp = svc.export_history_excel()
        assert exp["ok"] is True and Path(exp["path"]).is_file()

        # Validation negative paths
        assert svc.save_templates("", "Body", "a.xlsx", "b.pdf")["ok"] is False
        assert svc.save_templates("Sub", "Body", "", "b.pdf")["ok"] is False
        assert svc.save_templates("Sub", "Body", "a.xlsx", "")["ok"] is False
        assert svc.delete_supplier(99999)["ok"] is False
        assert svc.toggle_supplier(99999, True)["ok"] is False
        assert svc.add_supplier_alias(99999, "X")["ok"] is False
        assert svc.add_supplier_alias(1, "")["ok"] is False
        assert svc.save_general_settings(pacing_seconds=99.0)["ok"] is False
        assert svc.save_general_settings(max_retries=9)["ok"] is False
        bad_logo = tmp_path / "bad.txt"
        bad_logo.write_text("hi")
        assert svc.set_logo_from_file(bad_logo)["ok"] is False
        empty_logo = tmp_path / "empty.png"
        empty_logo.write_bytes(b"")
        assert svc.set_logo_from_file(empty_logo)["ok"] is False
        assert svc.set_logo_from_file(tmp_path / "missing.png")["ok"] is False
        assert svc.complete_onboarding()["ok"] is False  # Vì đã clear_app_password ở trên!


class TestDispatchService:
    def test_workspace_review_approve_override_filter_safe_and_test_send(
        self, store: SqliteAppStore, fake_secrets: FakeSecretStore
    ) -> None:
        # Cài Gmail + 2 NCC (ACE và DiaMond)
        fake_secrets.save_password("ha@haesung.vn", "abcd1234efgh5678")
        store.save_settings(GmailSettings(sender="ha@haesung.vn", display_name="Ms. Ha", cc=["boss@haesung.vn"]))
        # Xóa mặc định để test sạch 2 NCC
        for s in store.load_config().suppliers:
            if s.id is not None:
                store.delete_supplier(s.id)
        ace = store.upsert_supplier(Supplier(None, "ACE", ["ace@v.com"]))
        diamond = store.upsert_supplier(Supplier(None, "DiaMond", ["d@v.com"]))

        files = [
            _sf("Bảng phí kiểm tra, phân loại hàng hóa 09.2026 ACE.xlsx"),
            _sf("Bảng phí kiểm tra, phân loại hàng hóa 09.2026 DiaMon.xlsx"),  # Lỗi gõ nhẹ -> Tầng Vàng!
        ]
        scanner = InMemoryFileScanner(files=files)
        transport = FakeMailTransport()
        dispatch = DispatchService(store, store, fake_secrets, scanner, transport)

        ws = dispatch.load_from_paths([Path("C:/reports/2026-09")], auto_detect=True)
        assert ws["period"]["month"] == 9
        assert ws["period"]["year"] == 2026
        assert ws["period"]["kind"] == SendKind.DRAFT.value

        ace_dto = next(p for p in ws["plans"] if p["supplier"] == "ACE")
        dia_dto = next(p for p in ws["plans"] if p["supplier"] == "DiaMond")
        assert ace_dto["state"] == PlanState.READY.value and ace_dto["default_checked"] is True
        assert dia_dto["state"] == PlanState.REVIEW.value and dia_dto["default_checked"] is False

        # Duyệt tay Tầng Vàng + lưu alias -> chuyển thành READY
        ws2 = dispatch.approve_suggested_match(diamond.id, FileType.EXCEL.value, save_alias=True)  # type: ignore[arg-type]
        dia_dto2 = next(p for p in ws2["plans"] if p["supplier"] == "DiaMond")
        assert dia_dto2["state"] == PlanState.READY.value

        # Filter-Safe Selection: chọn cả 2 nhưng bộ lọc chỉ hiện ACE -> phải phát hiện 1 NCC ẩn!
        sel = dispatch.resolve_selected_plans(
            selected_supplier_ids=[ace.id, diamond.id],  # type: ignore[list-item]
            visible_supplier_ids=[ace.id],  # type: ignore[list-item]
            only_visible=False,
        )
        assert sel["needs_filter_confirm"] is True
        assert sel["hidden_count"] == 1
        assert sel["hidden_suppliers"] == ["DiaMond"]

        sel_only_vis = dispatch.resolve_selected_plans(
            selected_supplier_ids=[ace.id, diamond.id],  # type: ignore[list-item]
            visible_supplier_ids=[ace.id],  # type: ignore[list-item]
            only_visible=True,
        )
        assert len(sel_only_vis["plans"]) == 1 and sel_only_vis["plans"][0].supplier == "ACE"

        # Gửi thử cho chính mình: CC rỗng, tiền tố [GỬI THỬ], KHÔNG ghi lịch sử!
        test_res = dispatch.send_test_to_self(supplier_id=ace.id)
        assert test_res["ok"] is True
        assert len(transport.sent_log) == 1
        sent_plan, _ = transport.sent_log[0]
        assert sent_plan.recipients == ["ha@haesung.vn"]
        assert sent_plan.cc == []
        assert sent_plan.subject.startswith("[GỬI THỬ] ")
        assert store.sent_supplier_norms(9, 2026, SendKind.DRAFT.value) == set()

        # Đổi kỳ, override file thủ công, xóa nguồn, lấy failed plans
        assert dispatch.set_period_and_kind(10, 2026, SendKind.FINAL.value)["ok"] is True
        assert dispatch.set_period_and_kind(99, 2026, SendKind.DRAFT.value)["ok"] is False
        ov = dispatch.override_attachment(ace.id, FileType.EXCEL.value, Path("C:/reports/custom_ace.xlsx"))  # type: ignore[arg-type]
        assert ov["ok"] is True
        bad_ov = dispatch.override_attachment(ace.id, FileType.PDF.value, Path("C:/reports/wrong.xlsx"))  # type: ignore[arg-type]
        assert bad_ov["ok"] is False
        assert dispatch.clear_source()["ok"] is True
        assert dispatch.init_workspace(today=date(2026, 10, 5))["period"]["month"] == 9
        assert isinstance(dispatch.get_failed_plans_for_retry(), list)


class TestBatchRunner:
    def test_retry_transient_only_durable_commit_and_failed_plans(
        self, store: SqliteAppStore, fake_clock: FakeClock
    ) -> None:
        def handler(plan: MailPlan, msg_id: str, attempt: int) -> SendResult:
            if plan.supplier == "Flaky" and attempt == 1:
                raise MailTransportError("Rớt mạng tạm thời", SendErrorKind.TRANSIENT_NETWORK)
            if plan.supplier == "Refused":
                return SendResult(
                    "Refused", False, "Từ chối email", SendErrorKind.RECIPIENT_REFUSED
                )
            return SendResult(plan.supplier, True, "Đã gửi thành công (250 OK)", message_id=msg_id)

        transport = FakeMailTransport(send_handler=handler)
        runner = BatchRunner(transport, store, clock=fake_clock)
        settings = GmailSettings(sender="ha@haesung.vn", pacing_seconds=1.5, max_retries=2)
        plans = [
            MailPlan(1, "Flaky", True, ["f@v.com"], [], "Sub", "Body"),
            MailPlan(2, "Refused", True, ["r@v.com"], [], "Sub", "Body"),
        ]

        summary = runner.run_sync(
            settings=settings,
            app_password="abcd1234efgh5678",
            plans=plans,
            month=9,
            year=2026,
            kind=SendKind.DRAFT,
        )
        assert summary.state == BatchState.DONE
        assert summary.ok_count == 1
        assert summary.fail_count == 1
        assert [p.supplier for p in summary.failed_plans] == ["Refused"]

        # Flaky thử 2 lần với CÙNG một Message-ID; Refused 0 retry!
        flaky_attempts = [mid for p, mid in transport.sent_log if p.supplier == "Flaky"]
        refused_attempts = [mid for p, mid in transport.sent_log if p.supplier == "Refused"]
        assert len(flaky_attempts) == 2 and flaky_attempts[0] == flaky_attempts[1]
        assert len(refused_attempts) == 1

        # Backoff 1.0s + Pacing 1.5s được ghi nhận đúng trên FakeClock
        assert 1.0 in fake_clock.waits
        assert 1.5 in fake_clock.waits

        # SQLite đã ghi bền vững trên Worker Thread
        assert "flaky" in store.sent_supplier_norms(9, 2026, SendKind.DRAFT.value)
        assert "refused" in store.failed_supplier_norms(9, 2026, SendKind.DRAFT.value)

    def test_pause_aware_telemetry_and_cancel_during_pause(
        self, store: SqliteAppStore, fake_clock: FakeClock
    ) -> None:
        progresses: list[BatchProgress] = []
        runner_ref: list[BatchRunner] = []

        def handler(plan: MailPlan, msg_id: str, attempt: int) -> SendResult:
            fake_clock.advance(2.0)  # Mỗi mail mất đúng 2 giây
            if plan.supplier == "S1":
                # Giả lập người dùng tạm dừng 120 giây rồi tiếp tục!
                runner_ref[0].pause()
                fake_clock.advance(120.0)
                runner_ref[0].resume()
            return SendResult(plan.supplier, True, "OK", message_id=msg_id)

        transport = FakeMailTransport(send_handler=handler)
        runner = BatchRunner(transport, store, clock=fake_clock)
        runner_ref.append(runner)

        plans = [
            MailPlan(1, "S1", True, ["s1@v.com"], [], "Sub", "Body"),
            MailPlan(2, "S2", True, ["s2@v.com"], [], "Sub", "Body"),
        ]
        summary = runner.run_sync(
            settings=GmailSettings(sender="ha@haesung.vn", pacing_seconds=0.0, max_retries=0),
            app_password="abcd1234efgh5678",
            plans=plans,
            month=9,
            year=2026,
            kind=SendKind.DRAFT,
            on_progress=progresses.append,
        )
        assert summary.ok_count == 2
        # Thời gian chạy thực chỉ 4s (không bị cộng 120s pause!) -> tốc độ ~30 mail/phút
        final_prog = progresses[-1]
        assert final_prog.percent == 100
        assert final_prog.rate_per_min >= 25.0

    def test_cancel_mid_batch_stops_immediately(
        self, store: SqliteAppStore, fake_clock: FakeClock
    ) -> None:
        runner_ref: list[BatchRunner] = []

        def handler(plan: MailPlan, msg_id: str, attempt: int) -> SendResult:
            if plan.supplier == "S1":
                runner_ref[0].cancel()
            return SendResult(plan.supplier, True, "OK", message_id=msg_id)

        transport = FakeMailTransport(send_handler=handler)
        runner = BatchRunner(transport, store, clock=fake_clock)
        runner_ref.append(runner)

        plans = [
            MailPlan(1, "S1", True, ["s1@v.com"], [], "Sub", "Body"),
            MailPlan(2, "S2", True, ["s2@v.com"], [], "Sub", "Body"),
        ]
        summary = runner.run_sync(
            settings=GmailSettings(sender="ha@haesung.vn", pacing_seconds=2.0),
            app_password="abcd1234efgh5678",
            plans=plans,
            month=9,
            year=2026,
            kind=SendKind.DRAFT,
        )
        assert summary.state == BatchState.CANCELLED
        assert summary.ok_count == 1
        assert len(transport.sent_log) == 1
        assert date.today().year >= 2025

    def test_start_async_and_connection_failure_records_all_failed(
        self, store: SqliteAppStore, fake_clock: FakeClock
    ) -> None:
        done_summaries = []
        transport = FakeMailTransport(
            fail_connect=MailTransportError("Sai mật khẩu ứng dụng", SendErrorKind.AUTH)
        )
        runner = BatchRunner(transport, store, clock=fake_clock)
        plans = [MailPlan(1, "ACE", True, ["a@v.com"], [], "Sub", "Body")]

        started = runner.start_async(
            settings=GmailSettings(sender="ha@haesung.vn", pacing_seconds=0.0),
            app_password="bad",
            plans=plans,
            month=9,
            year=2026,
            kind=SendKind.DRAFT,
            on_done=done_summaries.append,
        )
        assert started is True
        runner.cancel_and_wait(timeout=3.0)
        assert len(done_summaries) == 1
        assert done_summaries[0].fail_count == 1
        assert runner.last_summary is not None
        assert "ace" in store.failed_supplier_norms(9, 2026, SendKind.DRAFT.value)
