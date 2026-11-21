---
name: python-gui-architecture
description: >-
  Kỹ năng thiết kế kiến trúc giao diện ứng dụng Desktop bằng Python (PySide6 / PyQt6 / CustomTkinter / Flet):
  đảm bảo nguyên tắc bất biến Non-Blocking UI Thread (tách biệt luồng giao diện và Background Worker I/O),
  truyền thông điệp an toàn luồng (Signals/Queues), hiển thị tiến trình thời gian thực (MB/s, ETA, Progress),
  chuẩn 4 trạng thái UI, và tích hợp chạy ngầm trên System Tray.
---

# Python GUI Architecture Skill (Kiến Trúc Giao Diện Python Đa Luồng Mượt Mà)

Bộ kỹ năng này hướng dẫn xây dựng giao diện người dùng (Desktop GUI) cho ứng dụng sao lưu dữ liệu bằng Python, đảm bảo giao diện luôn phản hồi tức thì ở mức 60 FPS ngay cả khi đang quét và sao chép hàng trăm nghìn tệp tin lên NAS.

---

## 1. Nguyên Tắc Sắt Đá: Non-Blocking Main Thread

Lỗi phổ biến nhất của ứng dụng Desktop Python là chạy vòng lặp copy tệp hoặc kết nối mạng ngay trên Main Thread khiến cửa sổ bị đơ trắng (`"Not Responding"`).
- **Quy tắc Bắt buộc**:
  1. **Main Thread (UI Thread)** chỉ làm nhiệm vụ vẽ giao diện, nhận thao tác chuột/bàn phím và cập nhật trạng thái từ sự kiện gửi về.
  2. Mọi thao tác quét thư mục (`os.scandir`), tính mã băm, nén, mã hóa, kiểm tra kết nối NAS (`ping`/SMB/SFTP) và truyền tệp **BẮT BUỘC** thực thi trong **Background Worker** (`QThread`/`QRunnable` với Qt Signals, hoặc `threading.Thread`/`concurrent.futures` kết hợp `queue.Queue` / `asyncio`).
  3. **Điều khiển Vòng đời Tiến trình (Pause / Resume / Cancel)**:
     - Mỗi Worker phải kiểm tra cờ trạng thái `threading.Event` (`_pause_event`, `_cancel_event`) giữa từng chunk dữ liệu (mỗi 1–4 MB) để khi người dùng bấm **Tạm dừng** hoặc **Hủy**, ứng dụng phản hồi ngay trong vòng < 200ms và dọn dẹp sạch tệp `.part` đang ghi dở.

---

## 2. Telemetry Thời Gian Thực & Chống Ngập Sự Kiện (UI Throttling)

Khi sao lưu hàng nghìn tệp nhỏ (1 KB – 10 KB), nếu bắn sự kiện cập nhật UI sau mỗi tệp sẽ làm nghẽn hàng đợi sự kiện (Event Loop Flood).
- **Throttled Progress Updates**:
  - Chỉ phát sự kiện cập nhật thanh tiến trình (Progress Bar), tốc độ truyền (`MB/s`), thời gian ước tính còn lại (`ETA`) và tên tệp hiện tại ở tần suất tối đa **10–15 lần/giây** (mỗi `66ms – 100ms`).
- **Thuật toán tính tốc độ mượt mà (Exponential Moving Average - EMA)**:
  - Sử dụng trung bình trượt hàm mũ (EMA) hoặc cửa sổ trượt 3–5 giây gần nhất để hiển thị tốc độ `MB/s` và `ETA` ổn định, tránh nhảy số loạn xạ.

---

## 3. Chuẩn Mực 4 Trạng Thái Giao Diện (4 Mandatory UI States)

Mọi màn hình và khu vực dữ liệu trong ứng dụng phải thiết kế trọn vẹn 4 trạng thái:
1. **Idle / Empty State**: Khi chưa tạo Job sao lưu nào hoặc chưa có lịch sử chạy — hiển thị hướng dẫn trực quan và nút hành động chính *"Tạo tác vụ sao lưu đầu tiên"*.
2. **Scanning / Connecting State**: Khi đang kiểm tra kết nối NAS hoặc tính toán tổng dung lượng tệp nguồn — hiển thị trạng thái đang quét kèm bộ đếm số tệp tìm thấy.
3. **Active / Running State**: Hiển thị thanh tiến độ tổng thể, thanh tiến độ tệp hiện tại, tốc độ `MB/s`, `ETA`, số tệp `Đã xong / Tổng số`, cùng 3 nút điều khiển rõ ràng: **Tạm dừng (Pause)**, **Tiếp tục (Resume)**, **Hủy an toàn (Cancel)**.
4. **Completed / Error State**:
   - *Thành công*: Hiển thị huy hiệu xanh, tổng dung lượng đã sao lưu, thời gian thực hiện và mã kiểm tra toàn vẹn.
   - *Lỗi*: Hiển thị thông báo tiếng Việt rõ nguyên nhân (VD: *"Không kết nối được NAS tại 192.168.1.100"*, *"Ổ đĩa NAS không đủ dung lượng trống"*), kèm nút **Thử lại (Retry)** và **Xem chi tiết nhật ký (View Error Log)**.

---

## 4. Tích Hợp Khay Hệ Thống (System Tray & Background Lifecycle)

- Cho phép thu nhỏ ứng dụng xuống khay hệ thống Windows (**Minimize to System Tray**) để chạy ngầm theo lịch trình mà không chiếm chỗ trên thanh Taskbar.
- Biểu tượng System Tray đổi trạng thái trực quan (Bình thường / Đang chạy sao lưu / Cảnh báo lỗi) kèm menu chuột phải nhanh: *"Mở bảng điều khiển"*, *"Chạy sao lưu ngay"*, *"Tạm dừng tất cả"*, *"Thoát"*.
