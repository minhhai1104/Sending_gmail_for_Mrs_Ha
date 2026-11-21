# User Profile & Operating Context

- **Người dùng**: Minh Hải (minhhai1104).
- **Hệ điều hành**: Windows 11 (64-bit).
- **Môi trường Python**: Python 3.13.3 (tại `C:\Users\minhh\AppData\Local\Programs\Python\Python313\python.exe`).
- **Mục đích dự án**: Ứng dụng Desktop tự động hóa gửi email hàng loạt hàng tháng cho các nhà cung cấp / đối tác (áp dụng cho báo cáo Bảng phí kiểm tra, phân loại hàng hóa của **Haesung Vina**).
- **Đối tượng sử dụng cuối**: Nhân viên văn phòng, kế toán / nhân sự non-tech, quen sử dụng Microsoft Excel để nhập liệu.
- **Yêu cầu cốt lõi**:
  1. Thao tác siêu đơn giản, có thể copy chạy ngay mà không cần cài Python (file thực thi `.exe`).
  2. Tuyệt đối không gửi nhầm, không gửi thiếu file: Phải có màn hình xem trước và cảnh báo đỏ nếu thiếu file hoặc thiếu mail.
  3. Không gửi trùng lặp: Tự động ghi nhớ các nhà đã gửi thành công trong kỳ và cho phép bỏ qua.
  4. An toàn thông tin: Không để lộ mật khẩu Gmail ra bên ngoài khi chia sẻ file cấu hình.
  5. Ổn định cao: Không bị treo đơ giao diện khi gửi mail số lượng lớn, không bị lỗi khi người dùng đang mở Excel.

- **Quy tắc Phát hành & Cập nhật OTA theo yêu cầu (Standing Release SOP)**:
  - Khi người dùng yêu cầu cập nhật hoặc phát hành phiên bản mới: Đội ngũ tự động tăng version (`app/__init__.py`, `pyproject.toml`, `README.md`, `CHANGELOG.md`), chạy cổng kiểm định (`ruff`, `mypy`, `pytest`), đóng gói 2 tiến trình (`Gui_mail_nha_cung_cap.exe` + `updater.exe`), tạo gói `.zip` + `version.json` kèm mã băm `SHA-256`, và tự động commit + push Git tag + tạo GitHub Release qua `python scripts/publish_release.py` (sử dụng `git` và `gh release`).
