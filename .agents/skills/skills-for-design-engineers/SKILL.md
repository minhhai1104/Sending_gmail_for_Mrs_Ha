---
name: skills-for-design-engineers
description: >-
  Kỹ năng Design Engineer chuyên sâu (dựa trên triết lý của Emil Kowalski): animation chuyển động mượt mà
  dựa trên vật lý lò xo (spring physics), hệ thống đổ bóng đa tầng tự nhiên (layered shadows), hiệu ứng chiều sâu,
  viền vi mô (inner highlights) và chi tiết xúc giác tinh tế để triệt tiêu bệnh giao diện "cứng đơ", thiếu sức sống của AI.
  Kích hoạt khi tinh chỉnh hiệu ứng chuyển động, card nổi, modal trượt hoặc nâng cao cảm giác chạm (tactile feel).
---

# Skills for Design Engineers (Nghệ Thuật Chuyển Động & Chi Tiết Xúc Giác)

Được đúc kết từ triết lý của **Emil Kowalski** (Design Engineer nổi tiếng với Radix UI, Sonner, Vaul), bộ kỹ năng này biến các giao diện thô cứng của AI thành những sản phẩm sống động, mượt mà và mang lại cảm giác chạm cao cấp (Tactile & Delightful).

## 1. Nguyên Tắc Vàng của Chuyển Động (Purposeful Animation)

- **Không bao giờ dùng hiệu ứng tuyến tính (`linear`) hoặc giật cục**:
  - Giao diện AI thường lạm dụng `transition: all 0.3s ease;` khiến chuyển động như rô-bốt.
  - Sử dụng **Vật lý lò xo (Spring Physics)** hoặc đường cong Bézier tự nhiên:
    - *Bật ra / Xuất hiện (Enter)*: `cubic-bezier(0.16, 1, 0.3, 1)` (chạy nhanh lúc đầu, hãm phanh êm ái).
    - *Thu vào / Biến mất (Exit)*: `cubic-bezier(0.7, 0, 0.84, 0)` (tăng tốc biến mất nhanh).
- **Chỉ animate `transform` và `opacity`**:
  - Tuyệt đối không animate `width`, `height`, `top`, `left`, `margin` vì sẽ gây giật khung hình (Browser Reflow).
  - Luôn sử dụng `scale()`, `translate3d()`, `opacity` để tận dụng tăng tốc phần cứng GPU (Hardware Acceleration: 60fps / 120fps mượt mà).

## 2. Hệ Thống Đổ Bóng Đa Tầng Tự Nhiên (Multi-Layered Shadows)

Đổ bóng kiểu AI thường là một vệt đen mờ thô thiển (`box-shadow: 0 10px 20px rgba(0,0,0,0.2)`).  
Hệ thống đổ bóng cao cấp của Emil Kowalski kết hợp 3 lớp bóng mờ với độ khuếch tán khác nhau:

```css
/* Đổ bóng tự nhiên cho Thẻ Thành Viên & Modal Phả Hệ */
.elevation-card {
  box-shadow:
    0 1px 2px -1px rgba(28, 25, 23, 0.06),
    0 3px 6px -2px rgba(28, 25, 23, 0.05),
    0 10px 20px -4px rgba(28, 25, 23, 0.04);
}

.elevation-hover {
  transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}
.elevation-hover:hover {
  transform: translateY(-2px);
  box-shadow:
    0 2px 4px -2px rgba(28, 25, 23, 0.08),
    0 6px 12px -3px rgba(28, 25, 23, 0.08),
    0 20px 25px -5px rgba(28, 25, 23, 0.06);
}
```

## 3. Viền Vi Mô & Chiều Sâu Vật Lý (Inner Highlights & Borders)

- **Đường viền có ánh sáng phản chiếu (Subtle Top Inner Highlight)**:
  - Tạo một đường viền sáng 1px ở mép trên của nút bấm hoặc card để tạo độ dày vật lý như một tấm thẻ thật:
    ```css
    .tactile-button {
      box-shadow: inset 0 1px 0 0 rgba(255, 255, 255, 0.25), 0 1px 2px 0 rgba(0, 0, 0, 0.15);
    }
    ```
- **Phản hồi xúc giác khi nhấp chuột / chạm tay (Tactile Active State)**:
  - Nút bấm lún xuống tức thì khi ấn ngón tay: `active:scale-[0.97] active:duration-75`.
  - Nảy trở lại nhẹ nhàng khi nhấc tay: `transition-transform duration-150 ease-out`.

## 4. Trải Nghiệm Modal & Bảng Trượt Mượt Mà (Vaul / Bottom Sheets)

- Trên điện thoại di động:
  - Khi xem chi tiết một Cụ/Con cháu trên cây gia phả: Không mở một popup cứng nhắc giữa màn hình.
  - Sử dụng **Bottom Drawer (Bảng trượt từ đáy)** có thanh kéo nhỏ (drag handle), kéo trượt theo ngón tay với quán tính tự nhiên (momentum swipe-to-dismiss).
- Khi mở modal: Lớp nền mờ dần nhẹ nhàng (`backdrop-blur-sm bg-stone-900/40`), trang chính phía sau thu nhỏ nhẹ (`scale(0.98)`), tạo cảm giác phân tầng không gian 3D sâu thẳm.
