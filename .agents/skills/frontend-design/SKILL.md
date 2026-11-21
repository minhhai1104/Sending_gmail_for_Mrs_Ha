---
name: frontend-design
description: >-
  Bộ kỹ năng và quy chuẩn thiết kế giao diện Frontend chuẩn mực (phát triển bởi Anthropic): định hướng
  thẩm mỹ thực tế, phân cấp thị giác (visual hierarchy), bảng màu có chủ đích, typography tinh tế,
  khoảng trắng có nhịp điệu và kiên quyết loại bỏ thiết kế rập khuôn, sáo rỗng kiểu AI.
  Kích hoạt khi thiết kế giao diện, chọn màu sắc, dàn trang hoặc xây dựng Design System.
---

# Frontend-Design Skill (Chuẩn mực Thiết kế Giao diện Thực tế & Cao cấp)

Skill này được thiết kế để loại bỏ tư duy thiết kế máy móc, mang lại linh hồn, chiều sâu và tính chân thực cho sản phẩm web, giúp giao diện trông như được nhào nặn bởi các Senior Product Designer hàng đầu.

## 1. Triết lý Thiết kế Cốt lõi (Anti-Generic Mindset)

- **Không bao giờ dùng "AI Defaults"**: Cấm tiệt việc lạm dụng gradient tím - xanh cyberpunk, nền đen bóng bẩy neon, hay các khối card nổi lơ lửng vô nghĩa.
- **Tính Bối cảnh (Context-Driven Aesthetics)**:
  - Dự án dòng họ Việt Nam yêu cầu tính **Tôn nghiêm, Ấm cúng, Bền vững, Minh bạch**.
  - Không thể khoác lên trang web dòng họ phong cách của một ứng dụng Crypto SaaS hào nhoáng.
  - Tận dụng chất liệu văn hóa: Họa tiết vân mây, hoa sen cách điệu tối giản, màu giấy dó, gỗ lim, đồng cổ.

## 2. Hệ thống Màu sắc có Chủ đích (Color Palette with Intention)

- **Quy tắc 60 - 30 - 10**:
  - `60% Nền chủ đạo`: Tone màu ấm nhẹ (Warm White / Off-white: `#FAF8F5`, `#F5F0E6`, Slate 50), không dùng trắng toát chói mắt (`#FFFFFF` thuần túy).
  - `30% Cấu trúc & Nội dung`: Màu than ấm (Warm Charcoal `#1C1917`, Stone 800) mang lại độ tương phản dễ chịu, chữ sắc nét, không dùng đen tuyền (`#000000`).
  - `10% Điểm nhấn (Accent)`: Màu Đỏ son cổ truyền (`#991B1B` / `#8B2500`) hoặc Vàng kim hoàng thổ (`#B45309` / `#D4AF37`) cho CTA, huy hiệu, ngày giỗ quan trọng.
- **Tránh bão hòa màu quá mức**: Không dùng các màu neon chói lọi; ưu tiên màu đất (earth tones), màu khoáng thạch tự nhiên.

## 3. Nghệ thuật Typography (Visual Typography Hierarchy)

- **Quy tắc kết hợp phông chữ (Font Pairing)**:
  - *Tiêu đề (Headings)*: Dùng font Serif tiếng Việt trang nhã, cổ kính và vững chãi (`Noto Serif Vietnamese`, `Merriweather`, `Playfair Display`).
  - *Nội dung (Body & UI)*: Dùng font Sans-Serif hiện đại, hình học cân đối, hỗ trợ tiếng Việt hoàn hảo (`Be Vietnam Pro`, `Plus Jakarta Sans`, `Inter`).
- **Tỷ lệ và Nhịp điệu dòng (Type Scale & Leading)**:
  - Tỷ lệ bước nhảy phông hài hòa: `12px` (caption) - `14px` (small) - `16px` (body) - `20px` (h4) - `24px` (h3) - `32px` (h2) - `44px` (h1).
  - Line-height luôn thoáng đãng: `1.5 - 1.6` cho văn bản thông thường, `1.2 - 1.3` cho tiêu đề lớn.

## 4. Bố cục & Nhịp điệu Không gian (Spatial Rhythm & Whitespace)

- **Khoảng trắng là một thành phần thiết kế**: Để nội dung "thở". Không cố nhồi nhét mọi thông tin vào màn hình đầu tiên.
- **Hệ thống bước nhảy 8pt Grid**: Toàn bộ padding, margin, gap đều chia hết cho 4 hoặc 8 (`8px`, `16px`, `24px`, `32px`, `48px`, `64px`).
- **Phân cấp thị giác rõ ràng**: Mắt người dùng phải nhận biết ngay: Đâu là thông tin quan trọng nhất -> Kế tiếp -> Chi tiết phụ.
