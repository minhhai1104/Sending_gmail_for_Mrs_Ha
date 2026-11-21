# Technical Concerns, Logic Bugs & Security Vulnerabilities (Forensic Pass 2)

Tài liệu này ghi nhận toàn bộ các quan ngại kỹ thuật, lỗi logic ngầm, rủi ro bảo mật và nợ kỹ thuật phát hiện qua 2 lượt rà soát toàn diện (Pass 1 & Deep Forensic Pass 2):

---

## 🔴 Nhóm 1: Lỗi Logic Nghiêm Trọng & Nguy Cơ Mất/Sai Lệch Dữ Liệu (Critical / P0)

1. **Lỗ hổng Lộ Mật Khẩu Gmail Plaintext (CWE-256) — `app/config.py:154, 277`**:
   - `Cau_hinh.xlsx` lưu Mật khẩu ứng dụng Gmail (16 ký tự) dạng văn bản thô tại ô `B6` sheet `Gmail`.
   - Rủi ro: Người dùng văn phòng gửi file `Cau_hinh.xlsx` qua Zalo/Email hoặc lưu trên thư mục chia sẻ sẽ làm lộ hoàn toàn quyền truy cập Gmail của công ty.

2. **Lỗi Báo Thành Công Giả Khi Một Số Người Nhận Bị Từ Chối (Silent Partial Delivery Bug) — `app/mailer.py:93, 112`**:
   - Hàm `smtplib.SMTP.send_message(msg)` chỉ quăng ngoại lệ `SMTPRecipientsRefused` khi **tất cả** người nhận đều bị từ chối.
   - Nếu một nhà cung cấp có nhiều email nhận (hoặc có CC) mà 1 địa chỉ thành công, 1 địa chỉ bị từ chối, `send_message()` **không quăng lỗi** mà trả về `dict` chứa các địa chỉ bị từ chối.
   - Hiện tại `session.send(plan)` bỏ qua giá trị trả về này, dẫn đến ứng dụng báo `"✔ Đã gửi"` và ghi lịch sử `"Thành công"` dù có người nhận hoặc sếp (CC) không nhận được mail!

3. **Lỗi Mất Hiệu Lực Lịch Sử Khi Mở CSV Bằng Microsoft Excel (Excel Leading-Zero Strip Bug) — `app/history.py:19, 42`**:
   - Khi ghi lịch sử vào `Lich_su_gui.csv`, cột `Tháng` được ghi dạng chuỗi 2 chữ số (`"09"`).
   - Khi người dùng bấm nút `"Xem lịch sử gửi"`, Microsoft Excel mở file CSV và tự động ép kiểu `"09"` thành số `9`. Nếu người dùng bấm Lưu (`Ctrl+S`) trong Excel, file CSV sẽ lưu thành `9`.
   - Lần gửi tiếp theo, `sent_suppliers()` so sánh `row["Tháng"] == f"{month:02d}"` (`"9" == "09"` -> `False`), làm **mất toàn bộ trạng thái đã gửi của các tháng 01 đến 09**, dẫn đến gửi trùng lặp hàng loạt!

4. **Lỗi Xung Đột Khóa File Khi Đang Mở Excel (File Lock Data Loss) — `app/history.py:25-31`**:
   - Nếu `Lich_su_gui.csv` đang được mở trong Excel trên Windows, lệnh `open(HISTORY_PATH, "a")` bị chặn bởi `PermissionError`. Hàm `record()` trả về `False` và dòng lịch sử gửi mail bị mất vĩnh viễn.

5. **Lỗi Dừng Toàn Bộ Đợt Gửi Khi Reconnect Thất Bại — `app/mailer.py:79, 94-96, 114`**:
   - Trong `GmailSession.send()`, khi bắt lỗi `SMTPServerDisconnected`, hàm gọi `self._connect()`.
   - Nếu lúc đó mạng chập chờn khiến `_connect()` thất bại, `_connect()` quăng ra `MailError` (kế thừa từ `Exception`).
   - Tuy nhiên, vòng lặp `send_plans()` ở dòng 114 chỉ bắt `except (smtplib.SMTPException, OSError):` mà **không bắt `MailError`**! Hậu quả: Toàn bộ đợt gửi bị văng lỗi dừng đột ngột, trái ngược với cam kết *"Lỗi ở một nhà cung cấp không làm dừng cả đợt"*.

---

## 🟠 Nhóm 2: Chẩn Đoán Sai Lỗi, Rò Rỉ Tài Nguyên & Thiếu Kiểm Tra Đầu Vào (High / P1)

6. **Chẩn Đoán Sai Lỗi Đọc File Đính Kèm Thành Lỗi Mất Mạng Internet — `app/mailer.py:37-38, 53, 114`**:
   - Trong `build_message()`, lệnh `attachment.path.read_bytes()` đọc file đính kèm ngay trong lúc gửi.
   - Nếu file đính kèm bị xóa hoặc bị khóa quyền đọc sau khi mở cửa sổ Xem trước, Python quăng `FileNotFoundError` hoặc `PermissionError` (đều là lớp con của `OSError`).
   - Hàm `friendly_error(exc)` kiểm tra `if isinstance(exc, OSError): return "Không kết nối được tới Gmail. Hãy kiểm tra Internet."` khiến người dùng nhận thông báo sai hoàn toàn bản chất lỗi!

7. **Rò Rỉ Kết Nối Socket SSL Khi Sai Mật Khẩu — `app/mailer.py:75-79`**:
   - Trong `_connect()`, sau khi `server = smtplib.SMTP_SSL(...)` mở kết nối thành công, nếu `server.login(...)` thất bại (sai mật khẩu), ngoại lệ được quăng ra mà không gọi `server.close()`, gây rò rỉ socket.

8. **Thiếu Kiểm Tra File Đính Kèm Rỗng (0 Byte), File Quá 25MB & Tên NCC Chứa Ký Tự Đường Dẫn — `app/planner.py:91-95` & `app/config.py:124`**:
   - `planner.py` chỉ kiểm tra `path.is_file()`, không kiểm tra file rỗng `0 byte` hoặc tổng dung lượng đính kèm vượt giới hạn `25MB` của Gmail (tương đương ~18.5MB file gốc trước khi mã hóa Base64).
   - Không kiểm tra trùng lặp tên Nhà cung cấp trong sheet `Nhà cung cấp` (nếu có 2 dòng trùng tên mã NCC sẽ gửi đúp 2 lần cùng 1 file).
   - Nếu tên NCC chứa ký tự `/` hoặc `\` (ví dụ `ACE/Vina`), phép ghép `attach_dir / render(...)` sẽ hiểu nhầm thành thư mục con thay vì tên file.

9. **Không Bắt Ngoại Lệ File Excel Hỏng & Không Đóng Workbook — `app/config.py:138-145`**:
   - `load_config()` không gọi `wb.close()` sau khi đọc xong và không bắt các lỗi `zipfile.BadZipFile`, `InvalidFileException` khi file Excel bị lỗi cấu trúc.

10. **Thiếu Pacing & Exponential Backoff Retry — `app/mailer.py:110`**:
    - Vòng lặp gửi liên tiếp không có khoảng nghỉ 1.5 - 3.0 giây, dễ bị máy chủ Gmail đánh dấu spam hoặc chặn tạm thời (`421 4.7.0`).

---

## 🟡 Nhóm 3: Vấn Đề Giao Diện, Luồng UI, Đóng Gói & Cập Nhật OTA (Medium / P1-P2)

11. **Đọc Excel, Quét File & Đọc CSV Chạy Trực Tiếp Trên Main UI Thread — `app/main_window.py:157-170`**:
    - Khi bấm `"XEM TRƯỚC & GỬI"`, toàn bộ việc đọc `Cau_hinh.xlsx`, quét ổ đĩa kiểm tra file đính kèm và đọc `Lich_su_gui.csv` đều chạy đồng bộ trên luồng giao diện chính. Nếu thư mục nằm trên ổ mạng LAN/NAS hoặc Google Drive ảo, ứng dụng sẽ bị đơ vài giây.

12. **Tắt Đột Ngột Khi Người Dùng Đóng Cửa Sổ Lúc Đang Gửi (`WM_DELETE_WINDOW`) — `app/main_window.py:23-41`**:
    - Chưa bắt sự kiện đóng cửa sổ `WM_DELETE_WINDOW`. Nếu người dùng bấm nút `X` khi luồng nền đang gửi mail, tiến trình bị giết ngang xương mà không có cảnh báo xác nhận hay đóng phiên SMTP an toàn.

13. **Thiếu Nút Điều Khiển Luồng (Pause/Resume/Cancel) & Chọn Lọc Từng NCC Trong Preview**:
    - Không thể tạm dừng hoặc hủy khi đang gửi; trong `PreviewDialog` chưa cho phép tick chọn/bỏ chọn nhanh từng nhà cung cấp mà phải quay ra sửa file Excel.

14. **Nhòe Chữ Trên Màn Hình Windows Độ Phân Giải Cao (High-DPI Blur) & Lỗi `os.startfile`**:
    - Chưa bật `SetProcessDpiAwareness` trên Windows; lệnh `os.startfile()` chưa bọc `try...except OSError`.

15. **Xung Đột `.gitignore` Với `*.spec` & Bảo Toàn Dữ Liệu Khi Update OTA**:
    - `.gitignore` dòng 15 đang chặn `*.spec`, ngăn việc quản lý file cấu hình PyInstaller trên Git.
    - Quá trình cập nhật OTA cần cơ chế bảo vệ không ghi đè `Cau_hinh.xlsx`, `history.db`, `Lich_su_gui.csv`, `Dinh_kem/` và tự động migrate cấu trúc `Cau_hinh.xlsx` khi nâng cấp phiên bản.
