# Changelog

Mọi thay đổi đáng chú ý của dự án **Ứng dụng Gửi Email Hàng Loạt Cho Nhà Cung Cấp (Gmail Auto Mailer)** đều được ghi nhận tại tài liệu này theo chuẩn [Keep a Changelog](https://keepachangelog.com/vi/1.0.0/) và [Semantic Versioning](https://semver.org/).

---

## [2.0.0] - 2026-11-21

### ✨ Mẫu Email HTML Doanh Nghiệp, Nhúng Logo Inline CID & Báo Cáo Excel (`.xlsx`)
- **Định dạng Email HTML Doanh nghiệp tự động (`app/mailer.py`)**:
  - Mọi email gửi đi đều hỗ trợ song song `Multipart Alternative (text/plain + text/html)` tương thích 100% với mọi trình đọc thư.
  - Tự động định dạng nội dung văn bản sang phông chữ `Segoe UI` chuyên nghiệp và làm nổi bật khối chữ ký doanh nghiệp bên dưới dòng phân cách `---` với màu thương hiệu Haesung Vina (`#1F4E78`).
  - Hỗ trợ người dùng viết trực tiếp mã HTML tùy chỉnh trong ô `Nội dung mail` nếu muốn.
- **Nhúng Logo Công ty vào Chữ ký qua Inline CID (`app/mailer.py`, `app/config.py`)**:
  - Bổ sung dòng cấu hình tùy chọn `Logo chữ ký (không bắt buộc)` trong sheet `Gmail` (hoặc tự nhận diện file `logo.png` đặt cạnh ứng dụng).
  - Nhúng ảnh logo trực tiếp vào phần chữ ký HTML qua `Content-ID` (`cid:company_logo_haesung`) mà không làm lẫn với danh sách file Excel/PDF đính kèm.
- **Xuất Báo cáo Lịch sử Gửi Mail ra File Excel Định dạng Đẹp (`Lich_su_gui.xlsx` — `app/history.py`)**:
  - Tự động kết xuất lịch sử từ SQLite `history.db` ra file `Lich_su_gui.xlsx` có tiêu đề nền xanh đậm `#1F4E78`, cố định dòng tiêu đề (`freeze_panes`), tô màu nền xanh lá (`#E2EFDA`) cho dòng `"Thành công"` và cam nhạt (`#FCE4D6`) cho dòng `"Lỗi"`.
  - Giữ định dạng chuỗi `@` cho cột `Tháng` (`"09"`), khắc phục vĩnh viễn việc Microsoft Excel tự cắt số `0` ở đầu hoặc lỗi font khi mở file CSV.
- **Nâng cấp Trải nghiệm Xem trước & Telemetry Tốc độ Gửi (`app/preview_dialog.py`, `app/main_window.py`)**:
  - Bổ sung thanh thống kê tổng quan theo trạng thái (`Sẵn sàng mới`, `Đã gửi trong kỳ`, `Lỗi`, `Tạm tắt`) và ô **`🔍 Lọc NCC`** tìm kiếm theo tên nhà cung cấp theo thời gian thực trên `PreviewDialog`.
  - Hiển thị tốc độ gửi thực tế (`mail/phút`) cùng phần trăm tiến độ và đồng hồ `ETA` trên cửa sổ chính.

---

## [1.2.0] - 2026-11-21

### 🚀 Tự Động Cập Nhật OTA 2 Tiến Trình Qua GitHub Releases (OTA Auto-Update)
- **Lõi Cập nhật OTA (`app/updater.py`)**:
  - Tự động kiểm tra bản phát hành mới từ GitHub Releases API (`releases/latest`) theo chuẩn Semantic Versioning.
  - Tải gói cập nhật qua kết nối bảo mật `https://` với thanh tiến độ thời gian thực (`64 KB` streaming chunks).
  - **Cổng kiểm chứng toàn vẹn `SHA-256` (`Integrity Gate`)**: Tự động hủy cập nhật và xóa tệp tạm ngay lập tức nếu mã băm SHA-256 không khớp.
  - **Chống lỗ hổng `Zip Slip` (`Path Traversal Prevention`)**: Kiểm soát chặt mọi đường dẫn giải nén trong gói `.zip`.
  - **Danh sách bất khả xâm phạm (`PROTECTED_USER_ITEMS`) & Rollback `.bak` tự động**: Bảo toàn 100% dữ liệu người dùng (`Cau_hinh.xlsx`, `history.db`, `Lich_su_gui.csv`, `.credentials.dat`, `Dinh_kem/`) và tự động khôi phục từ bản sao lưu `.bak` nếu quá trình ghi đè gặp sự cố.
- **Tiến trình Cập nhật Độc lập Thứ 2 (`updater_runner.py` / `updater.exe`)**:
  - Chờ tiến trình chính (`Gui_mail_nha_cung_cap.exe`) đóng hoàn toàn để Windows giải phóng khóa file `.exe`, sau đó giải nén ghi đè bản mới và tự động khởi chạy lại ứng dụng.
- **Giao diện Thông báo & Cập nhật OTA Trên `MainWindow` (`app/main_window.py`)**:
  - Kiểm tra bản cập nhật ngầm khi mở ứng dụng (không làm gián đoạn nếu máy đang offline), hiển thị thanh thông báo màu xanh kèm nút **"Cập nhật ngay"** và nút **"🔄 Kiểm tra cập nhật"** trên thanh tiêu đề.
- **Đóng gói 2 Tiến trình & GitHub Actions Release Pipeline (`updater.spec`, `Dong_goi_exe.bat`, `.github/workflows/release.yml`)**:
  - Tự động đóng gói song song `Gui_mail_nha_cung_cap.exe` và `updater.exe`, nén `.zip`, tính mã băm SHA-256, sinh `version.json` và phát hành lên GitHub Releases khi push git tag `v*.*.*`.
- **Mở rộng Bộ Kiểm thử Tự động (`tests/test_app.py`)**:
  - Nâng tổng số bài kiểm thử lên **27 bài test** (`pytest`), bao phủ toàn diện luồng cập nhật OTA, xác thực SHA-256, chống Zip Slip, bảo toàn dữ liệu người dùng và Rollback khi lỗi.

---

## [1.1.0] - 2026-11-21

### 🛡️ Bảo mật (Security)
- **Bảo mật Hybrid Mật khẩu ứng dụng Gmail (`app/security.py`, `app/config.py`)**: Tự động mã hóa và lưu trữ Mật khẩu ứng dụng Gmail vào kho bảo mật nội bộ (`.credentials.dat` / Windows Credential Manager `keyring`) ngay sau lần đọc đầu tiên, đồng thời thay thế mật khẩu thô trong `Cau_hinh.xlsx` bằng chuỗi đánh dấu `******** (Đã lưu an toàn trên máy)` để chống lộ lọt khi chia sẻ file Excel (`CWE-256`).
- **Kiểm tra độ dài chuẩn 16 ký tự của Gmail App Password**: Cảnh báo sớm nếu người dùng nhập nhầm mật khẩu đăng nhập Gmail thông thường.
- **Chống CSV Formula Injection (`CWE-1236`)**: Tự động làm sạch các trường dữ liệu bắt đầu bằng `=`, `+`, `-`, `@` khi xuất ra `Lich_su_gui.csv`.

### 🐛 Sửa lỗi Logic Ngầm (Bug Fixes — Forensic Audit Pass 2)
- **Chặn báo thành công giả khi một phần người nhận hoặc CC bị từ chối (`Silent Partial Delivery` — `app/mailer.py`)**: Kiểm tra từ điển địa chỉ bị từ chối trả về từ `smtplib.SMTP.send_message(msg)` và ghi nhận lỗi rõ ràng thay vì báo `"✔ Đã gửi"`.
- **Khắc phục lỗi dừng toàn bộ đợt gửi khi Reconnect thất bại (`app/mailer.py`)**: Bắt ngoại lệ `MailError` trong vòng lặp `send_plans()` để sự cố mạng ở một nhà cung cấp không làm hủy các nhà cung cấp tiếp theo.
- **Tách lỗi đọc file đính kèm khỏi lỗi mất mạng Internet (`app/mailer.py`)**: Báo đúng thông báo *"Không đọc được file đính kèm (file đã bị xóa hoặc đang bị khóa)"* thay vì báo nhầm là mất kết nối Internet.
- **Đóng Socket SSL an toàn khi đăng nhập Gmail thất bại (`app/mailer.py`)**: Giải phóng tài nguyên socket ngay trong khối `except` của `GmailSession._connect()`.
- **Sửa lỗi mất lịch sử đã gửi khi mở CSV bằng Microsoft Excel và bấm Lưu (`app/history.py`)**: Chuẩn hóa kiểu số nguyên cho cột `Tháng` (`"09"` và `"9"` đều được nhận diện chính xác).

### ✨ Tính năng Mới & Cải tiến (Added & Changed)
- **Cơ sở dữ liệu Lịch sử SQLite (`history.db` — `app/history.py`)**: Lưu trữ lịch sử gửi mail nguyên tử vào SQLite làm nguồn sự thật chính (Single Source of Truth) chống lỗi khóa file khi người dùng đang mở `Lich_su_gui.csv` trong Excel, đồng thời tự động đồng bộ/xuất ra CSV.
- **Cơ chế Smart Pacing (1.5s) & Exponential Backoff Retry (`app/mailer.py`)**: Giãn cách gửi tự động giữa các email để tuân thủ hạn mức Gmail SMTP và chống đánh dấu spam.
- **Kiểm tra an toàn File đính kèm & Tên Nhà cung cấp (`app/planner.py`)**: Phát hiện file đính kèm rỗng (`0 KB`), file vượt quá giới hạn `18 MB` (trước mã hóa Base64), tên nhà cung cấp trùng lặp hoặc chứa ký tự đường dẫn bất hợp pháp (`/ \ : * ? " < > |`).
- **Tự động nâng cấp cấu trúc Excel không mất dữ liệu (`migrate_config_if_needed` — `app/config.py`)**: Bảo toàn 100% danh sách nhà cung cấp của người dùng khi nâng cấp phiên bản.
- **Bộ điều khiển luồng gửi trực tiếp & Telemetry (`app/main_window.py`)**: Bổ sung nút **Tạm dừng (Pause) / Tiếp tục (Resume)** và **Hủy gửi (Cancel)**, thanh trạng thái hiển thị phần trăm, số lượng thành công/lỗi và thời gian hoàn thành ước tính (ETA), chuyển đổi Giao diện Sáng / Tối (Light / Dark Mode), bật High-DPI sắc nét trên Windows 10/11 và bảo vệ đóng cửa sổ (`WM_DELETE_WINDOW`) khi đang gửi.
- **Chọn/Bỏ chọn lẻ từng nhà cung cấp trên màn hình Xem trước (`app/preview_dialog.py`)**: Cho phép nhấp đúp hoặc nhấn phím Space để tick chọn (`☑`) / bỏ chọn (`☐`) gửi lẻ từng nhà cung cấp kèm hiển thị dung lượng từng file đính kèm.
- **Hạ tầng Kỹ nghệ Đa Tác Nhân & CI/CD**: Thiết lập đội ngũ 7 Sub-Agents tại `.agents/`, `pyproject.toml`, `Gui_mail_nha_cung_cap.spec`, `.github/workflows/ci.yml`, và bộ kiểm thử `pytest` 21 bài test 3 khía cạnh (Happy, Edge, Chaos) đạt chuẩn `ruff` & `mypy`.

---

## [1.0.0] - 2026-10-30

### 🎉 Phát hành phiên bản đầu tiên
- Giao diện Tkinter hỗ trợ chọn kỳ gửi (tháng, năm) và chế độ gửi (Tạm tính / Chốt).
- Cấu hình qua file Excel `Cau_hinh.xlsx` (4 sheet).
- Gửi mail qua Gmail SMTP SSL (Port 465).
- Màn hình Xem trước (`PreviewDialog`) và ghi lịch sử vào `Lich_su_gui.csv`.
