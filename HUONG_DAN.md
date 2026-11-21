# Hướng Dẫn Sử Dụng Nhanh — Gmail Auto Mailer v3.1.0 (Haesung Vina)

## 1. Cài đặt chỉ với 1 cú click (Không cần cài Python, Không cần quyền Admin)
1. Chạy file bộ cài **`Cai_dat_Gui_mail_Haesung_Vina_v3.1.0.exe`** (trong thư mục `Ban_phat_hanh`).
2. Bấm **Install** — bộ cài tự động tạo biểu tượng **Gmail Auto Mailer** có logo thương hiệu ngoài màn hình chính (Desktop) & Start Menu và tự mở ứng dụng ngay lập tức.
3. Toàn bộ cấu hình, mật khẩu (mã hóa bằng Windows DPAPI) và lịch sử gửi được lưu riêng tại `%LOCALAPPDATA%\GmailAutoMailer` — an toàn tuyệt đối khi cập nhật phiên bản mới (OTA).

---

## 2. Thiết lập lần đầu (60 giây ngay trong ứng dụng — KHÔNG cần dùng Excel)
Lần mở đầu tiên, trợ lý thiết lập 3 bước sẽ tự mở:
1. **Bước 1 — Kết nối Gmail**: Nhập Gmail, Tên hiển thị và **Mật khẩu ứng dụng Google (16 ký tự)**. Bấm nút *"Lấy Mật khẩu 16 ký tự ↗"* ngay trên màn hình để mở thẳng trang Google, dán vào và bấm **Kiểm tra Gmail & Tiếp tục**.
2. **Bước 2 — Email Nhà cung cấp**: Nhập email nhận báo cáo của từng nhà cung cấp (nhiều email cách nhau bằng dấu `;`).
3. **Bước 3 — Chữ ký & Logo**: Chọn ảnh logo công ty (nếu có), xem trước ngay mẫu email HTML thật và bấm **Hoàn tất**.

---

## 3. Gửi báo cáo hàng tháng chỉ trong 3 bước
1. **Kéo thả thư mục** (hoặc bấm **Chọn thư mục / Chọn file rời**) chứa báo cáo Excel & PDF của tháng vào ứng dụng. Hệ thống tự động nhận diện tháng/năm, tự chọn chế độ **Tạm tính** (chỉ Excel) hay **Chốt** (Excel + PDF) và tự khớp an toàn vào từng nhà cung cấp.
2. **Kiểm tra trực tiếp**: Bảng danh sách 1 dòng hiển thị thẳng cột `Email · Excel · PDF · Trạng thái` (dùng phím `↑ / ↓` để lướt nhanh 50+ nhà cung cấp và bấm tiêu đề `Trạng thái` để gom mục lỗi lên đầu). Bấm trực tiếp vào ô đỏ `✕` để thêm email / chọn file, hoặc ô vàng `?` để xem và duyệt file bên khung **Xem trước Email HTML + Chữ ký + Logo 1:1**. Có thể bấm **Gửi thử cho tôi** để kiểm tra hộp thư trước khi gửi thật.
3. **Bấm Gửi ngay**: Theo dõi tiến độ trực tiếp (tốc độ `mail/phút`, `ETA`, nút **Tạm dừng / Tiếp tục / Hủy**). Nếu có nhà bị lỗi mạng, bấm **Gửi lại nhà bị lỗi** trong 1 click.

---

## 4. Tra cứu Lịch sử & Cập nhật tự động
- Mở mục **Lịch sử gửi** ngay trong ứng dụng để lọc theo tháng/năm/trạng thái hoặc bấm **Xuất báo cáo Excel** khi cần lưu trữ kế toán.
- Khi có phiên bản mới trên GitHub Releases, thanh thông báo sẽ tự hiện ở đầu ứng dụng — bấm **Cập nhật ngay** để tự động nâng cấp mà không mất bất kỳ dữ liệu nào.
