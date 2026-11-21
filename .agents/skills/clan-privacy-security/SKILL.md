---
name: clan-privacy-security
description: >-
  Quy chuẩn bảo mật thông tin dòng họ và quyền riêng tư theo Nghị định 13/2023/NĐ-CP:
  phân quyền 5 cấp (GUEST / MEMBER / WRITER / ADMIN / SUPERADMIN), che giấu dữ liệu cá nhân
  (Số điện thoại, địa chỉ, rút gọn ngày sinh người còn sống về năm sinh YYYY), cơ chế xác thực JWT Bearer
  với khóa ký bắt buộc từ biến môi trường, và kiểm soát truy cập dữ liệu nội bộ. Kích hoạt khi phát triển Auth, API bảo mật và User Management.
---

# Clan Privacy & Data Security Skill (Bảo mật Thông tin Dòng họ)

Bộ kỹ năng này định nghĩa các nguyên tắc bảo mật và quyền riêng tư cho cổng thông tin dòng họ nhằm bảo vệ con cháu khỏi nguy cơ lộ lọt dữ liệu cá nhân, lừa đảo hoặc làm phiền.

## 1. Tuân thủ Pháp lý & Bảo vệ Dữ liệu Cá nhân

- Website dòng họ lưu trữ thông tin của nhiều thế hệ con cháu đang sinh sống trên khắp cả nước và nước ngoài.
- Phải tuyệt đối tuân thủ **Nghị định 13/2023/NĐ-CP của Chính phủ về Bảo vệ Dữ liệu Cá nhân**:
  - Không công khai số điện thoại, email, địa chỉ cư trú chi tiết và ngày tháng sinh đầy đủ của người còn sống ra internet cho khách vãng lai (`GUEST`).
  - Phân tách rõ ràng giữa thông tin của **Người đã khuất** (tưởng nhớ, công khai ngày mất/mộ phần) và **Người còn sống** (bảo vệ quyền riêng tư: `phone = null`, `address = "Khu vực nội bộ (Cần đăng nhập thành viên)"`, `birthDate` rút gọn về năm sinh 4 chữ số `'YYYY'`).

## 2. Ma trận Phân quyền 5 Cấp (Role-Based Access Control - RBAC)

| Nhóm thông tin | Khách (`GUEST`) | Con cháu (`MEMBER`) | Biên tập (`WRITER`) | Ban Trị Sự (`ADMIN`) | Quản trị Hệ thống (`SUPERADMIN`) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Lịch sử, Tộc ước, Công trạng, Khuyến học** | Xem đầy đủ | Xem đầy đủ | Đăng/sửa bài viết | Toàn quyền nghiệp vụ | Toàn quyền + cấu hình |
| **Cây gia phả (Tên, Đời, Chi)** | Xem tổng quan | Thêm/sửa từ nhánh ông nội trở xuống | Như `MEMBER` | Thêm / Sửa / Xóa toàn phả hệ | Toàn quyền |
| **Thông tin người còn sống (SĐT, Địa chỉ, Ngày sinh)** | ❌ Ẩn SĐT & địa chỉ; chỉ hiện năm sinh `YYYY` | ✅ Xem danh bạ nội tộc | ✅ Xem danh bạ nội tộc | Quản lý, xuất danh bạ | Toàn quyền |
| **Sổ quỹ & Sổ vàng Công đức** | Xem công khai phiếu `APPROVED` | Xem chi tiết & gửi báo cáo đóng góp | Như `MEMBER` | Tạo phiếu, duyệt `APPROVED`, hủy `VOIDED` | Toàn quyền |
| **SQL Studio, Sao lưu/Phục hồi `.db`, Cấu hình Server** | ❌ Cấm | ❌ Cấm | ❌ Cấm | ❌ Cấm | ✅ Độc quyền (`Administrator`) |

## 3. Kiến trúc Xác thực An toàn (Secure Authentication — xem `docs/adr/0004-jwt-bearer-authentication.md`)

1. **Cơ chế Token & Biến môi trường**:
   - Sử dụng **JWT Bearer Token** (`Authorization: Bearer <token>`, thời hạn 7 ngày) do client gửi qua header cho SPA/API đồng nhất.
   - Ở `NODE_ENV=production`, máy chủ bắt buộc yêu cầu `JWT_SECRET` (độ dài tối thiểu, cấm khóa mặc định công khai); nếu thiếu sẽ dừng khởi động ngay lập tức (fail-fast).
   - Tài khoản tối cao `Administrator` (`SUPERADMIN`) được khởi tạo qua biến môi trường `SUPERADMIN_PASSWORD` khi tạo mới và **không bao giờ tự động ghi đè** mật khẩu đã đổi trên production khi restart.
2. **Cơ chế Xác minh Thành viên Dòng họ**:
   - Khi con cháu đăng ký tài khoản mới: hồ sơ nằm ở bảng chờ duyệt (`PENDING`).
   - Admin đối chiếu phả hệ (Chi, Đời, con ông nào) rồi duyệt kích hoạt và cấp mật khẩu ban đầu (không dùng mật khẩu mặc định cố định).
3. **Bảo vệ API & Kiểm toán (Audit Log)**:
   - Thiết lập Rate Limiting chống brute-force trên `/api/auth/login` và các cổng gửi biểu mẫu công khai.
   - Mọi thao tác quản trị (duyệt thành viên, duyệt/hủy thu chi, tải bản sao lưu `.db`, chạy SQL Studio) đều ghi vào `audit_logs`.
