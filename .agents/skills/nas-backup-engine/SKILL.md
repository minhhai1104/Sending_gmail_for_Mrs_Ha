---
name: nas-backup-engine
description: >-
  Kỹ năng thiết kế và triển khai lõi sao lưu dữ liệu sang NAS bằng Python (NAS Backup Engine):
  hỗ trợ đa giao thức (SMB/CIFS, SFTP/SSH, WebDAV, Rsync/Robocopy), các chế độ sao lưu
  (Full, Incremental, Differential, Mirror/Sync an toàn), truyền tải streaming theo chunk,
  kiểm tra toàn vẹn SHA-256/XXHash, nén zstd/zip, chính sách lưu trữ GFS (Grandfather-Father-Son),
  và xử lý đường dẫn dài / tệp đang mở trên Windows.
---

# NAS Backup Engine Skill (Lõi Sao Lưu Dữ Liệu Đa Giao Thức Sang NAS)

Bộ kỹ năng này định nghĩa kiến trúc và thuật toán cốt lõi cho công cụ sao lưu dữ liệu từ máy tính cá nhân / máy trạm sang thiết bị lưu trữ mạng (NAS: Synology, QNAP, TrueNAS, Unraid, Windows/Linux SMB/SFTP Server).

---

## 1. Kiến Trúc Storage Adapter Đa Giao Thức (Multi-Protocol Abstraction)

Tách biệt hoàn toàn logic sao lưu khỏi giao thức truyền tải thông qua giao diện trừu tượng `StorageAdapter`:
1. **Local / Mapped Drive & UNC SMB (`\\NAS\Share`)**:
   - Hỗ trợ đường dẫn UNC trực tiếp và tự động thêm tiền tố `\\?\` hoặc `\\?\UNC\` trên Windows để vượt giới hạn `MAX_PATH` (260 ký tự).
   - Hỗ trợ kết nối phiên SMB thông qua `smbprotocol` / `pysmb` hoặc `net use` an toàn với thông tin xác thực từ Windows Credential Manager.
2. **SFTP / SSH (`paramiko` / `asyncssh`)**:
   - Hỗ trợ xác thực bằng mật khẩu hoặc SSH Private Key (Ed25519 / RSA), tự động căn chỉnh kích thước cửa sổ truyền tải (`window_size`, `max_packet_size`) để tối ưu tốc độ mạng LAN Gigabit / 2.5GbE / 10GbE.
3. **WebDAV / FTP / Rsync**:
   - Cho phép mở rộng qua chuẩn `Protocol` / `ABC` của Python mà không phải sửa đổi tầng `BackupService`.

---

## 2. Các Chế Độ Sao Lưu Chuẩn Mực (Backup Strategies)

1. **Full Backup (Sao lưu toàn phần)**:
   - Sao chép toàn bộ tệp tin được chọn vào thư mục đích hoặc đóng gói thành bản chụp (snapshot) hoàn chỉnh kèm tệp `manifest.json` / bản ghi SQLite.
2. **Incremental Backup (Sao lưu gia tăng)**:
   - Chỉ sao chép những tệp mới hoặc thay đổi kể từ **lần sao lưu gần nhất** (bất kể Full hay Incremental).
   - Phát hiện thay đổi nhanh qua tổ hợp `(file_size, mtime_ns)` và xác minh lại bằng mã băm **SHA-256 / XXHash64** khi cần độ chính xác tuyệt đối.
   - Hỗ trợ cơ chế Hardlink-based Snapshot (tương tự `rsync --link-dest` hoặc Time Machine) để tiết kiệm dung lượng NAS nhưng vẫn duyệt được từng phiên bản đầy đủ.
3. **Differential Backup (Sao lưu vi sai)**:
   - Sao chép tất cả tệp thay đổi kể từ **lần Full Backup gần nhất**, giúp rút ngắn thời gian khôi phục (chỉ cần 1 bản Full + 1 bản Differential mới nhất).
4. **Mirror / Two-Way Sync Có Bảo Vệ (Safe Sync with Trash Bin)**:
   - Khi đồng bộ 1 chiều (Mirror), những tệp đã xóa ở nguồn **KHÔNG** bị xóa vĩnh viễn ngay lập tức trên NAS mà được di chuyển vào thư mục `.nas_backup_trash/<timestamp>/` trong một khoảng thời gian lưu giữ (ví dụ 30 ngày) để phòng ngừa xóa nhầm hoặc mã độc tống tiền.

---

## 3. Truyền Tải Streaming, Ghi Nguyên Tử & Kiểm Tra Toàn Vẹn

- **Streaming Chunked I/O (Không tràn RAM)**:
  - Đọc và ghi tệp theo từng khối bộ đệm (`chunk_size = 1 MB` đến `8 MB`). Dù sao lưu tệp máy ảo hay video `.iso`/`.mp4` nặng 50 GB, mức tiêu thụ RAM của tiến trình Python luôn giữ phẳng (< 100 MB).
- **Atomic File Write (Ghi tệp nguyên tử)**:
  - Mọi tệp đang truyền lên NAS phải mang hậu tố tạm thời `.part.<run_id>`.
  - Chỉ sau khi ghi đủ số byte, đồng bộ bộ đệm (`fsync`) và kiểm tra khớp mã băm, tệp mới được đổi tên (`rename` / `replace`) sang tên chính thức. Nếu rớt mạng giữa chừng, không bao giờ để lại tệp đích bị hỏng đè lên bản sao lưu cũ.
- **End-to-End Checksum Verification**:
  - Tính toán mã băm SHA-256 (hoặc BLAKE3/XXHash) ngay trong luồng đọc (single-pass streaming hash) và lưu vào bảng `file_manifests` trong SQLite.

---

## 4. Chính Sách Lưu Trữ & Dọn Dẹp Tự Động (GFS Retention Policy)

Hỗ trợ quy tắc **Grandfather-Father-Son (GFS)** để ổ đĩa NAS không bị đầy theo thời gian:
- Giữ `N` bản sao lưu hàng ngày gần nhất (Daily - Son).
- Giữ `W` bản sao lưu hàng tuần (Weekly - Father).
- Giữ `M` bản sao lưu hàng tháng (Monthly - Grandfather).
- Luôn giữ lại ít nhất 1 bản sao lưu thành công hoàn chỉnh trước khi xoay vòng xóa bản cũ nhất.
