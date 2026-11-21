# Technical Decisions & Architectural Commitments

Ghi nhận các quyết định kiến trúc đã thống nhất qua quá trình Grill-Me với người dùng:

1. **ADR-001: Cấu trúc Đội ngũ 7 Sub-Agents Kế thừa Toàn diện**:
   - Thống nhất tổ chức đội ngũ 7 Sub-Agents chuyên trách: `pm-agent`, `designer-agent`, `be-agent`, `fe-agent`, `tester-agent`, `qa-agent`, `devops-agent`.
   - Cấu trúc thư mục `.agents/` là nguồn sự thật duy nhất (Single Source of Truth), kế thừa trọn vẹn 50+ kỹ năng từ `Backup-data-to-NAS` và `Nguyen-Ba-Toc`, kết hợp bản đồ tri thức `.agents/knowledge/` và bộ nhớ vĩnh cửu `.agents/memory/`.

2. **ADR-002 (Supersede v3.0): Bảo mật Thông tin Đăng nhập bằng Windows DPAPI + Write-Only UI**:
   - Từ v3.0 trở đi, ứng dụng **KHÔNG còn đọc/ghi mật khẩu qua `Cau_hinh.xlsx`** và **loại bỏ `_machine_secret()` / `_PORTABLE_OTA_SECRET` hardcode**.
   - Toàn bộ Mật khẩu ứng dụng Gmail (16 ký tự) và Token nhạy cảm được mã hóa bằng **Windows DPAPI thuần (`ctypes.windll.crypt32.CryptProtectData`)** lưu tại `%LOCALAPPDATA%\GmailAutoMailer\vault.dpapi` (tách biệt hoàn toàn khỏi thư mục cài app, gắn chặt tài khoản Windows cục bộ, không cần cài thư viện ngoài).
   - Giao diện Cài đặt áp dụng nguyên tắc **Write-Only**: không bao giờ nạp ngược mật khẩu thật ra ô nhập liệu, mọi log/traceback đi qua bộ lọc `redact_secrets()`.

3. **ADR-003 (Nâng cấp v3.0): SQLite WAL Single Source of Truth (`app_data.db` & `history.db`) + Pacing & SMTP 465/587**:
   - **Cấu hình 100% trong App** (theo chỉ thị chốt của Chủ dự án ngày 21/11/2026: bỏ hoàn toàn cấu hình qua Excel `Cau_hinh.xlsx`, không cần nhập/xuất cấu hình Excel cũ).
   - Lưu trữ cấu hình (Gmail settings, danh sách NCC, mẫu Email/chữ ký, tùy chọn giao diện) và lịch sử gửi vào SQLite chuẩn hóa có `PRAGMA journal_mode=WAL`, `busy_timeout`, `schema_migrations`.
   - Bắt buộc ghi lịch sử trên Worker Thread ngay sau `250 OK` (chống mất log khi đóng app), hỗ trợ xuất báo cáo lịch sử Excel `.xlsx` trên luồng nền.
   - Giữ cơ chế **Smart Pacing (1.5s–3.0s)**, **Exponential Backoff Retry** (cố định `Message-ID` tránh gửi trùng), và **tự động fallback SMTP `465 (SSL)` -> `587 (STARTTLS)`**.

4. **ADR-004 (Supersede v3.0): Giao diện Thương mại Modern Enterprise qua PyWebView + Microsoft Edge WebView2**:
   - Nâng cấp từ Tkinter thuần sang **PyWebView + Edge WebView2** (sẵn có trên Windows 10/11) với Web UI HTML/CSS/JS tĩnh nội bộ chuẩn **Modern Enterprise Precision v3.0** (Light/Dark Mode 100%, 6 màn hình In-App: Wizard 60s, Live Send Workspace, Quản lý NCC, Trình soạn Mẫu Email + Live HTML Preview thật 1:1, Lịch sử gửi In-App, Cài đặt).
   - Bắt buộc áp **6 rào chắn bảo mật QA**: `<iframe sandbox="">` cho email preview, sanitize HTML phía Python, Strict CSP, Whitelist JS-API Facade (không trả secret, không nhận đường dẫn file tự do), tắt DevTools bản release, và đặt WebView2 `storage_path` tại `%LOCALAPPDATA%\GmailAutoMailer\webview` (chống khóa DLL khi OTA).

5. **ADR-005 (Nâng cấp v3.0): Kiến trúc Headless ViewModel + Kiểm thử 3 Khía Cạnh (`>=90%` coverage)**:
   - Tách kiến trúc sạch `domain -> ports -> application (ViewModels) -> adapters -> ui` để `pytest` kiểm thử 100% logic màn hình, Retry, Pause/Resume và ma trận **Chống khớp nhầm NCC (`matching.py` 100% branch coverage)** với `FakeClock` chạy `<5s`.
   - Kiểm toán tĩnh bằng `ruff check` (kèm rule bảo mật `S` & `B`), `mypy` strict và kiểm định thực tế trên file `.exe`.

6. **ADR-006 (Nâng cấp v3.0): OTA 2 Tiến Trình & Bộ Cài 1-Click Chuẩn Thương Mại (`Setup.exe`)**:
   - Đóng gói App chính dạng `--onedir` (khởi động nhanh gấp 3 lần) kèm **Icon thương hiệu Haesung Vina `.ico`** (6 cỡ) và đầy đủ **Windows Version Info** (`Haesung Vina Co., Ltd.`), tắt `upx`.
   - Tạo **Bộ cài 1-Click Per-User (`Setup.exe` — Inno Setup)** cài vào `%LOCALAPPDATA%\Programs\HaesungVina\GmailAutoMailer`, không cần quyền Admin UAC, tự tạo Shortcut Desktop & Start Menu, tự kiểm tra Edge WebView2 Runtime.
   - Tách `updater_runner.py` thuần stdlib (giảm ~50% dung lượng `updater.exe`), bắt buộc xác thực SHA-256 (rỗng = từ chối) + domain allowlist GitHub.

7. **ADR-007: Động Cơ Khớp File Thông Minh 3 Tầng (Zero Wrong-Vendor Delivery)**:
   - Khớp file đính kèm (từ chọn thư mục hoặc kéo-thả) theo 3 tầng cứng:
     - **Xanh (`AUTO_READY`)**: Chỉ khớp 100% Word-Boundary Token tên NCC/Alias (chuẩn hóa NFC, hoa/thường, tháng `9`<->`09`, dấu phân cách) + đúng kỳ tháng/năm.
     - **Vàng (`NEEDS_REVIEW` — mặc định KHÔNG tick gửi)**: Mọi khớp gần đúng (fuzzy) bắt buộc người dùng đối chiếu và bấm duyệt từng dòng.
     - **Đỏ (`BLOCKED`)**: >=2 file cho 1 NCC, 1 file khớp >=2 NCC, chứa tên NCC khác, lệch kỳ tháng/năm, file rác `~$*`, trùng email chéo NCC.
   - Bất biến Song ánh 1–1 (path + `SHA-256`) và **TOCTOU Hash Pinning** trước khi gửi SMTP.
