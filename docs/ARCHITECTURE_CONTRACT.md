# Architecture Contract v3.0 — Gmail Auto Mailer ("Zero-Manual Enterprise")

> **Trạng thái**: Khóa hợp đồng triển khai `v3.0.0` (Locked Contract — Approved by Project Owner 21/11/2026)  
> **Quản trị bởi**: `pm-agent` • `designer-agent` • `be-agent` • `fe-agent` • `tester-agent` • `qa-agent` • `devops-agent`

---

## 1. Kiến Trúc Tổng Thể (Clean Architecture + Passive Web View)

Toàn bộ nghiệp vụ và trạng thái màn hình chạy bằng **Python thuần** tách biệt hoàn toàn với lớp giao diện **PyWebView (Microsoft Edge WebView2)** để `pytest` kiểm thử được >= 90% mã nguồn không cần mở cửa sổ GUI:

```text
app/
├── __init__.py                 # __version__ = "3.0.0"
├── domain/                     # Pure Python (0 I/O, 0 GUI, 0 framework)
│   ├── models.py               # AppConfig, GmailSettings, Supplier, MailTemplates, AttachmentMatch, MailPlan, BatchSummary, Enums
│   ├── templating.py           # Render {thang}/{nam}/{nha_cung_cap}/{loai}, Variable Chips, HTML sanitizer (nh3)
│   ├── matching.py             # Động cơ Khớp File 3 Tầng (Zero Wrong-Vendor Delivery — 100% branch coverage)
│   └── validation.py           # Kiểm tra email, trùng tên (NFC+strip+lower), trùng email chéo NCC, mật khẩu ứng dụng 16 ký tự
├── ports/                      # Typing Protocols cho Dependency Injection & Testability
│   └── protocols.py            # ConfigRepository, SecretStore, HistoryRepository, MailTransport, FileScanner, Clock
├── adapters/                   # Triển khai thực tế hạ tầng Windows & Mạng
│   ├── dpapi_vault.py          # Windows DPAPI thuần (ctypes CryptProtectData) tại %LOCALAPPDATA%\GmailAutoMailer\vault.dpapi
│   ├── sqlite_store.py         # SQLite WAL + schema_migrations (SSOT cho AppConfig & SendHistory + Export lịch sử .xlsx)
│   ├── smtp_mailer.py          # SMTP SSL (465) -> STARTTLS (587) fallback, Multipart HTML+Logo CID, Message-ID cố định, TOCTOU SHA-256
│   ├── fs_scanner.py           # Quét thư mục/file an toàn, tính SHA-256, lọc file rác hệ thống
│   └── ota_updater.py          # OTA 2 tiến trình cứng hóa (Mandatory SHA-256, GitHub HTTPS allowlist, Zip Slip, Rollback .bak)
├── application/                # Headless ViewModels / Services (100% testable không cần GUI)
│   ├── app_service.py          # Điều phối Onboarding, Settings CRUD, Suppliers CRUD, Templates + Live HTML Preview, History Query
│   ├── dispatch_service.py     # Lập kế hoạch gửi, Smart Auto-Match, Manual Override, Auto-Discovery, Test-to-Self, Filter-Safe Selection
│   └── batch_runner.py         # Worker Thread State Machine (IDLE/RUNNING/PAUSED/CANCELLED/DONE), Pause-aware Telemetry, Graceful Shutdown
├── ui/                         # Thin Shell PyWebView + Edge WebView2
│   ├── bridge.py               # Strict Whitelist JS-API Facade (Write-Only Secrets, không nhận đường dẫn file tự do)
│   ├── window.py               # Khởi tạo PyWebView, %LOCALAPPDATA% storage_path, Dark Titlebar, Drag & Drop, Event Bus 100ms
│   └── web/                    # Tài nguyên tĩnh 100% offline (Strict CSP, Zero CDN)
│       ├── index.html
│       ├── styles.css
│       └── app.js
└── main.py / updater_runner.py # Entry points (updater_runner.py thuần stdlib giảm 50% dung lượng)
```

---

## 2. Hợp Đồng Bảo Mật Thông Tin Đăng Nhập (`app/adapters/dpapi_vault.py` — Zero Plaintext Secrets)

1. **Tách rời hoàn toàn khỏi thư mục cài đặt App**:
   - Thư mục dữ liệu người dùng chuẩn Windows: `%LOCALAPPDATA%\GmailAutoMailer\` (tạo tự động).
   - File kho mật khẩu: `%LOCALAPPDATA%\GmailAutoMailer\vault.dpapi`.
   - File CSDL cấu hình & lịch sử: `%LOCALAPPDATA%\GmailAutoMailer\app_data.db` (tự động đọc kế thừa lịch sử cũ nếu thấy `history.db` cạnh thư mục cài đặt ở lần đầu nâng cấp từ v2.0).
2. **Mã hóa Windows DPAPI thuần (`CryptProtectData` / `CryptUnprotectData`)**:
   - Gắn trực tiếp với Master Key của tài khoản Windows hiện tại (`CRYPTPROTECT_UI_FORBIDDEN`), không cần cài `keyring`, không lưu key tĩnh trong source code.
   - Khi copy thư mục cài App sang máy khác / USB / Google Drive: **tuyệt đối không mang theo mật khẩu**.
   - Loại bỏ hoàn toàn `_PORTABLE_OTA_SECRET` và `_machine_secret()`.
3. **Write-Only Secret Contract**:
   - `bridge.py` **TUYỆT ĐỐI KHÔNG** có API nào trả về chuỗi mật khẩu ứng dụng hay GitHub Token sang phía JavaScript.
   - UI chỉ nhận cờ `has_app_password: bool` và `has_github_token: bool`.
   - Mọi thông báo lỗi, log sự kiện đều đi qua `redact_secrets(text, active_secrets)` trước khi gửi lên UI hoặc ghi vào `send_history`.

---

## 3. Hợp Đồng Cơ Sở Dữ Liệu SQLite SSOT (`app/adapters/sqlite_store.py`)

**100% Cấu hình trong App — Loại bỏ hoàn toàn `Cau_hinh.xlsx`:**
- Mọi kết nối SQLite bật bắt buộc:
  - `PRAGMA journal_mode=WAL;`
  - `PRAGMA busy_timeout=5000;`
  - `PRAGMA foreign_keys=ON;`
- Quản lý lược đồ qua bảng `schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)`.
- **Các bảng dữ liệu**:
  1. `app_settings(key TEXT PRIMARY KEY, value TEXT NOT NULL)`: lưu `sender`, `display_name`, `attach_dir`, `cc_json`, `logo_path`, `subject_tpl`, `body_tpl`, `excel_tpl`, `pdf_tpl`, `pacing_seconds`, `max_retries`, `theme`, `onboarding_completed`, `last_source_dir`. *(Tuyệt đối không lưu mật khẩu hay token vào bảng này!)*
  2. `suppliers(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, norm_name TEXT NOT NULL UNIQUE, recipients_json TEXT NOT NULL, aliases_json TEXT NOT NULL DEFAULT '[]', note TEXT NOT NULL DEFAULT '', enabled INTEGER NOT NULL DEFAULT 1, sort_order INTEGER NOT NULL DEFAULT 0)`
     - `norm_name = normalize_name(name)` dùng chung chuẩn `unicodedata.normalize("NFC", name).strip().lower()`.
  3. `send_history(id INTEGER PRIMARY KEY AUTOINCREMENT, batch_id TEXT NOT NULL DEFAULT '', sent_at TEXT NOT NULL, month INTEGER NOT NULL, year INTEGER NOT NULL, kind TEXT NOT NULL, supplier TEXT NOT NULL, norm_supplier TEXT NOT NULL, recipients TEXT NOT NULL, subject TEXT NOT NULL, attachments TEXT NOT NULL, status TEXT NOT NULL, detail TEXT NOT NULL)`
     - Index: `idx_history_period_norm(year, month, kind, status, norm_supplier)`.
     - Hỗ trợ truy vấn trực tiếp cho màn hình Lịch sử In-App (`query_history`, `failed_suppliers_in_period`, `period_summary`) và kết xuất báo cáo `Lich_su_gui.xlsx` (chạy trên Background Worker, giữ định dạng chuỗi `"09"` cho cột Tháng, chống CSV/Excel Formula Injection).

---

## 4. Hợp Đồng Động Cơ Khớp File Thông Minh 3 Tầng (`app/domain/matching.py`)

**Nguyên tắc tối thượng: Zero Wrong-Vendor Delivery (100% Branch Coverage).**

### 4.1. Tiền xử lý & Lọc rác bắt buộc
- Lọc bỏ tuyệt đối trước khi chấm điểm: file tạm Office (`~$*`, `.~lock*`, `*.tmp`, `*.bak`), file ẩn hệ thống (`desktop.ini`, `Thumbs.db`, `.DS_Store`), file không đúng phần mở rộng được phép (Excel: `.xlsx`, `.xls`, `.xlsm`; PDF: `.pdf`), file 0 byte, đường dẫn thoát khỏi thư mục nguồn (Path Traversal).
- Chuẩn hóa Unicode **NFC** cho toàn bộ tên file và tên NCC trước khi so sánh (triệt tiêu lỗi tên file tiếng Việt NFD từ macOS/Zalo/Google Drive).

### 4.2. Trích xuất Kỳ Tháng/Năm & Chế độ
- `extract_period_from_text(text) -> Optional[tuple[int, int]]`: Nhận diện an toàn các mẫu có ranh giới số rõ ràng (`09.2026`, `9.2026`, `2026-09`, `2026_09`, `T09-2026`, `Thang 9 nam 2026`), tuyệt đối **không khớp nhầm số dính liền** (`19.2026`, `90`, `20260`).
- `suggest_period(files, default_attach_root, today)`:
  1. Ưu tiên majority vote từ tên thư mục / tên file vừa chọn/kéo-thả.
  2. Nếu chưa chọn file: tìm thư mục kỳ mới nhất trong `default_attach_root` có chứa file Excel/PDF thật.
  3. Fallback theo chu kỳ kế toán: `today.day <= 15` → tháng trước; `today.day >= 16` → tháng hiện tại.
- `detect_send_kind(files)`: Chỉ có Excel → `Tạm tính`; có cả Excel & PDF → `Chốt` (kèm cờ `partial_pdf_warning` nếu số PDF < số Excel).

### 4.3. Quy tắc Khớp File 3 Tầng (Triệt tiêu bẫy `ACE` vs `AHC`)
Với mỗi NCC đang bật và từng loại file cần thiết (Excel; thêm PDF nếu `Chốt`):
1. **Lọc theo kỳ (Period Gate)**: Nếu tên file chứa `(month, year)` rõ ràng nhưng **khác kỳ đang chọn** → gắn nhãn `WRONG_PERIOD` (Tầng Đỏ — KHÔNG tự động đính kèm).
2. **Khớp ranh giới từ (Token Boundary Match) — Longest-Match-First**:
   - Kiểm tra tên NCC và từng `alias` (đã chuẩn hóa NFC + lowercase) xuất hiện như một **token độc lập** (bao bởi đầu/cuối chuỗi hoặc ký tự ngăn cách không phải chữ/số: khoảng trắng, `.`, `_`, `-`, `(`, `)`, `[`, `]`).
   - Ưu tiên tên dài hơn trước (`T&T Logistics` > `T&T`, `HR Partner` > `HR`, `ACE2` > `ACE`, `AB` > `A`) để **chống đụng độ chuỗi con (Substring/Prefix Collision)**.
   - **Kiểm tra chéo âm tính**: Nếu một file chứa token của >= 2 NCC khác nhau (sau khi loại quan hệ chuỗi con đã thắng dài nhất) → đánh dấu `CONFLICT` (**Tầng Đỏ — Khóa cứng cả 2 NCC**).
3. **Phân tầng trạng thái `MatchStatus`**:
   - **`EXACT`** *(Tầng Xanh — Auto Ready)*: Khớp đúng 100% tên file render từ template (NFC).
   - **`AUTO_MATCHED`** *(Tầng Xanh — Auto Ready)*: Khớp duy nhất 1 file cùng loại qua Token Boundary Match với `name`/`aliases` + không lệch kỳ + không xung đột với NCC khác.
   - **`NEEDS_REVIEW`** *(Tầng Vàng — **Mặc định KHÔNG tick gửi**, bắt buộc user bấm xác nhận)*: Khớp gần đúng (fuzzy trên phần tên đã tước tiền tố/hậu tố chung & kỳ tháng, ngưỡng >= 0.80), chỉ khi ứng viên không chứa token của NCC khác và không đang gắn cho NCC khác.
   - **`AMBIGUOUS`** *(Tầng Đỏ — Khóa cứng)*: 1 NCC có >= 2 file ứng viên cùng loại (vd `ACE_v1.xlsx` và `ACE_final.xlsx`).
   - **`CONFLICT`** *(Tầng Đỏ — Khóa cứng)*: 1 file vật lý (theo đường dẫn hoặc `SHA-256`) trùng cho >= 2 NCC.
   - **`WRONG_PERIOD`** *(Tầng Đỏ — Khóa cứng)*: File khớp tên NCC nhưng ghi sai tháng/năm.
   - **`MISSING` / `INVALID_FILE`** *(Tầng Đỏ — Khóa cứng)*: Thiếu file, file 0 byte, hoặc tổng dung lượng (tính cả Logo nếu có) > `18 MB`.
4. **Global 1–1 Disjoint Invariant**: Kiểm tra cuối vòng lặp đảm bảo 0 có 2 NCC nào dùng chung cùng đường dẫn hoặc cùng `SHA-256`.
5. **Auto-Discovery (`discover_unknown_suppliers`)**: Các file Excel/PDF hợp lệ chưa gán cho NCC nào được gom theo tên ứng viên trích xuất từ template đảo ngược để gợi ý thêm NCC mới 1-click.

---

## 5. Hợp Đồng Lõi Gửi Mail, Lịch Sử & Telemetry (`app/adapters/smtp_mailer.py`, `app/application/batch_runner.py`)

1. **TOCTOU Hash Pinning**: Mỗi `AttachmentMatch` lưu sẵn `sha256` tại thời điểm người dùng xem trước/xác nhận. Ngay trước khi gắn vào `EmailMessage`, `build_message()` đối chiếu lại `sha256` thực tế — nếu khác, hủy gửi NCC đó với lỗi `SendErrorKind.ATTACHMENT_CHANGED`.
2. **SMTP SSL (465) → STARTTLS (587) Fallback & Chống Gửi Trùng**:
   - Thử kết nối `SMTP_SSL(smtp.gmail.com, 465)` trước; nếu gặp lỗi mạng/timeout kết nối ban đầu (`OSError`), tự động thử `SMTP(smtp.gmail.com, 587)` + `starttls(context=ssl.create_default_context())`.
   - Cố định header `Message-ID` cho mỗi `MailPlan` trước vòng lặp retry; gọi `server.noop()` kiểm tra socket sống trước khi gửi `DATA` để triệt tiêu nguy cơ retry gửi trùng sau `DATA`.
   - Phân loại lỗi tường minh bằng `SendErrorKind` (`AUTH`, `RECIPIENT_REFUSED`, `PARTIAL_REFUSED`, `ATTACHMENT_IO`, `ATTACHMENT_CHANGED`, `TRANSIENT_NETWORK`, `UNKNOWN`) — không phân loại bằng chuỗi tiếng Việt.
3. **Explicit Logo & HTML Sanitization**:
   - Chỉ nhúng logo khi `settings.logo_path` được chọn rõ ràng và file tồn tại (cấm tự nhúng `APP_DIR/logo.png` âm thầm). Cộng dung lượng logo vào giới hạn `18 MB`.
   - Mọi nội dung HTML preview & gửi đi qua `nh3.clean(...)` với danh sách thẻ/thuộc tính an toàn (loại bỏ `<script>`, `on*`, `javascript:`, ảnh remote không cho phép).
4. **Worker-Side Durable Commit & Pause-Aware Telemetry**:
   - `BatchRunner` ghi kết quả vào `HistoryRepository` **ngay trên Worker Thread** ngay khi SMTP trả kết quả, TRƯỚC khi bắn sự kiện tiến độ về UI.
   - Khi đóng cửa sổ lúc đang gửi: kích hoạt `cancel_event` và chờ tối đa `5s` cho email hiện tại hoàn tất & commit DB (Graceful Shutdown).
   - Telemetry theo dõi `paused_seconds` tích lũy (tiêm `Clock` để `pytest` test tức thì trong `0ms`): `active_elapsed = (now - start) - paused_seconds`.
5. **Gửi thử an toàn (`send_test_email`)**:
   - Ép `recipients = [test_email hoặc settings.sender]`, `cc = []`, `subject = "[GỬI THỬ] " + plan.subject`, giữ nguyên HTML + Logo CID + đính kèm thật (nếu có), **tuyệt đối không ghi vào `send_history`**.

---

## 6. Hợp Đồng Cầu Nối UI & 6 Rào Chắn Bảo Mật PyWebView (`app/ui/bridge.py`, `app/ui/window.py`)

1. **6 Rào Chắn Bảo Mật Bắt Buộc**:
   - `<iframe sandbox="" srcdoc="...">` cho toàn bộ khung xem trước Email HTML (không `allow-scripts`, không `allow-same-origin`).
   - Sanitize HTML phía Python bằng `nh3` trước khi trả về UI.
   - Strict CSP trong `index.html` (`default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-src 'self' data:; connect-src 'none';`).
   - Strict Whitelist JS-API Facade (`bridge.py`): chỉ nhận ID / giá trị đã xác thực; chọn thư mục/file/logo qua hộp thoại OS native (`window.create_file_dialog`) hoặc danh sách đường dẫn đã qua kiểm tra từ sự kiện Drag & Drop thật của WebView2; không bao giờ trả mật khẩu/token.
   - Tắt DevTools (`debug=False`) ở bản đóng gói; hàm `open_external_url(url)` chỉ cho phép whitelist `https://myaccount.google.com/...` và `https://github.com/minhhai1104/Sending_gmail_for_Mrs_Ha/...`.
   - Đặt WebView2 `storage_path = %LOCALAPPDATA%\GmailAutoMailer\webview` (tách biệt hoàn toàn khỏi thư mục cài đặt ứng dụng để không bao giờ khóa tệp khi OTA).
2. **Filter-Safe Selection**:
   - Khi người dùng bấm Gửi trong lúc bộ lọc tìm kiếm đang kích hoạt và có NCC được tick nhưng đang bị ẩn: UI hiển thị hộp thoại xác nhận nêu rõ số lượng đang hiển thị vs đang bị ẩn, cho phép chọn *"Chỉ gửi các NCC đang lọc"* hoặc *"Gửi toàn bộ đã tick"*.

---

## 7. Hợp Đồng OTA Hardening & Bộ Cài 1-Click (`app/adapters/ota_updater.py`, `updater_runner.py`, `installer/`)

1. **Mandatory SHA-256 & Domain Allowlist**:
   - `verify_sha256()` trả về `False` nếu `expected_sha256` rỗng hoặc không đúng 64 ký tự hex.
   - Allowlist host HTTPS: `api.github.com`, `github.com`, `objects.githubusercontent.com`, `release-assets.githubusercontent.com`.
   - `updater_runner.py` viết thuần Python stdlib (không import `app.*`), kiểm tra kết quả `wait_for_process_exit()`, tự copy sang `%TEMP%` khi chạy, dọn file `.bak` và giữ nguyên `PROTECTED_USER_ITEMS`.
2. **Đóng gói `--onedir` + Bộ cài 1-Click Per-User (`Setup.exe`)**:
   - Nhúng `assets/app_icon.ico` (6 kích cỡ) + `build/version_info.txt` (Haesung Vina Co., Ltd., v3.0.0) + `SetCurrentProcessExplicitAppUserModelID("HaesungVina.GmailAutoMailer.3")`, tắt `upx`.
   - Bộ cài Inno Setup `installer/setup.iss` cài Per-User vào `%LOCALAPPDATA%\Programs\HaesungVina\GmailAutoMailer`, không yêu cầu Admin UAC, kiểm tra Edge WebView2 Runtime, tạo Shortcut Desktop + Start Menu + Uninstall chuẩn Windows.
