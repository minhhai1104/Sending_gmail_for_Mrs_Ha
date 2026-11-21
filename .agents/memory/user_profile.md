# User Profile & Operating Context

- **Người dùng**: Minh Hải (minhhai1104).
- **Hệ điều hành**: Windows 11 (64-bit).
- **Môi trường Python**: Python 3.13.3 (tại `C:\Users\minhh\AppData\Local\Programs\Python\Python313\python.exe`).
- **Mục đích dự án**: Ứng dụng Desktop tự động hóa gửi email hàng loạt hàng tháng cho các nhà cung cấp / đối tác (áp dụng cho báo cáo Bảng phí kiểm tra, phân loại hàng hóa của **Haesung Vina**).
- **Đối tượng sử dụng cuối**: Nhân viên văn phòng, kế toán / nhân sự non-tech.
- **Yêu cầu cốt lõi (Cập nhật v3.0 — 21/11/2026)**:
  1. **Cài đặt 1-Click chuyên nghiệp**: Có bộ cài `Setup.exe` 1-click (Per-User, không cần quyền Admin), tự tạo shortcut icon thương hiệu Haesung Vina ngoài Desktop, chạy không cần cài Python, kèm tự động cập nhật OTA.
  2. **Giao diện thương mại hiện đại & Cấu hình 100% trong App**: Không dùng file Excel `Cau_hinh.xlsx` để cấu hình nữa (bỏ hẳn nhập/xuất cấu hình Excel cũ); toàn bộ tài khoản Gmail, NCC, mẫu email HTML + logo, lịch sử đều cấu hình trực tiếp trong App qua giao diện hiện đại (PyWebView + Edge WebView2), không bắt đọc hướng dẫn dài.
  3. **Tuyệt đối không gửi nhầm, không gửi thiếu file**: Kéo-thả hoặc chọn thư mục tự động khớp file an toàn 3 tầng, xem trước Email HTML + Logo thật 1:1, cảnh báo đỏ nếu thiếu file/thiếu mail/trùng file, hỗ trợ gửi thử về chính mình.
  4. **Không gửi trùng lặp**: Tự động ghi nhớ các nhà đã gửi thành công trong kỳ (SQLite WAL) và hỗ trợ 1-click gửi lại các nhà bị lỗi.
  5. **An toàn thông tin tuyệt đối**: Không lộ mật khẩu Gmail (Windows DPAPI tại `%LOCALAPPDATA%`, giao diện Write-Only), không đơ lag UI.

- **Quy tắc Phát hành & Cập nhật OTA theo yêu cầu (Standing Release SOP)**:
  - Khi người dùng yêu cầu cập nhật hoặc phát hành phiên bản mới: Đội ngũ tự động tăng version (`app/__init__.py`, `pyproject.toml`, `README.md`, `CHANGELOG.md`), chạy cổng kiểm định (`ruff`, `mypy`, `pytest`), đóng gói 2 tiến trình (`Gui_mail_nha_cung_cap.exe` + `updater.exe`), tạo gói `.zip` + `version.json` kèm mã băm `SHA-256`, và tự động commit + push Git tag + tạo GitHub Release qua `python scripts/publish_release.py` (sử dụng `git` và `gh release`).
