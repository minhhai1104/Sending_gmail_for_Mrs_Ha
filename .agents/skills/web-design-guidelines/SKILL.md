---
name: web-design-guidelines
description: >-
  Hệ thống quy chuẩn toàn diện về Khả năng truy cập (Accessibility - WCAG 2.1 AA),
  Trải nghiệm người dùng (UX) và Hiệu năng web (Core Web Vitals): semantic HTML5, điều hướng bàn phím,
  độ tương phản màu sắc, chống giật bố cục và tối ưu cho người cao tuổi.
  Kích hoạt khi kiểm định khả năng tiếp cận (A11y Audit), tối ưu SEO/UX và chuẩn hóa semantic HTML.
---

# Web-Design Guidelines (Quy Chuẩn Accessibility WCAG 2.1 AA & UX Bền Vững)

Trang web dòng họ là nơi các cụ cao niên 70 - 80 tuổi cũng như các cháu thanh thiếu niên cùng sử dụng. Bộ quy chuẩn này đảm bảo web có khả năng tiếp cận (Accessibility - a11y) tốt nhất, dễ nhìn, dễ đọc và dễ thao tác cho mọi đối tượng.

## 1. Chuẩn mực Khả năng Tiếp cận (WCAG 2.1 Level AA)

### A. Độ tương phản Màu sắc (Color Contrast Ratio)
- Tỷ lệ tương phản chữ thường trên nền tối thiểu đạt **4.5:1**.
- Tỷ lệ tương phản chữ lớn (>= 18pt hoặc >= 14pt đậm) đạt tối thiểu **3:1**.
- **Không bao giờ dùng màu sắc làm dấu hiệu duy nhất để truyền tải thông tin**:
  - ❌ *Không chỉ dùng chấm tròn đỏ để báo "Đã mất" và chấm xanh để báo "Còn sống".*
  - ✅ *Phải luôn đi kèm chữ hoặc biểu tượng rõ ràng:* `[Icon dải lụa] Đã khuất` hoặc `[Icon lá mầm] Còn sống`.

### B. Điều hướng Bàn phím (Full Keyboard Navigation)
- Mọi thao tác có thể thực hiện bằng chuột thì đều phải thực hiện được bằng phím **Tab**, **Enter**, **Space** và **Phím mũi tên**.
- Bấm phím **Escape (Esc)** phải đóng ngay các hộp thoại Modal / Slide-over.
- Có đường link ẩn **"Chuyển nhanh đến nội dung chính" (Skip to main content)** hiển thị khi người dùng bấm phím Tab đầu tiên.

### C. Ngữ nghĩa HTML5 (Semantic HTML5)
- Sử dụng đúng thẻ HTML theo mục đích, không biến toàn bộ trang web thành một "rừng thẻ `<div>`":
  - `<header>`: Phần đầu trang và thanh điều hướng.
  - `<nav>`: Danh mục menu.
  - `<main>`: Khu vực nội dung chính của từng trang.
  - `<article>`: Từng bài viết phả ký, tiểu sử tiền nhân, tin tức giỗ tổ.
  - `<time dateTime="...">`: Dùng cho ngày tháng, ngày giỗ âm/dương để trình đọc màn hình hiểu được.
  - `<aside>`: Cột thông tin phụ hoặc danh bạ nhanh.
  - `<footer>`: Phần chân trang.

## 2. Thân thiện với Người Cao tuổi (Senior-Friendly UX)

1. **Cỡ chữ Nhập liệu an toàn**:
   - Tất cả các ô `input`, `select`, `textarea` trên mobile phải có `font-size: 16px` trở lên để ngăn trình duyệt Safari / Chrome tự động phóng to màn hình gây méo giao diện.
2. **Khu vực Chạm lớn (Touch Targets)**:
   - Các nút xem cây gia phả, nút gọi điện nhanh trong danh bạ phải có kích thước tối thiểu `44px x 44px` với khoảng cách an toàn tránh bấm nhầm.
3. **Ngôn từ Trong sáng, Thuần Việt**:
   - Không lạm dụng thuật ngữ tiếng Anh trong giao diện:
     - Dùng *"Sổ Quỹ Dòng Họ"* thay vì *"Finance Management"*.
     - Dùng *"Cây Phả Hệ"* thay vì *"Genealogy Tree"*.
     - Dùng *"Ban Trị Sự"* thay vì *"Admin Panel"*.

## 3. Chỉ số Hiệu năng Web Cốt lõi (Core Web Vitals)

- **LCP (Largest Contentful Paint)** < **2.5 giây**: Hình ảnh nhà thờ tổ ở banner trang chủ phải được nén WebP và nạp ưu tiên (`fetchpriority="high"`).
- **INP (Interaction to Next Paint)** < **200 mili-giây**: Khi bấm vào tên thành viên trong cây phả hệ, bảng thông tin phải mở ra tức thì không gây khựng màn hình.
- **CLS (Cumulative Layout Shift)** < **0.1**: Không để font chữ hoặc banner tải chậm làm xô lệch vị trí các dòng chữ đang đọc.
