"""Thay các biến dạng {ten_bien} trong tiêu đề, nội dung và tên file."""
import re

# Biến được phép dùng: tên biến -> mô tả (hiển thị trong file cấu hình)
VARIABLES = {
    "thang": "Tháng gồm 2 chữ số, ví dụ 09",
    "nam": "Năm, ví dụ 2026",
    "nha_cung_cap": "Tên nhà cung cấp, ví dụ AHC",
    "loai": "Loại gửi: Tạm tính hoặc Chốt",
}

_PATTERN = re.compile(r"\{([^{}]*)\}")


def render(template: str, values: dict[str, str]) -> str:
    """Thay biến bằng giá trị; biến không biết được giữ nguyên."""
    return _PATTERN.sub(lambda m: values.get(m.group(1).strip(), m.group(0)), template)


def unknown_variables(template: str) -> list[str]:
    """Danh sách biến viết sai/không tồn tại trong mẫu."""
    names = {name.strip() for name in _PATTERN.findall(template)}
    return sorted(names - VARIABLES.keys())
