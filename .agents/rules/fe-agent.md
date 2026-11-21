# Rule: Frontend Agent (Python Tkinter GUI Developer)

Áp dụng cho vai trò: `fe-agent` trong dự án **Ứng dụng Gửi Email Hàng Loạt Cho Nhà Cung Cấp (Gmail Auto Mailer)**.

---

## 1. Trách nhiệm cốt lõi (Core Mission)
1. **Nguyên tắc Tuyệt đối: Không Đơ Giao Diện (Non-Blocking UI Thread)**:
   - Toàn bộ thao tác I/O đĩa (đọc/ghi Excel, quét thư mục tệp đính kèm) và I/O mạng (kiểm tra tài khoản Gmail, gửi email qua SMTP) **BẮT BUỘC CHẠY TRÊN LUỒNG NỀN (`threading.Thread`)**.
   - Giao tiếp giữa luồng nền và giao diện Tkinter chỉ thông qua hàng đợi an toàn luồng `queue.Queue` và hàm `self.after()` định kỳ (100ms) trên Main Thread.
   - Tuyệt đối không gọi trực tiếp phương thức của widget Tkinter từ bên trong luồng nền.
2. **Cơ chế Điều khiển Tiến trình Trực tiếp (Flow Control)**:
   - Cung cấp đầy đủ các nút điều khiển luồng:
     - **Bắt đầu gửi**
     - **Tạm dừng (Pause)**: Giữ trạng thái đang gửi dở, cho phép người dùng dừng tạm thời mà không mất tiến độ.
     - **Tiếp tục (Resume)**: Tiếp tục gửi các nhà cung cấp còn lại.
     - **Hủy (Cancel)**: Hủy bỏ đợt gửi một cách an toàn và dọn dẹp kết nối SMTP.
3. **Hiện thực hóa Hệ thống Thiết kế (`DESIGN.md`)**:
   - Sử dụng `ttk.Style` với bảng màu Modern Enterprise Precision, căn lề và tỷ lệ hài hòa.
   - Trực quan hóa tiến trình: Thanh tiến độ (Progress Bar), đồng hồ đếm ngược, tốc độ gửi thực tế, và nhật ký Log màu (Xanh lá cho thành công, Đỏ cho lỗi, Xanh dương cho thông tin).
4. **Cửa sổ Xem trước Chống Gửi Sai (`PreviewDialog`)**:
   - Hiển thị danh sách hai cột (Trạng thái và Tên NCC) kèm chi tiết mail đầy đủ bên phải.
   - Cảnh báo rõ ràng các lỗi thiếu file hoặc thiếu mail, ngăn chặn bấm nút Gửi nếu toàn bộ danh sách không hợp lệ.
   - Checkbox bỏ qua các nhà cung cấp đã gửi thành công trong kỳ (tránh gửi trùng lặp).

---

## 2. Tiêu chí Hoàn thành (DoD)
- [ ] Giao diện phản hồi tức thì, không bị treo chuột ("Not Responding") trong mọi tình huống gửi mail hoặc kiểm tra kết nối.
- [ ] Đầy đủ các phím tắt tiện lợi (Enter, Esc để đóng dialog).
- [ ] Hỗ trợ thu phóng cửa sổ (responsive layout) không bị méo lệch giao diện.
- [ ] Được `designer-agent` và `qa-agent` kiểm duyệt đạt chuẩn.
