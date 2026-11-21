# Active Sprint: Hoàn Tất Toàn Bộ Lộ Trình v1.1.0 -> v1.2.0 -> v2.0.0

- **Sprint Goal**: Hoàn thành toàn bộ 3 giai đoạn nâng cấp trong Báo cáo Thẩm định Dự án (`v1.1.0` Bảo mật & Ổn định lõi -> `v1.2.0` Tự động cập nhật OTA 2 tiến trình qua GitHub Releases -> `v2.0.0` Mẫu Email HTML Doanh nghiệp + Nhúng Logo Inline CID + Xuất báo cáo lịch sử Excel `.xlsx` + Lọc nhanh & Telemetry `mail/phút`).
- **Trạng thái**: Hoàn tất 100% (`v2.0.0` Verified & Gatekeeper Approved).
- **Bằng chứng Kiểm chứng Thực nghiệm**:
  - `pytest tests/test_app.py -v`: **29/29 Passed (100%)**.
  - `ruff check app tests main.py updater_runner.py`: **All checks passed! (0 errors)**.
  - `mypy app main.py updater_runner.py`: **Success: no issues found in 12 source files (0 errors)**.
- **Các hạng mục đã bàn giao trong v2.0.0**:
  - [x] Khóa hợp đồng kiến trúc Mục 8 trong `docs/ARCHITECTURE_CONTRACT.md`.
  - [x] Bổ sung `build_html_body()` và nhúng ảnh logo công ty qua Inline CID (`Content-ID`) vào `app/mailer.py` & `app/config.py` (`LBL_LOGO`).
  - [x] Bổ sung `export_sqlite_to_excel()` trong `app/history.py` kết xuất báo cáo `Lich_su_gui.xlsx` định dạng màu chuyên nghiệp, giữ nguyên định dạng chuỗi `"09"` cho cột Tháng.
  - [x] Nâng cấp `app/preview_dialog.py` (thanh thống kê tổng quan các trạng thái + ô `🔍 Lọc NCC` theo thời gian thực + nhấp đúp chọn lẻ từng NCC).
  - [x] Nâng cấp `app/main_window.py` (hiển thị tốc độ gửi thực tế `mail/phút`, ETA, mở báo cáo Excel `Lich_su_gui.xlsx`).
  - [x] Đồng bộ phiên bản `v2.0.0` tại `app/__init__.py`, `pyproject.toml`, `CHANGELOG.md`.
