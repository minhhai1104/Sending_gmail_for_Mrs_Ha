# Design System: Modern Enterprise Precision

Hệ thống thiết kế giao diện cho ứng dụng Desktop Python **Gmail Auto Mailer** (sử dụng thư viện `tkinter` + `ttk`).

---

## 🎨 1. Bảng Màu Chuẩn (Color Palette & Semantic Tokens)

Đạt tỷ lệ tương phản tối thiểu **4.5:1** theo tiêu chuẩn **WCAG 2.1 AA**:

| Semantic Token | Light Mode Hex | Dark Mode Hex | Ý nghĩa & Vị trí Sử dụng |
| :--- | :--- | :--- | :--- |
| `primary` | `#107C41` (Excel Green) | `#21A366` | Nút hành động chính (Xem trước & Gửi), Trạng thái thành công |
| `primary_hover` | `#0E6B37` | `#2BBB72` | Trạng thái di chuột trên nút chính |
| `accent` | `#0078D4` (Office Blue) | `#2899F5` | Điểm nhấn giao diện, tab active, trạng thái đã gửi trước đó |
| `danger` | `#D83B01` (Crimson) | `#F7630C` | Lỗi thiếu file, thiếu email, lỗi kết nối Gmail |
| `warning` | `#FFB900` | `#FCE100` | Cảnh báo chưa lưu cấu hình, trạng thái tạm dừng (Pause) |
| `surface_bg` | `#F3F2F1` | `#201F1E` | Màu nền chính của cửa sổ ứng dụng |
| `card_bg` | `#FFFFFF` | `#2D2C2C` | Màu nền phân vùng (LabelFrame, Treeview, Text log) |
| `text_primary` | `#201F1E` | `#F3F2F1` | Chữ chính tiêu đề, nhãn dữ liệu |
| `text_secondary` | `#605E5C` | `#A19F9D` | Chữ gợi ý, đường dẫn phụ |
| `border` | `#EDEBE9` | `#3B3A39` | Đường viền ngăn cách phân khu |

---

## 📐 2. Hệ Thống Kiểu Chữ & Phông Chữ (Typography)

Sử dụng phông chữ hệ thống chuẩn của Microsoft Windows:
- **Font gia đình**: `Segoe UI` (cho UI widget) và `Consolas` (cho Log terminal).
- **Phân cấp kích thước**:
  - `Title`: `Segoe UI`, 14pt, Bold (Tiêu đề cửa sổ xem trước, tiêu đề phân vùng).
  - `Body`: `Segoe UI`, 10pt, Normal (Nhãn trường nhập, chữ trong bảng danh sách).
  - `Action Button`: `Segoe UI`, 12pt, Bold (Nút Xem trước & Gửi).
  - `Monospace / Log`: `Consolas`, 10pt, Regular (Khung ghi nhật ký kết quả gửi).

---

## 🧱 3. Bố Cục Công Thái Học 3 Phân Vùng (Visual Layout)

```text
+-------------------------------------------------------------------------+
| [1. KỲ GỬI & CHẾ ĐỘ]                                                    |
| Tháng: [ 09 ]    Năm: [ 2026 ]                                          |
| (•) Bản tạm tính (Chỉ Excel)        ( ) Bản chốt (Excel + PDF)          |
+-------------------------------------------------------------------------+
| [XEM TRƯỚC & GỬI] -> Nút to nổi bật màu Xanh lá (#107C41)               |
+-------------------------------------------------------------------------+
| [2. CÔNG CỤ TIỆN ÍCH]                                                   |
| [Mở file cấu hình]  [Mở thư mục đính kèm]  [Kiểm tra Gmail]  [Xem lịch sử] |
+-------------------------------------------------------------------------+
| [3. TIẾN TRÌNH & ĐIỀU KHIỂN LUỒNG (TELEMETRY)]                          |
| Tiến độ: [=========================>          ] 65% (13/20 nhà)          |
| Tốc độ: 25 mail/phút | Ước tính còn lại: 18 giây                        |
| [Tạm dừng (Pause)]   [Hủy gửi (Cancel)]                                  |
|                                                                         |
| Khung nhật ký hoạt động (ScrolledText Consolas 10pt):                   |
| ✔ ACE: Đã gửi thành công (1 file Excel)                                 |
| ✔ AHC: Đã gửi thành công (1 file Excel)                                 |
| ✖ DiaMond: Không tìm thấy file: Bảng phí...                             |
+-------------------------------------------------------------------------+
```

---

## 🚫 4. Quy Chuẩn Triệt Tiêu AI Slop (Anti-AI Slop Rules)

1. **Không màu sắc lòe loẹt ngẫu nhiên**: Chỉ sử dụng đúng bảng màu Semantic Tokens ở trên.
2. **Không làm giao diện méo mó khi co giãn**: Bắt buộc đặt `weight` cho grid và `minsize` (720x540) để giao diện co giãn tỷ lệ đẹp.
3. **Mọi icon đều có nhãn chữ đi kèm**: Không dùng icon đứng một mình gây hiểu lầm cho người dùng văn phòng (`✔ Sẵn sàng`, `✖ Lỗi`, `⏸ Không gửi`, `↺ Đã gửi rồi`).
