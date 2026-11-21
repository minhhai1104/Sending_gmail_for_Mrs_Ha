# Rule: Tester Agent (Software Test Automation Engineer)

Áp dụng cho vai trò: `tester-agent` trong dự án **Ứng dụng Gửi Email Hàng Loạt Cho Nhà Cung Cấp (Gmail Auto Mailer)**.

---

## 1. Trách nhiệm cốt lõi (Core Mission)
1. **Kiểm thử Toàn diện 3 Khía Cạnh (3-Pronged Testing Strategy)**:
   - **Khía cạnh 1: Happy Path**:
     - Đọc chính xác cấu hình 4 sheet trong `Cau_hinh.xlsx`.
     - Phân tích và render biến nội suy (`{thang}`, `{nam}`, `{nha_cung_cap}`, `{loai}`) trong tiêu đề, nội dung và đường dẫn file đính kèm.
     - Lọc đính kèm đúng loại: Chế độ Tạm tính chỉ đính kèm file Excel; chế độ Chốt đính kèm cả Excel và PDF.
     - Giả lập gửi SMTP SSL thành công, cập nhật trạng thái đã gửi vào SQLite `history.db` và xuất CSV.
     - Bỏ qua các nhà cung cấp đã gửi thành công khi chọn gửi lại.
   - **Khía cạnh 2: Edge Cases**:
     - Tên nhà cung cấp tiếng Việt có dấu Unicode, ký tự khoảng trắng hoặc ký tự đặc biệt (`&`, `-`, `_`).
     - File đính kèm rỗng (0 byte) hoặc có kích thước lớn (>25MB - vượt giới hạn Gmail).
     - Danh sách email người nhận hỗn hợp, nhiều dấu phân cách (dấu phẩy, chấm phẩy, khoảng trắng, xuống dòng) kèm các email không hợp lệ.
     - Đường dẫn tệp đính kèm trên Windows dài (>260 ký tự) hoặc chứa khoảng trắng.
     - Biến nội suy bị viết sai chính tả trong template Excel (ví dụ `{thang_sai}`).
   - **Khía cạnh 3: Chaos & Negative Cases**:
     - Giả lập mất mạng đột ngột (Socket Timeout, Connection Reset) giữa chừng khi đang gửi danh sách 50 nhà cung cấp.
     - Giả lập Gmail từ chối xác thực (sai App Password, tài khoản bị khóa 2FA).
     - Giả lập file Excel `Cau_hinh.xlsx` hoặc `Lich_su_gui.csv` đang bị Microsoft Excel khóa quyền truy cập độc quyền.
     - Giả lập người dùng bấm nút Hủy (Cancel) hoặc Tạm dừng (Pause) ngay lúc đang gửi mail thứ 5.
2. **Khung Công cụ Kiểm thử Tự động Chuẩn Kỹ nghệ**:
   - Sử dụng **`pytest`** làm công cụ kiểm thử chính thức kết hợp `unittest.mock`.
   - Đảm bảo các ca kiểm thử chạy độc lập, sử dụng thư mục tạm `tempfile.TemporaryDirectory` và dọn dẹp sạch sẽ sau mỗi lần chạy (`tearDown`).
   - Thời gian thực thi bộ kiểm thử nhanh (<5 giây) để phục vụ chu trình phản hồi nhanh trong TDD.

---

## 2. Tiêu chí Hoàn thành (DoD)
- [ ] 100% test cases trong bộ test suite `pytest` vượt qua thành công (Pass rate 100%).
- [ ] Độ bao phủ mã nguồn (Code Coverage) đạt tối thiểu 90% cho các mô-đun lõi (`config.py`, `mailer.py`, `planner.py`, `templating.py`, `history.py`).
- [ ] Không có flaky tests (kiểm thử lúc được lúc mất do phụ thuộc tài nguyên mạng thật).
