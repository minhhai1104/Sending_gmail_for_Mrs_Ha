# Architecture Contract — Gmail Auto Mailer (`v1.1.0`)

> **Trạng thái**: Khóa hợp đồng (Locked Contract for Sprint v1.1.0)  
> **Quản trị bởi**: `pm-agent` • `be-agent` • `fe-agent` • `qa-agent`

---

## 1. Hợp Đồng Mô-đun Bảo Mật Thông Tin Đăng Nhập (`app/security.py`)

### Mục tiêu
Bảo vệ Mật khẩu ứng dụng Gmail (16 ký tự) theo cơ chế **Hybrid Zero-Plaintext**:
1. Cho phép người dùng nhập mật khẩu từ file Excel `Cau_hinh.xlsx` (ô `B6` sheet `Gmail`) hoặc từ giao diện GUI.
2. Khi phát hiện mật khẩu thực trong `Cau_hinh.xlsx` (khác giá trị placeholder `******** (Đã lưu an toàn trên máy)`), hệ thống tự động:
   - Lưu mật khẩu vào **Windows Credential Manager (`keyring`)** (hoặc fallback sang **Windows DPAPI / Local Encrypted Vault** nếu môi trường chưa cài `keyring`).
   - Thay thế ô mật khẩu trong `Cau_hinh.xlsx` bằng chuỗi đánh dấu `SAVED_PLACEHOLDER = "******** (Đã lưu an toàn trên máy)"` (nếu file không bị khóa ghi) để khi người dùng chia sẻ file Excel sẽ không bị lộ mật khẩu.
3. Khi đọc cấu hình, nếu ô mật khẩu trong Excel là `SAVED_PLACEHOLDER` hoặc trống, hệ thống tự động nạp mật khẩu đã lưu từ kho bảo mật theo địa chỉ `sender`.

### Giao diện hàm (Public API)
- `SAVED_PLACEHOLDER: str = "******** (Đã lưu an toàn trên máy)"`
- `normalize_app_password(raw: str) -> str`: Xóa mọi khoảng trắng trong chuỗi mật khẩu.
- `is_valid_app_password(password: str) -> bool`: Kiểm tra mật khẩu ứng dụng hợp lệ (đúng 16 ký tự chữ/số không dấu).
- `save_password(sender: str, password: str, vault_path: Optional[Path] = None) -> bool`: Lưu mật khẩu an toàn cho `sender`.
- `load_password(sender: str, vault_path: Optional[Path] = None) -> str`: Đọc mật khẩu đã lưu của `sender` (trả về `""` nếu chưa có).
- `resolve_and_protect_password(sender: str, raw_cell_value: str, excel_path: Optional[Path] = None, vault_path: Optional[Path] = None, mask_excel: bool = True) -> str`: Giải quyết mật khẩu từ ô Excel + kho bảo mật, tự động cất vào kho và che mật khẩu trong file Excel nếu có thể.

---

## 2. Hợp Đồng Mô-đun Cấu Hình & Auto-Migration (`app/config.py`)

### Invariants & Cải tiến Lượt 2
1. **Đóng Workbook an toàn**: Luôn đóng `wb.close()` trong khối `try...finally`.
2. **Bắt lỗi file Excel hỏng**: Bắt `zipfile.BadZipFile`, `InvalidFileException`, `KeyError`, `ValueError` và chuyển thành `ConfigError` tiếng Việt rõ ràng.
3. **Auto-Migration không mất dữ liệu (`migrate_config_if_needed`)**: Tự động kiểm tra và bổ sung các dòng cấu hình mới nếu file `Cau_hinh.xlsx` từ phiên bản cũ thiếu nhãn mới, giữ nguyên 100% dữ liệu nhà cung cấp của người dùng.
4. **Kiểm tra `Settings.problems()`**:
   - Kiểm tra `sender` đúng định dạng email.
   - Kiểm tra `app_password` không trống và đúng chuẩn 16 ký tự của Gmail App Password (cảnh báo rõ nếu người dùng nhập sai độ dài hoặc điền mật khẩu thường).
   - Kiểm tra danh sách `cc` hợp lệ.

---

## 3. Hợp Đồng Mô-đun Lập Kế Hoạch (`app/planner.py`)

### Invariants & Cải tiến Lượt 2
1. **Kiểm tra Tên Nhà cung cấp (`_supplier_errors`)**:
   - Phát hiện trùng lặp tên nhà cung cấp (không phân biệt hoa/thường sau khi `strip()`) trong danh sách và báo lỗi rõ: `"Tên nhà cung cấp bị trùng lặp trong danh sách: {name}"`.
   - Chặn các ký tự đường dẫn không hợp lệ trong tên nhà cung cấp (`/`, `\`, `:`, `*`, `?`, `"`, `<`, `>`, `|`) để chống lỗi biến tên NCC thành thư mục con (Path Traversal).
2. **Kiểm tra File Đính Kèm (`Attachment` & `build_plans`)**:
   - Kiểm tra tồn tại file (`path.is_file()`).
   - Kiểm tra file rỗng `0 byte` (`size_bytes == 0` -> báo lỗi `"File đính kèm bị rỗng (0 KB): {path.name}"`).
   - Kiểm tra tổng dung lượng đính kèm của một mail không vượt quá `MAX_TOTAL_ATTACHMENT_BYTES = 18 * 1024 * 1024` (~18 MB raw $\approx$ 24 MB MIME sau Base64, an toàn dưới ngưỡng 25 MB của Gmail).

---

## 4. Hợp Đồng Mô-đun Lịch Sử SQLite & Xuất CSV (`app/history.py`)

### Invariants & Cải tiến Lượt 2
1. **Single Source of Truth bằng SQLite (`history.db`)**:
   - Bảng `send_history`:
     ```sql
     CREATE TABLE IF NOT EXISTS send_history (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         sent_at TEXT NOT NULL,
         month INTEGER NOT NULL,
         year INTEGER NOT NULL,
         kind TEXT NOT NULL,
         supplier TEXT NOT NULL,
         recipients TEXT NOT NULL,
         subject TEXT NOT NULL,
         attachments TEXT NOT NULL,
         status TEXT NOT NULL,
         detail TEXT NOT NULL
     );
     CREATE INDEX IF NOT EXISTS idx_history_period ON send_history(year, month, kind, status);
     ```
   - Không bao giờ bị lỗi khóa file khi người dùng đang mở `Lich_su_gui.csv` bằng Microsoft Excel.
2. **Tương thích ngược & Tự động đồng bộ với `Lich_su_gui.csv`**:
   - Nếu có dữ liệu cũ trong `Lich_su_gui.csv`, tự động nạp (import) vào SQLite và chuẩn hóa cột `Tháng` bằng `int(row["Tháng"])` (xử lý triệt để lỗi Excel cắt số `0` biến `"09"` thành `"9"`!).
   - Khi `record()` ghi vào SQLite thành công, hàm luôn trả về `True` (đảm bảo lịch sử đã lưu an toàn 100%), đồng thời cố gắng xuất đồng bộ ra `Lich_su_gui.csv` (nếu CSV đang mở trong Excel thì không làm mất dữ liệu vì đã có trong SQLite, và lần bấm `"Xem lịch sử gửi"` sẽ tự xuất lại từ SQLite).
   - Chống **CSV Formula Injection (`CWE-1236`)**: Làm sạch các giá trị văn bản bắt đầu bằng `=`, `+`, `-`, `@` khi ghi ra CSV để Excel không hiểu nhầm là công thức lỗi `#NAME?`.

---

## 5. Hợp Đồng Mô-đun Lõi Gửi Mail SMTP (`app/mailer.py`)

### Invariants & Cải tiến Lượt 2
1. **Tách lỗi Đọc File Đính Kèm khỏi lỗi Kết nối Mạng**:
   - Đọc nội dung file đính kèm trong `build_message()` nếu gặp `FileNotFoundError` hoặc `PermissionError` sẽ quăng `MailError("Không đọc được file đính kèm '...' (file đang mở hoặc đã bị xóa).")` thay vì báo nhầm là mất mạng Internet.
2. **Đóng Socket SSL an toàn khi Login thất bại**:
   - Trong `GmailSession._connect()`, nếu `server.login()` quăng lỗi, bắt buộc đóng `server.close()` trước khi raise `MailError`.
3. **Kiểm tra Partial Delivery (`refused_recipients`)**:
   - Kiểm tra từ điển trả về của `refused = self._server.send_message(msg)`.
   - Nếu `refused` không rỗng (có ít nhất 1 người nhận hoặc CC bị từ chối), đánh dấu `SendResult(ok=False, message="Gmail từ chối một số địa chỉ nhận: ...")` để tuyệt đối không báo thành công giả!
4. **Sửa lỗi Văng Vòng Lặp Khi Reconnect Thất Bại & Exponential Backoff Retry**:
   - Trong `send_plans()`, bắt cả `(MailError, smtplib.SMTPException, OSError)` cho từng `plan` để lỗi ở một nhà cung cấp (kể cả khi mất mạng reconnect thất bại) không bao giờ làm văng vòng lặp các nhà cung cấp tiếp theo.
   - Hỗ trợ thử lại tối đa `max_retries` với Exponential Backoff khi gặp lỗi kết nối mạng tạm thời.
5. **Smart Pacing & Điều khiển Luồng (Pause / Resume / Cancel)**:
   - Giãn cách thông minh `pacing_delay: float` (mặc định `1.5` giây trong vận hành thật, `0.0` giây trong unit test) giữa các mail.
   - Hỗ trợ `pause_event: Optional[threading.Event]` và `cancel_event: Optional[threading.Event]` để tạm dừng hoặc hủy đợt gửi ngay lập tức.

---

## 6. Hợp Đồng Giao Diện Tkinter & Xem Trước (`app/main_window.py`, `app/preview_dialog.py`)

### Invariants & Cải tiến Lượt 2
1. **High-DPI Awareness**: Kích hoạt `SetProcessDpiAwareness` trên Windows để giao diện sắc nét trên màn hình Full HD / 2K / 4K.
2. **Design System (`DESIGN.md`)**: Bảng màu Modern Enterprise Precision, hỗ trợ chuyển đổi giao diện Sáng / Tối (Light / Dark Mode).
3. **Telemetry & Bộ Điều Khiển Luồng Trực Tiếp**:
   - Hiển thị nhãn phần trăm tiến độ (`65% - 13/20 mail`), tốc độ gửi và ước tính thời gian còn lại (ETA).
   - Nút **Tạm dừng (Pause) / Tiếp tục (Resume)** và **Hủy gửi (Cancel)** hoạt động tức thì khi đang gửi.
4. **Bảo vệ Đóng Cửa Sổ (`WM_DELETE_WINDOW`)**:
   - Khi đang gửi mail (`self._busy == True`), nếu người dùng bấm nút `X` đóng cửa sổ, hiển thị hộp thoại xác nhận; nếu đồng ý thoát thì kích hoạt `cancel_event` để đóng kết nối SMTP an toàn.
5. **Tick Chọn/Bỏ Chọn Lẻ Từng Nhà Cung Cấp Trên `PreviewDialog`**:
   - Người dùng có thể nhấp đúp hoặc bấm nút Chọn/Bỏ chọn trực tiếp từng nhà cung cấp trên bảng Xem trước mà không cần quay ra sửa file Excel.


---

## 7. Hợp Đồng Mô-đun Cập Nhật Tự Động OTA 2 Tiến Trình (`app/updater.py` & `updater_runner.py` — `v1.2.0`)

### Mục tiêu
Cập nhật ứng dụng Over-The-Air (OTA) từ **GitHub Releases** trên Windows mà không bao giờ gặp lỗi khóa file thực thi (`WinError 5 / WinError 32`), đảm bảo **Zero Broken Installations** và **100% Bảo toàn dữ liệu người dùng**.

### Hằng số & Danh sách Bất khả xâm phạm
- `GITHUB_REPO = "minhhai1104/Sending_gmail_for_Mrs_Ha"`
- `PROTECTED_USER_ITEMS: frozenset[str] = frozenset({"Cau_hinh.xlsx", "history.db", "history.db-journal", "history.db-wal", "history.db-shm", "Lich_su_gui.csv", ".credentials.dat", "Dinh_kem"})`

### Giao diện hàm (Public API của `app/updater.py`)
1. `parse_version(version_str: str) -> tuple[int, ...]`: Chuẩn hóa chuỗi phiên bản (`"v1.2.0"` $\rightarrow$ `(1, 2, 0)`).
2. `is_newer_version(remote_ver: str, local_ver: str) -> bool`: So sánh phiên bản ngữ nghĩa (Semantic Versioning).
3. `ReleaseInfo` (dataclass): `version: str`, `download_url: str`, `sha256: str`, `release_notes: str`, `asset_name: str`.
4. `check_for_update(current_version: str, repo: str = GITHUB_REPO, api_url: Optional[str] = None, timeout: float = 5.0) -> Optional[ReleaseInfo]`:
   - Truy vấn GitHub Releases API (`releases/latest`).
   - Hỗ trợ đọc mã băm SHA-256 từ nội dung Release Notes (`SHA256: <64-hex>`) hoặc từ tệp đính kèm `version.json`.
   - Trả về `ReleaseInfo` nếu có bản mới hơn `current_version`, ngược lại trả về `None`.
5. `compute_sha256(file_path: Path) -> str` & `verify_sha256(file_path: Path, expected_sha256: str) -> bool`:
   - Kiểm tra toàn vẹn gói tải về bằng thuật toán băm SHA-256 theo từng chunk 64KB.
6. `download_release_asset(release: ReleaseInfo, dest_dir: Path, on_progress: Optional[Callable[[int, int], None]] = None, timeout: float = 30.0) -> Path`:
   - Bắt buộc giao thức `https://`.
   - Tải gói cập nhật về thư mục tạm, kiểm tra cổng `Integrity Gate` (khớp mã băm SHA-256). Nếu lệch mã băm, lập tức xóa file tạm và quăng `UpdateError`.
7. `safe_extract_zip(zip_path: Path, staging_dir: Path) -> list[Path]`:
   - Giải nén gói cập nhật vào thư mục staging.
   - Chặn tuyệt đối lỗ hổng **Zip Slip (Path Traversal)** (mọi đường dẫn chứa `../` thoát khỏi `staging_dir` đều bị từ chối và quăng `UpdateError`).
   - Bỏ qua mọi tệp trùng tên với `PROTECTED_USER_ITEMS`.
8. `apply_staged_update(staging_dir: Path, target_dir: Path) -> list[Path]`:
   - Sao lưu tệp hiện tại sang `.bak` trước khi ghi đè tệp mới từ `staging_dir` vào `target_dir`.
   - Tuyệt đối không đụng chạm tới bất kỳ tệp/thư mục nào trong `PROTECTED_USER_ITEMS`.
   - **Rollback tự động**: Nếu quá trình ghi đè bất kỳ tệp nào gặp lỗi giữa chừng, tự động khôi phục toàn bộ tệp `.bak` về trạng thái ban đầu.
9. `spawn_standalone_updater(package_path: Path, target_dir: Path, current_pid: Optional[int] = None, relaunch_exe: Optional[Path] = None) -> Any`:
   - Khởi chạy tiến trình thứ 2 độc lập (`updater.exe` hoặc `python updater_runner.py`) để thực hiện hoán đổi binary sau khi tiến trình chính thoát.


---

## 8. Hợp Đồng Nâng Cấp Phiên Bản `v2.0.0` (HTML Email Template, Inline Logo CID, Excel History Report & Telemetry)

### 8.1. Mẫu Email HTML Doanh Nghiệp & Nhúng Logo Inline CID (`app/mailer.py`, `app/config.py`)
1. **Nhãn cấu hình tùy chọn mới trong Sheet `Gmail`**:
   - `LBL_LOGO = "Logo chữ ký (không bắt buộc)"` (mặc định `""`, người dùng có thể điền đường dẫn tương đối như `logo.png` hoặc đường dẫn tuyệt đối tới ảnh `.png`/`.jpg`).
   - Trường `Settings.logo_path: str = ""` (tự động migrate bổ sung vào `Cau_hinh.xlsx` cũ thông qua `migrate_config_if_needed()`).
2. **Hàm dựng nội dung HTML chuẩn doanh nghiệp**:
   - `build_html_body(body_text: str, logo_cid: Optional[str] = None) -> str`:
     - Chuyển đổi văn bản thuần sang HTML định dạng `Segoe UI, Arial, sans-serif` (cỡ chữ `14px`, màu `#201F1E`, khoảng cách dòng `1.6`).
     - Tự động nhận diện khối chữ ký bên dưới dòng phân cách (`---` hoặc `___`) để định dạng chữ ký doanh nghiệp trang trọng; nếu có `logo_cid`, chèn thẻ `<img src="cid:{logo_cid}" ...>` ngay dưới chữ ký.
     - Nếu `body_text` đã chứa thẻ HTML (`<html>`, `<p>`, `<br>`, `<div>`, `<table>`), bảo toàn cấu trúc HTML của người dùng và bổ sung ảnh logo nếu có.
3. **Thông điệp MIME Multipart (`build_message`)**:
   - Luôn gửi đồng thời cả `text/plain` (fallback tương thích 100%) và `text/html` (`msg.add_alternative(..., subtype="html")`).
   - Nếu `settings.logo_path` được cấu hình và tệp ảnh tồn tại, nhúng ảnh vào phần HTML qua `Content-ID` (Inline CID) để hiển thị trực tiếp trong chữ ký mà không làm lẫn với danh sách file Excel/PDF đính kèm.

### 8.2. Xuất Báo Cáo Lịch Sử Ra File Excel Định Dạng Đẹp (`Lich_su_gui.xlsx` — `app/history.py`)
1. `EXCEL_HISTORY_PATH = APP_DIR / "Lich_su_gui.xlsx"`
2. `export_sqlite_to_excel(excel_path: Path = EXCEL_HISTORY_PATH, db_path: Path = DB_PATH) -> bool`:
   - Kết xuất toàn bộ lịch sử từ SQLite `history.db` ra file Excel `.xlsx` thông qua `openpyxl`.
   - Định dạng bảng chuyên nghiệp:
     - Dòng tiêu đề nền xanh đậm `#1F4E78`, chữ trắng in đậm, cố định tiêu đề (`freeze_panes = "A2"`).
     - Cột `Tháng` lưu chuỗi `"09"` với `number_format = "@"` (Text) để Microsoft Excel không bao giờ cắt mất số `0` ở đầu.
     - Tô màu nền xanh nhạt (`#E2EFDA`) cho dòng `"Thành công"` và cam/đỏ nhạt (`#FCE4D6`) cho dòng `"Lỗi"`.
     - Chống Formula Injection (`_sanitize_csv_field`).

### 8.3. Telemetry Tốc Độ Gửi (`mail/phút`) & Bộ Lọc Nhanh Trên `PreviewDialog`
1. `MainWindow` tính toán và hiển thị tốc độ gửi thực tế theo đơn vị `mail/phút` bên cạnh phần trăm tiến độ và đồng hồ đếm ngược `ETA`.
2. `PreviewDialog` hiển thị thanh tóm tắt số lượng theo từng trạng thái (`Sẵn sàng`, `Đã gửi rồi`, `Lỗi`, `Không gửi`) và ô tìm kiếm/lọc nhanh theo tên nhà cung cấp.
