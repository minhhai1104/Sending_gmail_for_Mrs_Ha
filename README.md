# Gmail Auto Mailer v3.1 — Haesung Vina

![Version](https://img.shields.io/badge/version-v3.1.1-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-0078D4.svg)
![UI](https://img.shields.io/badge/UI-PyWebView%20%2B%20Edge%20WebView2-0F7B43.svg)

Ứng dụng Desktop tự động hóa gửi email báo cáo **Bảng phí kiểm tra, phân loại hàng hóa** hàng tháng cho các nhà cung cấp — thiết kế theo triết lý **Zero-Manual Enterprise** cho nhân viên văn phòng / HR / Kế toán: **cài đặt 1-click, cấu hình 100% trong App (không cần chỉnh Excel), bảng danh sách siêu gọn tối ưu 50+ nhà cung cấp, kéo-thả tự khớp file an toàn 3 tầng và xem trước Email HTML + Logo 1:1**.

---

## Tính Năng Nổi Bật (v3.1.1)

1. **Giao diện thương mại Modern Enterprise (PyWebView + Edge WebView2)**:
   - Bố cục 1 cửa sổ thống nhất với 6 màn hình In-App: **Trợ lý thiết lập 60s**, **Gửi Mail (Split Live Preview với Bảng NCC 1 dòng siêu gọn tối ưu 50+ đối tác, sắp xếp cột tại chỗ, chỉ báo 1 chạm & điều hướng `↑/↓`)**, **Danh bạ Nhà cung cấp**, **Mẫu Email & Chữ ký**, **Lịch sử gửi**, **Cài đặt**.
   - Hỗ trợ **Dark / Light / Theo Windows 100%** (đồng bộ cả thanh tiêu đề Win32), bộ icon SVG sắc nét, hoạt động 100% offline.
2. **Cấu hình 100% trong App (Loại bỏ hoàn toàn `Cau_hinh.xlsx`)**:
   - Dữ liệu cấu hình và lịch sử lưu tập trung trong SQLite WAL (`%LOCALAPPDATA%\GmailAutoMailer\app_data.db`), có `schema_migrations`, chống xung đột khóa file Windows tuyệt đối.
   - Trình soạn mẫu thư hỗ trợ **Chip chèn biến 1-click** (`+ Tháng`, `+ Năm`, `+ Tên NCC`, `+ Loại`), chọn Logo bằng File Picker và xem trước Email HTML thật theo thời gian thực.
3. **Động cơ Khớp File Thông Minh 3 Tầng — Cam kết Zero Wrong-Vendor Delivery**:
   - Hỗ trợ **Kéo-thả thư mục / tệp** trực tiếp từ Explorer; tự gợi ý kỳ gửi & tự nhận diện chế độ `Tạm tính` vs `Chốt`.
   - Phân tầng an toàn: **Xanh** (khớp ranh giới từ Longest-Match-First + đúng kỳ), **Vàng** (gợi ý gần đúng — mặc định không tick, bắt buộc duyệt tay), **Đỏ** (khóa cứng trùng file, xung đột NCC, lệch kỳ, file rác `~$*`, 0 KB, >18 MB).
   - Bất biến Song ánh 1–1 (Path + `SHA-256`), cảnh báo trùng email chéo NCC, **TOCTOU Hash Pinning** trước khi gửi và **Filter-Safe Selection** chống gửi nhầm dòng bị ẩn bởi bộ lọc.
   - Tự phát hiện NCC mới từ thư mục báo cáo (**Auto-Discovery**).
4. **An Toàn Tuyệt Đối & Vận Hành Bền Bỉ**:
   - **Windows DPAPI Vault thuần** (`%LOCALAPPDATA%\GmailAutoMailer\vault.dpapi`), giao diện Write-Only (không bao giờ nạp ngược mật khẩu), lọc `redact_secrets()` toàn hệ thống.
   - **Gửi thử về Gmail của tôi** (`[GỬI THỬ]`, xóa sạch CC, không ghi lịch sử), **SMTP SSL 465 → STARTTLS 587 fallback**, cố định `Message-ID`, **Smart Pacing** + **Exponential Backoff Retry**, **1-Click Gửi lại nhà bị lỗi**, và **Pause-Aware Telemetry**.
5. **Bộ Cài 1-Click Chuyên Nghiệp & Cập Nhật OTA An Toàn**:
   - Bộ cài Per-User `Cai_dat_Gui_mail_Haesung_Vina_v3.1.1.exe` (Inno Setup, không cần quyền Admin), icon thương hiệu Haesung Vina đa cỡ `.ico`, đầy đủ Windows Version Info, khởi động nhanh gấp 3 lần (`--onedir`).
   - Cập nhật OTA 2 tiến trình (`updater.exe` thuần stdlib) bắt buộc xác thực **SHA-256** và **GitHub HTTPS domain allowlist**.

---

## Cài Đặt & Phát Triển

### Dành cho Người dùng cuối
Tải và chạy file **`Cai_dat_Gui_mail_Haesung_Vina_v3.1.1.exe`** (xem thêm [HUONG_DAN.md](HUONG_DAN.md)).

### Dành cho Kỹ sư phát triển
```bash
# Cài đặt môi trường
pip install -e ".[dev]"

# Chạy ứng dụng từ mã nguồn
python main.py

# Cổng kiểm định chất lượng (Quality Gate)
python -m ruff check app tests scripts main.py updater_runner.py
python -m mypy app main.py updater_runner.py
python -m pytest -v --cov

# Đóng gói --onedir + updater.exe + Bộ cài 1-Click Setup.exe
python scripts/build_exe.py
```

---

## Kiến Trúc Hệ Thống

- `app/domain/` — Logic nghiệp vụ thuần (Models, Templating + `nh3` HTML Sanitizer, Động cơ Khớp File 3 tầng, Validation).
- `app/ports/` — Giao diện Protocol phục vụ Dependency Injection & kiểm thử Headless (`FakeClock`, `FakeMailTransport`).
- `app/adapters/` — Hạ tầng Windows DPAPI Vault, SQLite WAL SSOT, File Scanner SHA-256, SMTP 465/587, Hardened OTA Updater.
- `app/application/` — Headless Services & ViewModels (`AppService`, `DispatchService`, `BatchRunner`).
- `app/ui/` — Lớp vỏ PyWebView (`bridge.py` Whitelist Facade, `window.py` EdgeChromium + Win32 Dark Titlebar + Native Drag-Drop, `web/` HTML/CSS/JS tĩnh 100% offline).
- `installer/setup.iss` & `scripts/build_exe.py` — Đóng gói chuẩn thương mại & Bộ cài 1-Click.
