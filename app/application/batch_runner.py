"""Headless BatchRunner: State Machine, Worker-Side SQLite Commit, Pause-Aware Telemetry & Retry."""

from __future__ import annotations

import threading
import uuid
from typing import Callable, Optional

from ..adapters.smtp_mailer import MailTransportError, generate_message_id
from ..domain.models import (
    BatchProgress,
    BatchState,
    BatchSummary,
    GmailSettings,
    MailPlan,
    SendErrorKind,
    SendKind,
    SendResult,
)
from ..domain.validation import redact_secrets
from ..ports.protocols import Clock, HistoryRepository, MailTransport, SystemClock


class BatchRunner:
    """Điều phối luồng gửi hàng loạt trên Worker Thread, 100% kiểm thử được qua FakeClock."""

    def __init__(
        self,
        mail_transport: MailTransport,
        history_repo: HistoryRepository,
        clock: Optional[Clock] = None,
    ) -> None:
        self._transport = mail_transport
        self._history = history_repo
        self._clock: Clock = clock if clock is not None else SystemClock()

        self._lock = threading.Lock()
        self._state = BatchState.IDLE
        self._pause_event = threading.Event()
        self._cancel_event = threading.Event()
        self._worker: Optional[threading.Thread] = None
        self._last_summary: Optional[BatchSummary] = None

        # Bộ đếm thời gian Pause chuẩn xác
        self._pause_started_at: Optional[float] = None
        self._accumulated_pause: float = 0.0

    @property
    def state(self) -> BatchState:
        with self._lock:
            return self._state

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._state in {BatchState.RUNNING, BatchState.PAUSED, BatchState.CANCELLING}

    @property
    def last_summary(self) -> Optional[BatchSummary]:
        with self._lock:
            return self._last_summary

    def pause(self) -> bool:
        with self._lock:
            if self._state != BatchState.RUNNING:
                return False
            self._state = BatchState.PAUSED
            self._pause_started_at = self._clock.monotonic()
            self._pause_event.set()
            return True

    def resume(self) -> bool:
        with self._lock:
            if self._state != BatchState.PAUSED:
                return False
            if self._pause_started_at is not None:
                self._accumulated_pause += max(0.0, self._clock.monotonic() - self._pause_started_at)
                self._pause_started_at = None
            self._state = BatchState.RUNNING
            self._pause_event.clear()
            return True

    def cancel(self) -> bool:
        with self._lock:
            if self._state not in {BatchState.RUNNING, BatchState.PAUSED}:
                return False
            if self._pause_started_at is not None:
                self._accumulated_pause += max(0.0, self._clock.monotonic() - self._pause_started_at)
                self._pause_started_at = None
            self._state = BatchState.CANCELLING
            self._cancel_event.set()
            self._pause_event.clear()
            return True

    def cancel_and_wait(self, timeout: float = 5.0) -> None:
        """Graceful Shutdown: yêu cầu dừng và chờ email hiện tại commit xong vào SQLite."""
        self.cancel()
        worker = self._worker
        if worker is not None and worker.is_alive():
            worker.join(timeout=timeout)

    def start_async(
        self,
        *,
        settings: GmailSettings,
        app_password: str,
        plans: list[MailPlan],
        month: int,
        year: int,
        kind: SendKind,
        on_progress: Optional[Callable[[BatchProgress], None]] = None,
        on_item: Optional[Callable[[MailPlan, SendResult], None]] = None,
        on_done: Optional[Callable[[BatchSummary], None]] = None,
    ) -> bool:
        with self._lock:
            if self._state in {BatchState.RUNNING, BatchState.PAUSED, BatchState.CANCELLING}:
                return False
            self._state = BatchState.RUNNING
            self._pause_event.clear()
            self._cancel_event.clear()
            self._pause_started_at = None
            self._accumulated_pause = 0.0

        def _target() -> None:
            summary = self.run_sync(
                settings=settings,
                app_password=app_password,
                plans=plans,
                month=month,
                year=year,
                kind=kind,
                on_progress=on_progress,
                on_item=on_item,
            )
            if on_done is not None:
                on_done(summary)

        self._worker = threading.Thread(target=_target, daemon=True, name="MailBatchWorker")
        self._worker.start()
        return True

    def _wait_if_paused(self) -> bool:
        """Chờ trong lúc PAUSED, trả về True nếu nhận lệnh hủy."""
        while self._pause_event.is_set():
            if self._cancel_event.is_set():
                return True
            self._clock.sleep(0.1)
        return self._cancel_event.is_set()

    def _active_elapsed(self, start_time: float) -> float:
        now = self._clock.monotonic()
        with self._lock:
            extra_pause = (
                max(0.0, now - self._pause_started_at)
                if self._pause_started_at is not None
                else 0.0
            )
            total_pause = self._accumulated_pause + extra_pause
        return max(0.05, (now - start_time) - total_pause)

    def run_sync(
        self,
        *,
        settings: GmailSettings,
        app_password: str,
        plans: list[MailPlan],
        month: int,
        year: int,
        kind: SendKind,
        on_progress: Optional[Callable[[BatchProgress], None]] = None,
        on_item: Optional[Callable[[MailPlan, SendResult], None]] = None,
    ) -> BatchSummary:
        """Thực thi đồng bộ toàn bộ đợt gửi (được dùng trực tiếp trong pytest và từ `start_async`)."""
        with self._lock:
            if self._state not in {BatchState.RUNNING, BatchState.PAUSED}:
                self._state = BatchState.RUNNING
                self._pause_event.clear()
                self._cancel_event.clear()
                self._pause_started_at = None
                self._accumulated_pause = 0.0

        batch_id = uuid.uuid4().hex[:12]
        total = len(plans)
        completed = 0
        ok_count = 0
        fail_count = 0
        results: list[SendResult] = []
        failed_plans: list[MailPlan] = []
        start_time = self._clock.monotonic()

        def _emit_progress(current_supplier: str = "") -> None:
            if on_progress is None:
                return
            pct = min(100, int((completed / max(1, total)) * 100)) if total > 0 else 100
            elapsed = self._active_elapsed(start_time)
            if completed > 0:
                avg_sec = elapsed / completed
                rate = round((completed / elapsed) * 60.0, 1)
                eta = max(0, int((total - completed) * avg_sec))
            else:
                rate = 0.0
                eta = 0
            on_progress(
                BatchProgress(
                    state=self.state,
                    total=total,
                    completed=completed,
                    ok_count=ok_count,
                    fail_count=fail_count,
                    percent=pct,
                    rate_per_min=rate,
                    eta_seconds=eta,
                    current_supplier=current_supplier,
                )
            )

        _emit_progress(plans[0].supplier if plans else "")

        try:
            with self._transport.open_session(settings, app_password) as session:
                for idx, plan in enumerate(plans):
                    if self._wait_if_paused():
                        break

                    _emit_progress(plan.supplier)
                    msg_id = generate_message_id(settings.sender)
                    result = self._send_single_with_retry(
                        session=session,
                        plan=plan,
                        message_id=msg_id,
                        max_retries=settings.max_retries,
                        app_password=app_password,
                    )
                    if result is None:
                        break

                    # BẮT BUỘC: Ghi bền vững vào SQLite NGAY TRÊN WORKER THREAD trước khi báo UI!
                    self._history.record(plan, result, month, year, kind.value, batch_id=batch_id)

                    results.append(result)
                    completed += 1
                    if result.ok:
                        ok_count += 1
                    else:
                        fail_count += 1
                        failed_plans.append(plan)

                    if on_item is not None:
                        on_item(plan, result)
                    _emit_progress(plan.supplier)

                    if self._wait_if_paused():
                        break

                    # Smart Pacing giãn cách chống Gmail chặn spam
                    if settings.pacing_seconds > 0 and idx < total - 1:
                        if self._clock.wait_event(self._cancel_event, settings.pacing_seconds):
                            break
        except Exception as exc:
            # Lỗi mở phiên SMTP ban đầu (vd sai App Password hoặc mất mạng hoàn toàn)
            err_msg = redact_secrets(str(exc), (app_password,))
            err_kind = exc.kind if isinstance(exc, MailTransportError) else SendErrorKind.TRANSIENT_NETWORK
            for remaining_plan in plans[completed:]:
                fail_res = SendResult(
                    supplier=remaining_plan.supplier,
                    ok=False,
                    message=err_msg,
                    error_kind=err_kind,
                )
                self._history.record(
                    remaining_plan, fail_res, month, year, kind.value, batch_id=batch_id
                )
                results.append(fail_res)
                failed_plans.append(remaining_plan)
                completed += 1
                fail_count += 1
                if on_item is not None:
                    on_item(remaining_plan, fail_res)

        final_state = BatchState.CANCELLED if self._cancel_event.is_set() else BatchState.DONE
        with self._lock:
            self._state = final_state
            summary = BatchSummary(
                batch_id=batch_id,
                state=final_state,
                total=total,
                ok_count=ok_count,
                fail_count=fail_count,
                results=results,
                failed_plans=failed_plans,
            )
            self._last_summary = summary

        _emit_progress("")
        return summary

    def _send_single_with_retry(
        self,
        *,
        session: object,
        plan: MailPlan,
        message_id: str,
        max_retries: int,
        app_password: str,
    ) -> Optional[SendResult]:
        attempt = 0
        while True:
            err_kind: SendErrorKind = SendErrorKind.TRANSIENT_NETWORK
            try:
                res: SendResult = session.send(plan, message_id=message_id)  # type: ignore[attr-defined]
                if res.ok or res.error_kind != SendErrorKind.TRANSIENT_NETWORK:
                    return res
                err_msg = redact_secrets(res.message, (app_password,))
                err_kind = res.error_kind
            except MailTransportError as exc:
                err_msg = redact_secrets(str(exc), (app_password,))
                err_kind = exc.kind
            except Exception as exc:
                err_msg = redact_secrets(str(exc), (app_password,))
                err_kind = SendErrorKind.TRANSIENT_NETWORK

            # CHỈ retry khi lỗi mạng tạm thời (`TRANSIENT_NETWORK`)
            if err_kind == SendErrorKind.TRANSIENT_NETWORK and attempt < max_retries:
                attempt += 1
                backoff = min(8.0, 1.0 * (2 ** (attempt - 1)))
                if self._clock.wait_event(self._cancel_event, backoff):
                    return None
                continue

            return SendResult(
                supplier=plan.supplier,
                ok=False,
                message=err_msg,
                error_kind=err_kind,
                message_id=message_id,
            )
