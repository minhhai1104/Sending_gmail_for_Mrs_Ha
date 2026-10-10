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


@dataclass
class Attachment:
    path: Path
    exists: bool

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
    folder = Path(render(cfg.settings.attach_dir, {"thang": f"{month:02d}", "nam": str(year)}))
    return folder if folder.is_absolute() else APP_DIR / folder


def _template_errors(cfg: Config) -> list[str]:
    templates = cfg.templates
    texts = (templates.subject, templates.body, templates.excel_name,
             templates.pdf_name, cfg.settings.attach_dir)
    bad = sorted({name for text in texts for name in unknown_variables(text)})
    return [f"Biến không hợp lệ: {{{name}}}" for name in bad]


def _supplier_errors(supplier: Supplier) -> list[str]:
    if not supplier.recipients:
        return ["Chưa điền mail người nhận."]
    return [f"Mail người nhận sai định dạng: {mail}"
            for mail in supplier.recipients if not is_valid_email(mail)]


def build_plans(cfg: Config, month: int, year: int, kind: str) -> list[MailPlan]:
    """Tạo kế hoạch gửi cho tất cả nhà cung cấp trong danh sách."""
    attach_dir = resolve_attach_dir(cfg, month, year)
    shared_errors = _template_errors(cfg)
    plans = []
    for supplier in cfg.suppliers:
        values = {"thang": f"{month:02d}", "nam": str(year),
                  "nha_cung_cap": supplier.name, "loai": kind}
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
            errors=_supplier_errors(supplier) + shared_errors,
        )
        for template in file_names:
            path = attach_dir / render(template, values)
            plan.attachments.append(Attachment(path, path.is_file()))
            if not path.is_file():
                plan.errors.append(f"Không tìm thấy file: {path.name}")
        plans.append(plan)
    return plans
