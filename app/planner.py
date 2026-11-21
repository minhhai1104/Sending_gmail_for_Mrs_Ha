"""Dựng kế hoạch gửi mail (người nhận, tiêu đề, nội dung, file đính kèm) cho từng nhà cung cấp."""
from dataclasses import dataclass, field
from pathlib import Path

from .config import APP_DIR, Config, Supplier, is_valid_email
from .templating import render, unknown_variables

KIND_DRAFT = "Tạm tính"  # chỉ đính kèm file Excel
KIND_FINAL = "Chốt"      # đính kèm cả file Excel và PDF
KINDS = (KIND_DRAFT, KIND_FINAL)

STATE_READY = "ready"
STATE_ERROR = "error"
STATE_OFF = "off"

# Giới hạn 18 MB dữ liệu gốc (~24 MB sau khi mã hóa Base64 MIME, dưới ngưỡng 25 MB của Gmail)
MAX_TOTAL_ATTACHMENT_BYTES = 18 * 1024 * 1024
_INVALID_SUPPLIER_CHARS = set('/\\:*?"<>|')


@dataclass
class Attachment:
    path: Path
    exists: bool
    size_bytes: int = 0

    @property
    def name(self) -> str:
        return self.path.name


@dataclass
class MailPlan:
    supplier: str
    enabled: bool
    recipients: list[str]
    cc: list[str]
    subject: str
    body: str
    attachments: list[Attachment] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def state(self) -> str:
        if not self.enabled:
            return STATE_OFF
        return STATE_ERROR if self.errors else STATE_READY

    @property
    def sendable(self) -> bool:
        return self.state == STATE_READY


def resolve_attach_dir(cfg: Config, month: int, year: int) -> Path:
    """Thư mục chứa file đính kèm của kỳ gửi (đường dẫn tương đối tính từ thư mục app)."""
    folder = Path(
        render(cfg.settings.attach_dir, {"thang": f"{month:02d}", "nam": str(year)})
    )
    return folder if folder.is_absolute() else APP_DIR / folder


def _template_errors(cfg: Config) -> list[str]:
    templates = cfg.templates
    texts = (
        templates.subject,
        templates.body,
        templates.excel_name,
        templates.pdf_name,
        cfg.settings.attach_dir,
    )
    bad = sorted({name for text in texts for name in unknown_variables(text)})
    return [f"Biến không hợp lệ: {{{name}}}" for name in bad]


def _supplier_errors(supplier: Supplier, seen_names: set[str]) -> list[str]:
    issues: list[str] = []
    norm_name = supplier.name.strip().lower()
    if norm_name in seen_names:
        issues.append(f"Tên nhà cung cấp bị trùng lặp trong danh sách: {supplier.name}")
    else:
        seen_names.add(norm_name)

    if any(ch in _INVALID_SUPPLIER_CHARS for ch in supplier.name):
        issues.append(
            f"Tên nhà cung cấp chứa ký tự không hợp lệ (/ \\ : * ? \" < > |): {supplier.name}"
        )

    if not supplier.recipients:
        issues.append("Chưa điền mail người nhận.")
    else:
        issues.extend(
            f"Mail người nhận sai định dạng: {mail}"
            for mail in supplier.recipients
            if not is_valid_email(mail)
        )
    return issues


def build_plans(cfg: Config, month: int, year: int, kind: str) -> list[MailPlan]:
    """Tạo kế hoạch gửi cho tất cả nhà cung cấp trong danh sách."""
    attach_dir = resolve_attach_dir(cfg, month, year)
    shared_errors = _template_errors(cfg)
    plans: list[MailPlan] = []
    seen_names: set[str] = set()

    for supplier in cfg.suppliers:
        values = {
            "thang": f"{month:02d}",
            "nam": str(year),
            "nha_cung_cap": supplier.name,
            "loai": kind,
        }
        file_names = [cfg.templates.excel_name]
        if kind == KIND_FINAL:
            file_names.append(cfg.templates.pdf_name)

        plan = MailPlan(
            supplier=supplier.name,
            enabled=supplier.enabled,
            recipients=supplier.recipients,
            cc=cfg.settings.cc,
            subject=render(cfg.templates.subject, values),
            body=render(cfg.templates.body, values),
            errors=_supplier_errors(supplier, seen_names) + shared_errors,
        )

        total_bytes = 0
        has_bad_path = any(ch in _INVALID_SUPPLIER_CHARS for ch in supplier.name)

        for template in file_names:
            rendered_name = render(template, values)
            path = attach_dir / rendered_name
            exists = False if has_bad_path else path.is_file()
            size_bytes = 0
            if exists:
                try:
                    size_bytes = path.stat().st_size
                except OSError:
                    size_bytes = 0
            plan.attachments.append(Attachment(path, exists, size_bytes))
            if not exists:
                plan.errors.append(f"Không tìm thấy file: {rendered_name}")
            elif size_bytes == 0:
                plan.errors.append(f"File đính kèm bị rỗng (0 KB): {path.name}")
            else:
                total_bytes += size_bytes

        if total_bytes > MAX_TOTAL_ATTACHMENT_BYTES:
            mb = total_bytes / (1024 * 1024)
            plan.errors.append(
                f"Tổng dung lượng file đính kèm vượt quá giới hạn 18 MB của Gmail ({mb:.1f} MB)."
            )

        plans.append(plan)
    return plans
