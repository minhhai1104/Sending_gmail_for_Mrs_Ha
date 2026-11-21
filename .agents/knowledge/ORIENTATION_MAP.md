# Orientation Map: Ứng dụng Gửi Email Hàng Loạt Cho Nhà Cung Cấp (Gmail Auto Mailer)

> **Mục tiêu**: Giúp bất kỳ Agent nào khi bắt đầu phiên mới nắm bắt 100% bối cảnh dự án, kiến trúc và quy chuẩn kỹ thuật trong 30 giây mà người dùng không cần giải thích lại.

---

## 🎯 1. Bối cảnh & Nghiệp vụ Dự án
- **Dự án**: Ứng dụng Desktop tự động gửi báo cáo Bảng phí kiểm tra, phân loại hàng hóa hàng tháng cho các nhà cung cấp / đối tác của **Haesung Vina**.
- **Người dùng cuối**: Nhân viên văn phòng, thao tác cấu hình hoàn toàn qua file Excel `Cau_hinh.xlsx`.
- **Chế độ gửi**:
  - **Tạm tính**: Chỉ đính kèm file Excel (`Bảng phí kiểm tra, phân loại hàng hóa {thang}.{nam} {nha_cung_cap}.xlsx`).
  - **Chốt**: Đính kèm cả file Excel và file PDF (`PO {nha_cung_cap} {thang}.{nam}.pdf`).
- **Giao thức**: Gmail SMTP qua SSL (`smtp.gmail.com:465`) với Mật khẩu ứng dụng (App Password 16 chữ số).

---

## 🏗️ 2. Bản Đồ Thành Phần (Components Map)
```text
Sending_gmail_for_Mrs_Ha/
├── app/
│   ├── config.py             # Đọc/ghi cấu hình Excel Cau_hinh.xlsx (4 sheet)
│   ├── history.py            # Lưu trữ lịch sử gửi mail vào SQLite & CSV
│   ├── mailer.py             # Lõi kết nối SMTP SSL, Pacing (1.5-3s), Retry
│   ├── main_window.py        # Giao diện chính Tkinter, luồng nền Worker
│   ├── planner.py            # Dựng kế hoạch gửi MailPlan, kiểm tra file & email
│   ├── preview_dialog.py     # Cửa sổ xem trước, lọc nhà đã gửi, xác nhận gửi
│   └── templating.py         # Thay thế biến {thang}, {nam}, {nha_cung_cap}, {loai}
├── tests/
│   └── test_app.py           # Bộ kiểm thử pytest 3 khía cạnh (Happy, Edge, Chaos)
├── vendor/                   # Gói openpyxl tích hợp sẵn
├── .agents/                  # Hệ thống Đa tác nhân: 7 Agents, Rules, Skills, Memory, Knowledge
├── Cau_hinh.xlsx             # File cấu hình mẫu
├── Ban_phat_hanh/            # Thư mục chứa file exe phân phối
└── README.md                 # Tài liệu hướng dẫn sử dụng chi tiết
```

---

## 🛡️ 3. Quy Ước Bắt Buộc & Lời Thề An Toàn
1. **Zero Plaintext Secrets**: Không commit mật khẩu, chuyển đổi lưu trữ an toàn qua Windows Credential Manager (`keyring`).
2. **Zero Unverified Mail Loss**: Chỉ đánh dấu thành công khi nhận phản hồi 250 OK từ Gmail SMTP.
3. **Non-Blocking UI**: Mọi thao tác I/O mạng hoặc đĩa cứng bắt buộc chạy trên luồng nền (`threading.Thread`), giao diện Tkinter phản hồi mượt mà 100%.
4. **Pacing chống Spam**: Luôn có khoảng nghỉ 1.5 - 3.0s giữa các mail gửi đi.
5. **SQLite History**: Lưu trữ lịch sử gửi trong SQLite nội bộ để triệt tiêu lỗi khóa file khi người dùng mở Excel.
