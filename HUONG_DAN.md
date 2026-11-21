# Gửi mail hàng loạt cho nhà cung cấp (qua Gmail) — Phiên bản v2.0.0

## 1. Cài đặt & Triển khai cho người dùng

### Cách 1: Dùng bộ file EXE đóng gói sẵn (Khuyên dùng — Không cần cài Python)
1. Copy thư mục `Ban_phat_hanh` (gồm `Gui_mail_nha_cung_cap.exe` và `updater.exe`) sang máy cần dùng.
2. Bấm đúp `Gui_mail_nha_cung_cap.exe` để mở ứng dụng.
3. Ở lần chạy đầu tiên, ứng dụng tự tạo file cấu hình mẫu `Cau_hinh.xlsx` ngay cạnh file `.exe`.
4. Tiến trình `updater.exe` đi kèm giúp ứng dụng tự động cập nhật phiên bản mới (OTA) từ GitHub Releases mà không làm mất dữ liệu cấu hình hay lịch sử gửi của bạn.

> **Lưu ý**: Lần đầu mở trên máy mới, nếu Windows SmartScreen hiện cảnh báo, chọn **More info (Thêm thông tin) → Run anyway (Vẫn chạy)**.

### Cách 2: Chạy từ mã nguồn Python
1. Máy cần có **Python 3.10 trở lên** (tải tại https://www.python.org/downloads/, nhớ tick *Add python.exe to PATH*).
2. Bấm đúp `Chay_ung_dung.bat`.
3. Muốn đóng gói lại bộ file `.exe` sau khi sửa code: chạy `Dong_goi_exe.bat`.

---

## 2. Hướng dẫn sử dụng lần đầu
1. Mở file `Cau_hinh.xlsx` (bấm nút **Mở file cấu hình** trong app). Sheet **Hướng dẫn** giải thích chi tiết từng bước.
2. Điền **Gmail**, **Mật khẩu ứng dụng (16 ký tự)**, và **Mail người nhận** của từng nhà cung cấp rồi lưu file (`Ctrl+S`).
   - *Bảo mật tự động*: Sau lần đọc đầu tiên, ứng dụng tự động mã hóa lưu mật khẩu vào kho an toàn trên máy và ẩn mật khẩu trong file Excel thành `******** (Đã lưu an toàn trên máy)` để bạn yên tâm không lộ mật khẩu nếu lỡ gửi file Excel cho người khác.
   - *(Tùy chọn)* Bạn có thể đặt file ảnh `logo.png` cạnh file `.exe` (hoặc điền đường dẫn ở dòng `Logo chữ ký` trong sheet `Gmail`) để tự động nhúng logo công ty vào chữ ký email HTML.
3. Bỏ file Excel và PDF của tháng vào thư mục `Dinh_kem\năm-tháng` (ví dụ `Dinh_kem\2026-09`). Bấm nút **Mở thư mục đính kèm** để mở nhanh đúng thư mục của kỳ đang chọn.
4. Trong app: Chọn **Tháng**, **Năm**, chế độ **Tạm tính** (chỉ đính kèm Excel) hoặc **Chốt** (đính kèm Excel + PDF) → bấm **XEM TRƯỚC & GỬI**.
5. Tại cửa sổ Xem trước:
   - Dùng ô **🔍 Lọc NCC** để tìm nhanh đối tác.
   - **Nhấp đúp chuột** (hoặc nhấn phím `Space`) vào dòng nhà cung cấp bất kỳ để **Chọn (`☑`)** hoặc **Bỏ chọn (`☐`)** gửi lẻ từng đối tác mà không cần sửa file Excel.
   - Bấm **Xác nhận & Gửi**.

---

## 3. Tính năng an toàn & Lịch sử gửi
- **Điều khiển trực tiếp khi đang gửi**: Có thể bấm **⏸ Tạm dừng**, **▶ Tiếp tục** hoặc **⏹ Hủy gửi** bất cứ lúc nào.
- **Lịch sử thông minh chống khóa file**: Mọi kết quả gửi đều được lưu an toàn vào cơ sở dữ liệu nội bộ `history.db` và tự động xuất ra báo cáo Excel định dạng màu `Lich_su_gui.xlsx` (kèm `Lich_su_gui.csv`) khi bấm **Xem lịch sử gửi**.
