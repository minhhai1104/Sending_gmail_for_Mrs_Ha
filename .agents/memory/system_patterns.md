# System Patterns & Engineering Patterns

## 1. Architectural Patterns
- **Separation of Concerns (SoC)**: Tách bạch rõ rệt giữa Tầng Dữ liệu cấu hình (`config.py`), Tầng Kế hoạch gửi (`planner.py`), Tầng Dựng nội dung (`templating.py`), Tầng Lõi SMTP (`mailer.py`), Tầng Lưu trữ lịch sử (`history.py`), và Tầng Giao diện (`main_window.py`, `preview_dialog.py`).
- **Adapter Pattern**: Tách adapter kết nối SMTP và adapter lưu trữ SQLite ra khỏi nghiệp vụ gửi thư.
- **Worker-Thread Pattern**: Toàn bộ thao tác I/O chạy trên luồng nền `threading.Thread`, cập nhật tiến trình và log về Main Thread qua hàng đợi `queue.Queue`.
- **Producer-Consumer Telemetry**: Worker phát sinh các event `("log", ...)`, `("result", ...)`, `("finished", ...)`; Main Window tiêu thụ qua polling timer `after(100, poll)`.

## 2. Security Patterns
- **Least Privilege & Zero-Plaintext**: Mật khẩu ứng dụng Gmail được cách ly trong Windows Credential Manager (`keyring`).
- **Fail-Safe Attachment Verification**: Kiểm tra sự tồn tại thực tế của file trên đĩa cứng trước khi cho phép kích hoạt nút gửi; nếu thiếu file, đánh dấu lỗi đỏ và cấm gửi.

## 3. Resilience & Concurrency Patterns
- **Atomic Operations**: Ghi nhận lịch sử gửi vào SQLite với transaction nguyên tử (`BEGIN IMMEDIATE... COMMIT`).
- **Exponential Backoff**: Tự động thử lại khi gặp lỗi mạng tạm thời với thời gian chờ tăng theo hàm mũ (1s -> 2s -> 4s).
- **Graceful Cancellation**: Sử dụng `threading.Event` để báo hiệu dừng/hủy tiến trình gửi mà không làm rò rỉ socket hoặc corrupt dữ liệu.
