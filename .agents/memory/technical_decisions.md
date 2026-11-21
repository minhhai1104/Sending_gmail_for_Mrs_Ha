# Technical Decisions & Architectural Commitments

Ghi nhận các quyết định kiến trúc đã thống nhất qua quá trình Grill-Me với người dùng:

1. **ADR-001: Cấu trúc Đội ngũ 7 Sub-Agents Kế thừa Toàn diện**:
   - Thống nhất tổ chức đội ngũ 7 Sub-Agents chuyên trách: `pm-agent`, `designer-agent`, `be-agent`, `fe-agent`, `tester-agent`, `qa-agent`, `devops-agent`.
   - Cấu trúc thư mục `.agents/` là nguồn sự thật duy nhất (Single Source of Truth), kế thừa trọn vẹn 50+ kỹ năng từ `Backup-data-to-NAS` và `Nguyen-Ba-Toc`, kết hợp bản đồ tri thức `.agents/knowledge/` và bộ nhớ vĩnh cửu `.agents/memory/`.

2. **ADR-002: Cơ chế Bảo mật Thông tin Đăng nhập Hybrid**:
   - Thay vì lưu plaintext mật khẩu ứng dụng Gmail (16 ký tự) vĩnh viễn trong file `Cau_hinh.xlsx` (tiềm ẩn nguy cơ lộ lọt khi chia sẻ file), hệ thống áp dụng cơ chế Hybrid:
     - Cho phép nhập mật khẩu lần đầu từ GUI hoặc Excel.
     - Tự động lưu mật khẩu an toàn vào **Windows Credential Manager (`keyring`)** hoặc mã hóa AES-256 nội bộ.
     - Hỗ trợ làm sạch, xóa plaintext mật khẩu khỏi file Excel sau khi đã nạp an toàn vào hệ thống.

3. **ADR-003: Chuyển đổi Lưu trữ Lịch sử sang SQLite nội bộ (`history.db`) & Pacing Chống Spam**:
   - Lịch sử gửi mail được lưu trữ chính thức vào SQLite (`history.db`) để triệt tiêu lỗi xung đột khóa file (`PermissionError: [Errno 13] Permission denied`) khi người dùng đang mở xem file trong Microsoft Excel trên Windows.
   - Hỗ trợ hàm tự động xuất/đồng bộ sang `Lich_su_gui.csv` và Excel xem ngay.
   - Bắt buộc áp dụng cơ chế **Pacing thông minh** (giãn cách gửi 1.5s - 3.0s giữa các mail) và Exponential Backoff Retry để tuân thủ Gmail SMTP sending quota và chống kích hoạt bộ lọc chống spam của Google.

4. **ADR-004: Giao diện Tkinter Modern Enterprise thuần (Lightweight & Zero-Bloat)**:
   - Giữ vững công nghệ Tkinter thuần để đảm bảo thời gian khởi động tức thì, tiêu thụ RAM cực thấp (<50MB) và file `.exe` đóng gói nhỏ gọn (<15MB).
   - Tái thiết kế toàn diện theo hệ thống thiết kế `DESIGN.md` (Modern Enterprise Precision, bảng màu WCAG 2.1 AA, Dark/Light mode qua `ttk.Style`, telemetry thời gian thực, nút Tạm dừng/Hủy gửi trực tiếp).

5. **ADR-005: Tiêu chuẩn Kiểm thử 3 Khía Cạnh, Kiểm toán QA & Đóng gói Tự động**:
   - Áp dụng `pytest` kiểm thử tự động 3 khía cạnh: Happy Path, Edge Cases (Unicode, file rỗng/lớn, đường dẫn dài), Chaos Cases (rớt mạng, sai pass, khóa file, cancel giữa chừng).
   - Kiểm toán tĩnh bằng `ruff` và `mypy`.
   - Đóng gói bằng PyInstaller `.spec` file chuẩn hóa và thiết lập GitHub Actions CI tự động hóa.


6. **ADR-006: Kiến Trúc Tự Động Cập Nhật OTA Qua Mô Hình 2 Tiến Trình (Launcher/Updater + App Chính) & GitHub Releases**:
   - Triệt tiêu hoàn toàn rào cản Windows File Locking (`ERROR_ACCESS_DENIED` khi ghi đè tệp `.exe` đang chạy) bằng cách phân tách 2 tiến trình:
     - Ứng dụng chính (`Gui_mail_nha_cung_cap.exe`) kiểm tra bản cập nhật ngầm qua GitHub Releases API (`releases/latest`) và tải bản mới về thư mục tạm.
     - Tiến trình con độc lập (`updater.exe`) được kích hoạt khi người dùng xác nhận nâng cấp; Main App thoát hoàn toàn để mở khóa file binary; `updater.exe` thực hiện sao lưu `.bak`, giải nén ghi đè, xác thực SHA-256 và khởi động lại Main App mới.
   - Cơ chế Rollback tự động khôi phục bản cũ nếu phiên bản mới bị lỗi hoặc lệch mã băm SHA-256.
