# Architecture, Code Call Graph & Data Flow

## 1. Sơ Đồ Kiến Trúc & Phụ Thuộc Mô-đun Hiện Tại (Current Codebase Call Graph)

```mermaid
flowchart TD
    subgraph ENTRY ["Entry Point"]
        MAIN["main.py\nmain()"]
    end

    subgraph UI ["Presentation Layer (Tkinter UI)"]
        MW["app/main_window.py\nMainWindow(tk.Tk)"]
        PD["app/preview_dialog.py\nPreviewDialog(tk.Toplevel)"]
    end

    subgraph CORE ["Domain & Service Layer"]
        PL["app/planner.py\nbuild_plans()\nresolve_attach_dir()\nMailPlan, Attachment"]
        TP["app/templating.py\nrender()\nunknown_variables()"]
        ML["app/mailer.py\nGmailSession\nbuild_message()\nsend_plans()\ntest_connection()"]
    end

    subgraph DATA ["Data & Persistence Layer"]
        CF["app/config.py\nload_config()\ncreate_default_config()\nensure_config_file()\nConfig, Settings, Supplier"]
        HS["app/history.py\nrecord()\nsent_suppliers()"]
    end

    subgraph EXT ["External / Storage"]
        XLSX[("Cau_hinh.xlsx\n(4 Sheets)")]
        CSV[("Lich_su_gui.csv")]
        FS[("Dinh_kem/{nam}-{thang}/\n(*.xlsx, *.pdf)")]
        SMTP(("Gmail SMTP SSL\nsmtp.gmail.com:465"))
    end

    MAIN -->|"sys.path.insert('vendor')"| MW
    MW -->|"_check_first_run() / _load_config()"| CF
    MW -->|"_on_preview()"| PL
    MW -->|"_on_preview()"| HS
    MW -->|"wait_window()"| PD
    MW -->|"_test_worker() / _send_worker()\n(Background Thread + queue.Queue)"| ML
    MW -->|"_handle_result()"| HS
    PD -->|"Reads MailPlan & Settings"| PL
    PL -->|"render(), unknown_variables()"| TP
    PL -->|"is_valid_email()"| CF
    PL -->|"path.is_file()"| FS
    CF -->|"unknown_variables"| TP
    CF <-->|"openpyxl"| XLSX
    HS <-->|"csv.writer / DictReader"| CSV
    ML -->|"read_bytes()"| FS
    ML <-->|"smtplib.SMTP_SSL"| SMTP
```

---

## 2. Clean Architecture Layers (Kiến Trúc Mục Tiêu v1.1.0 & v1.2.0)

- **Domain Layer**: `MailPlan`, `Attachment`, `Settings`, `Supplier`, `SendResult` (Dataclasses thuần túy, bất biến, độc lập 100% khỏi framework I/O hay GUI).
- **Service Layer**:
  - `planner.py`: Tính toán kế hoạch gửi, kiểm tra tồn tại file, kiểm tra file rỗng `0 byte`, kiểm tra giới hạn dung lượng `< 18.5MB` (trước Base64), phát hiện trùng mã NCC và ký tự đường dẫn bất hợp pháp.
  - `templating.py`: Xử lý nội suy biến an toàn, phát hiện biến lạ.
  - `mailer.py`: Quản lý phiên kết nối `GmailSession`, kiểm tra từ điển địa chỉ bị từ chối trả về từ `send_message()` (chống lỗi Silent Partial Delivery), thực thi **Smart Pacing (1.5 - 3.0s)**, **Exponential Backoff Retry**, và lắng nghe cờ `pause_event` / `cancel_event`.
  - `updater.py`: Kiểm tra phiên bản mới qua GitHub Releases API, tải gói cập nhật với xác thực mã băm SHA-256 và bàn giao cho tiến trình `updater.exe`.
- **Adapter Layer**:
  - `config.py`: Adapter đọc/ghi file Excel thông qua `openpyxl` (đảm bảo đóng `wb.close()`, bắt lỗi file hỏng `BadZipFile`, tự động migrate cấu trúc sheet khi cập nhật OTA).
  - `security.py`: Adapter lưu trữ Mật khẩu ứng dụng Gmail qua **Windows Credential Manager (`keyring`)** / mã hóa AES-256-GCM và xóa plaintext trong Excel.
  - `history.py`: Adapter lưu trữ lịch sử qua **SQLite (`history.db`)** nguyên tử và tự động xuất CSV/Excel chống lỗi Excel cắt số `0` ở cột Tháng và chống CSV Injection.
- **Presentation Layer**:
  - `main_window.py`: Cửa sổ Tkinter bật High-DPI Awareness, điều khiển luồng nền (Pause / Resume / Cancel), bắt sự kiện đóng cửa sổ an toàn (`WM_DELETE_WINDOW`) và nhận telemetry qua `queue.Queue`.
  - `preview_dialog.py`: Hộp thoại xem trước hỗ trợ chọn/bỏ chọn nhanh từng nhà cung cấp trước khi gửi.

---

## 3. Luồng Dữ Liệu Chi Tiết (Data Flow)

```mermaid
sequenceDiagram
    autonumber
    actor User as Người dùng
    participant GUI as Tkinter Main Window
    participant Plan as Planner & Config
    participant Prev as Preview Dialog
    participant Worker as Background Worker
    participant SMTP as Gmail SMTP SSL
    participant DB as SQLite history.db

    User->>GUI: Chọn Kỳ gửi (Tháng, Năm, Loại) -> Bấm Xem trước & Gửi
    GUI->>Plan: Đọc Cau_hinh.xlsx (+ Keyring) & quét thư mục Dinh_kem/
    Plan-->>GUI: Danh sách MailPlan (Kiểm tra Email, Tồn tại, >0B, <18.5MB, Không trùng)
    GUI->>Prev: Mở PreviewDialog hiển thị chi tiết từng NCC & lịch sử từ SQLite
    User->>Prev: Tick chọn NCC / Bỏ qua nhà đã gửi -> Bấm Xác nhận & Gửi
    Prev-->>GUI: Danh sách MailPlan cần gửi
    GUI->>Worker: Kích hoạt Background Thread (kèm pause_event, cancel_event)
    loop Từng MailPlan (Pacing 1.5 - 3.0s)
        Worker->>Worker: Kiểm tra cancel_event / pause_event
        Worker->>SMTP: Kết nối & gửi EmailMessage (SSL 465 + Exponential Backoff)
        SMTP-->>Worker: 250 OK + Kiểm tra dict refused_recipients == {}
        Worker->>DB: Ghi log giao dịch vào SQLite history.db (& đồng bộ CSV)
        Worker->>GUI: Bắn event kết quả & ETA qua queue.Queue
        GUI->>GUI: Cập nhật Progress Bar, Telemetry & Log cửa sổ
    end
    Worker->>GUI: Thông báo hoàn tất đợt gửi
    GUI-->>User: Hiển thị tổng kết kết quả
```
