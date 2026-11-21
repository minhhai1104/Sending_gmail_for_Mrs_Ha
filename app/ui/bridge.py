"""Strict Whitelist JS-API Facade giữa Web UI (PyWebView) và tầng Application Python.

Tuân thủ 100% 6 rào chắn bảo mật QA:
- Write-Only Secrets: Không bao giờ trả App Password hay GitHub Token về JavaScript.
- Không nhận đường dẫn tệp tùy ý từ JS: Mọi chọn tệp/thư mục đi qua OS FileDialog native hoặc
  tập đường dẫn đã đăng ký bởi Native Drag-and-Drop / danh sách ứng viên đã quét.
- External URL Allowlist: Chỉ mở đúng 3 URL chính thức (Google 2FA, App Passwords, GitHub Releases).
- Mọi tác vụ mạng / xuất file chạy trên Background Thread, đẩy tiến độ về JS qua Event Bus an toàn.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any, Optional

import webview

from .. import __version__
from ..adapters import ota_updater
from ..adapters.paths import get_app_dir
from ..application.app_service import AppService
from ..application.batch_runner import BatchRunner
from ..application.dispatch_service import DispatchService
from ..domain.models import (
    BatchProgress,
    BatchSummary,
    MailPlan,
    ReleaseInfo,
    SendResult,
)
from ..domain.validation import GOOGLE_2FA_URL, GOOGLE_APP_PASSWORD_URL, redact_secrets
from ..ports.protocols import SecretStore

_ALLOWED_EXTERNAL_URLS: dict[str, str] = {
    "google_2fa": GOOGLE_2FA_URL,
    "google_app_password": GOOGLE_APP_PASSWORD_URL,
    "github_releases": f"https://github.com/{ota_updater.GITHUB_REPO}/releases",
}


class UiBridge:
    """Đối tượng API được expose sang `window.pywebview.api` với bề mặt tối giản & an toàn."""

    def __init__(
        self,
        app_service: AppService,
        dispatch_service: DispatchService,
        batch_runner: BatchRunner,
        secret_store: SecretStore,
        on_theme_change: Optional[Any] = None,
    ) -> None:
        self._app = app_service
        self._dispatch = dispatch_service
        self._runner = batch_runner
        self._secrets = secret_store
        self._on_theme_change = on_theme_change
        self._window: Optional[webview.Window] = None

        self._ota_lock = threading.Lock()
        self._ota_checking = False
        self._ota_downloading = False
        self._pending_release: Optional[ReleaseInfo] = None
        self._last_progress_push = 0.0
        self._last_failed_plans: list[MailPlan] = []

    def attach_window(self, window: webview.Window) -> None:
        self._window = window

    @property
    def is_busy(self) -> bool:
        return self._runner.is_running or self._ota_downloading

    def shutdown(self) -> None:
        """Graceful shutdown khi người dùng đóng cửa sổ."""
        if self._runner.is_running:
            self._runner.cancel_and_wait(timeout=5.0)

    def emit_event(self, event_name: str, payload: Any) -> None:
        """Đẩy sự kiện 1 chiều Python -> JS an toàn luồng (JSON-encoded)."""
        win = self._window
        if win is None:
            return
        try:
            name_json = json.dumps(event_name, ensure_ascii=False)
            data_json = json.dumps(payload, ensure_ascii=False)
            win.evaluate_js(f"window.AppBus && window.AppBus.emit({name_json}, {data_json});")
        except Exception:
            pass

    # ------------------------------------------------------------------ Khởi tạo & Điều hướng

    def get_initial_data(self) -> dict[str, Any]:
        boot = self._app.get_bootstrap_state()
        workspace = self._dispatch.init_workspace()
        boot["version"] = __version__
        boot["workspace"] = workspace
        return boot

    def open_external_url(self, link_key: str) -> dict[str, Any]:
        url = _ALLOWED_EXTERNAL_URLS.get((link_key or "").strip())
        if not url:
            return {"ok": False, "message": "Liên kết không nằm trong danh sách cho phép."}
        webbrowser.open(url)
        return {"ok": True}

    def set_theme(self, theme: str) -> dict[str, Any]:
        res = self._app.set_theme(theme)
        if self._on_theme_change is not None:
            try:
                self._on_theme_change(res["theme"])
            except Exception:
                pass
        return res

    # ------------------------------------------------------------------ Onboarding & Cài đặt

    def test_and_save_gmail(
        self, sender: str, display_name: str, raw_app_password: str = ""
    ) -> dict[str, Any]:
        res = self._app.test_and_save_gmail(
            sender=sender,
            display_name=display_name,
            raw_app_password=raw_app_password,
            verify_connection=True,
        )
        if res.get("ok"):
            res["bootstrap"] = self._app.get_bootstrap_state()
            res["workspace"] = self._dispatch.refresh_workspace()
        return res

    def test_current_gmail(self) -> dict[str, Any]:
        return self._app.test_current_gmail()

    def clear_app_password(self) -> dict[str, Any]:
        res = self._app.clear_app_password()
        res["bootstrap"] = self._app.get_bootstrap_state()
        res["workspace"] = self._dispatch.refresh_workspace()
        return res

    def save_general_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        res = self._app.save_general_settings(
            sender=payload.get("sender"),
            display_name=payload.get("display_name"),
            attach_dir=payload.get("attach_dir"),
            cc_list=payload.get("cc"),
            pacing_seconds=payload.get("pacing_seconds"),
            max_retries=payload.get("max_retries"),
            theme=payload.get("theme"),
        )
        if res.get("ok"):
            if payload.get("theme") and self._on_theme_change is not None:
                try:
                    self._on_theme_change(payload["theme"])
                except Exception:
                    pass
            res["bootstrap"] = self._app.get_bootstrap_state()
            res["workspace"] = self._dispatch.refresh_workspace()
        return res

    def save_github_token(self, token: str) -> dict[str, Any]:
        res = self._app.save_github_token(token)
        res["bootstrap"] = self._app.get_bootstrap_state()
        return res

    def complete_onboarding(self) -> dict[str, Any]:
        res = self._app.complete_onboarding()
        if res.get("ok"):
            res["bootstrap"] = self._app.get_bootstrap_state()
            res["workspace"] = self._dispatch.refresh_workspace()
        return res

    def pick_default_attach_folder(self) -> dict[str, Any]:
        if self._window is None:
            return {"ok": False, "message": "Cửa sổ chưa sẵn sàng."}
        chosen = self._window.create_file_dialog(webview.FileDialog.FOLDER)
        if not chosen:
            return {"ok": False, "cancelled": True}
        folder = str(chosen[0])
        res = self._app.save_general_settings(attach_dir=folder)
        if res.get("ok"):
            res["attach_dir"] = folder
            res["bootstrap"] = self._app.get_bootstrap_state()
        return res

    # ------------------------------------------------------------------ Nhà cung cấp

    def upsert_supplier(self, payload: dict[str, Any]) -> dict[str, Any]:
        raw_id = payload.get("id")
        sup_id = int(raw_id) if raw_id is not None and str(raw_id).strip() != "" else None
        res = self._app.upsert_supplier(
            supplier_id=sup_id,
            name=str(payload.get("name") or ""),
            recipients_raw=payload.get("recipients") or "",
            aliases_raw=payload.get("aliases") or "",
            note=str(payload.get("note") or ""),
            enabled=bool(payload.get("enabled", True)),
        )
        if res.get("ok"):
            res["bootstrap"] = self._app.get_bootstrap_state()
            res["workspace"] = self._dispatch.refresh_workspace()
        return res

    def delete_supplier(self, supplier_id: int) -> dict[str, Any]:
        res = self._app.delete_supplier(int(supplier_id))
        if res.get("ok"):
            res["bootstrap"] = self._app.get_bootstrap_state()
            res["workspace"] = self._dispatch.refresh_workspace()
        return res

    def toggle_supplier(self, supplier_id: int, enabled: bool) -> dict[str, Any]:
        res = self._app.toggle_supplier(int(supplier_id), bool(enabled))
        if res.get("ok"):
            res["bootstrap"] = self._app.get_bootstrap_state()
            res["workspace"] = self._dispatch.refresh_workspace()
        return res

    # ------------------------------------------------------------------ Mẫu Email & Logo

    def save_templates(self, payload: dict[str, Any]) -> dict[str, Any]:
        res = self._app.save_templates(
            subject=str(payload.get("subject") or ""),
            body=str(payload.get("body") or ""),
            excel_name=str(payload.get("excel_name") or ""),
            pdf_name=str(payload.get("pdf_name") or ""),
        )
        if res.get("ok"):
            res["bootstrap"] = self._app.get_bootstrap_state()
            res["workspace"] = self._dispatch.refresh_workspace()
        return res

    def reset_default_templates(self) -> dict[str, Any]:
        res = self._app.reset_default_templates()
        res["bootstrap"] = self._app.get_bootstrap_state()
        res["workspace"] = self._dispatch.refresh_workspace()
        return res

    def pick_logo_image(self) -> dict[str, Any]:
        if self._window is None:
            return {"ok": False, "message": "Cửa sổ chưa sẵn sàng."}
        chosen = self._window.create_file_dialog(
            webview.FileDialog.OPEN,
            allow_multiple=False,
            file_types=("Ảnh Logo (*.png;*.jpg;*.jpeg;*.webp)",),
        )
        if not chosen:
            return {"ok": False, "cancelled": True}
        res = self._app.set_logo_from_file(Path(chosen[0]))
        if res.get("ok"):
            res["bootstrap"] = self._app.get_bootstrap_state()
            res["workspace"] = self._dispatch.refresh_workspace()
        return res

    def clear_logo(self) -> dict[str, Any]:
        res = self._app.clear_logo()
        res["bootstrap"] = self._app.get_bootstrap_state()
        res["workspace"] = self._dispatch.refresh_workspace()
        return res

    def preview_template(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._app.render_live_template_preview(
            subject=str(payload.get("subject") or ""),
            body=str(payload.get("body") or ""),
            excel_name=str(payload.get("excel_name") or ""),
            pdf_name=str(payload.get("pdf_name") or ""),
            supplier_name=str(payload.get("supplier_name") or "ACE"),
            month=payload.get("month"),
            year=payload.get("year"),
            kind=str(payload.get("kind") or "Chốt"),
        )

    # ------------------------------------------------------------------ Workspace Gửi Mail

    def set_period_and_kind(self, month: int, year: int, kind: str) -> dict[str, Any]:
        return self._dispatch.set_period_and_kind(int(month), int(year), str(kind))

    def refresh_workspace(self) -> dict[str, Any]:
        return self._dispatch.refresh_workspace()

    def clear_source(self) -> dict[str, Any]:
        return self._dispatch.clear_source()

    def pick_source_folder(self) -> dict[str, Any]:
        if self._window is None:
            return {"ok": False, "message": "Cửa sổ chưa sẵn sàng."}
        chosen = self._window.create_file_dialog(webview.FileDialog.FOLDER)
        if not chosen:
            return {"ok": False, "cancelled": True}
        return self._dispatch.load_from_paths([Path(chosen[0])], auto_detect=True)

    def pick_source_files(self) -> dict[str, Any]:
        if self._window is None:
            return {"ok": False, "message": "Cửa sổ chưa sẵn sàng."}
        chosen = self._window.create_file_dialog(
            webview.FileDialog.OPEN,
            allow_multiple=True,
            file_types=("Báo cáo Excel & PDF (*.xlsx;*.xls;*.xlsm;*.pdf)",),
        )
        if not chosen:
            return {"ok": False, "cancelled": True}
        return self._dispatch.load_from_paths([Path(p) for p in chosen], auto_detect=True)

    def handle_native_dropped_paths(self, paths: list[Path]) -> None:
        """Chỉ được gọi từ native `DOMEventHandler('drop')` của Python — không expose đường dẫn tự do từ JS."""
        if not paths or self.is_busy:
            return
        ws = self._dispatch.load_from_paths(paths, auto_detect=True)
        self.emit_event("workspace:updated", ws)

    def approve_suggested_match(
        self, supplier_id: int, file_type: str, save_alias: bool = False
    ) -> dict[str, Any]:
        res = self._dispatch.approve_suggested_match(int(supplier_id), str(file_type), bool(save_alias))
        if save_alias and res.get("ok"):
            res["bootstrap"] = self._app.get_bootstrap_state()
        return res

    def pick_override_file(self, supplier_id: int, file_type: str) -> dict[str, Any]:
        if self._window is None:
            return {"ok": False, "message": "Cửa sổ chưa sẵn sàng."}
        ft = (
            ("Tệp PDF (*.pdf)",)
            if file_type == "pdf"
            else ("Tệp Excel (*.xlsx;*.xls;*.xlsm)",)
        )
        chosen = self._window.create_file_dialog(
            webview.FileDialog.OPEN, allow_multiple=False, file_types=ft
        )
        if not chosen:
            return {"ok": False, "cancelled": True}
        return self._dispatch.override_attachment(int(supplier_id), str(file_type), Path(chosen[0]))

    def select_candidate_file(
        self, supplier_id: int, file_type: str, candidate_index: int
    ) -> dict[str, Any]:
        """Chọn 1 ứng viên từ danh sách `candidates` hợp lệ của NCC đó (không nhận đường dẫn tự do từ JS)."""
        plan = next((p for p in self._dispatch.current_plans if p.supplier_id == int(supplier_id)), None)
        if plan is None:
            return {"ok": False, "message": "Không tìm thấy nhà cung cấp."}
        att = next((a for a in plan.attachments if a.file_type.value == file_type), None)
        if att is None or not (0 <= int(candidate_index) < len(att.candidates)):
            return {"ok": False, "message": "Không tìm thấy tệp ứng viên hợp lệ."}
        chosen = att.candidates[int(candidate_index)]
        return self._dispatch.override_attachment(int(supplier_id), str(file_type), chosen.path)

    def open_attachment_file(self, supplier_id: int, file_type: str) -> dict[str, Any]:
        """Mở tệp đính kèm hiện tại bằng ứng dụng mặc định Windows để kiểm tra (lấy path từ Python state)."""
        plan = next((p for p in self._dispatch.current_plans if p.supplier_id == int(supplier_id)), None)
        if plan is None:
            return {"ok": False, "message": "Không tìm thấy nhà cung cấp."}
        att = next((a for a in plan.attachments if a.file_type.value == file_type), None)
        if att is None or att.file is None or not att.file.path.is_file():
            return {"ok": False, "message": "Không tìm thấy tệp để mở."}
        try:
            os.startfile(att.file.path)  # type: ignore[attr-defined]  # noqa: S606
            return {"ok": True}
        except OSError as exc:
            return {"ok": False, "message": f"Không mở được tệp: {exc}"}

    def send_test_to_self(self, supplier_id: Optional[int] = None) -> dict[str, Any]:
        if self.is_busy:
            return {"ok": False, "message": "Đang có tác vụ gửi khác chạy."}
        sid = int(supplier_id) if supplier_id is not None else None
        return self._dispatch.send_test_to_self(supplier_id=sid)

    # ------------------------------------------------------------------ Điều khiển luồng gửi hàng loạt

    def check_send_selection(
        self, selected_ids: list[int], visible_ids: list[int]
    ) -> dict[str, Any]:
        """Kiểm tra Filter-Safe trước khi mở xác nhận gửi."""
        sel = self._dispatch.resolve_selected_plans(
            selected_supplier_ids=[int(i) for i in selected_ids],
            visible_supplier_ids=[int(i) for i in visible_ids],
            only_visible=False,
        )
        return {
            "total_selected": sel["total_selected"],
            "hidden_count": sel["hidden_count"],
            "hidden_suppliers": sel["hidden_suppliers"],
            "needs_filter_confirm": sel["needs_filter_confirm"],
        }

    def start_batch_send(
        self,
        selected_ids: list[int],
        visible_ids: Optional[list[int]] = None,
        only_visible: bool = False,
    ) -> dict[str, Any]:
        if self.is_busy:
            return {"ok": False, "message": "Đang có một đợt gửi đang chạy."}
        cfg = self._app.load_config()
        pw = self._secrets.load_password(cfg.settings.sender)
        if not pw:
            return {"ok": False, "message": "Chưa có Mật khẩu ứng dụng Gmail."}

        sel = self._dispatch.resolve_selected_plans(
            selected_supplier_ids=[int(i) for i in selected_ids],
            visible_supplier_ids=[int(i) for i in visible_ids] if visible_ids is not None else None,
            only_visible=bool(only_visible),
        )
        plans: list[MailPlan] = sel["plans"]
        if not plans:
            return {"ok": False, "message": "Chưa có nhà cung cấp hợp lệ nào được chọn để gửi."}

        return self._launch_batch(cfg.settings, pw, plans)

    def retry_failed_batch(self) -> dict[str, Any]:
        """1-Click gửi lại các nhà bị lỗi từ đợt gần nhất hoặc trong kỳ hiện tại."""
        if self.is_busy:
            return {"ok": False, "message": "Đang có một đợt gửi đang chạy."}
        cfg = self._app.load_config()
        pw = self._secrets.load_password(cfg.settings.sender)
        if not pw:
            return {"ok": False, "message": "Chưa có Mật khẩu ứng dụng Gmail."}

        plans = list(self._last_failed_plans) if self._last_failed_plans else self._dispatch.get_failed_plans_for_retry()
        if not plans:
            return {"ok": False, "message": "Không có nhà cung cấp nào đang lỗi cần gửi lại."}
        return self._launch_batch(cfg.settings, pw, plans)

    def _launch_batch(self, settings: Any, app_password: str, plans: list[MailPlan]) -> dict[str, Any]:
        month, year, kind = self._dispatch.current_period
        self._last_progress_push = 0.0
        self._last_failed_plans = []

        def on_progress(prog: BatchProgress) -> None:
            now = time.monotonic()
            # Throttle 100ms để không dội ngập JS, nhưng luôn đẩy trạng thái kết thúc
            if prog.completed < prog.total and (now - self._last_progress_push) < 0.08:
                return
            self._last_progress_push = now
            self.emit_event(
                "batch:progress",
                {
                    "state": prog.state.value,
                    "total": prog.total,
                    "completed": prog.completed,
                    "ok_count": prog.ok_count,
                    "fail_count": prog.fail_count,
                    "percent": prog.percent,
                    "rate_per_min": prog.rate_per_min,
                    "eta_seconds": prog.eta_seconds,
                    "current_supplier": prog.current_supplier,
                },
            )

        def on_item(plan: MailPlan, result: SendResult) -> None:
            self.emit_event(
                "batch:item",
                {
                    "supplier_id": plan.supplier_id,
                    "supplier": plan.supplier,
                    "ok": result.ok,
                    "message": result.message,
                    "error_kind": result.error_kind.value,
                },
            )

        def on_done(summary: BatchSummary) -> None:
            self._last_failed_plans = list(summary.failed_plans)
            ws = self._dispatch.refresh_workspace()
            self.emit_event(
                "batch:done",
                {
                    "batch_id": summary.batch_id,
                    "state": summary.state.value,
                    "total": summary.total,
                    "ok_count": summary.ok_count,
                    "fail_count": summary.fail_count,
                    "can_retry_failed": len(summary.failed_plans) > 0,
                    "workspace": ws,
                },
            )

        started = self._runner.start_async(
            settings=settings,
            app_password=app_password,
            plans=plans,
            month=month,
            year=year,
            kind=kind,
            on_progress=on_progress,
            on_item=on_item,
            on_done=on_done,
        )
        return {"ok": started, "total": len(plans)}

    def pause_batch(self) -> dict[str, Any]:
        ok = self._runner.pause()
        if ok:
            self.emit_event("batch:state", {"state": "paused"})
        return {"ok": ok}

    def resume_batch(self) -> dict[str, Any]:
        ok = self._runner.resume()
        if ok:
            self.emit_event("batch:state", {"state": "running"})
        return {"ok": ok}

    def cancel_batch(self) -> dict[str, Any]:
        ok = self._runner.cancel()
        if ok:
            self.emit_event("batch:state", {"state": "cancelling"})
        return {"ok": ok}

    # ------------------------------------------------------------------ Lịch sử gửi

    def query_history(self, filters: dict[str, Any]) -> dict[str, Any]:
        raw_m = filters.get("month")
        raw_y = filters.get("year")
        return self._app.query_history(
            month=int(raw_m) if raw_m not in (None, "", "all") else None,
            year=int(raw_y) if raw_y not in (None, "", "all") else None,
            kind=str(filters.get("kind") or "") or None,
            status=str(filters.get("status") or "") or None,
            keyword=str(filters.get("keyword") or ""),
        )

    def export_history_excel(self) -> dict[str, Any]:
        """Xuất báo cáo lịch sử Excel trên Background Thread + mở bằng Excel sau khi xong."""
        if self._window is None:
            return self._app.export_history_excel()

        chosen = self._window.create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename="Lich_su_gui_mail.xlsx",
            file_types=("Excel Workbook (*.xlsx)",),
        )
        if not chosen:
            return {"ok": False, "cancelled": True}
        dest_str = chosen if isinstance(chosen, str) else str(chosen[0])
        dest = Path(dest_str)

        def _worker() -> None:
            res = self._app.export_history_excel(dest)
            if res.get("ok"):
                try:
                    os.startfile(dest)  # type: ignore[attr-defined]  # noqa: S606
                except OSError:
                    pass
            self.emit_event("history:exported", res)

        threading.Thread(target=_worker, daemon=True, name="ExportHistoryWorker").start()
        return {"ok": True, "async": True}

    # ------------------------------------------------------------------ Cập nhật OTA 2 tiến trình

    def check_ota_update(self, silent: bool = False) -> dict[str, Any]:
        with self._ota_lock:
            if self._ota_checking or self._ota_downloading:
                return {"ok": False, "message": "Đang kiểm tra hoặc tải bản cập nhật."}
            self._ota_checking = True

        def _worker() -> None:
            token = self._secrets.load_github_token()
            try:
                rel = ota_updater.check_for_update(current_version=__version__, token=token)
                self._pending_release = rel
                if rel is not None:
                    self.emit_event(
                        "ota:checked",
                        {
                            "has_update": True,
                            "silent": silent,
                            "version": rel.version,
                            "release_notes": rel.release_notes[:600],
                            "asset_name": rel.asset_name,
                            "has_sha256": bool(rel.sha256),
                        },
                    )
                elif not silent:
                    self.emit_event(
                        "ota:checked",
                        {
                            "has_update": False,
                            "silent": False,
                            "version": __version__,
                            "message": f"Bạn đang sử dụng phiên bản mới nhất (v{__version__}).",
                        },
                    )
            except Exception as exc:
                if not silent:
                    self.emit_event(
                        "ota:checked",
                        {
                            "has_update": False,
                            "silent": False,
                            "error": redact_secrets(str(exc), (token,)),
                        },
                    )
            finally:
                with self._ota_lock:
                    self._ota_checking = False

        threading.Thread(target=_worker, daemon=True, name="OtaCheckWorker").start()
        return {"ok": True}

    def apply_ota_update(self) -> dict[str, Any]:
        rel = self._pending_release
        if rel is None:
            return {"ok": False, "message": "Chưa phát hiện bản cập nhật mới."}
        if self.is_busy:
            return {"ok": False, "message": "Hãy chờ tác vụ gửi mail hoàn tất trước khi cập nhật."}

        with self._ota_lock:
            self._ota_downloading = True

        def _worker() -> None:
            token = self._secrets.load_github_token()
            try:
                temp_dir = Path(tempfile.gettempdir()) / "GmailAutoMailer_OTA"

                def _on_prog(dl: int, total: int) -> None:
                    pct = min(100, int((dl / total) * 100)) if total > 0 else 0
                    self.emit_event("ota:progress", {"percent": pct, "version": rel.version})

                pkg = ota_updater.download_release_asset(
                    rel, temp_dir, on_progress=_on_prog, token=token
                )
                relaunch: Optional[Path] = None
                if getattr(sys, "frozen", False):
                    relaunch = Path(sys.executable).resolve()
                else:
                    cand = get_app_dir() / "Gui_mail_nha_cung_cap.exe"
                    if cand.is_file():
                        relaunch = cand

                ota_updater.spawn_standalone_updater(
                    package_path=pkg,
                    target_dir=get_app_dir(),
                    current_pid=os.getpid(),
                    relaunch_exe=relaunch,
                )
                self.emit_event("ota:restarting", {"version": rel.version})
                time.sleep(0.3)
                if self._window is not None:
                    self._window.destroy()
            except Exception as exc:
                self.emit_event(
                    "ota:error",
                    {"message": redact_secrets(str(exc), (token,))},
                )
            finally:
                with self._ota_lock:
                    self._ota_downloading = False

        threading.Thread(target=_worker, daemon=True, name="OtaDownloadWorker").start()
        return {"ok": True}
