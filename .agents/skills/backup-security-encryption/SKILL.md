---
name: backup-security-encryption
description: >-
  Kỹ năng bảo mật dữ liệu sao lưu và an toàn thông tin xác thực NAS: bảo vệ mật khẩu NAS/SMB/SFTP qua
  Windows Credential Manager (keyring), mã hóa bản sao lưu đầu-cuối chuẩn AES-256-GCM /PBKDF2/Argon2,
  chống tấn công Path Traversal (Zip Slip) khi khôi phục, và cam kết Zero Data Loss (chỉ đọc trên thư mục nguồn).
---

# Backup Security & Encryption Skill (Bảo Mật Dữ Liệu & Thông Tin Xác Thực NAS)

Ứng dụng sao lưu nắm quyền truy cập vào toàn bộ dữ liệu quan trọng trên máy tính và máy chủ NAS. Bộ kỹ năng này thiết lập các hàng rào bảo mật bắt buộc.

---

## 1. Quản Lý Mật Khẩu & Khóa Truy Cập NAS An Toàn (Zero Plaintext Credentials)

- **Nghiêm cấm lưu mật khẩu dạng rõ (Plaintext)**:
  - Tuyệt đối không lưu mật khẩu SMB, SFTP, WebDAV hoặc Telegram Bot Token dưới dạng văn bản thuần trong tệp `config.json`, `.ini` hay cơ sở dữ liệu SQLite.
- **Sử dụng OS Keyring / Windows Credential Manager**:
  - Ưu tiên dùng thư viện `keyring` (tích hợp trực tiếp với **Windows Credential Manager** trên Windows) để lưu và truy xuất mật khẩu theo `service_name = "BackupDataToNAS"` và `username = <profile_id>`.
  - Trường hợp cần xuất/nhập cấu hình di động, bắt buộc mã hóa trường nhạy cảm bằng khóa dẫn xuất từ Master Password qua `PBKDF2HMAC` (SHA-256, >= 600,000 vòng lặp) + `AES-256-GCM` (`cryptography`).

---

## 2. Mã Hóa Bản Sao Lưu Phía Máy Khách (Client-Side Encryption - Tùy Chọn Theo Job)

Đối với các thư mục nhạy cảm (tài liệu tài chính, hồ sơ cá nhân, khóa cá nhân):
1. Hỗ trợ bật tùy chọn **Mã hóa bản sao lưu (AES-256-GCM / Fernet Stream)** trước khi đẩy lên NAS.
2. Mã hóa theo từng khối (Chunked Authenticated Encryption) để:
   - Không cần nạp cả tệp lớn vào RAM.
   - Phát hiện tức thì nếu bất kỳ khối dữ liệu nào trên NAS bị chỉnh sửa trái phép hoặc lỗi bit (Authentication Tag Verification).

---

## 3. Cam Kết Bất Biến Thư Mục Nguồn (Source Read-Only Guarantee)

- **Nguyên tắc Sắt đá trong chiều Backup (`Source -> NAS`)**:
  - Tầng `BackupService` chỉ được mở tệp nguồn ở chế độ **chỉ đọc (`"rb"`)**.
  - Tuyệt đối không gọi bất kỳ lệnh xóa (`os.remove`, `shutil.rmtree`), đổi tên hay cắt bớt (`truncate`) nào lên cây thư mục nguồn trong suốt quá trình sao lưu.
- **An toàn trong chiều Khôi phục (`NAS -> Restore Target`)**:
  - Mặc định khuyến nghị khôi phục vào thư mục mới hoặc tạo bản chụp dự phòng cho các tệp bị ghi đè.
  - Kiểm tra chống lỗ hổng **Path Traversal / Zip Slip**: Mọi đường dẫn tương đối đọc từ bản sao lưu phải được chuẩn hóa (`Path.resolve()`) và xác minh nằm hoàn toàn bên trong thư mục đích khôi phục trước khi ghi xuống đĩa.

---

## 4. Vệ Sinh Kho Mã Nguồn (Git Secret Hygiene)

- Kiểm soát nghiêm ngặt `.gitignore`: Không bao giờ commit tệp `.env`, cấu hình NAS cục bộ (`*config.local.json`), tệp cơ sở dữ liệu `.db`/`.sqlite`, tệp nhật ký `.log` hoặc khóa SSH vào Git.
