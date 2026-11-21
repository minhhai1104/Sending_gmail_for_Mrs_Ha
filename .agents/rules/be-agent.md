# Rule: Backend Agent (Mail Core & Storage Engine)

Áp dụng cho vai trò: `be-agent` trong dự án **Ứng dụng Gửi Email Hàng Loạt Cho Nhà Cung Cấp (Gmail Auto Mailer)**.

---

## 1. Trách nhiệm cốt lõi (Core Mission)
1. **Lõi Gửi Email SMTP Chuẩn Mực (`app/mailer.py`)**:
   - Sử dụng kết nối bảo mật SMTP qua SSL (`smtp.gmail.com:465`) hoặc STARTTLS (`587`).
   - Xây dựng thông điệp MIME Multipart chuẩn RFC: Hỗ trợ văn bản thuần (Plaintext) và HTML định dạng đẹp, nhúng chữ ký chuyên nghiệp.
   - Định tuyến chính xác tệp đính kèm theo từng chế độ gửi:
     - Chế độ **Tạm tính**: Chỉ đính kèm tệp Excel theo quy tắc đặt tên.
     - Chế độ **Chốt**: Đính kèm đồng thời cả tệp Excel và tệp PDF.
2. **Cơ chế Pacing & Rate Limiting Chống Chặn Spam**:
   - Bắt buộc giãn cách gửi tự động từ 1.5 đến 3.0 giây giữa mỗi email gửi đi để tránh bị máy chủ Google đưa vào danh sách gửi thư rác hoặc ngắt kết nối tạm thời.
   - Triển khai Exponential Backoff Retry (thử lại tối đa 3 lần với thời gian chờ tăng dần khi gặp sự cố mạng tạm thời hoặc mất kết nối socket).
3. **Cơ sở Dữ liệu Lịch sử Gửi SQLite (`history.db`)**:
   - Chuyển đổi cơ chế lưu trữ lịch sử từ CSV đơn thuần sang SQLite nội bộ có khóa nguyên tử và migration chuẩn hóa.
   - Triệt tiêu hoàn toàn lỗi xung đột khóa tệp (File Lock Exception) khi người dùng mở xem file báo cáo trong Microsoft Excel trên Windows.
   - Hỗ trợ hàm xuất tự động ra `Lich_su_gui.csv` và Excel bất cứ khi nào người dùng cần kiểm tra.
4. **Kiến trúc Tách Biệt Sạch Sẽ (Python Clean Architecture)**:
   - Tách biệt rõ ràng: Data Model (`MailPlan`, `Attachment`, `Settings`) -> Adapters (SMTP Session, SQLite Storage, Excel Reader) -> Services (Send Orchestrator, Pacer).
   - Tuyệt đối không import bất kỳ widget GUI nào (`tkinter`, `ttk`) vào tầng Backend Core.

---

## 2. Tiêu chí Hoàn thành (DoD)
- [ ] 100% logic có Type Hints đầy đủ và docstrings tiếng Việt rõ ràng.
- [ ] Có bài test giả lập SMTP (`unittest.mock` / `smtplib.SMTP_SSL`) kiểm chứng toàn bộ các trường hợp thành công và lỗi mạng.
- [ ] Không có lỗ hổng rò rỉ tài nguyên (mọi kết nối SMTP và tệp tin đều được giải phóng qua context managers `with`).
- [ ] Vượt qua kiểm tra tĩnh của `ruff` và `mypy`.
