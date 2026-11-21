# Design System v3.0: Modern Enterprise Precision (Zero-Manual UX)

Hệ thống thiết kế giao diện cho ứng dụng Desktop Windows **Gmail Auto Mailer v3.0 — Haesung Vina** (chạy trên nền **PyWebView + Microsoft Edge WebView2** với Web UI HTML/CSS/JS tĩnh nội bộ, 100% offline, Zero CDN).

---

## 1. Triết Lý Thiết Kế (Design Principles)

1. **Zero-Manual UX (Không cần đọc hướng dẫn)**:
   - Nhân viên văn phòng / HR mở app lần đầu chỉ cần đi qua **Wizard 3 bước (~60 giây)** ngay trong app.
   - Không còn file Excel `Cau_hinh.xlsx`, không còn 67 dòng hướng dẫn hay phải nhớ cú pháp `{nha_cung_cap}` / `Alt+Enter`.
   - Mọi thao tác gửi mail hàng tháng rút gọn còn **3 bước trong 1 cửa sổ duy nhất**: Kéo-thả (hoặc chọn) thư mục file → Xem trước Email HTML thật & duyệt → Bấm Gửi.
2. **Thẩm mỹ Modern Enterprise (Microsoft 365 Fluent / Linear Precision)**:
   - Sạch sẽ, sắc nét, đáng tin cậy cho nghiệp vụ tài chính/kế toán/HR.
   - **Anti-AI Slop tuyệt đối**: Không gradient tím/neon, không bóng phát sáng lòe loẹt, không nút bo tròn con nhộng lạm dụng, không emoji Unicode lộn xộn (100% bộ icon SVG nét mảnh `1.5px` đồng nhất kèm nhãn chữ tiếng Việt rõ ràng).
3. **Truthful Preview & Safety First**:
   - Khung xem trước hiển thị **100% Email HTML thật + Chữ ký + Logo công ty** trong `<iframe sandbox="">` — thấy sao gửi vậy.
   - Trạng thái trực quan 4 cấp màu Soft-Tint đạt chuẩn tương phản **WCAG 2.1 AA (>= 4.5:1)** ở cả Light & Dark Mode.

---

## 2. Hệ Thống Màu Sắc (Semantic Color Tokens — Light & Dark 100%)

| Token CSS | Light Mode | Dark Mode | Ý nghĩa & Vị trí sử dụng |
| :--- | :--- | :--- | :--- |
| `--bg-canvas` | `#F6F8FA` | `#111317` | Nền chính vùng nội dung |
| `--bg-sidebar` | `#EEF2F6` | `#16191F` | Nền thanh điều hướng trái (224px) |
| `--bg-surface` | `#FFFFFF` | `#1C2028` | Nền Card, Bảng, Drawer, Modal |
| `--bg-elevated` | `#F8FAFC` | `#242934` | Nền ô nhập, hover dòng, header bảng |
| `--border-subtle` | `#E2E8F0` | `#2C3240` | Đường viền mảnh `1px` ngăn cách card/cột |
| `--border-strong` | `#CBD5E1` | `#3E4658` | Viền input, nút secondary |
| `--text-primary` | `#0F172A` | `#F1F5F9` | Tiêu đề, dữ liệu chính |
| `--text-secondary` | `#475569` | `#94A3B8` | Nhãn phụ, đường dẫn, mô tả ngắn |
| `--text-muted` | `#526071` | `#7C8A9E` | Placeholder, metadata nhẹ (đạt >= 4.5:1 trên mọi nền) |
| `--brand-primary` | `#0F7B43` | `#22A861` | 1 nút CTA chính duy nhất mỗi màn hình (Gửi, Lưu) |
| `--brand-primary-hover` | `#0C6536` | `#2BC070` | Hover nút CTA chính |
| `--accent` | `#0066CC` | `#3B9EFF` | Focus ring, tab active, liên kết hành động |
| `--status-ok-bg` / `-fg` | `#ECFDF3` / `#067647` | `#0D2B1E` / `#4ADE80` | Sẵn sàng / Đã gửi thành công |
| `--status-warn-bg` / `-fg` | `#FFFBEB` / `#B45309` | `#2D220A` / `#FBBF24` | Cần duyệt tay (Fuzzy match) / Đang tạm dừng |
| `--status-err-bg` / `-fg` | `#FEF2F2` / `#B91C1C` | `#2F1416` / `#F87171` | Thiếu file / Thiếu email / Khóa xung đột / Lỗi |
| `--status-info-bg` / `-fg` | `#EFF6FF` / `#1D4ED8` | `#12233D` / `#60A5FA` | Đã gửi trước đó trong kỳ |

---

## 3. Hệ Thống Chữ & Nhịp Điệu Không Gian (Typography & 8pt Grid)

- **Phông chữ hệ thống Windows sắc nét**: `'Segoe UI Variable Text', 'Segoe UI', -apple-system, sans-serif`; số liệu thống kê (tốc độ `mail/phút`, `ETA`, dung lượng MB, phần trăm) bắt buộc dùng `font-variant-numeric: tabular-nums;` để không bị giật nhảy ngang.
- **Thang kích thước**:
  - Page Title: `20px` / Weight `600` (KHÔNG viết IN HOA toàn bộ).
  - Section Title: `14px` / Weight `600`.
  - Body / Table Cell: `13.5px` / Line-height `1.45`.
  - Badge / Meta / Helper: `12px` / Weight `500`.
- **Bo góc chuẩn mực**: Card `10px`, Button/Input `7px`, Badge `6px` (không dùng pill bo tròn quá đà cho nút chính).
- **Khoảng cách theo bội số 4px / 8px**: Padding vùng chính `20px`, khoảng cách giữa card `16px`, khoảng cách nội bộ `8px / 12px`.

---

## 4. Kiến Trúc 6 Màn Hình In-App (Single-Window App Shell)

```text
+----------------------------------------------------------------------------------+
| [Sidebar 224px]   | [Top Header: Kỳ gửi · Chế độ · Đèn Gmail · Sáng/Tối · OTA]   |
|  Haesung Mailer   +--------------------------------------------------------------+
|  v3.0             |                                                              |
|  ───────────────  |   [Active View Canvas]                                       |
|  ● Gửi Mail       |   1. Send Workspace (Mặc định):                              |
|    Nhà cung cấp   |      - Smart Dropzone / Chọn thư mục + Auto-Discovery Banner |
|    Mẫu Email      |      - Split Pane 56% / 44%:                                 |
|    Lịch sử gửi    |        [Trái: KPI Chips + Search + Bảng Checkbox 1-chạm]     |
|    Cài đặt        |        [Phải: Header Mail + Chips Đính kèm + HTML Preview]   |
|  ───────────────  |      - Sticky Footer: Gửi thử | Gửi ngay (N mail)            |
|  [Đèn kết nối]    |      - Live Dispatch Drawer (Progress, 4 KPI, Pause/Cancel)  |
+-------------------+--------------------------------------------------------------+
```

### Đặc tả 6 màn hình:
1. **`FirstRunWizard` (Overlay 3 bước lần đầu — ~60s)**:
   - Bước 1: Kết nối Gmail (Email, Tên hiển thị, Mật khẩu ứng dụng 16 ký tự tự xóa dấu cách + nút mở thẳng trang tạo App Password của Google + nút kiểm tra kết nối ngay).
   - Bước 2: Thêm nhanh danh sách Nhà cung cấp đầu tiên (có sẵn 7 NCC mặc định của Haesung Vina để chỉ cần gõ email, hoặc tự thêm/xóa).
   - Bước 3: Tùy chỉnh Chữ ký & Chọn ảnh Logo (xem trước chữ ký HTML thật ngay lập tức) → Hoàn tất.
2. **`SendWorkspace` (Gửi Mail — Màn hình chính)**:
   - Tự gợi ý Tháng/Năm phù hợp (ngày 1–15 gợi ý tháng trước; tự đọc tháng/năm từ thư mục/file được kéo-thả) và tự nhận diện chế độ `Tạm tính` vs `Chốt`.
   - Hỗ trợ kéo-thả trực tiếp thư mục hoặc cụm file từ Windows Explorer, hoặc bấm nút **Chọn thư mục / Chọn file**.
   - **Bảng danh sách NCC 1 dòng siêu gọn (`38px/dòng` — tối ưu 50+ NCC, cập nhật v3.1)**:
     - Hiển thị cùng lúc **11–12 nhà cung cấp** trên khung nhìn chuẩn (`1240×790`) thay vì dạng thẻ dọc nhiều tầng; giữ tiêu đề cột cố định (`position: sticky`) kèm **Checkbox chọn tất cả 3 trạng thái** (`checked` / `indeterminate` / `unchecked`).
     - Các cột thẳng hàng cố định: `[☐]` · `Nhà cung cấp ↕` · `Email` · `Excel` · (`PDF` tự động hiện khi ở chế độ `Chốt`) · `Trạng thái ↕`.
     - Loại bỏ hoàn toàn hàng nút lặp lại trên từng dòng; thay bằng **nút chỉ báo SVG 1 chạm (`>= 28×26px` đạt WCAG 2.5.8)**: bấm `✕` ở cột Email mở thẳng Drawer sửa email (tự focus ô nhập email), bấm `✕` ở cột Excel/PDF mở File Picker, bấm `?` (Cần duyệt) hoặc `!` (Xung đột/Trùng file) nhảy thẳng tới thẻ tệp tương ứng bên Panel Xem Trước (đảm bảo Zero Wrong-Vendor Delivery).
     - Nhãn trạng thái cột phải cô đọng rõ nguyên nhân (`Sẵn sàng`, `Cần duyệt`, `Thiếu Excel`, `Thiếu PDF`, `Thiếu email`, `Thiếu 2 mục`, `Xung đột`, `Trùng file`, `Sai kỳ`, `Đã gửi`, `Tạm tắt`).
     - Hỗ trợ sắp xếp tại chỗ không mất focus (`Intl.Collator('vi')` & ưu tiên lỗi trước) và điều hướng bàn phím nhanh **`↑` / `↓` / `Home` / `End` / `Space`** kết hợp lọc tab (`Tất cả`, `Sẵn sàng`, `Cần xử lý`, `Đã gửi`) và `Ctrl+F`.
   - Panel phải hiển thị **Live Email HTML Preview thật** trong `<iframe sandbox="">` kèm chữ ký và logo, cùng danh sách chip file đính kèm (bấm để mở kiểm tra).
   - Thanh ghim đáy: `Bỏ qua NCC đã gửi kỳ này`, nút **`Gửi thử về Gmail của tôi`**, nút CTA **`Gửi ngay (N mail)`**.
   - Khi đang gửi: Trượt lên `LiveDispatchDrawer` hiển thị thanh tiến độ mượt (0–100%), 4 thẻ KPI độc lập (`Tiến độ`, `Tốc độ mail/phút` trừ thời gian Pause, `ETA`, `Thành công / Lỗi`), nút `Tạm dừng / Tiếp tục`, `Hủy gửi`, dòng kết quả live và nút **`Gửi lại N nhà bị lỗi`** sau khi kết thúc.
3. **`SuppliersPage` (Nhà cung cấp)**:
   - Bảng danh sách NCC có công tắc gạt Bật/Tắt tức thì, chip email có kiểm tra hợp lệ màu đỏ ngay khi nhập, cảnh báo trùng email chéo NCC, quản lý từ khóa/bí danh tên file (`aliases`) và ghi chú.
4. **`TemplateStudioPage` (Mẫu Email & Chữ ký)**:
   - Chia đôi 50/50: Trái là trình soạn Tiêu đề, Nội dung, Chữ ký, Chọn ảnh Logo (File Picker + thumbnail), Mẫu tên file Excel/PDF kèm ví dụ thực tế; Phải là **Live HTML Preview** cập nhật tức thì.
   - Thanh nút **Chip chèn biến 1-click** (`+ Tháng`, `+ Năm`, `+ Tên NCC`, `+ Loại`) — không bao giờ phải tự gõ `{...}`.
5. **`HistoryPage` (Lịch sử gửi)**:
   - 4 thẻ KPI theo kỳ, bộ lọc Tháng/Năm/Loại/Trạng thái/Từ khóa, bảng lịch sử đọc thẳng từ SQLite `history.db`.
   - Nút **`Gửi lại các NCC lỗi`** (đưa thẳng về Workspace) và nút **`Xuất báo cáo Excel (.xlsx)`** chạy luồng nền.
6. **`SettingsPage` (Cài đặt)**:
   - Thẻ Tài khoản Gmail & Bảo mật (**Write-Only**: chỉ hiện trạng thái `Đã lưu an toàn trong Windows DPAPI` + nút `Đổi mật khẩu` / `Kiểm tra kết nối`, không bao giờ nạp ngược mật khẩu ra ô input).
   - Thẻ CC chung (dạng chip), Thư mục đính kèm mặc định (Folder Picker), Giãn cách chống spam Pacing (`1.5s–3.0s`), Số lần tự thử lại.
   - Thẻ Giao diện (`Sáng` / `Tối` / `Theo hệ thống`), Kiểm tra & cài đặt cập nhật OTA; mục *Nâng cao (Quản trị IT — GitHub Token)* đóng gọn mặc định.

---

## 5. Chuẩn 4 Trạng Thái Giao Diện & Khả Năng Tiếp Cận

- Mọi màn hình đều có đủ **Empty State** (hướng dẫn hành động 1 chạm), **Loading/Scanning State** (skeleton/spinner mượt), **Error State** (thông báo tiếng Việt rõ nguyên nhân & nút khắc phục tại chỗ) và **Success State** (toast gọn không làm gián đoạn bằng popup `messagebox`).
- Hỗ trợ phím tắt cơ bản (`Ctrl+F` tìm kiếm, `Esc` đóng modal/drawer) và tự thích ứng High-DPI 100%–200% trên Windows 10/11.
