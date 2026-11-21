---
name: python-clean-testing
description: >-
  Kỹ năng kiến trúc Python sạch (Clean Architecture), kiểm tra kiểu tĩnh (mypy/ruff) và chiến lược kiểm thử
  3 khía cạnh bằng pytest (Happy Path, Edge Cases, Chaos/Network Drop Testing) cho ứng dụng sao lưu dữ liệu.
---

# Python Clean Architecture & 3-Facet Pytest Skill

Bộ kỹ năng này quy định chuẩn mực chất lượng mã nguồn Python và chiến lược kiểm thử tự động cho dự án `Backup-data-to-NAS`.

---

## 1. Kiến Trúc Phân Tầng Sạch (Python Clean Architecture)

Tổ chức mã nguồn theo các tầng độc lập, phụ thuộc hướng vào trong:
- `src/domain/` (hoặc `core/models/`): Chứa các `dataclass` / `Pydantic` models, `Enum` trạng thái, ngoại lệ nghiệp vụ (`BackupError`, `NASConnectionError`, `ChecksumMismatchError`, `InsufficientStorageError`). Không phụ thuộc vào thư viện GUI.
- `src/adapters/` (hoặc `infrastructure/`): Chứa các bộ kết nối `LocalStorageAdapter`, `SmbStorageAdapter`, `SftpStorageAdapter`, `SqliteRepository`, `KeyringCredentialStore`, `TelegramNotifier`.
- `src/services/`: Chứa `BackupEngineService`, `RestoreService`, `SchedulerService`, `RetentionService` — nhận các Adapter qua Dependency Injection để dễ dàng kiểm thử bằng Mock/Fake.
- `src/ui/` (hoặc `gui/`): Chứa cửa sổ chính, các tab/views, custom widgets, và các Background Workers kết nối `services` với giao diện.

---

## 2. Tiêu Chuẩn Mã Nguồn & Static Analysis

1. **Type Annotations Bắt Buộc**:
   - Mọi hàm, phương thức và thuộc tính lớp phải khai báo đầy đủ Type Hints chuẩn Python 3.11+ (`list[Path]`, `dict[str, Any]`, `str | None`).
2. **Công cụ Kiểm tra Tự động**:
   - `ruff check .` và `ruff format --check .`: Không có lỗi cú pháp, import thừa hay vi phạm chuẩn PEP 8.
   - `mypy src`: Kiểm tra kiểu tĩnh nghiêm ngặt.

---

## 3. Chiến Lược Kiểm Thử 3 Khía Cạnh Với `pytest`

Mỗi tính năng trong `tests/` bắt buộc phải có các bài test tự động sử dụng fixture `tmp_path` (mô phỏng cả thư mục nguồn `source_dir` và thư mục đích `nas_dir`):
1. **Happy Path**:
   - Chạy Full Backup -> kiểm tra toàn bộ tệp đích tồn tại và trùng khớp mã băm SHA-256.
   - Sửa 1 tệp, thêm 1 tệp mới -> chạy Incremental Backup -> xác minh chỉ đúng 2 tệp đó được truyền đi.
   - Chạy Restore -> xác minh cây thư mục khôi phục giống hệt bản gốc 100%.
2. **Edge Cases**:
   - Tệp rỗng `0 bytes`, tên tệp tiếng Việt có dấu và khoảng trắng, đường dẫn lồng sâu nhiều cấp, thư mục rỗng, tệp không đổi nội dung nhưng truy cập lại.
3. **Negative & Chaos Cases**:
   - Giả lập mất kết nối mạng giữa chừng (`SimulatedNetworkDropAdapter` ném `IOError` khi đang ghi ở 50% dung lượng tệp): xác minh tệp `.part` được dọn sạch, bản sao lưu cũ không bị hỏng, và cơ chế retry/cancel hoạt động chuẩn xác.
   - Giả lập tệp trên NAS bị sửa đổi nội dung (bit-rot) -> xác minh `RestoreService` hoặc `VerifyService` phát hiện lỗi `ChecksumMismatchError`.
