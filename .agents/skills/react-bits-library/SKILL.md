---
name: react-bits-library
description: >-
  Kho thành phần giao diện React động với hơn 200 components hiệu ứng chuyển động từ DavidHDev/react-bits:
  hiệu ứng chữ chuyển động (Text Animations), nền tương tác (Interactive Backgrounds), nút bấm xúc giác (Tactile Buttons),
  thẻ hiển thị sống động (Animated Cards), và các thành phần trực quan hóa dữ liệu.
  Kích hoạt khi xây dựng hoặc nâng cấp giao diện Frontend, thêm hiệu ứng di sản dòng họ, làm sinh động trang chủ và cây gia phả.
---

# React Bits Library Skill (Kho Component React Hiệu Ứng Chuyển Động)

Được kế thừa từ dự án mã nguồn mở danh tiếng **`DavidHDev/react-bits`** (hơn 49.000 sao trên GitHub), bộ kỹ năng này trang bị cho `fe-agent` và `designer-agent` kho vũ khí gồm hơn 200 linh kiện React có hiệu ứng chuyển động sống động, tinh tế và tối ưu hiệu năng cao.

## 1. Các Mẫu Component Trọng Tâm Ứng Dụng Cho Dự Án Dòng Họ

### A. Hiệu Ứng Chữ & Tiêu Đề Di Sản (Heritage Text Animations)
- **Shiny / Metallic Gold Text**: Tạo hiệu ứng ánh kim nhũ vàng lướt nhẹ qua dòng chữ *"CỔNG THÔNG TIN DÒNG HỌ NGUYỄN BÁ"*, mang lại cảm giác dát vàng cung đình sang trọng.
- **Blur Text / Split Text Fade In**: Tiêu đề từng đời trong phả ký xuất hiện êm ái khi cuộn trang, tạo sự tôn nghiêm và chiều sâu lịch sử.
- **Counter Number Roll**: Hiệu ứng đếm số mượt mà trên Dashboard (Tổng số nhân khẩu: 0 ➔ 470, Số thế hệ: 0 ➔ 12, Quỹ tồn: 0 ➔ 52.000.000 đ).

### B. Thẻ Card & Phản Hồi Xúc Giác (Tactile & Spotlight Cards)
- **Spotlight Border Card**: Thẻ thành viên danh gia vọng tộc có viền bắt sáng vàng kim theo hướng di chuột, tạo cảm giác bề mặt thẻ bài phủ sơn mài cao cấp.
- **Tilted 3D Card**: Thẻ vinh danh học sinh giỏi khuyến học và Bảng vàng công đức nghiêng nhẹ theo góc nhìn 3D khi rê chuột.
- **Magnetic Button**: Nút "Quay về Khởi Tổ" (Home) và "Đăng ký Giỗ Tổ" có lực hút nam châm nhẹ theo con trỏ chuột, bấm vào lún êm ái theo vật lý lò xo.

### C. Nền Tương Tác Tĩnh Tại (Subtle Ambient Backgrounds)
- **Particles / Floating Embers**: Hạt bụi vàng lơ lửng nhẹ nhàng phía sau Hoành phi Câu đối, gợi nhớ làn khói trầm hương bảng lảng trong gian thờ tổ.
- **Dot Pattern / Grid Grain**: Lớp hoa văn vi hạt trên nền Imperial Warm Ivory (`#faf8f4`) giúp nền trang không bị phẳng lì đơn điệu mà có chất liệu như giấy dó cổ truyền.

## 2. Tiêu Chuẩn Triển Khai Không Gây Giật Lag (60fps Performance Rule)

1. **Pure CSS & Transform First**: Ưu tiên 100% các chuyển động trên thuộc tính `transform: translate3d(), scale()` và `opacity` để tận dụng GPU.
2. **Reduced Motion**: Luôn tôn trọng tùy chọn `prefers-reduced-motion` của người dùng cao tuổi; tự động tắt các hiệu ứng chuyển động mạnh nếu người dùng kích hoạt chế độ chống chóng mặt.
3. **Zero Layout Shift**: Mọi component động phải định sẵn kích thước `width`, `height`, hoặc `aspect-ratio` để không gây giật bố cục khi tải trang.
