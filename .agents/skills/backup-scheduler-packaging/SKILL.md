---
name: backup-scheduler-packaging
description: >-
  Kỹ năng lập lịch chạy tự động, phục hồi kết nối mạng bền bỉ và đóng gói ứng dụng Python Desktop:
  lập lịch chạy ngầm (APScheduler / Windows Task Scheduler), quản lý SQLite catalog có schema_migrations,
  kiểm tra NAS trực tuyến & Wake-on-LAN, retry thông minh với Exponential Backoff, thông báo Telegram/Webhook,
  và đóng gói thực thi độc lập (.exe) bằng PyInstaller / Nuitka.
---

# Backup Scheduler, Reliability & Packaging Skill

Bộ kỹ năng này đảm bảo ứng dụng sao lưu vận hành bền bỉ 24/7 như một dịch vụ công nghiệp và dễ dàng đóng gói phân phối trên Windows.

---

## 1. Bộ Lập Lịch Tự Động & Chạy Ngầm (Automated Scheduling)

1. **Đa chế độ lập lịch cho từng Backup Job**:
   - **Theo định kỳ**: Hàng ngày (chọn giờ:phút), Hàng tuần (chọn thứ trong tuần), Hàng tháng, hoặc mỗi `N` giờ.
   - **Theo sự kiện**: Khi khởi động máy / đăng nhập Windows, hoặc chạy thủ công 1-click (*"Sao lưu ngay"*).
   - **Missed-Run Catch-up**: Nếu máy tính đang tắt vào đúng giờ hẹn (ví dụ hẹn 02:00 sáng nhưng 08:00 sáng mới bật máy), ứng dụng tự động phát hiện lượt chạy bị lỡ khi khởi động và thực thi bù an toàn.
2. **Tích hợp Khởi động cùng Windows**:
   - Hỗ trợ đăng ký chạy ngầm khi đăng nhập Windows (qua Registry `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` hoặc **Windows Task Scheduler**) với tham số `--minimized` / `--background`.

---

## 2. Độ Bền Kết Nối Mạng & Đánh Thức NAS (Network Resilience & Wake-on-LAN)

- **Kiểm tra sức khỏe NAS trước khi chạy (Pre-flight Health Check)**:
  - Trước khi bắt đầu sao lưu, kiểm tra nhanh kết nối mạng tới NAS (TCP connect tới cổng SMB `445`, SFTP `22`, hoặc kiểm tra sự tồn tại của thư mục đích).
  - Hỗ trợ gửi gói tin **Wake-on-LAN (Magic Packet UDP)** theo địa chỉ MAC của NAS nếu NAS đang ở chế độ ngủ (Sleep/Hibernation), sau đó chờ NAS thức dậy trước khi chạy job.
- **Retry với Exponential Backoff**:
  - Khi mạng Wi-Fi/LAN chập chờn làm gián đoạn quá trình truyền tệp, hệ thống tự động thử lại theo chu kỳ tăng dần (`2s -> 5s -> 15s -> 30s`, tối đa `N` lần) thay vì hủy bỏ toàn bộ tiến trình ngay lập tức.

---

## 3. Cơ Sở Dữ Liệu SQLite Catalog & Versioned Migrations

- Lưu trữ toàn bộ cấu hình Job (`backup_jobs`), lịch sử các lần chạy (`job_runs`), danh mục phiên bản tệp (`file_manifests`) và nhật ký sự kiện (`audit_logs`) trong cơ sở dữ liệu SQLite cục bộ.
- **Migration An Toàn**:
  - Mọi thay đổi cấu trúc bảng phải đi qua bảng `schema_migrations` và tự động tạo bản sao lưu DB (`VACUUM INTO`) trước khi nâng cấp schema để người dùng cập nhật ứng dụng không bao giờ mất lịch sử sao lưu.

---

## 4. Cảnh Báo Tự Động & Đóng Gói Thực Thi (`.exe`)

1. **Thông báo Đa Kênh (Notifications)**:
   - Hiển thị Windows Toast Notification khi hoàn tất hoặc gặp lỗi.
   - Hỗ trợ gửi báo cáo tóm tắt (Tên Job, Trạng thái, Số tệp mới/thay đổi, Tổng dung lượng, Thời gian chạy, Dung lượng trống trên NAS) qua **Telegram Bot** hoặc **Webhook (Discord/Slack)**.
2. **Đóng gói `.exe` Chuẩn Production**:
   - Đóng gói bằng **PyInstaller** hoặc **Nuitka** với cấu hình `--noconsole` / `--windowed`, nhúng biểu tượng ứng dụng (`.ico`), tệp giao diện/theme, và tạo script kiểm tra khởi chạy thực tế trước khi phát hành.
