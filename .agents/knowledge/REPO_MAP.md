# Repository Map (Bản Đồ Cấu Trúc Mã Nguồn — `v2.0.0`)

| Đường dẫn tệp | Dòng code | Mục đích & Trách nhiệm chính | Thành phần / Hàm chính |
| :--- | :--- | :--- | :--- |
| `main.py` | ~38 | Điểm khởi chạy ứng dụng GUI & bật High-DPI | `_enable_high_dpi`, `main` |
| `updater_runner.py` | ~130 | Tiến trình thứ 2 độc lập (`updater.exe`) cập nhật OTA | `wait_for_process_exit`, `execute_update`, `main` |
| `app/__init__.py` | ~3 | Khai báo package & phiên bản ứng dụng | `__version__ = "2.0.0"` |
| `app/security.py` | ~155 | Bảo mật Hybrid Mật khẩu ứng dụng Gmail (Vault + Keyring) | `save_password`, `load_password`, `is_valid_app_password`, `SAVED_PLACEHOLDER` |
| `app/config.py` | ~475 | Đọc/ghi cấu hình `Cau_hinh.xlsx`, ẩn mật khẩu & Auto-Migration | `load_config`, `create_default_config`, `migrate_config_if_needed`, `Settings` |
| `app/history.py` | ~305 | Lưu trữ lịch sử gửi vào SQLite `history.db`, xuất CSV & Excel `.xlsx` | `record`, `sent_suppliers`, `export_sqlite_to_csv`, `export_sqlite_to_excel` |
| `app/mailer.py` | ~290 | Kết nối SMTP SSL, HTML + Logo Inline CID, Pacing (1.5s) & Retry | `GmailSession`, `build_html_body`, `build_message`, `send_plans` |
| `app/updater.py` | ~340 | Kiểm tra GitHub Releases, tải HTTPS, kiểm chứng SHA-256 & Rollback | `check_for_update`, `download_release_asset`, `safe_extract_zip`, `apply_staged_update` |
| `app/main_window.py` | ~630 | Cửa sổ chính Tkinter, Pause/Resume/Cancel, Telemetry & Banner OTA | `MainWindow`, `_start_ota_check`, `_on_toggle_pause`, `_on_cancel_send` |
| `app/planner.py` | ~160 | Lập kế hoạch gửi, kiểm tra file 0-byte, >18MB, trùng mã NCC | `build_plans`, `resolve_attach_dir`, `MailPlan`, `Attachment` |
| `app/preview_dialog.py` | ~315 | Cửa sổ xem trước v2.0: thống kê, lọc nhanh NCC & chọn gửi lẻ (`☑`/`☐`) | `PreviewDialog`, `_refresh_tree_checks`, `_on_double_click_row` |
| `app/templating.py` | ~25 | Xử lý nội suy biến `{thang}`, `{nam}`, `{nha_cung_cap}`, `{loai}` | `render`, `unknown_variables`, `VARIABLES` |
| `tests/test_app.py` | ~660 | Bộ kiểm thử tự động `pytest` 29 bài test (Happy, Edge, Chaos, OTA, V2) | `TemplatingTests`, `ConfigAndSecurityTests`, `PlanAndMailTests`, `HistorySQLiteAndCSVTests`, `OTAUpdaterTests`, `V2HtmlAndExcelReportTests` |
| `Gui_mail_nha_cung_cap.spec` | ~48 | Đặc tả đóng gói PyInstaller cho ứng dụng chính | Build `Ban_phat_hanh/Gui_mail_nha_cung_cap.exe` |
| `updater.spec` | ~52 | Đặc tả đóng gói PyInstaller cho tiến trình cập nhật OTA độc lập | Build `Ban_phat_hanh/updater.exe` |
| `pyproject.toml` | ~50 | Cấu hình dự án, dependencies, `pytest`, `ruff`, `mypy` | Chuẩn hóa gói phần mềm `v2.0.0` |
| `docs/ARCHITECTURE_CONTRACT.md` | ~210 | Hợp đồng kiến trúc khóa giao diện giữa các tầng (Mục 1 -> Mục 8) | Quy định API, invariants, schema SQLite & giao thức OTA |
| `CHANGELOG.md` | ~100 | Nhật ký phát hành các phiên bản `v1.0.0` -> `v1.1.0` -> `v1.2.0` -> `v2.0.0` | Keep a Changelog & Semantic Versioning |
