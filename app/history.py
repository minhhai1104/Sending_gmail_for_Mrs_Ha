"""Lịch sử gửi mail: Lưu trữ an toàn vào SQLite (history.db), đồng bộ CSV và xuất báo cáo Excel (.xlsx)."""
import csv
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .config import APP_DIR
from .mailer import SendResult
from .planner import MailPlan

HISTORY_PATH = APP_DIR / "Lich_su_gui.csv"
EXCEL_HISTORY_PATH = APP_DIR / "Lich_su_gui.xlsx"
DB_PATH = APP_DIR / "history.db"
_COLUMNS = [
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
_OK = "Thành công"
_FAIL = "Lỗi"
_FORMULA_PREFIXES = ("=", "+", "-", "@")


def _sanitize_csv_field(value: Any) -> str:
    """Chống lỗi CSV/Excel Formula Injection khi mở file bằng Microsoft Excel."""
    text = str(value) if value is not None else ""
    if text and text[0] in _FORMULA_PREFIXES:
        return "'" + text
    return text


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS send_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sent_at TEXT NOT NULL,
            month INTEGER NOT NULL,
            year INTEGER NOT NULL,
            kind TEXT NOT NULL,
            supplier TEXT NOT NULL,
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
        CREATE INDEX IF NOT EXISTS idx_history_period
        ON send_history(year, month, kind, status)
        """
    )


def _append_csv_row(row: list[Any], csv_path: Path) -> None:
    is_new = not csv_path.exists()
    safe_row = [_sanitize_csv_field(col) for col in row]
    with open(
        csv_path,
        "a",
        newline="",
        encoding="utf-8-sig" if is_new else "utf-8",
    ) as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(_COLUMNS)
        writer.writerow(safe_row)


def record(
    plan: MailPlan,
    result: SendResult,
    month: int,
    year: int,
    kind: str,
    csv_path: Path = HISTORY_PATH,
    db_path: Path = DB_PATH,
) -> bool:
    """Ghi lịch sử gửi vào SQLite (nguồn sự thật chính) và đồng bộ sang file CSV."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    recipients_str = "; ".join(plan.recipients)
    attachments_str = "; ".join(a.name for a in plan.attachments)
    status_str = _OK if result.ok else _FAIL

    db_saved = False
    try:
        with closing(sqlite3.connect(db_path)) as conn:
            _init_db(conn)
            conn.execute(
                """
                INSERT INTO send_history (
                    sent_at, month, year, kind, supplier,
                    recipients, subject, attachments, status, detail
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now_str,
                    int(month),
                    int(year),
                    kind,
                    plan.supplier,
                    recipients_str,
                    plan.subject,
                    attachments_str,
                    status_str,
                    result.message,
                ),
            )
            conn.commit()
        db_saved = True
    except sqlite3.Error:
        db_saved = False

    row = [
        now_str,
        f"{int(month):02d}",
        int(year),
        kind,
        plan.supplier,
        recipients_str,
        plan.subject,
        attachments_str,
        status_str,
        result.message,
    ]
    csv_saved = False
    try:
        _append_csv_row(row, csv_path)
        csv_saved = True
    except OSError:
        csv_saved = False

    return db_saved or csv_saved


def _parse_int(val: Any) -> int:
    try:
        return int(str(val).strip().lstrip("'"))
    except (ValueError, TypeError):
        return -1


def sent_suppliers(
    month: int,
    year: int,
    kind: str,
    csv_path: Path = HISTORY_PATH,
    db_path: Path = DB_PATH,
) -> set[str]:
    """Các nhà cung cấp đã gửi thành công trong kỳ (tháng, năm, loại) từ cả SQLite và CSV."""
    found: set[str] = set()

    if db_path.is_file():
        try:
            with closing(sqlite3.connect(db_path)) as conn:
                _init_db(conn)
                cur = conn.execute(
                    """
                    SELECT DISTINCT supplier FROM send_history
                    WHERE month = ? AND year = ? AND kind = ? AND status = ?
                    """,
                    (int(month), int(year), kind, _OK),
                )
                found.update(row[0] for row in cur.fetchall() if row[0])
        except sqlite3.Error:
            pass

    if csv_path.is_file():
        try:
            with open(csv_path, newline="", encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    if (
                        _parse_int(row.get("Tháng")) == int(month)
                        and _parse_int(row.get("Năm")) == int(year)
                        and (row.get("Loại") or "").strip() == kind
                        and (row.get("Kết quả") or "").strip() == _OK
                    ):
                        sup = (row.get("Nhà cung cấp") or "").strip().lstrip("'")
                        if sup:
                            found.add(sup)
        except (OSError, KeyError, csv.Error):
            pass

    return found


def export_sqlite_to_csv(
    csv_path: Path = HISTORY_PATH,
    db_path: Path = DB_PATH,
) -> bool:
    """Xuất đồng bộ dữ liệu từ SQLite ra file CSV để mở xem bằng Excel."""
    if not db_path.is_file():
        return csv_path.is_file()
    try:
        with closing(sqlite3.connect(db_path)) as conn:
            _init_db(conn)
            rows = conn.execute(
                """
                SELECT sent_at, month, year, kind, supplier,
                       recipients, subject, attachments, status, detail
                FROM send_history ORDER BY id ASC
                """
            ).fetchall()
        if not rows:
            return csv_path.is_file()
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(_COLUMNS)
            for r in rows:
                formatted = [
                    r[0],
                    f"{int(r[1]):02d}",
                    r[2],
                    r[3],
                    r[4],
                    r[5],
                    r[6],
                    r[7],
                    r[8],
                    r[9],
                ]
                writer.writerow([_sanitize_csv_field(c) for c in formatted])
        return True
    except (sqlite3.Error, OSError):
        return csv_path.is_file()


def export_sqlite_to_excel(
    excel_path: Path = EXCEL_HISTORY_PATH,
    db_path: Path = DB_PATH,
) -> bool:
    """Kết xuất toàn bộ lịch sử từ SQLite ra file Excel (.xlsx) định dạng chuyên nghiệp."""
    if not db_path.is_file():
        return False
    try:
        with closing(sqlite3.connect(db_path)) as conn:
            _init_db(conn)
            rows = conn.execute(
                """
                SELECT sent_at, month, year, kind, supplier,
                       recipients, subject, attachments, status, detail
                FROM send_history ORDER BY id ASC
                """
            ).fetchall()
        if not rows:
            return False

        wb = Workbook()
        try:
            ws = wb.active
            ws.title = "Lịch sử gửi mail"
            header_fill = PatternFill("solid", fgColor="1F4E78")
            ok_fill = PatternFill("solid", fgColor="E2EFDA")
            fail_fill = PatternFill("solid", fgColor="FCE4D6")
            thin = Side(style="thin", color="D9D9D9")
            border = Border(left=thin, right=thin, top=thin, bottom=thin)

            for col_idx, col_name in enumerate(_COLUMNS, 1):
                cell = ws.cell(row=1, column=col_idx, value=col_name)
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = header_fill
                cell.alignment = Alignment(vertical="center", horizontal="center")
                cell.border = border

            for row_offset, r in enumerate(rows, 2):
                month_text = f"{int(r[1]):02d}"
                row_values = [
                    _sanitize_csv_field(r[0]),
                    month_text,
                    int(r[2]),
                    _sanitize_csv_field(r[3]),
                    _sanitize_csv_field(r[4]),
                    _sanitize_csv_field(r[5]),
                    _sanitize_csv_field(r[6]),
                    _sanitize_csv_field(r[7]),
                    _sanitize_csv_field(r[8]),
                    _sanitize_csv_field(r[9]),
                ]
                is_ok = str(r[8]).strip() == _OK
                row_fill = ok_fill if is_ok else fail_fill
                for col_idx, val in enumerate(row_values, 1):
                    c = ws.cell(row=row_offset, column=col_idx, value=val)
                    c.border = border
                    c.fill = row_fill
                    if col_idx == 2:
                        c.number_format = "@"  # Giữ nguyên số 0 ở đầu cho cột Tháng ("09")
                    if col_idx in (2, 3, 4, 9):
                        c.alignment = Alignment(horizontal="center", vertical="top")
                    else:
                        c.alignment = Alignment(vertical="top", wrap_text=True)

            col_widths = [20, 8, 8, 12, 18, 32, 42, 38, 14, 30]
            for idx, width in enumerate(col_widths, 1):
                ws.column_dimensions[get_column_letter(idx)].width = width
            ws.freeze_panes = "A2"
            wb.save(excel_path)
            return True
        finally:
            wb.close()
    except (sqlite3.Error, OSError):
        return False
