---
name: codebase-map
description: "Thiết lập và duy trì bản đồ tri thức toàn diện của dự án (STACK.md, ARCHITECTURE.md, STRUCTURE.md, INTEGRATIONS.md, CONVENTIONS.md, TESTING.md, CONCERNS.md, ORIENTATION_MAP.md). Chỉ cần đọc ORIENTATION_MAP.md một lần ở đầu phiên chat mới, bất kỳ Sub-Agent nào cũng hiểu trọn vẹn 100% bối cảnh, kiến trúc, quy tắc bất biến mà người dùng không cần phải nhắc lại."
---

# Codebase Knowledge Map Engine (`codebase-map`)

Kỹ năng lập bản đồ tri thức toàn diện cho AI Coding Agent dựa trên chuẩn công nghiệp **GSD Codebase Mapping (`gsd:map-codebase`)** và **Cartography Knowledge Engine**.

---

## 1. Mục Đích & Nguyên Tắc Vàng

1. **Triệt tiêu "Não cá vàng" & Không làm phiền Người dùng**:
   - Ở đầu mỗi phiên chat mới hoặc sau khi compact context, Agent **bắt buộc đọc ngay** tệp [`.agents/knowledge/ORIENTATION_MAP.md`](file:///g:/My%20Drive/DEV/Googel%20Antigravity/Nguyen-Ba-Toc/.agents/knowledge/ORIENTATION_MAP.md).
   - Nắm vững 100% bản chất dự án (Gia phả 12 đời, 4 Chi tách từ Đời 5, Soft-Void tài chính, Nghị định 13/2023, Botkeep Free Tier) mà **không cần người dùng phải giải thích hay nhắc lại**.
2. **Tiết kiệm 95% Chi phí Ngữ cảnh (Token Economy)**:
   - Thay vì cào thô (raw grep / cat) hàng chục file mã nguồn để tìm vị trí sửa code, Agent tham chiếu trực tiếp qua Bản đồ định hướng và Bản đồ mã nguồn `REPO_MAP.md`.
   - Mở chính xác đúng 1–2 file cần chỉnh sửa.

---

## 2. Hệ Thống Tài Liệu Bản Đồ Tri Thức

Toàn bộ bản đồ tri thức được tổ chức tại `.agents/knowledge/` (đồng thời được mirror tại `.planning/codebase/`):

| Tệp tri thức | Mục đích & Nội dung | Khi nào tham chiếu? |
| :--- | :--- | :--- |
| **`ORIENTATION_MAP.md`** | **Bản đồ định hướng 1 trang**: Tóm tắt toàn bộ bối cảnh, kiến trúc, quy chuẩn bất biến, và bảng điều hướng task. | **BẮT BUỘC ĐỌC ĐẦU MỖI PHIÊN CHAT MỚI** |
| **`STACK.md`** | Ngôn ngữ, framework, runtime Node 22, cấu hình Botkeep, Turso Cloud, biến môi trường. | Khi thiết lập môi trường, thêm dependency, cấu hình deploy. |
| **`ARCHITECTURE.md`** | Kiến trúc 4 tầng (Controller -> Service -> Repository -> DB), cơ chế Hybrid Sync SQLite + Turso. | Khi thiết kế module mới, mở endpoint API, sửa luồng dữ liệu. |
| **`STRUCTURE.md`** | Topology toàn bộ thư mục & nhiệm vụ cụ thể từng tệp tin. | Khi tìm kiếm file mã nguồn hoặc tạo file mới. |
| **`INTEGRATIONS.md`** | Chi tiết tích hợp Botkeep, Turso Cloud, Telegram backup, Cloudflare, Lịch Âm GMT+7. | Khi can thiệp các dịch vụ bên ngoài. |
| **`CONVENTIONS.md`** | Quy chuẩn Soft-Void tài chính, NĐ 13/2023, thuật toán cây 4 chi, chuẩn đặt tên. | Khi viết code để đảm bảo không vi phạm nguyên tắc bất biến. |
| **`TESTING.md`** | Chiến lược kiểm thử tại Highest Seams, danh mục 29 tests Node Test Runner. | Trước khi viết code (TDD) và trước khi nghiệm thu task. |
| **`CONCERNS.md`** | Giới hạn 2GB RAM Botkeep, cảnh báo rò rỉ bộ nhớ, an toàn CSDL SQLite production. | Khi tối ưu hiệu năng hoặc kiểm soát rủi ro. |
| **`REPO_MAP.md`** | Bản đồ mã nguồn chi tiết từng file, số dòng code và danh mục exported symbols/routes. | Khi cần xác định hàm, class, router nằm ở file nào. |

---

## 3. Quy Trình Vận Hành Cho Sub-Agents

1. **Khởi động phiên (Session Onboarding)**:
   - Đọc ngay `.agents/knowledge/ORIENTATION_MAP.md`.
2. **Xác định tọa độ code**:
   - Tra cứu nhanh trong `.agents/knowledge/REPO_MAP.md` để lấy đường dẫn file và symbol chính xác.
3. **Cập nhật Bản đồ khi có thay đổi cấu trúc lớn**:
   - Khi thêm/sửa bảng CSDL hoặc quy chuẩn hệ thống, cập nhật tài liệu tương ứng trong `.agents/knowledge/` và mirror sang `.planning/codebase/`.
   - Chạy lệnh `npm run map` (hoặc `node scripts/generate_repo_map.mjs`) để cập nhật lại `REPO_MAP.md`.
