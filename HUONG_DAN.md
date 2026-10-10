# Gửi mail hàng loạt cho nhà cung cấp (qua Gmail)

## Cài đặt

### Cách 1: dùng file exe (khuyên dùng, không cần cài Python)
1. Copy file `Ban_phat_hanh\Gui_mail_nha_cung_cap.exe` sang máy cần dùng, đặt trong một thư mục riêng.
2. Bấm đúp file exe. Lần đầu app tự tạo `Cau_hinh.xlsx` ngay cạnh file exe. Cùng thư mục này sẽ có `Dinh_kem\` và `Lich_su_gui.csv`.
3. Muốn tạo lại file exe sau khi sửa code: chạy `Dong_goi_exe.bat` (máy build cần `pip install pyinstaller`).

> Windows SmartScreen hoặc phần mềm diệt virus có thể cảnh báo file exe lạ ở lần chạy đầu. Chọn *More info → Run anyway* nếu file do bạn tự build.

### Cách 2: chạy từ mã nguồn
1. Máy cần có **Python 3.10 trở lên** (tải tại https://www.python.org/downloads/, nhớ tick *Add python.exe to PATH*).
2. Copy nguyên thư mục này sang máy cần dùng. **Không cần cài thêm gì khác.**
3. Bấm đúp `Chay_ung_dung.bat`.

## Dùng lần đầu
1. Mở file `Cau_hinh.xlsx` (nút **Mở file cấu hình** trong app). Sheet **Hướng dẫn** giải thích từng bước.
2. Điền **Gmail**, **Mật khẩu ứng dụng**, **mail người nhận** của từng nhà cung cấp, rồi lưu file (Ctrl+S).
3. Bỏ file Excel/PDF của tháng vào thư mục `Dinh_kem\năm-tháng` (ví dụ `Dinh_kem\2026-09`). Nút **Mở thư mục đính kèm** sẽ mở (hoặc tạo) thư mục này.
4. Trong app: chọn tháng, năm, loại **Tạm tính** hoặc **Chốt** → **Xem trước & Gửi** → **Xác nhận & Gửi**.

## Lưu ý
- Tạm tính chỉ đính kèm file Excel. Chốt đính kèm cả Excel và PDF.
- Nhà cung cấp thiếu file hoặc thiếu mail người nhận sẽ báo đỏ ở màn hình xem trước và bị bỏ qua.
- Mỗi lần gửi được ghi vào `Lich_su_gui.csv`. Nếu gửi lại cùng kỳ, app mặc định bỏ qua nhà cung cấp đã gửi thành công.
- `Cau_hinh.xlsx` chứa Mật khẩu ứng dụng Gmail, **không gửi file này cho người khác**.
- Nên bấm **Kiểm tra kết nối Gmail** trước. Lần đầu, hãy thử với mail người nhận là chính bạn.

## Cấu trúc
- `main.py`: điểm khởi động. `app/`: mã nguồn. `vendor/`: thư viện openpyxl đóng gói sẵn.
- `tests/`: chạy `python -m unittest discover tests`.
