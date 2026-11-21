---
name: gsap-interactive-motion
description: >-
  Kỹ nghệ hoạt ảnh cuộn và trải nghiệm kể chuyện tương tác dựa trên greensock/gsap-skills,
  oso95/scroll-world và DavidHDev/canvas-ui: hiệu ứng cuộn mượt mà (Smooth Scroll),
  dòng thời gian lịch sử xuyên suốt (Scroll-Driven Timeline), phối cảnh 3D và canvas WebGL
  giữ nguyên khả năng chọn và bấm nội dung HTML. Kích hoạt khi thiết kế trang Lịch sử Dòng họ,
  Trục thế thứ phả hệ, và các sự kiện Đại Lễ Giỗ Tổ trọng đại.
---

# GSAP Interactive Motion & Scroll Storytelling Skill

Được tổng hợp từ các dự án mã nguồn mở hàng đầu về hoạt ảnh tương tác trên GitHub (**`greensock/gsap-skills`**, **`oso95/scroll-world`**, và **`DavidHDev/canvas-ui`**), bộ kỹ năng này biến website dòng họ từ một bảng tài liệu tĩnh thành một **Hành Trình Kể Chuyện Di Sản Sống Động (Heritage Storytelling Journey)**.

## 1. Trục Thời Gian Lịch Sử Cuộn Xuyên Cảnh (Scroll-Driven Heritage Timeline)

Thay vì cuộn trang thông thường, trang **Lịch Sử Dòng Họ (`/history`)** và **Trục Thế Thứ 12 Đời** được dẫn dắt theo từng thước phim:
- **ScrollTrigger Pinning**: Ghim cố định khung tranh di tích Nhà Thờ Tổ hoặc Bia Phả Hệ ở nửa màn hình, trong khi nửa còn lại cuộn lướt qua các mốc son lịch sử (Thủy Tổ khai lập năm 1720 ➔ Khởi dựng từ đường ➔ Phát tích 4 Chi Đời thứ V).
- **Parallax Layering**: Các lớp mây rồng, mái đao ngói đỏ và mặt hồ sen chuyển động ở các tốc độ khác nhau, tạo chiều sâu phối cảnh 3D cuốn hút.

## 2. Canvas WebGL Tương Tác Giữ Nguyên Khả Năng Chọn Chữ (Canvas UI Architecture)

Theo triết lý từ `DavidHDev/canvas-ui`:
- ❌ **Sai lầm phổ biến**: Dùng WebGL render đè toàn bộ màn hình khiến chữ biến thành hình ảnh, người dùng không thể bôi đen copy tên tổ tiên, trình đọc màn hình cho người khiếm thị bị hỏng, và công cụ tìm kiếm không đọc được.
- ✅ **Chuẩn Canvas UI**:
  - Lớp WebGL Canvas chạy làm nền phía dưới (Ambient Shaders: khói hương trầm, ánh nến lung linh, mặt nước hồ sen dao động).
  - Lớp HTML Semantic nằm phía trên với đầy đủ thẻ `<article>`, `<h1>`, `<time>`, đảm bảo chuẩn khả năng tiếp cận WCAG 2.1 AA và 100% người dùng có thể tra cứu, sao chép chữ bình thường.

## 3. Đồng Hồ Đếm Ngược Giỗ Tổ & Lễ Hội Tương Tác (Celebration & Memorial Motion)

- Hoạt ảnh lật số cơ học (Mechanical Flip Clock) hoặc vòng tròn tiến trình dát vàng cho đồng hồ đếm ngược Giỗ Tổ ngày 15/08 Âm lịch.
- Khi người dùng gửi công đức hoặc báo công thành công: Bắn hoạt ảnh pháo hoa hoa sen trang trọng, lưu giữ kỷ niệm thiêng liêng hướng về nguồn cội.
