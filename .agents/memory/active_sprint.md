# Active Sprint: Hoàn Tất Nâng Cấp v3.1.0 ("High-Density 50+ Supplier Table")

- **Sprint Goal**:
  - Kế thừa trọn vẹn bản tái thiết kế toàn diện **v3.0.0 ("Zero-Manual Enterprise")** (PyWebView + Edge WebView2, SQLite WAL SSOT, Windows DPAPI Vault, Động cơ Khớp File 3 Tầng, Bộ cài 1-Click `Setup.exe`, OTA 2 tiến trình SHA-256).
  - **Nâng cấp v3.1.0 theo phản hồi người dùng (21/11/2026)**: Tái thiết kế danh sách Nhà cung cấp trên `SendWorkspace` từ dạng thẻ dọc nhiều tầng (~120px/dòng, chỉ hiện 3–4 NCC) sang **Bảng Dữ Liệu 1 Dòng Siêu Gọn (`38px/dòng` — Phương án 1)** tối ưu cho **50+ nhà cung cấp**:
    1. Hiển thị **11–12 NCC cùng lúc**, cột thẳng hàng cố định (`[☐]` · `Nhà cung cấp ↕` · `Email` · `Excel` · `PDF` tự ẩn/hiện theo chế độ `Tạm tính`/`Chốt` · `Trạng thái ↕`) kèm tiêu đề cột cố định (`position: sticky`) và **Checkbox chọn tất cả 3 trạng thái**.
    2. Xóa bỏ hoàn toàn nhiễu nút bấm lặp lại trên dòng; thay bằng chỉ báo SVG 1 chạm đạt chuẩn WCAG 2.5.8 (`28×26px`): bấm `✕` mở sửa email / chọn file ngay, bấm `?`/`!` trỏ thẳng thẻ tệp bên khung Xem Trước (bảo toàn Zero Wrong-Vendor Delivery).
    3. Hiển thị trạng thái cụ thể theo nguyên nhân (`Thiếu Excel`, `Thiếu PDF`, `Thiếu email`, `Thiếu 2 mục`, `Cần duyệt`, `Xung đột`, `Sẵn sàng`, `Đã gửi`), sắp xếp cột tại chỗ (`Intl.Collator('vi')` & gom lỗi lên đầu), điều hướng bàn phím `↑/↓/Home/End/Space`, đồng bộ `color-scheme: light/dark` và đạt **0 findings** trên `impeccable detect` (WCAG 2.1 AA).
- **Trạng thái**: **Hoàn tất 100% (`v3.1.0` Verified, Built & Published on GitHub Releases)**.
- **Bằng chứng Kiểm chứng Thực nghiệm (`v3.1.0`)**:
  - `impeccable detect --json app/ui/web/index.html app/ui/web/styles.css app/ui/web/app.js`: **0 findings (`[]`)**; xác minh trực quan qua Microsoft Edge headless 4 kịch bản với 50 NCC (Light Tạm tính, Light Chốt sắp xếp, Dark Chốt, cửa sổ hẹp `980×650`).
  - `node --check app/ui/web/app.js`: **0 syntax errors**.
  - `ruff check app tests scripts main.py updater_runner.py` (kèm rule bảo mật `S` & `B`): **0 errors**.
  - `mypy app main.py updater_runner.py`: **0 errors** (24 source files).
  - `pytest -v --cov --cov-fail-under=85`: **74/74 Passed (100%)**, tổng branch coverage **86.12%**.
  - **Đóng gói thực tế**: `Ban_phat_hanh/Cai_dat_Gui_mail_Haesung_Vina_v3.1.0.exe` (**16.17 MB** — Inno Setup Per-User 1-Click) + `Ban_phat_hanh/App/Gui_mail_nha_cung_cap.exe` (11 PKG entries verified) + `Ban_phat_hanh/App/updater.exe` (54 PKG entries verified) + `Ban_phat_hanh/Gui_mail_nha_cung_cap_v3.1.0.zip` + `Ban_phat_hanh/version.json` (SHA-256).
