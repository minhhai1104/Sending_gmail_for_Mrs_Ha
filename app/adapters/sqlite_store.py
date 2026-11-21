"""SQLite WAL Single Source of Truth (SSOT) cho Cấu hình In-App & Lịch sử gửi mail."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from ..domain.models import (
    DEFAULT_BODY,
    DEFAULT_EXCEL_TEMPLATE,
    DEFAULT_MAX_RETRIES,
    DEFAULT_PACING_SECONDS,
    DEFAULT_PDF_TEMPLATE,
    DEFAULT_SUBJECT,
    DEFAULT_SUPPLIER_NAMES,
    AppConfig,
    AppPrefs,
    GmailSettings,
    HistoryRecord,
    MailPlan,
    MailTemplates,
    PeriodStats,
    SendResult,
    Supplier,
)
from ..domain.validation import normalize_name
from .paths import get_db_path, get_default_attach_dir

STATUS_OK = "Thành công"
STATUS_FAIL = "Lỗi"
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
_EXCEL_COLUMNS = [
    "Thời gian",
    "Tháng",
    "Năm",
    "Loại",
    "Nhà cung cấp",
    "Người nhận",
    "Tiêu đề",
    "File đính kèm",
    "Kết quả",
    "Chi tiết",
]


def sanitize_spreadsheet_cell(value: Any) -> str:
    """Chống lỗi CSV/Excel Formula Injection (CWE-1236) khi mở báo cáo lịch sử bằng Excel."""
    text = str(value) if value is not None else ""
    if text and text[0] in _FORMULA_PREFIXES:
        return "'" + text
    return text


class SqliteAppStore:
    """Triển khai đồng thời `ConfigRepository` và `HistoryRepository` trên SQLite WAL."""

    def __init__(self, db_path: Optional[Path] = None, seed_defaults: bool = True) -> None:
        self._db_path = db_path if db_path is not None else get_db_path()
        self._seed_defaults = seed_defaults
        self._ensure_schema()

    @property
    def db_path(self) -> Path:
        return self._db_path

    def _connect(self) -> sqlite3.Connection:
        if str(self._db_path) != ":memory:":
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path), timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _ensure_schema(self) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                """
            )
            cur = conn.execute("SELECT MAX(version) FROM schema_migrations")
            row = cur.fetchone()
            current_ver = int(row[0]) if row and row[0] is not None else 0

            if current_ver < 1:
                self._apply_migration_v1(conn)
                conn.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                    (1, datetime.now().isoformat(timespec="seconds")),
                )
            conn.commit()

    def _apply_migration_v1(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                norm_name TEXT NOT NULL UNIQUE,
                recipients_json TEXT NOT NULL,
                aliases_json TEXT NOT NULL DEFAULT '[]',
                note TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS send_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT NOT NULL DEFAULT '',
                sent_at TEXT NOT NULL,
                month INTEGER NOT NULL,
                year INTEGER NOT NULL,
                kind TEXT NOT NULL,
                supplier TEXT NOT NULL,
                norm_supplier TEXT NOT NULL,
                recipients TEXT NOT NULL,
                subject TEXT NOT NULL,
                attachments TEXT NOT NULL,
                status TEXT NOT NULL,
                detail TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_history_period_norm
            ON send_history(year, month, kind, status, norm_supplier)
            """
        )

        # Khởi tạo giá trị mặc định sạch sẽ (100% không lưu mật khẩu)
        defaults = {
            "sender": "",
            "display_name": "Ms. Ngoc Ha - Haesung Vina",
            "attach_dir": str(get_default_attach_dir()),
            "cc_json": "[]",
            "logo_path": "",
            "pacing_seconds": str(DEFAULT_PACING_SECONDS),
            "max_retries": str(DEFAULT_MAX_RETRIES),
            "subject_tpl": DEFAULT_SUBJECT,
            "body_tpl": DEFAULT_BODY,
            "excel_tpl": DEFAULT_EXCEL_TEMPLATE,
            "pdf_tpl": DEFAULT_PDF_TEMPLATE,
            "theme": "system",
            "onboarding_completed": "0",
            "last_source_dir": "",
        }
        for k, v in defaults.items():
            conn.execute(
                "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
                (k, v),
            )

        if self._seed_defaults:
            sup_count = conn.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0]
            if sup_count == 0:
                for order, name in enumerate(DEFAULT_SUPPLIER_NAMES):
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO suppliers
                        (name, norm_name, recipients_json, aliases_json, note, enabled, sort_order)
                        VALUES (?, ?, '[]', '[]', '', 1, ?)
                        """,
                        (name, normalize_name(name), order),
                    )

    def import_legacy_history_db(self, legacy_db_path: Path) -> int:
        """Kế thừa một lần lịch sử gửi từ `history.db` của v2.0 (nếu tồn tại) khi nâng cấp."""
        if not legacy_db_path.is_file():
            return 0
        imported = 0
        try:
            with closing(self._connect()) as conn:
                already = conn.execute(
                    "SELECT value FROM app_settings WHERE key = 'legacy_history_imported'"
                ).fetchone()
                if already and already["value"] == "1":
                    return 0

                with closing(sqlite3.connect(str(legacy_db_path), timeout=3.0)) as old_conn:
                    tables = {
                        r[0]
                        for r in old_conn.execute(
                            "SELECT name FROM sqlite_master WHERE type='table'"
                        ).fetchall()
                    }
                    if "send_history" not in tables:
                        return 0
                    old_rows = old_conn.execute(
                        """
                        SELECT sent_at, month, year, kind, supplier,
                               recipients, subject, attachments, status, detail
                        FROM send_history ORDER BY id ASC
                        """
                    ).fetchall()

                for r in old_rows:
                    conn.execute(
                        """
                        INSERT INTO send_history (
                            batch_id, sent_at, month, year, kind, supplier, norm_supplier,
                            recipients, subject, attachments, status, detail
                        ) VALUES ('legacy_v2', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(r[0]),
                            int(r[1]),
                            int(r[2]),
                            str(r[3]),
                            str(r[4]),
                            normalize_name(str(r[4])),
                            str(r[5]),
                            str(r[6]),
                            str(r[7]),
                            str(r[8]),
                            str(r[9]),
                        ),
                    )
                    imported += 1

                conn.execute(
                    "INSERT OR REPLACE INTO app_settings (key, value) VALUES ('legacy_history_imported', '1')"
                )
                conn.commit()
        except sqlite3.Error:
            return imported
        return imported

    # ------------------------------------------------------------------ ConfigRepository

    def load_config(self) -> AppConfig:
        with closing(self._connect()) as conn:
            kv = {
                row["key"]: row["value"]
                for row in conn.execute("SELECT key, value FROM app_settings").fetchall()
            }
            sup_rows = conn.execute(
                """
                SELECT id, name, recipients_json, aliases_json, note, enabled, sort_order
                FROM suppliers ORDER BY sort_order ASC, id ASC
                """
            ).fetchall()

        cc_list = _parse_json_str_list(kv.get("cc_json", "[]"))
        settings = GmailSettings(
            sender=kv.get("sender", ""),
            display_name=kv.get("display_name", "Ms. Ngoc Ha - Haesung Vina"),
            attach_dir=kv.get("attach_dir", ""),
            cc=cc_list,
            logo_path=kv.get("logo_path", ""),
            pacing_seconds=_safe_float(kv.get("pacing_seconds"), DEFAULT_PACING_SECONDS),
            max_retries=_safe_int(kv.get("max_retries"), DEFAULT_MAX_RETRIES),
        )
        templates = MailTemplates(
            subject=kv.get("subject_tpl", DEFAULT_SUBJECT),
            body=kv.get("body_tpl", DEFAULT_BODY),
            excel_name=kv.get("excel_tpl", DEFAULT_EXCEL_TEMPLATE),
            pdf_name=kv.get("pdf_tpl", DEFAULT_PDF_TEMPLATE),
        )
        prefs = AppPrefs(
            theme=kv.get("theme", "system"),
            onboarding_completed=kv.get("onboarding_completed", "0") == "1",
            last_source_dir=kv.get("last_source_dir", ""),
        )
        suppliers = [
            Supplier(
                id=int(r["id"]),
                name=str(r["name"]),
                recipients=_parse_json_str_list(r["recipients_json"]),
                aliases=_parse_json_str_list(r["aliases_json"]),
                note=str(r["note"] or ""),
                enabled=bool(int(r["enabled"])),
                sort_order=int(r["sort_order"]),
            )
            for r in sup_rows
        ]
        return AppConfig(settings=settings, templates=templates, prefs=prefs, suppliers=suppliers)

    def save_settings(self, settings: GmailSettings) -> None:
        updates = {
            "sender": settings.sender.strip(),
            "display_name": settings.display_name.strip(),
            "attach_dir": settings.attach_dir.strip(),
            "cc_json": json.dumps(settings.cc, ensure_ascii=False),
            "logo_path": settings.logo_path.strip(),
            "pacing_seconds": str(float(settings.pacing_seconds)),
            "max_retries": str(int(settings.max_retries)),
        }
        with closing(self._connect()) as conn:
            for k, v in updates.items():
                conn.execute(
                    "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
                    (k, v),
                )
            conn.commit()

    def save_templates(self, subject: str, body: str, excel_name: str, pdf_name: str) -> None:
        updates = {
            "subject_tpl": subject,
            "body_tpl": body,
            "excel_tpl": excel_name.strip(),
            "pdf_tpl": pdf_name.strip(),
        }
        with closing(self._connect()) as conn:
            for k, v in updates.items():
                conn.execute(
                    "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
                    (k, v),
                )
            conn.commit()

    def save_prefs(
        self,
        *,
        theme: Optional[str] = None,
        onboarding_completed: Optional[bool] = None,
        last_source_dir: Optional[str] = None,
    ) -> None:
        updates: dict[str, str] = {}
        if theme is not None:
            updates["theme"] = theme if theme in {"light", "dark", "system"} else "system"
        if onboarding_completed is not None:
            updates["onboarding_completed"] = "1" if onboarding_completed else "0"
        if last_source_dir is not None:
            updates["last_source_dir"] = last_source_dir
        if not updates:
            return
        with closing(self._connect()) as conn:
            for k, v in updates.items():
                conn.execute(
                    "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
                    (k, v),
                )
            conn.commit()

    def upsert_supplier(self, supplier: Supplier) -> Supplier:
        clean_name = supplier.name.strip()
        norm = normalize_name(clean_name)
        rec_json = json.dumps(supplier.recipients, ensure_ascii=False)
        alias_json = json.dumps(supplier.aliases, ensure_ascii=False)
        with closing(self._connect()) as conn:
            if supplier.id is not None:
                conn.execute(
                    """
                    UPDATE suppliers
                    SET name = ?, norm_name = ?, recipients_json = ?,
                        aliases_json = ?, note = ?, enabled = ?, sort_order = ?
                    WHERE id = ?
                    """,
                    (
                        clean_name,
                        norm,
                        rec_json,
                        alias_json,
                        supplier.note.strip(),
                        1 if supplier.enabled else 0,
                        int(supplier.sort_order),
                        int(supplier.id),
                    ),
                )
                sup_id = int(supplier.id)
            else:
                max_order = conn.execute(
                    "SELECT COALESCE(MAX(sort_order), -1) FROM suppliers"
                ).fetchone()[0]
                order = supplier.sort_order if supplier.sort_order > 0 else int(max_order) + 1
                cur = conn.execute(
                    """
                    INSERT INTO suppliers
                    (name, norm_name, recipients_json, aliases_json, note, enabled, sort_order)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        clean_name,
                        norm,
                        rec_json,
                        alias_json,
                        supplier.note.strip(),
                        1 if supplier.enabled else 0,
                        order,
                    ),
                )
                sup_id = int(cur.lastrowid or 0)
            conn.commit()
        return Supplier(
            id=sup_id,
            name=clean_name,
            recipients=list(supplier.recipients),
            aliases=list(supplier.aliases),
            note=supplier.note.strip(),
            enabled=supplier.enabled,
            sort_order=supplier.sort_order,
        )

    def delete_supplier(self, supplier_id: int) -> bool:
        with closing(self._connect()) as conn:
            cur = conn.execute("DELETE FROM suppliers WHERE id = ?", (int(supplier_id),))
            conn.commit()
            return cur.rowcount > 0

    def set_supplier_enabled(self, supplier_id: int, enabled: bool) -> bool:
        with closing(self._connect()) as conn:
            cur = conn.execute(
                "UPDATE suppliers SET enabled = ? WHERE id = ?",
                (1 if enabled else 0, int(supplier_id)),
            )
            conn.commit()
            return cur.rowcount > 0

    # ------------------------------------------------------------------ HistoryRepository

    def record(
        self,
        plan: MailPlan,
        result: SendResult,
        month: int,
        year: int,
        kind: str,
        batch_id: str = "",
    ) -> bool:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        recipients_str = "; ".join(plan.recipients)
        attachments_str = "; ".join(
            att.file.name for att in plan.attachments if att.file is not None
        )
        status_str = STATUS_OK if result.ok else STATUS_FAIL
        try:
            with closing(self._connect()) as conn:
                conn.execute(
                    """
                    INSERT INTO send_history (
                        batch_id, sent_at, month, year, kind, supplier, norm_supplier,
                        recipients, subject, attachments, status, detail
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        batch_id,
                        now_str,
                        int(month),
                        int(year),
                        kind,
                        plan.supplier,
                        normalize_name(plan.supplier),
                        recipients_str,
                        plan.subject,
                        attachments_str,
                        status_str,
                        result.message,
                    ),
                )
                conn.commit()
            return True
        except sqlite3.Error:
            return False

    def sent_supplier_norms(self, month: int, year: int, kind: str) -> set[str]:
        """Trả về tập `norm_supplier` đã gửi thành công trong kỳ (chống lệch hoa/thường & NFC)."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT norm_supplier FROM send_history
                WHERE month = ? AND year = ? AND kind = ? AND status = ?
                """,
                (int(month), int(year), kind, STATUS_OK),
            ).fetchall()
        return {str(r["norm_supplier"]) for r in rows if r["norm_supplier"]}

    def failed_supplier_norms(self, month: int, year: int, kind: str) -> set[str]:
        """Trả về tập `norm_supplier` hiện vẫn đang lỗi (tự loại những nhà sau đó đã gửi lại OK)."""
        with closing(self._connect()) as conn:
            failed_rows = conn.execute(
                """
                SELECT DISTINCT norm_supplier FROM send_history
                WHERE month = ? AND year = ? AND kind = ? AND status = ?
                """,
                (int(month), int(year), kind, STATUS_FAIL),
            ).fetchall()
        failed = {str(r["norm_supplier"]) for r in failed_rows if r["norm_supplier"]}
        sent_ok = self.sent_supplier_norms(month, year, kind)
        return failed - sent_ok

    def query_history(
        self,
        month: Optional[int] = None,
        year: Optional[int] = None,
        kind: Optional[str] = None,
        status: Optional[str] = None,
        keyword: str = "",
        limit: int = 500,
    ) -> list[HistoryRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if month is not None:
            clauses.append("month = ?")
            params.append(int(month))
        if year is not None:
            clauses.append("year = ?")
            params.append(int(year))
        if kind:
            clauses.append("kind = ?")
            params.append(kind)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if keyword.strip():
            kw = f"%{keyword.strip().lower()}%"
            clauses.append(
                "(LOWER(supplier) LIKE ? OR LOWER(recipients) LIKE ? "
                "OR LOWER(subject) LIKE ? OR LOWER(detail) LIKE ?)"
            )
            params.extend([kw, kw, kw, kw])

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = (
            "SELECT id, batch_id, sent_at, month, year, kind, supplier, "  # noqa: S608
            "recipients, subject, attachments, status, detail "
            f"FROM send_history {where} ORDER BY id DESC LIMIT ?"
        )
        params.append(max(1, min(int(limit), 5000)))
        with closing(self._connect()) as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            HistoryRecord(
                id=int(r["id"]),
                batch_id=str(r["batch_id"]),
                sent_at=str(r["sent_at"]),
                month=int(r["month"]),
                year=int(r["year"]),
                kind=str(r["kind"]),
                supplier=str(r["supplier"]),
                recipients=str(r["recipients"]),
                subject=str(r["subject"]),
                attachments=str(r["attachments"]),
                status=str(r["status"]),
                detail=str(r["detail"]),
            )
            for r in rows
        ]

    def period_stats(self, month: int, year: int, kind: Optional[str] = None) -> PeriodStats:
        clauses = ["month = ?", "year = ?"]
        params: list[Any] = [int(month), int(year)]
        if kind:
            clauses.append("kind = ?")
            params.append(kind)
        sql = (
            f"SELECT status, COUNT(*) as cnt FROM send_history WHERE {' AND '.join(clauses)} GROUP BY status"  # noqa: S608
        )
        with closing(self._connect()) as conn:
            rows = conn.execute(sql, params).fetchall()
        ok_count = 0
        fail_count = 0
        for r in rows:
            if r["status"] == STATUS_OK:
                ok_count = int(r["cnt"])
            else:
                fail_count += int(r["cnt"])
        total = ok_count + fail_count
        rate = round((ok_count / total) * 100.0, 1) if total > 0 else 0.0
        return PeriodStats(total=total, ok_count=ok_count, fail_count=fail_count, success_rate=rate)

    def export_excel(self, dest_path: Path) -> bool:
        """Xuất báo cáo lịch sử gửi ra file Excel (.xlsx) định dạng chuyên nghiệp."""
        records = self.query_history(limit=5000)
        if not records:
            return False
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        wb = Workbook()
        try:
            ws = wb.active
            ws.title = "Lịch sử gửi mail"
            header_fill = PatternFill("solid", fgColor="0F4C81")
            ok_fill = PatternFill("solid", fgColor="ECFDF3")
            fail_fill = PatternFill("solid", fgColor="FEF2F2")
            thin = Side(style="thin", color="CBD5E1")
            border = Border(left=thin, right=thin, top=thin, bottom=thin)

            for col_idx, col_name in enumerate(_EXCEL_COLUMNS, 1):
                cell = ws.cell(row=1, column=col_idx, value=col_name)
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = header_fill
                cell.alignment = Alignment(vertical="center", horizontal="center")
                cell.border = border

            for row_offset, rec in enumerate(reversed(records), 2):
                values = [
                    sanitize_spreadsheet_cell(rec.sent_at),
                    f"{rec.month:02d}",
                    rec.year,
                    sanitize_spreadsheet_cell(rec.kind),
                    sanitize_spreadsheet_cell(rec.supplier),
                    sanitize_spreadsheet_cell(rec.recipients),
                    sanitize_spreadsheet_cell(rec.subject),
                    sanitize_spreadsheet_cell(rec.attachments),
                    sanitize_spreadsheet_cell(rec.status),
                    sanitize_spreadsheet_cell(rec.detail),
                ]
                row_fill = ok_fill if rec.status == STATUS_OK else fail_fill
                for col_idx, val in enumerate(values, 1):
                    c = ws.cell(row=row_offset, column=col_idx, value=val)
                    c.border = border
                    c.fill = row_fill
                    if col_idx == 2:
                        c.number_format = "@"  # Giữ số 0 đầu tháng ("09")
                    if col_idx in (2, 3, 4, 9):
                        c.alignment = Alignment(horizontal="center", vertical="top")
                    else:
                        c.alignment = Alignment(vertical="top", wrap_text=True)

            widths = [20, 8, 8, 12, 18, 32, 42, 38, 14, 34]
            for idx, width in enumerate(widths, 1):
                ws.column_dimensions[get_column_letter(idx)].width = width
            ws.freeze_panes = "A2"
            wb.save(dest_path)
            return True
        except OSError:
            return False
        finally:
            wb.close()


def _parse_json_str_list(raw: str) -> list[str]:
    try:
        data = json.loads(raw or "[]")
        if isinstance(data, list):
            return [str(x).strip() for x in data if str(x).strip()]
    except ValueError:
        pass
    return []


def _safe_float(raw: Optional[str], default: float) -> float:
    try:
        return float(raw) if raw is not None else default
    except ValueError:
        return default


def _safe_int(raw: Optional[str], default: int) -> int:
    try:
        return int(raw) if raw is not None else default
    except ValueError:
        return default
