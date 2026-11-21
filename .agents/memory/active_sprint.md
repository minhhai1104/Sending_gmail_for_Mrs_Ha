# Active Sprint: Phát Hành Bản Vá v3.1.1 ("Domain Mail Attachment Compatibility")

- **Sprint Goal**:
  - Kế thừa trọn vẹn bản tái thiết kế toàn diện **v3.0.0 ("Zero-Manual Enterprise")** và **v3.1.0 ("High-Density 50+ Supplier Table")** (PyWebView + Edge WebView2, SQLite WAL SSOT, Windows DPAPI Vault, Động cơ Khớp File 3 Tầng, Bảng NCC 1 dòng 38px tối ưu 50+ đối tác, Bộ cài 1-Click `Setup.exe`, OTA 2 tiến trình SHA-256).
  - **Bản vá khẩn cấp v3.1.1 (21/11/2026)**: Khắc phục triệt để lỗi hỏng tên file đính kèm & mất đuôi `.xlsx`/`.pdf` khi gửi sang mail domain doanh nghiệp (DaouOffice `@hso.co.kr`, Hiworks, Naver Works, Outlook/Exchange cũ) tại `app/adapters/smtp_mailer.py` (chuyển từ RFC 2231 `filename*0*=` sang RFC 2047 UTF-8 Base64 trên cả `Content-Type; name=` và `Content-Disposition; filename=`, chuẩn hóa NFC, bảng MIME tường minh cho `.xlsx`/`.xls`/`.pdf`/logo, giữ nguyên tương thích 100% trên Gmail).
- **Trạng thái**: **Hoàn tất 100% (`v3.1.1` Verified, Built & Published on GitHub Releases)**.
- **Bằng chứng Kiểm chứng Thực nghiệm (`v3.1.1`)**:
  - `ruff check app tests scripts main.py updater_runner.py` (kèm rule bảo mật `S` & `B`): **0 errors**.
  - `mypy app main.py updater_runner.py`: **0 errors** (24 source files).
  - `pytest -v --cov --cov-fail-under=85`: **76/76 Passed (100%)**, tổng branch coverage **86.49%**.
  - **Đóng gói thực tế**: `Ban_phat_hanh/Cai_dat_Gui_mail_Haesung_Vina_v3.1.1.exe` (Inno Setup Per-User 1-Click) + `Ban_phat_hanh/App/Gui_mail_nha_cung_cap.exe` + `Ban_phat_hanh/App/updater.exe` + `Ban_phat_hanh/Gui_mail_nha_cung_cap_v3.1.1.zip` + `Ban_phat_hanh/version.json` (SHA-256).

