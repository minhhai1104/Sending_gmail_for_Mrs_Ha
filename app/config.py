"""Đọc file cấu hình Excel (Cau_hinh.xlsx), bảo mật mật khẩu và tự động nâng cấp cấu trúc."""
import re
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils.exceptions import InvalidFileException
from openpyxl.worksheet.datavalidation import DataValidation

from .security import (
    SAVED_PLACEHOLDER,
    is_valid_app_password,
    load_password,
    normalize_app_password,
    save_password,
)
from .templating import VARIABLES

if getattr(sys, "frozen", False):  # chạy từ file .exe: dữ liệu nằm cạnh file exe
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = APP_DIR / "Cau_hinh.xlsx"
DEFAULT_VAULT_PATH = APP_DIR / ".credentials.dat"

SHEET_GUIDE = "Hướng dẫn"
SHEET_GMAIL = "Gmail"
SHEET_SUPPLIERS = "Nhà cung cấp"
SHEET_CONTENT = "Nội dung mail"

# Nhãn ở cột A. App đọc theo nhãn nên người dùng chèn thêm dòng cũng không sao.
LBL_SENDER = "Gmail dùng để gửi"
LBL_NAME = "Tên hiển thị người gửi"
LBL_PASSWORD = "Mật khẩu ứng dụng Gmail"
LBL_ATTACH_DIR = "Thư mục chứa file đính kèm"
LBL_CC = "CC chung (không bắt buộc)"
LBL_LOGO = "Logo chữ ký (không bắt buộc)"
LBL_SUBJECT = "Tiêu đề mail"
LBL_BODY = "Nội dung mail"
LBL_EXCEL = "Tên file Excel đính kèm"
LBL_PDF = "Tên file PDF đính kèm"

SUPPLIER_HEADER_ROW = 3
_OFF_VALUES = {"không", "khong", "no", "n", "0", "false"}
_EMAIL_RE = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$")


class ConfigError(Exception):
    """File cấu hình thiếu hoặc sai định dạng (thông báo bằng tiếng Việt)."""


def split_emails(text: str) -> list[str]:
    """Tách danh sách mail, phân cách bằng dấu ; , khoảng trắng hoặc xuống dòng."""
    return [item for item in re.split(r"[;,\s]+", text or "") if item]


def is_valid_email(address: str) -> bool:
    return bool(_EMAIL_RE.match(address))


@dataclass
class Settings:
    sender: str
    display_name: str
    app_password: str
    attach_dir: str
    cc: list[str] = field(default_factory=list)
    logo_path: str = ""

    def problems(self) -> list[str]:
        """Các lỗi cấu hình Gmail khiến không thể gửi mail."""
        issues = []
        if not is_valid_email(self.sender):
            issues.append(f"Sheet '{SHEET_GMAIL}': chưa điền hoặc điền sai '{LBL_SENDER}'.")
        if not self.app_password:
            issues.append(f"Sheet '{SHEET_GMAIL}': chưa điền '{LBL_PASSWORD}'.")
        elif not is_valid_app_password(self.app_password):
            issues.append(
                f"Sheet '{SHEET_GMAIL}': '{LBL_PASSWORD}' phải gồm đúng 16 ký tự chữ/số "
                "của Google (không dùng mật khẩu đăng nhập Gmail thường)."
            )
        issues += [
            f"Sheet '{SHEET_GMAIL}': CC không hợp lệ: {cc}"
            for cc in self.cc
            if not is_valid_email(cc)
        ]
        return issues


@dataclass
class Supplier:
    name: str
    recipients: list[str]
    enabled: bool = True


@dataclass
class Templates:
    subject: str
    body: str
    excel_name: str
    pdf_name: str


@dataclass
class Config:
    settings: Settings
    suppliers: list[Supplier]
    templates: Templates


# --------------------------------------------------------------------------- đọc


def _cell_text(value: Any) -> str:
    return "" if value is None else str(value).replace("\r\n", "\n").strip()


def _read_labeled_values(ws: Any) -> dict[str, str]:
    """Đọc các cặp (nhãn ở cột A, giá trị ở cột B) của một sheet."""
    pairs: dict[str, str] = {}
    for label, value in ws.iter_rows(min_col=1, max_col=2, values_only=True):
        if _cell_text(label):
            pairs[_cell_text(label)] = _cell_text(value)
    return pairs


def _get_sheet(wb: Any, name: str) -> Any:
    if name not in wb.sheetnames:
        raise ConfigError(
            f"File cấu hình thiếu sheet '{name}'. "
            f"Hãy xóa file {CONFIG_PATH.name} để app tạo lại file mẫu."
        )
    return wb[name]


def _require(values: dict[str, str], label: str, sheet: str) -> str:
    if label not in values:
        raise ConfigError(
            f"Sheet '{sheet}' thiếu dòng '{label}'. Đừng sửa hoặc xóa tên ở cột A."
        )
    return values[label]


def _read_suppliers(ws: Any) -> list[Supplier]:
    suppliers: list[Supplier] = []
    for enabled, name, recipients in ws.iter_rows(
        min_row=SUPPLIER_HEADER_ROW + 1, max_col=3, values_only=True
    ):
        clean_name = _cell_text(name)
        if clean_name:
            suppliers.append(
                Supplier(
                    name=clean_name,
                    recipients=split_emails(_cell_text(recipients)),
                    enabled=_cell_text(enabled).lower() not in _OFF_VALUES,
                )
            )
    return suppliers


def _mask_password_in_excel(path: Path) -> None:
    """Thay mật khẩu thô trong file Excel bằng chuỗi đánh dấu đã lưu an toàn."""
    wb = None
    try:
        wb = load_workbook(path)
        if SHEET_GMAIL in wb.sheetnames:
            ws = wb[SHEET_GMAIL]
            for row in range(1, ws.max_row + 1):
                if _cell_text(ws.cell(row=row, column=1).value) == LBL_PASSWORD:
                    ws.cell(row=row, column=2, value=SAVED_PLACEHOLDER)
                    wb.save(path)
                    break
    except Exception:
        # Nếu file đang mở trong Excel khiến không lưu đè được ngay thì bỏ qua an toàn
        pass
    finally:
        if wb is not None:
            wb.close()


def load_config(
    path: Path = CONFIG_PATH,
    vault_path: Optional[Path] = None,
    mask_excel: bool = True,
) -> Config:
    wb = None
    try:
        try:
            wb = load_workbook(path, data_only=True)
        except PermissionError as exc:
            raise ConfigError(
                "Không đọc được file cấu hình. Hãy lưu (Ctrl+S) và đóng Excel rồi thử lại."
            ) from exc
        except FileNotFoundError as exc:
            raise ConfigError(f"Không tìm thấy file cấu hình {path.name}.") from exc
        except (zipfile.BadZipFile, InvalidFileException, KeyError, ValueError, OSError) as exc:
            raise ConfigError(
                f"File cấu hình '{path.name}' bị hỏng hoặc không đúng định dạng Excel (.xlsx)."
            ) from exc

        gmail = _read_labeled_values(_get_sheet(wb, SHEET_GMAIL))
        content = _read_labeled_values(_get_sheet(wb, SHEET_CONTENT))
        suppliers = _read_suppliers(_get_sheet(wb, SHEET_SUPPLIERS))
    finally:
        if wb is not None:
            wb.close()

    sender = _require(gmail, LBL_SENDER, SHEET_GMAIL)
    raw_password = _require(gmail, LBL_PASSWORD, SHEET_GMAIL)

    active_vault = vault_path if vault_path is not None else (path.parent / ".credentials.dat")
    use_keyring = vault_path is None and path.resolve() == CONFIG_PATH.resolve()

    if raw_password and raw_password.strip() != SAVED_PLACEHOLDER:
        app_password = normalize_app_password(raw_password)
        if sender and is_valid_app_password(app_password):
            if save_password(
                sender, app_password, vault_path=active_vault, use_os_keyring=use_keyring
            ) and mask_excel:
                _mask_password_in_excel(path)
    else:
        app_password = load_password(
            sender, vault_path=active_vault, use_os_keyring=use_keyring
        )

    return Config(
        settings=Settings(
            sender=sender,
            display_name=gmail.get(LBL_NAME, ""),
            app_password=app_password,
            attach_dir=_require(gmail, LBL_ATTACH_DIR, SHEET_GMAIL),
            cc=split_emails(gmail.get(LBL_CC, "")),
            logo_path=gmail.get(LBL_LOGO, ""),
        ),
        suppliers=suppliers,
        templates=Templates(
            subject=_require(content, LBL_SUBJECT, SHEET_CONTENT),
            body=_require(content, LBL_BODY, SHEET_CONTENT),
            excel_name=_require(content, LBL_EXCEL, SHEET_CONTENT),
            pdf_name=_require(content, LBL_PDF, SHEET_CONTENT),
        ),
    )


# ----------------------------------------------------------------- tạo file mẫu

_INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")
_HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
_THIN = Side(style="thin", color="BFBFBF")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_WRAP_TOP = Alignment(wrap_text=True, vertical="top")

DEFAULT_SUBJECT = (
    "Bảng phí kiểm tra, phân loại hàng hóa tháng {thang} năm {nam} - {nha_cung_cap} - {loai}"
)
DEFAULT_BODY = """Kính gửi quý đối tác,
Công ty TNHH Haesung Vina gửi Bảng phí kiểm tra, phân loại hàng hóa tháng {thang} năm {nam}.
Vui lòng kiểm tra file đính kèm.
Trân trọng cảm ơn.
Best regards,
-------------------
Ms. Ngoc Ha
HR Staff
Haesung Vina Co., Ltd
Lot CN7, Khai Quang IZ, Vinh Yen city, Vinh Phuc province.
Mobile: 0378 092 637"""
DEFAULT_SUPPLIERS = ["ACE", "AHC", "T&T", "DiaMond", "Hitech", "HR Partner", "Mansa"]

_GMAIL_DEFAULT_ROWS: list[tuple[str, str, str, Optional[int]]] = [
    (LBL_SENDER, "", "Địa chỉ Gmail của bạn, ví dụ: ten.ban@gmail.com", None),
    (
        LBL_NAME,
        "Ms. Ngoc Ha - Haesung Vina",
        "Tên người nhận mail sẽ nhìn thấy cạnh địa chỉ Gmail.",
        None,
    ),
    (
        LBL_PASSWORD,
        "",
        "KHÔNG phải mật khẩu đăng nhập Gmail. Xem cách tạo ở sheet 'Hướng dẫn' (Bước 1). "
        "Sau khi lưu, app sẽ tự động mã hóa và ẩn mật khẩu để bảo mật.",
        45,
    ),
    (
        LBL_ATTACH_DIR,
        "Dinh_kem\\{nam}-{thang}",
        "Thư mục chứa file Excel/PDF cần đính kèm. Dùng {nam} và {thang} để mỗi tháng một thư mục, "
        "ví dụ Dinh_kem\\2026-09. Có thể điền đường dẫn đầy đủ như D:\\BaoCao\\{nam}-{thang}.",
        60,
    ),
    (
        LBL_CC,
        "",
        "Không bắt buộc. Mail nhận bản sao (CC) của TẤT CẢ các mail gửi đi, "
        "ví dụ mail của bạn hoặc sếp. Nhiều mail cách nhau bằng dấu ;",
        45,
    ),
    (
        LBL_LOGO,
        "",
        "Không bắt buộc. Đường dẫn file ảnh logo công ty (.png/.jpg) để nhúng vào chữ ký HTML, "
        "ví dụ: logo.png (đặt cạnh file exe).",
        45,
    ),
]

_CONTENT_DEFAULT_ROWS: list[tuple[str, str, str, Optional[int]]] = [
    (LBL_SUBJECT, DEFAULT_SUBJECT, "Tiêu đề của mail.", 45),
    (LBL_BODY, DEFAULT_BODY, "Nội dung mail. Nhấn Alt+Enter để xuống dòng.", 230),
    (
        LBL_EXCEL,
        "Bảng phí kiểm tra, phân loại hàng hóa {thang}.{nam} {nha_cung_cap}.xlsx",
        "Tên file Excel (gồm cả đuôi .xlsx). Có trong cả bản Tạm tính và bản Chốt.",
        45,
    ),
    (
        LBL_PDF,
        "PO {nha_cung_cap} {thang}.{nam}.pdf",
        "Tên file PDF (gồm cả đuôi .pdf). Chỉ đính kèm ở bản Chốt.",
        45,
    ),
]

_GUIDE_LINES = [
    ("HƯỚNG DẪN SỬ DỤNG", "title"),
    (
        "File này là nơi duy nhất để cài đặt. Ô MÀU VÀNG là ô bạn được điền/sửa. "
        "Sửa xong nhấn Ctrl+S để lưu.",
        "note",
    ),
    ("", None),
    ("BƯỚC 1 - Sheet 'Gmail': điền Gmail dùng để gửi và Mật khẩu ứng dụng", "head"),
    (
        "   Gmail KHÔNG cho dùng mật khẩu đăng nhập thường. Bạn cần tạo 'Mật khẩu ứng dụng' (chỉ làm 1 lần):",
        None,
    ),
    ("   a) Vào https://myaccount.google.com/security rồi bật 'Xác minh 2 bước'.", None),
    (
        "   b) Vào https://myaccount.google.com/apppasswords, đặt tên bất kỳ (ví dụ 'Gui mail') rồi bấm Tạo.",
        None,
    ),
    (
        "   c) Google hiện 16 ký tự. Sao chép và dán vào ô 'Mật khẩu ứng dụng Gmail' (có dấu cách cũng được).",
        None,
    ),
    ("", None),
    ("BƯỚC 2 - Sheet 'Nhà cung cấp': mỗi dòng là 1 nhà cung cấp", "head"),
    (
        "   - Cột 'Gửi?': chọn Có hoặc Không. Chọn Không thì tháng này bỏ qua nhà cung cấp đó.",
        None,
    ),
    (
        "   - Cột 'Mail người nhận': điền nhiều mail, cách nhau bằng dấu chấm phẩy (;) hoặc xuống dòng (Alt+Enter).",
        None,
    ),
    (
        "   - Muốn thêm nhà cung cấp: điền vào dòng trống tiếp theo. Muốn xóa: xóa chữ ở cột tên.",
        None,
    ),
    ("", None),
    ("BƯỚC 3 - Sheet 'Nội dung mail': sửa tiêu đề, nội dung, tên file đính kèm", "head"),
    (
        "   Dùng các biến trong dấu { } để app tự thay theo từng nhà cung cấp, tháng, năm:",
        None,
    ),
    *[(f"   {{{k}}}  →  {v}", None) for k, v in VARIABLES.items()],
    ("   Muốn xuống dòng trong ô nội dung: nhấn Alt+Enter.", None),
    ("", None),
    ("BƯỚC 4 - Chuẩn bị file đính kèm", "head"),
    (
        "   Bỏ file Excel và PDF của tháng vào thư mục đã ghi ở sheet 'Gmail' "
        "(mặc định: Dinh_kem\\năm-tháng, ví dụ Dinh_kem\\2026-09).",
        None,
    ),
    (
        "   Tên file phải đúng theo mẫu ở sheet 'Nội dung mail'. "
        "Nếu thiếu file, app sẽ báo đỏ ở màn hình xem trước.",
        None,
    ),
    ("   - Bản Tạm tính: chỉ đính kèm file Excel.", None),
    ("   - Bản Chốt: đính kèm cả file Excel và file PDF.", None),
    ("", None),
    (
        "BƯỚC 5 - Mở app (Chay_ung_dung.bat), chọn tháng, năm, loại gửi rồi bấm 'Xem trước & Gửi'",
        "head",
    ),
    (
        "   Kiểm tra bản xem trước, đúng thì bấm 'Xác nhận & Gửi'. "
        "Mỗi lần gửi đều được ghi vào cơ sở dữ liệu lịch sử và file Lich_su_gui.csv.",
        None,
    ),
]


def _style_header(ws: Any, row: int, headers: list[str]) -> None:
    for col, text in enumerate(headers, 1):
        cell = ws.cell(row=row, column=col, value=text)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = _HEADER_FILL
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        cell.border = _BORDER


def _write_title(ws: Any, title: str, note: str, last_col: str) -> None:
    ws["A1"] = title
    ws["A1"].font = Font(bold=True, size=14, color="1F4E78")
    ws["A2"] = note
    ws["A2"].font = Font(italic=True, color="7F7F7F")
    ws.merge_cells(f"A2:{last_col}2")
    ws["A2"].alignment = _WRAP_TOP
    ws.row_dimensions[2].height = 32


def _write_labeled_sheet(
    ws: Any,
    title: str,
    note: str,
    rows: list[tuple[str, str, str, Optional[int]]],
) -> None:
    """Sheet dạng 3 cột: Mục | Điền vào đây | Giải thích."""
    _write_title(ws, title, note, "C")
    _style_header(ws, 3, ["Mục", "Điền vào đây (ô màu vàng)", "Giải thích"])
    for offset, (label, value, hint, height) in enumerate(rows):
        row = 4 + offset
        for col, text in enumerate((label, value, hint), 1):
            cell = ws.cell(row=row, column=col, value=text)
            cell.alignment = _WRAP_TOP
            cell.border = _BORDER
        ws.cell(row=row, column=1).font = Font(bold=True)
        ws.cell(row=row, column=2).fill = _INPUT_FILL
        ws.cell(row=row, column=3).font = Font(italic=True, color="595959")
        if height:
            ws.row_dimensions[row].height = height
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 70
    ws.column_dimensions["C"].width = 60


def _build_guide(ws: Any) -> None:
    ws.column_dimensions["A"].width = 130
    for row, (text, style) in enumerate(_GUIDE_LINES, 1):
        cell = ws.cell(row=row, column=1, value=text)
        if style == "title":
            cell.font = Font(bold=True, size=16, color="1F4E78")
        elif style == "head":
            cell.font = Font(bold=True, size=12, color="FFFFFF")
            cell.fill = _HEADER_FILL
        elif style == "note":
            cell.font = Font(bold=True, color="C00000")


def _build_gmail(ws: Any) -> None:
    _write_labeled_sheet(
        ws, "Cài đặt Gmail gửi mail", "Điền vào các ô màu vàng.", _GMAIL_DEFAULT_ROWS
    )


def _build_suppliers(ws: Any) -> None:
    _write_title(
        ws,
        "Danh sách nhà cung cấp",
        "Mỗi dòng là 1 nhà cung cấp. Nhiều mail người nhận cách nhau bằng dấu ; hoặc xuống dòng (Alt+Enter). "
        "Muốn thêm nhà cung cấp mới, điền vào dòng trống tiếp theo.",
        "D",
    )
    _style_header(
        ws,
        SUPPLIER_HEADER_ROW,
        ["Gửi?", "Tên nhà cung cấp", "Mail người nhận", "Ghi chú (tùy ý, app không đọc)"],
    )
    validation = DataValidation(type="list", formula1='"Có,Không"', allow_blank=True)
    ws.add_data_validation(validation)
    last_row = SUPPLIER_HEADER_ROW + 100
    for row in range(SUPPLIER_HEADER_ROW + 1, last_row + 1):
        index = row - SUPPLIER_HEADER_ROW - 1
        ws.cell(
            row=row,
            column=1,
            value="Có" if index < len(DEFAULT_SUPPLIERS) else None,
        )
        ws.cell(
            row=row,
            column=2,
            value=DEFAULT_SUPPLIERS[index] if index < len(DEFAULT_SUPPLIERS) else None,
        )
        validation.add(ws.cell(row=row, column=1))
        for col in range(1, 5):
            cell = ws.cell(row=row, column=col)
            cell.border = _BORDER
            cell.alignment = _WRAP_TOP
            if col <= 3:
                cell.fill = _INPUT_FILL
    ws.column_dimensions["A"].width = 10
    ws.column_dimensions["B"].width = 28
    ws.column_dimensions["C"].width = 70
    ws.column_dimensions["D"].width = 35
    ws.freeze_panes = ws.cell(row=SUPPLIER_HEADER_ROW + 1, column=1)


def _build_content(ws: Any) -> None:
    _write_labeled_sheet(
        ws,
        "Nội dung mail và tên file đính kèm",
        "Dùng các biến trong { } ở bảng bên dưới, app sẽ tự thay cho từng nhà cung cấp.",
        _CONTENT_DEFAULT_ROWS,
    )
    start = 4 + len(_CONTENT_DEFAULT_ROWS) + 1
    ws.cell(row=start, column=1, value="Biến có thể dùng").font = Font(bold=True)
    for offset, (name, description) in enumerate(VARIABLES.items(), 1):
        ws.cell(row=start + offset, column=1, value=f"{{{name}}}")
        ws.cell(row=start + offset, column=2, value=description)


def create_default_config(path: Path = CONFIG_PATH) -> None:
    """Tạo file cấu hình mẫu có sẵn hướng dẫn, danh sách 7 nhà cung cấp và mẫu mail."""
    wb = Workbook()
    try:
        guide = wb.active
        guide.title = SHEET_GUIDE
        _build_guide(guide)
        _build_gmail(wb.create_sheet(SHEET_GMAIL))
        _build_suppliers(wb.create_sheet(SHEET_SUPPLIERS))
        _build_content(wb.create_sheet(SHEET_CONTENT))
        wb.save(path)
    finally:
        wb.close()


def migrate_config_if_needed(path: Path = CONFIG_PATH) -> bool:
    """Tự động bổ sung các dòng cấu hình còn thiếu khi nâng cấp phiên bản mà không mất dữ liệu cũ."""
    if not path.is_file():
        return False
    wb = None
    changed = False
    try:
        wb = load_workbook(path)
        for sheet_name, default_rows in (
            (SHEET_GMAIL, _GMAIL_DEFAULT_ROWS),
            (SHEET_CONTENT, _CONTENT_DEFAULT_ROWS),
        ):
            if sheet_name not in wb.sheetnames:
                continue
            ws = wb[sheet_name]
            existing = _read_labeled_values(ws)
            for label, default_val, hint, height in default_rows:
                if label not in existing:
                    next_row = ws.max_row + 1
                    for col, text in enumerate((label, default_val, hint), 1):
                        cell = ws.cell(row=next_row, column=col, value=text)
                        cell.alignment = _WRAP_TOP
                        cell.border = _BORDER
                    ws.cell(row=next_row, column=1).font = Font(bold=True)
                    ws.cell(row=next_row, column=2).fill = _INPUT_FILL
                    ws.cell(row=next_row, column=3).font = Font(italic=True, color="595959")
                    if height:
                        ws.row_dimensions[next_row].height = height
                    changed = True
        if changed:
            wb.save(path)
    except Exception:
        return False
    finally:
        if wb is not None:
            wb.close()
    return changed


def ensure_config_file(path: Path = CONFIG_PATH) -> bool:
    """Tạo file mẫu nếu chưa có, hoặc tự nâng cấp cấu trúc nếu đã tồn tại."""
    if path.exists():
        migrate_config_if_needed(path)
        return False
    create_default_config(path)
    return True
