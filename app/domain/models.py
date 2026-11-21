"""Các mô hình dữ liệu và Enum chuẩn hóa cho Gmail Auto Mailer v3.0."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class SendKind(str, Enum):
    """Chế độ gửi báo cáo định kỳ."""

    DRAFT = "Tạm tính"  # Chỉ đính kèm file Excel
    FINAL = "Chốt"  # Đính kèm cả Excel và PDF


class FileType(str, Enum):
    """Loại tệp đính kèm nghiệp vụ."""

    EXCEL = "excel"
    PDF = "pdf"


class MatchStatus(str, Enum):
    """Trạng thái khớp tệp đính kèm theo mô hình an toàn 3 tầng."""

    EXACT = "exact"  # Tầng Xanh: khớp đúng 100% tên mẫu
    AUTO_MATCHED = "auto_matched"  # Tầng Xanh: khớp token duy nhất + đúng kỳ
    MANUAL_CONFIRMED = "manual_confirmed"  # Tầng Xanh: người dùng đã duyệt/chọn tay
    NEEDS_REVIEW = "needs_review"  # Tầng Vàng: gợi ý gần đúng -> MẶC ĐỊNH KHÔNG TICK
    AMBIGUOUS = "ambiguous"  # Tầng Đỏ: >=2 ứng viên cùng loại cho 1 NCC
    CONFLICT = "conflict"  # Tầng Đỏ: 1 file (path/SHA-256) khớp >=2 NCC
    WRONG_PERIOD = "wrong_period"  # Tầng Đỏ: file khớp tên NCC nhưng lệch tháng/năm
    MISSING = "missing"  # Tầng Đỏ: không tìm thấy file
    INVALID_FILE = "invalid_file"  # Tầng Đỏ: 0 byte, sai định dạng hoặc vượt 18MB


class PlanState(str, Enum):
    """Trạng thái tổng hợp của một nhà cung cấp trong đợt gửi."""

    READY = "ready"  # Đủ điều kiện gửi ngay
    REVIEW = "review"  # Có file gợi ý Tầng Vàng cần người dùng bấm duyệt tay
    ERROR = "error"  # Lỗi thiếu file/email/xung đột/quá dung lượng
    OFF = "off"  # Nhà cung cấp đang tạm tắt


class SendErrorKind(str, Enum):
    """Phân loại lỗi gửi SMTP tường minh (không dựa vào chuỗi tiếng Việt)."""

    NONE = "none"
    AUTH = "auth"
    RECIPIENT_REFUSED = "recipient_refused"
    PARTIAL_REFUSED = "partial_refused"
    ATTACHMENT_IO = "attachment_io"
    ATTACHMENT_CHANGED = "attachment_changed"
    TRANSIENT_NETWORK = "transient_network"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class BatchState(str, Enum):
    """Trạng thái máy trạng thái của trình gửi hàng loạt."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    CANCELLING = "cancelling"
    DONE = "done"
    CANCELLED = "cancelled"


MAX_TOTAL_ATTACHMENT_BYTES = 18 * 1024 * 1024  # 18 MB raw (~24 MB MIME Base64 < 25 MB Gmail)
DEFAULT_PACING_SECONDS = 1.8
DEFAULT_MAX_RETRIES = 2

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
DEFAULT_EXCEL_TEMPLATE = "Bảng phí kiểm tra, phân loại hàng hóa {thang}.{nam} {nha_cung_cap}.xlsx"
DEFAULT_PDF_TEMPLATE = "PO {nha_cung_cap} {thang}.{nam}.pdf"
DEFAULT_SUPPLIER_NAMES: tuple[str, ...] = (
    "ACE",
    "AHC",
    "T&T",
    "DiaMond",
    "Hitech",
    "HR Partner",
    "Mansa",
)


@dataclass
class GmailSettings:
    sender: str = ""
    display_name: str = "Ms. Ngoc Ha - Haesung Vina"
    attach_dir: str = ""
    cc: list[str] = field(default_factory=list)
    logo_path: str = ""
    pacing_seconds: float = DEFAULT_PACING_SECONDS
    max_retries: int = DEFAULT_MAX_RETRIES


@dataclass
class MailTemplates:
    subject: str = DEFAULT_SUBJECT
    body: str = DEFAULT_BODY
    excel_name: str = DEFAULT_EXCEL_TEMPLATE
    pdf_name: str = DEFAULT_PDF_TEMPLATE


@dataclass
class AppPrefs:
    theme: str = "system"  # "light" | "dark" | "system"
    onboarding_completed: bool = False
    last_source_dir: str = ""


@dataclass
class Supplier:
    id: Optional[int]
    name: str
    recipients: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    note: str = ""
    enabled: bool = True
    sort_order: int = 0


@dataclass
class AppConfig:
    settings: GmailSettings = field(default_factory=GmailSettings)
    templates: MailTemplates = field(default_factory=MailTemplates)
    prefs: AppPrefs = field(default_factory=AppPrefs)
    suppliers: list[Supplier] = field(default_factory=list)


@dataclass(frozen=True)
class ScannedFile:
    """Thông tin tệp tin đã quét an toàn trên đĩa (kèm mã băm SHA-256 chống TOCTOU)."""

    path: Path
    name: str
    ext: str  # ".xlsx", ".xls", ".xlsm", ".pdf"
    size_bytes: int
    sha256: str = ""
    mtime: float = 0.0

    @property
    def file_type(self) -> Optional[FileType]:
        if self.ext in {".xlsx", ".xls", ".xlsm"}:
            return FileType.EXCEL
        if self.ext == ".pdf":
            return FileType.PDF
        return None


@dataclass
class AttachmentMatch:
    """Kết quả khớp cho một vị trí tệp đính kèm (Excel hoặc PDF) của một NCC."""

    file_type: FileType
    expected_name: str
    status: MatchStatus
    file: Optional[ScannedFile] = None
    candidates: list[ScannedFile] = field(default_factory=list)
    note: str = ""
    score: float = 0.0

    @property
    def is_ready(self) -> bool:
        return self.status in {
            MatchStatus.EXACT,
            MatchStatus.AUTO_MATCHED,
            MatchStatus.MANUAL_CONFIRMED,
        }

    @property
    def needs_review(self) -> bool:
        return self.status == MatchStatus.NEEDS_REVIEW

    @property
    def is_blocked(self) -> bool:
        return self.status in {
            MatchStatus.AMBIGUOUS,
            MatchStatus.CONFLICT,
            MatchStatus.WRONG_PERIOD,
            MatchStatus.MISSING,
            MatchStatus.INVALID_FILE,
        }


@dataclass
class MailPlan:
    """Kế hoạch gửi mail hoàn chỉnh cho một nhà cung cấp."""

    supplier_id: Optional[int]
    supplier: str
    enabled: bool
    recipients: list[str]
    cc: list[str]
    subject: str
    body: str
    attachments: list[AttachmentMatch] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    already_sent: bool = False
    logo_path: Optional[Path] = None
    logo_size_bytes: int = 0

    @property
    def state(self) -> PlanState:
        if not self.enabled:
            return PlanState.OFF
        if self.errors or any(att.is_blocked for att in self.attachments):
            return PlanState.ERROR
        if any(att.needs_review for att in self.attachments):
            return PlanState.REVIEW
        return PlanState.READY

    @property
    def sendable(self) -> bool:
        return self.state == PlanState.READY

    @property
    def total_bytes(self) -> int:
        att_bytes = sum(att.file.size_bytes for att in self.attachments if att.file is not None)
        return att_bytes + self.logo_size_bytes


@dataclass(frozen=True)
class DiscoveredSupplier:
    """Nhà cung cấp tiềm năng được tự phát hiện từ thư mục file đính kèm."""

    suggested_name: str
    files: list[ScannedFile]


@dataclass(frozen=True)
class PeriodSuggestion:
    month: int
    year: int
    reason: str
    source_dir: str = ""


@dataclass(frozen=True)
class SendResult:
    supplier: str
    ok: bool
    message: str
    error_kind: SendErrorKind = SendErrorKind.NONE
    refused_recipients: tuple[str, ...] = ()
    accepted_recipients: tuple[str, ...] = ()
    message_id: str = ""


@dataclass(frozen=True)
class BatchProgress:
    state: BatchState
    total: int
    completed: int
    ok_count: int
    fail_count: int
    percent: int
    rate_per_min: float
    eta_seconds: int
    current_supplier: str = ""


@dataclass
class BatchSummary:
    batch_id: str
    state: BatchState
    total: int
    ok_count: int
    fail_count: int
    results: list[SendResult] = field(default_factory=list)
    failed_plans: list[MailPlan] = field(default_factory=list)


@dataclass(frozen=True)
class HistoryRecord:
    id: int
    batch_id: str
    sent_at: str
    month: int
    year: int
    kind: str
    supplier: str
    recipients: str
    subject: str
    attachments: str
    status: str
    detail: str


@dataclass(frozen=True)
class PeriodStats:
    total: int
    ok_count: int
    fail_count: int
    success_rate: float


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    download_url: str
    sha256: str
    release_notes: str
    asset_name: str
    published_at: str = ""
    api_asset_url: str = ""
