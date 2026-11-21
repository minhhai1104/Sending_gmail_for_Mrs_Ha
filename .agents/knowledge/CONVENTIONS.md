# Coding Conventions & Engineering Guidelines

1. **Ngôn ngữ & Tài liệu**:
   - Giao diện người dùng và thông báo lỗi hiển thị cho người dùng cuối: **100% Tiếng Việt tự nhiên, lịch sự, dễ hiểu cho người dùng văn phòng**.
   - Docstrings và chú thích mã nguồn: Tiếng Việt súc tích, giải thích rõ lý do thiết kế ("tại sao") thay vì chỉ nhắc lại code ("làm gì").
   - Tên biến, hàm, lớp: Chuẩn tiếng Anh theo PEP 8 (ví dụ: `build_plans`, `resolve_attach_dir`, `MailPlan`).

2. **Cấu trúc Mã Nguồn**:
   - Tuân thủ PEP 8, độ dài dòng tối đa 100 ký tự.
   - Luôn sử dụng Type Hints đầy đủ cho tham số và giá trị trả về của các hàm public.
   - Bắt buộc xử lý đóng tài nguyên bằng Context Managers (`with open(...)`, `with GmailSession(...)`, `with sqlite3.connect(...)`).

3. **An toàn Luồng (Thread Safety)**:
   - Widget Tkinter chỉ được khởi tạo, truy cập và sửa đổi từ Main Thread.
   - Giao tiếp liên luồng bắt buộc đi qua `queue.Queue`.
