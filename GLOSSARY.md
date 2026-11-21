# Project Glossary (Từ Điển Thuật Ngữ Nghiệp Vụ & Kỹ Thuật)

Tài liệu chuẩn hóa các thuật ngữ được sử dụng thống nhất giữa 7 Sub-Agents và người dùng trong dự án:

| Thuật ngữ | Tiếng Anh / Kỹ thuật | Định nghĩa & Ý nghĩa trong Dự án |
| :--- | :--- | :--- |
| **Bản tạm tính** | Draft Report | Chế độ gửi mail báo cáo chi phí tạm tính giữa kỳ. Chỉ đính kèm duy nhất file Excel `Bảng phí kiểm tra, phân loại hàng hóa {thang}.{nam} {nha_cung_cap}.xlsx`. |
| **Bản chốt** | Final Report | Chế độ gửi mail quyết toán chi phí chính thức cuối kỳ. Bắt buộc đính kèm đồng thời 2 file: 1 file Excel và 1 file PDF `PO {nha_cung_cap} {thang}.{nam}.pdf`. |
| **Mật khẩu ứng dụng** | App Password | Chuỗi ký tự bí mật 16 chữ cái được Google sinh ra cho tài khoản Gmail đã bật 2-Step Verification, cho phép ứng dụng đăng nhập gửi mail qua giao thức SMTP an toàn. |
| **Pacing** | Smart Pacing | Cơ chế chủ động tạo khoảng nghỉ (1.5 - 3.0 giây) giữa các email gửi liên tiếp nhằm tuân thủ giới hạn lưu lượng (rate limits) của Gmail và tránh kích hoạt bộ lọc spam. |
| **Exponential Backoff** | Thử lại lũy thừa | Giải thuật tự động thử lại khi gặp sự cố mạng tạm thời, với thời gian chờ tăng gấp đôi sau mỗi lần thất bại (1s -> 2s -> 4s) trước khi báo lỗi dứt điểm. |
| **Non-Blocking UI** | Giao diện không đơ | Nguyên tắc lập trình tách toàn bộ tác vụ I/O đĩa và mạng sang luồng nền (Worker Thread), giúp giao diện Tkinter phản hồi mượt mà, không bị treo ("Not Responding"). |
| **Xung đột Khóa File** | File Lock Exception | Lỗi xảy ra trên hệ điều hành Windows khi người dùng đang mở tệp CSV hoặc Excel bằng Microsoft Excel, khiến ứng dụng không thể ghi tiếp dữ liệu vào tệp đó. |
| **SQLite Catalog** | Lịch sử SQLite | Cơ chế lưu trữ lịch sử các lần gửi thư vào cơ sở dữ liệu SQLite (`history.db`) nội bộ để đảm bảo an toàn giao dịch, hỗ trợ truy vấn tức thì và triệt tiêu lỗi khóa file. |
| **Zero Plaintext Secrets** | Không mật khẩu thô | Quy chuẩn bảo mật nghiêm ngặt: Tuyệt đối không lưu trữ mật khẩu ứng dụng Gmail dưới dạng văn bản thô; sử dụng Windows DPAPI (`vault.dpapi` tại `%LOCALAPPDATA%`) và giao diện Write-Only. |
| **Zero Unverified Mail Loss** | Không gửi thiếu xác nhận | Nguyên tắc kiểm soát: Một email chỉ được coi là hoàn tất khi nhận mã phản hồi thành công `250 OK` từ máy chủ Gmail SMTP và ghi bền vững vào SQLite trên Worker Thread. |
| **Zero Wrong-Vendor Delivery** | Chống gửi nhầm NCC | Bộ bất biến an toàn của Động cơ Khớp File 3 Tầng (Word-Boundary Token, Longest-Match-First, Song ánh 1–1 theo path & SHA-256, TOCTOU Hash Pinning, cảnh báo trùng email chéo NCC, Filter-Safe Selection). |
| **TOCTOU Hash Pinning** | Ghim mã băm trước khi gửi | Kỹ thuật tính mã băm SHA-256 của tệp đính kèm lúc người dùng xem trước và đối chiếu lại ngay trước khi truyền SMTP nhằm chặn trường hợp file bị sửa đổi nội dung giữa chừng. |
