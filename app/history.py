"""Lịch sử gửi mail, lưu vào Lich_su_gui.csv (mở được bằng Excel)."""
import csv
from datetime import datetime

from .config import APP_DIR
from .mailer import SendResult
from .planner import MailPlan

HISTORY_PATH = APP_DIR / "Lich_su_gui.csv"
_COLUMNS = ["Thời gian", "Tháng", "Năm", "Loại", "Nhà cung cấp", "Người nhận",
            "Tiêu đề", "File đính kèm", "Kết quả", "Chi tiết"]
_OK = "Thành công"
_FAIL = "Lỗi"


def record(plan: MailPlan, result: SendResult, month: int, year: int, kind: str) -> bool:
    """Ghi 1 dòng lịch sử. Trả về False nếu không ghi được (ví dụ file đang mở trong Excel)."""
    is_new = not HISTORY_PATH.exists()
    row = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), f"{month:02d}", year, kind,
           plan.supplier, "; ".join(plan.recipients), plan.subject,
           "; ".join(a.name for a in plan.attachments),
           _OK if result.ok else _FAIL, result.message]
    try:
        # utf-8-sig chỉ ghi ở lần đầu để Excel hiển thị đúng tiếng Việt
        with open(HISTORY_PATH, "a", newline="", encoding="utf-8-sig" if is_new else "utf-8") as f:
            writer = csv.writer(f)
            if is_new:
                writer.writerow(_COLUMNS)
            writer.writerow(row)
    except OSError:
        return False
    return True


def sent_suppliers(month: int, year: int, kind: str) -> set[str]:
    """Các nhà cung cấp đã gửi thành công trong kỳ (tháng, năm, loại) này."""
    if not HISTORY_PATH.exists():
        return set()
    try:
        with open(HISTORY_PATH, newline="", encoding="utf-8-sig") as f:
            return {row["Nhà cung cấp"] for row in csv.DictReader(f)
                    if row["Tháng"] == f"{month:02d}" and row["Năm"] == str(year)
                    and row["Loại"] == kind and row["Kết quả"] == _OK}
    except (OSError, KeyError):
        return set()
