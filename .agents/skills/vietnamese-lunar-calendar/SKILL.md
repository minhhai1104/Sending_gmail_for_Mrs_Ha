---
name: vietnamese-lunar-calendar
description: >-
  Kỹ năng tính toán và chuyển đổi Lịch Âm - Dương Việt Nam chuẩn xác theo múi giờ GMT+7 (thuật toán Hồ Ngọc Đức),
  xử lý tháng nhuận, tính ngày Giỗ Tổ và ngày giỗ gia tiên hàng năm, đồng hồ đếm ngược và cơ chế nhắc lịch giỗ tự động.
  Kích hoạt khi phát triển các module Lịch giỗ, Tâm linh và Hệ thống nhắc nhở.
---

# Vietnamese Lunar Calendar Skill (Chuyển đổi Lịch Âm - Dương & Nhắc Giỗ)

Bộ kỹ năng này hướng dẫn thuật toán xử lý ngày tháng tâm linh, chuyển đổi qua lại giữa Âm lịch và Dương lịch theo đúng chuẩn Việt Nam và lập trình tự động nhắc giỗ.

## 1. Lưu ý Sống còn về Múi giờ Lịch Âm Việt Nam

- **Múi giờ bắt buộc**: Múi giờ `UTC+7` (Việt Nam).
- **Cảnh báo sai lệch Lịch Trung Quốc**:
  - Không sử dụng các thư viện `chinese-lunar-calendar` phổ thông vì Trung Quốc dùng múi giờ `UTC+8`. Sự chênh lệch 1 giờ dẫn đến thời điểm Sóc (New Moon) có thể rơi vào 2 ngày khác nhau, làm lệch ngày mồng 1 đầu tháng âm lịch hoặc lệch cả tháng nhuận!
  - Luôn sử dụng bộ thuật toán chuẩn của nhà thiên văn học **Hồ Ngọc Đức** (được kiểm chứng và ứng dụng rộng rãi nhất tại Việt Nam).

## 2. Mô hình Lưu trữ Ngày Giỗ

Trong Database, **ngày giỗ của người đã khuất luôn được lưu theo Âm lịch**:
- `deathLunarDay`: Ngày âm (1 - 30).
- `deathLunarMonth`: Tháng âm (1 - 12).
- `isLeapMonth`: Có phải tháng nhuận hay không (boolean).
- `memorialNote`: Nghi lễ đặc thù (tiểu tường, đại tường, giỗ chính, giỗ chi họ).

## 3. Thuật toán Quy đổi & Đếm ngược Giỗ Hàng năm

1. **Tính ngày giỗ Dương lịch cho năm hiện tại ($Y$)**:
   - Nhập: `(deathLunarDay, deathLunarMonth, Y)`
   - Gọi hàm chuyển đổi Âm -> Dương theo múi giờ GMT+7: Trả về `solarDate = { day, month, year }`.
   - Nếu ngày này đã qua trong năm nay, tự động tính tiếp cho năm kế tiếp ($Y + 1$).
2. **Đồng hồ đếm ngược (Countdown)**:
   - Tính số ngày còn lại: `remainingDays = floor((solarDate - today) / (1000 * 60 * 60 * 24))`.
   - Hiển thị widget đếm ngược trang trọng ở Banner trang chủ: *"Còn [X] ngày nữa là đến Đại lễ Giỗ Tổ [Tên ngày giỗ] (ngày ... âm lịch, tức ngày ... dương lịch)"*.

## 4. Kịch bản Tự động Nhắc Giỗ (Cron Job & Notification)

- Hệ thống chạy tiến trình kiểm tra hàng ngày vào lúc 06:00 sáng (giờ VN):
  - **Mốc 15 ngày**: Gửi thông báo chuẩn bị lễ vật, mâm cỗ cho Ban Trị Sự và các Trưởng chi.
  - **Mốc 7 ngày**: Gửi thông báo công khai lên trang chủ và bắn tin nhắn Telegram / Email / Zalo cho toàn bộ con cháu trong họ nắm lịch về tham dự.
  - **Mốc 1 ngày**: Nhắc nhở lần cuối về thời gian khai mạc, tiếp đón con cháu phương xa.
