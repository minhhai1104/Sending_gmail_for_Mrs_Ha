---
name: context-mode-optimizer
description: >-
  Kỹ năng tối ưu hóa cửa sổ ngữ cảnh và duy trì trí nhớ phiên làm việc từ dự án mksglu/context-mode:
  sandbox hóa kết quả lệnh (giảm 98% token rác), nén lịch sử làm việc qua thuật toán BM25 / FTS5
  để triệt tiêu hoàn toàn bệnh "não cá vàng" khi compact chat, và giám sát ngân sách token.
  Kích hoạt khi xử lý tác vụ dài hạn, điều phối đa agent, hoặc khi ngữ cảnh phiên làm việc bắt đầu đầy.
---

# Context-Mode Optimizer Skill (Kiểm Soát Ngữ Cảnh & Trí Nhớ Bền Vững)

Được lấy cảm hứng từ dự án **`mksglu/context-mode`** (công cụ tối ưu hóa ngữ cảnh nổi tiếng cho AI Coding Agents), kỹ năng này thiết lập kỷ luật quản lý context window nghiêm ngặt, giúp Agent duy trì sự tập trung sắc bén suốt các phiên làm việc kéo dài mà không bị mất dấu hay cạn kiệt hạn mức.

## 1. Cơ Chế Triệt Tiêu "Bệnh Não Cá Vàng" Khi Compact Chat

Khi phiên làm việc kéo dài và hệ thống thực hiện tóm tắt (Compact / Summary):
- ❌ **Rủi ro thường gặp**: Agent quên mất mình vừa sửa dở file nào, cấu trúc dữ liệu vừa chốt là gì, sinh ra code mâu thuẫn với các quyết định 5 phút trước.
- ✅ **Chuẩn Context-Mode**:
  - Lưu trữ nhật ký trạng thái (Session Memory) dạng key-value / index:
    - `activeFiles`: Danh sách các tệp đang được sửa đổi trực tiếp.
    - `architectureDecisions`: Các quyết định kiến trúc bất biến đã chốt (ví dụ: Node.js 22 SQLite native, Single Port, Botkeep Free Tier).
    - `lastPassedTest`: Trạng thái test suite gần nhất (ví dụ: 17/17 passed).
  - Khi cần khôi phục ngữ cảnh: Sử dụng từ khóa truy vấn chính xác (BM25 retrieval) để đọc lại đúng thông tin quan trọng nhất thay vì phỏng đoán mò.

## 2. Quy Tắc Sandbox Hóa Dữ Liệu Nặng (98% Token Reduction)

1. **Không in toàn bộ dữ liệu thô vào chat**:
   - Khi đọc file dữ liệu lớn (như file Excel 470 thành viên phả hệ hoặc database dump), không dump toàn bộ nội dung JSON 50.000 dòng ra terminal.
   - Luôn sử dụng lệnh đếm, lọc mẫu (head/tail, slice) hoặc chạy script trích xuất chỉ số thống kê tổng hợp (Aggregate stats: số bản ghi, cấu trúc cột, số lỗi).
2. **Kiểm soát đầu ra của lệnh (Command Output Truncation)**:
   - Các lệnh kiểm thử hoặc build: Chỉ cần trả về dòng kết luận tổng hợp (ví dụ: `17 tests, 17 passed, duration: 221ms`) thay vì in toàn bộ 500 dòng log chi tiết nếu không có lỗi.
3. **Phân Vùng Ngữ Cảnh Cho Từng Sub-Agent**:
   - `pm-agent` chỉ nhận báo cáo tiến độ và mã lỗi tóm tắt.
   - `be-agent` chỉ tập trung vào backend và API contract.
   - `fe-agent` chỉ tập trung vào React components và Tailwind specs.
   - Tránh hiện tượng "nhiễm chéo ngữ cảnh" (context pollution) làm loãng sự tập trung của Agent.
