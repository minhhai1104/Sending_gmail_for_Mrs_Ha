# Testing Strategy (Chiến Lược Kiểm Thử Kỹ Nghệ)

Dự án áp dụng khung kiểm thử tự động hóa với **`pytest`**, bao quát 3 khía cạnh:

## 1. Khía Cạnh 1: Happy Path
- Đọc cấu hình đầy đủ từ file Excel mẫu.
- Thay thế đúng các biến nội suy `{thang}`, `{nam}`, `{nha_cung_cap}`, `{loai}`.
- Kiểm tra cơ chế đính kèm:
  - Bản Tạm tính: 1 tệp Excel duy nhất.
  - Bản Chốt: 2 tệp (1 Excel + 1 PDF).
- Gửi thành công với SMTP mock, ghi nhận lịch sử vào database và file CSV.
- Kiểm tra tính năng bỏ qua các nhà cung cấp đã gửi thành công trong cùng kỳ.

## 2. Khía Cạnh 2: Edge Cases
- Tên nhà cung cấp tiếng Việt có dấu Unicode, dấu gạch ngang, ký tự đặc biệt.
- Tệp đính kèm rỗng (0 byte) hoặc tệp kích thước lớn.
- Danh sách email người nhận phức tạp: phân cách bởi dấu chấm phẩy, dấu phẩy, khoảng trắng, xuống dòng, và các email sai định dạng cú pháp.
- Đường dẫn thư mục đính kèm trên Windows dài (>260 ký tự) hoặc chứa ký tự đặc biệt.
- Tệp cấu hình Excel bị trống dòng hoặc chèn thêm cột/dòng.

## 3. Khía Cạnh 3: Chaos & Negative Cases
- Máy tính mất mạng Internet giữa chừng trong khi đang gửi dở đợt mail (Network Disconnection / Timeout).
- Gmail từ chối xác thực tài khoản (sai Mật khẩu ứng dụng / tài khoản bị khóa 2FA).
- Tệp tin `Lich_su_gui.csv` hoặc `Cau_hinh.xlsx` đang bị người dùng mở trong Microsoft Excel trên Windows (khóa ghi độc quyền).
- Người dùng bấm nút Hủy (Cancel) hoặc Tạm dừng (Pause) khi đợt gửi đang diễn ra.
