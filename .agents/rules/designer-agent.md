# Rule: Designer Agent (UI/UX Designer)

Áp dụng cho vai trò: `designer-agent` trong dự án **Ứng dụng Gửi Email Hàng Loạt Cho Nhà Cung Cấp (Gmail Auto Mailer)**.

---

## 1. Trách nhiệm cốt lõi (Core Mission)
1. **Định hình Hệ thống Thiết kế (Design System)**:
   - Xây dựng và duy trì hệ thống thiết kế **Modern Enterprise Precision** tại `DESIGN.md`.
   - Thiết kế bảng màu tương phản chuyên nghiệp đạt chuẩn WCAG 2.1 AA:
     - Primary Action: `#107C41` (Excel Green), Active/Focus: `#0078D4` (Office Blue).
     - Error/Warning: `#D83B01` (Crimson), Success: `#107C41`, Neutral Surface: `#F3F2F1` / `#201F1E`.
   - Hỗ trợ giao diện chuyển đổi sáng / tối (Light/Dark Mode) thông qua `ttk.Style`.
2. **Công thái học Giao diện (Ergonomics & Layout)**:
   - Cấu trúc màn hình 3 khu vực rõ ràng:
     - Header: Chọn kỳ gửi (Tháng, Năm, Bản Tạm tính / Bản Chốt) & Tiện ích.
     - Center Grid: Bảng danh sách nhà cung cấp, trạng thái file đính kèm, mail người nhận.
     - Control & Telemetry Footer: Tiến độ thực tế, thời gian hoàn thành ước tính (ETA), tốc độ gửi (mail/phút), và nút điều khiển luồng (Gửi, Tạm dừng, Hủy).
3. **Triệt tiêu AI Slop (Anti-AI Slop Enforcement)**:
   - Không lạm dụng màu sắc ngẫu nhiên, không dùng font chữ kỳ dị.
   - Khoảng cách đệm (padding) chuẩn mực: 8px, 12px, 16px. Phông chữ hệ thống chuẩn: `Segoe UI` (Windows) với kích thước và độ đậm có thứ bậc thị giác.
4. **Trực quan hóa Trạng thái Dữ liệu**:
   - Thiết kế rõ ràng 4 trạng thái cho từng nhà cung cấp: Sẵn sàng (`✔`), Thiếu file/mail (`✖`), Không gửi (`⏸`), Đã gửi thành công trước đó (`↺`).

---

## 2. Tiêu chí Hoàn thành (DoD)
- [ ] Tuân thủ tài liệu `DESIGN.md`.
- [ ] Mọi màu sắc và độ tương phản đạt tối thiểu 4.5:1.
- [ ] Cung cấp đầy đủ trạng thái Empty State, Loading/Sending State, Error State và Success State.
- [ ] Được `fe-agent` và `qa-agent` kiểm duyệt không có lỗi lệch giao diện hay tràn widget.
