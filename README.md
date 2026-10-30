# Ứng dụng Gửi Email Hàng Loạt Cho Nhà Cung Cấp (Gmail Auto Mailer)

[![Version](https://img.shields.io/badge/version-v1.0.0-blue.svg)](https://github.com/minhhai1104/Sending_gmail_for_Mrs_Ha)
[![Python](https://img.shields.io/badge/python-3.10%2B-brightgreen.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()

Ứng dụng đồ họa (GUI) nhỏ gọn, trực quan, chuyên dùng để tự động hóa quy trình gửi email hàng loạt hàng tháng cho các nhà cung cấp / đối tác (áp dụng cho báo cáo Bảng phí kiểm tra, phân loại hàng hóa của **Haesung Vina**).

---

## 📌 Tính năng nổi bật

- **Giao diện trực quan, dễ dùng**: Thiết kế bằng Tkinter thuần, không yêu cầu thao tác phức tạp, có thể copy là chạy ngay.
- **Tùy biến tiêu đề và nội dung linh hoạt**: Dễ dàng chỉnh sửa mẫu email với các biến tự động thay thế: `{thang}`, `{nam}`, `{nha_cung_cap}`, `{loai}`.
- **Hỗ trợ 2 chế độ gửi hàng tháng**:
  - **Bản tạm tính**: Tự động lọc và chỉ đính kèm file Excel.
  - **Bản chốt**: Tự động đính kèm đồng thời file Excel và file PDF.
- **Cấu hình bằng Excel thân thiện (`Cau_hinh.xlsx`)**: Thích hợp cho người dùng văn phòng/non-tech, có hướng dẫn chi tiết và ô màu vàng trực quan.
- **Kiểm tra & Xem trước an toàn (Preview)**:
  - Cho phép kiểm tra trước danh sách người nhận, tiêu đề, nội dung và các file đính kèm thực tế trước khi bấm gửi.
  - Tự động phát hiện và cảnh báo màu đỏ nếu thiếu file đính kèm hoặc thiếu địa chỉ email.
- **Ghi nhật ký lịch sử gửi (`Lich_su_gui.csv`)**: Tránh gửi trùng lặp; tự động phát hiện và bỏ qua các nhà cung cấp đã gửi thành công trước đó khi gửi lại.
- **Kiểm tra kết nối Gmail**: Nút kiểm tra tài khoản Gmail và Mật khẩu ứng dụng trước khi thực hiện gửi chính thức.

---

## 🚀 Hướng dẫn cài đặt & Chạy ứng dụng

### Cách 1: Sử dụng file EXE đóng gói sẵn (Khuyên dùng - Không cần cài Python)

Dành cho người dùng văn phòng muốn copy chạy ngay:

1. Tải hoặc copy thư mục `Ban_phat_hanh` chứa file `Gui_mail_nha_cung_cap.exe` về máy tính.
2. Bấm đúp vào `Gui_mail_nha_cung_cap.exe` để mở ứng dụng.
3. Ở lần khởi chạy đầu tiên, ứng dụng sẽ **tự động sinh ra file `Cau_hinh.xlsx`** mẫu ngay tại cùng thư mục với file `.exe`.

> **Lưu ý**: Lần đầu mở, Windows SmartScreen hoặc trình diệt virus có thể hiện cảnh báo vì đây là phần mềm nội bộ chưa ký số chứng chỉ thương mại. Bấm **More info** (Thêm thông tin) → **Run anyway** (Vẫn chạy).

---

### Cách 2: Chạy trực tiếp từ mã nguồn Python

Dành cho lập trình viên hoặc muốn tùy biến mã nguồn:

1. Cài đặt **Python 3.10 trở lên** (tải tại [python.org](https://www.python.org/downloads/), chú ý tick chọn `Add python.exe to PATH`).
2. Clone repository hoặc tải toàn bộ mã nguồn về máy:
   ```bash
   git clone https://github.com/minhhai1104/Sending_gmail_for_Mrs_Ha.git
   cd Sending_gmail_for_Mrs_Ha
   ```
3. Chạy ứng dụng:
   - Bấm đúp vào file `Chay_ung_dung.bat` (chạy ngầm không mở cửa sổ đen).
   - Hoặc chạy bằng lệnh:
     ```powershell
     python main.py
     ```
   *(Thư viện `openpyxl` đã được đóng gói sẵn trong thư mục `vendor/`, không cần chạy lệnh `pip install`)*.

---

## 🔑 Hướng dẫn lấy Mật khẩu ứng dụng Gmail (App Password)

Google yêu cầu sử dụng **Mật khẩu ứng dụng (App Password 16 chữ số)** thay cho mật khẩu tài khoản Gmail thông thường để gửi qua giao thức SMTP:

1. Đăng nhập vào tài khoản Google gửi thư: [myaccount.google.com](https://myaccount.google.com).
2. Vào mục **Bảo mật** (Security) → Đảm bảo **Xác minh 2 bước** (2-Step Verification) đã được **Bật**.
3. Tại thanh tìm kiếm trên cùng của trang tài khoản Google, gõ tìm **"Mật khẩu ứng dụng"** (hoặc truy cập trực tiếp link: [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)).
4. Nhập tên ứng dụng (ví dụ: `Auto Mailer`) rồi bấm **Tạo** (Create).
5. Google sẽ hiện một dãy mã gồm **16 chữ cái** (dạng `abcd efgh ijkl mnop`). Hãy copy dãy mã này và dán vào ô mật khẩu trong file `Cau_hinh.xlsx`.

---

## ⚙️ Hướng dẫn cấu hình (`Cau_hinh.xlsx`)

Bấm nút **Mở file cấu hình** trên giao diện ứng dụng để chỉnh sửa `Cau_hinh.xlsx`. File gồm 4 sheet:

1. **Sheet Hướng dẫn**: Giải thích các bước thao tác và các biến được hỗ trợ.
2. **Sheet Gmail**:
   - `Địa chỉ Gmail gửi đi`: Điền địa chỉ Gmail của bạn.
   - `Mật khẩu ứng dụng`: Điền chuỗi 16 chữ số lấy từ Google (xóa dấu cách nếu có).
   - `Tên người gửi`: Tên hiển thị khi người nhận nhận thư.
3. **Sheet Nhà cung cấp**:
   - Cột `Mã NCC`: Tên/mã nhà cung cấp (ví dụ: `ACE`, `AHC`, `T&T`, `DiaMond`, `Hitech`, `HR Partner`, `Mansa`...).
   - Cột `Tên đầy đủ`: Tên công ty hoặc tên đại diện.
   - Cột `Danh sách email nhận`: Danh sách email người nhận của nhà cung cấp đó. Nếu có nhiều email, phân cách bằng dấu chấm phẩy `;` hoặc dấu phẩy `,`.
   - Cột `Kích hoạt`: Điền `Có` (để gửi) hoặc `Không` (tạm dừng gửi cho nhà này).
4. **Sheet Nội dung mail**:
   - Mẫu tiêu đề thư (chứa các biến `{thang}`, `{nam}`, `{nha_cung_cap}`, `{loai}`).
   - Mẫu nội dung thư (chứa lời chào, thông báo chi phí, chữ ký...).
   - Quy tắc tên file đính kèm:
     - Excel: `Bảng phí kiểm tra, phân loại hàng hóa {thang}.{nam} {nha_cung_cap}.xlsx`
     - PDF: `PO {nha_cung_cap} {thang}.{nam}.pdf`

---

## 📂 Quy ước thư mục file đính kèm (`Dinh_kem`)

Trước khi gửi, đặt các file cần gửi vào thư mục theo cấu trúc:
```text
Dinh_kem/
  └── YYYY-MM/                     (Ví dụ: 2026-09)
        ├── Bảng phí kiểm tra, phân loại hàng hóa 09.2026 ACE.xlsx
        ├── PO ACE 09.2026.pdf
        ├── Bảng phí kiểm tra, phân loại hàng hóa 09.2026 AHC.xlsx
        ├── PO AHC 09.2026.pdf
        └── ...
```

> **Mẹo**: Trong app có sẵn nút **Mở thư mục đính kèm**, ứng dụng sẽ tự động mở đúng thư mục theo tháng/năm bạn đang chọn.

---

## 🖥️ Quy trình gửi mail hàng tháng

1. **Chuẩn bị file**: Copy các file Excel và PDF vào thư mục `Dinh_kem/năm-tháng` tương ứng.
2. **Mở ứng dụng**: Chọn **Tháng**, **Năm**, và chọn loại đợt gửi:
   - **Tạm tính**: Chỉ đính kèm file Excel.
   - **Chốt**: Đính kèm cả file Excel và PDF.
3. **Kiểm tra**:
   - *(Tùy chọn)* Bấm **Kiểm tra kết nối Gmail** để kiểm tra mạng & mật khẩu.
   - Bấm **Xem trước & Gửi**: Cửa sổ kiểm tra sẽ hiển thị từng nhà cung cấp, danh sách người nhận, tiêu đề, nội dung và trạng thái file đính kèm.
   - Nếu có dòng màu đỏ (bị thiếu file hoặc thiếu mail), app sẽ thông báo rõ ràng.
4. **Gửi**:
   - Bấm nút **Xác nhận & Gửi**.
   - Tiến trình gửi hiển thị trực tiếp trên thanh Progress Bar và khung Log.
   - Kết quả thành công/thất bại được lưu vào `Lich_su_gui.csv`.

---

## 📁 Cấu trúc mã nguồn

```text
Sending_gmail_for_Mrs_Ha/
├── app/
│   ├── __init__.py           # Khai báo package & phiên bản (__version__)
│   ├── config.py             # Đọc và khởi tạo file Excel cấu hình Cau_hinh.xlsx
│   ├── history.py            # Quản lý lịch sử gửi mail vào Lich_su_gui.csv
│   ├── mailer.py             # Xử lý kết nối SMTP Gmail SSL & gửi email
│   ├── main_window.py        # Giao diện chính Tkinter
│   ├── planner.py            # Lập kế hoạch gửi và kiểm tra tính hợp lệ từng NCC
│   ├── preview_dialog.py     # Cửa sổ xem trước & kiểm duyệt trước khi gửi
│   └── templating.py         # Xử lý nội suy biến {thang}, {nam}, {loai}...
├── tests/
│   └── test_app.py           # Unit tests kiểm tra toàn bộ logic
├── vendor/                   # Gói thư viện openpyxl tích hợp sẵn (không cần pip install)
├── .gitignore                # Danh sách loại trừ (file bảo mật, cache, exe...)
├── Ban_phat_hanh/            # Chứa file thực thi Gui_mail_nha_cung_cap.exe
├── Chay_ung_dung.bat         # File batch khởi động nhanh bằng Python
├── Dong_goi_exe.bat          # File batch tự động đóng gói ứng dụng bằng PyInstaller
├── HUONG_DAN.md              # Tài liệu hướng dẫn tóm tắt cho người dùng
├── main.py                   # Điểm khởi chạy ứng dụng
└── README.md                 # Tài liệu giới thiệu & hướng dẫn chi tiết dự án
```

---

## 📦 Cách đóng gói lại file EXE (Dành cho Dev)

Khi có thay đổi về code và cần cập nhật lại file thực thi `.exe`:

1. Cài đặt PyInstaller:
   ```bash
   pip install pyinstaller
   ```
2. Chạy file đóng gói:
   - Bấm đúp vào file `Dong_goi_exe.bat`.
   - File `.exe` mới sẽ được tạo trong thư mục `Ban_phat_hanh/Gui_mail_nha_cung_cap.exe`.

---

## 🏷️ Lịch sử phiên bản (Changelog)

### **v1.0.0 (30/10/2026)**
- 🎉 **Phát hành phiên bản chính thức đầu tiên**.
- Xây dựng giao diện Tkinter hỗ trợ chọn kỳ gửi (tháng, năm) và chế độ gửi (Tạm tính / Chốt).
- Tích hợp cấu hình hoàn toàn qua Excel `Cau_hinh.xlsx` (4 sheet chuyên biệt).
- Hỗ trợ gửi qua Gmail SMTP SSL với Mật khẩu ứng dụng an toàn.
- Đóng gói sẵn thư viện `openpyxl` trong thư mục `vendor/`.
- Thêm màn hình Xem trước (Preview Dialog) chống gửi sai, gửi thiếu.
- Thêm tính năng ghi nhật ký và bỏ qua các nhà cung cấp đã gửi thành công trong kỳ.
- Đóng gói thành công file thực thi độc lập `Gui_mail_nha_cung_cap.exe`.

---

## 🔒 Bảo mật dữ liệu

- File `Cau_hinh.xlsx` chứa Mật khẩu ứng dụng Gmail của bạn.
- File `Lich_su_gui.csv` và thư mục `Dinh_kem/` chứa thông tin danh tính và chứng từ nội bộ.
- File `.gitignore` của dự án đã được thiết lập để **không bao giờ đồng bộ các file nhạy cảm này lên GitHub**. Vui lòng giữ bí mật và không chia sẻ file `Cau_hinh.xlsx` cho người khác.
