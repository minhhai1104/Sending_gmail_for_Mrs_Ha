---
name: agent-memory
description: >-
  Kỹ năng duy trì bộ nhớ vĩnh cửu (Persistent Long-Term Memory) cho toàn bộ đội ngũ Sub-Agents dựa trên
  kiến trúc Git-backed Memory Bank và chuẩn MCP Memory: tự động đọc và nạp trí nhớ từ .agents/memory/
  ở đầu mỗi phiên làm việc, chống quên trước quên sau, bảo toàn 100% yêu cầu của người dùng, quyết định kỹ thuật
  và trạng thái sprint xuyên suốt các lần compact context.
---

# Agent-Memory Skill (Hệ Thống Duy Trì Trí Nhớ Vĩnh Cửu)

Lấy cảm hứng từ các dự án mã nguồn mở hàng đầu (**`akitaonrails/ai-memory`**, **`@modelcontextprotocol/server-memory`**, và **`mem0`**), kỹ năng này thiết lập cơ chế nạp - cập nhật trí nhớ tự động cho toàn bộ đội ngũ Sub-Agents.

---

## 1. Nguyên Tắc Cốt Lõi: Memory-First

Mỗi khi Agent bắt đầu một phiên làm việc mới hoặc tiếp nhận một yêu cầu từ người dùng:
1. **Pha 0 - Nạp Trí Nhớ (Memory Load)**:
   - Đọc tệp `.agents/memory/user_profile.md` để nắm chắc mọi căn dặn, thói quen và quy tắc của người dùng.
   - Đọc tệp `.agents/memory/active_sprint.md` để biết phiên bản hiện tại, công việc đang dở dang và danh sách backlog.
   - Đọc tệp `.agents/memory/technical_decisions.md` để không vi phạm các quyết định kiến trúc bất biến.
2. **Pha 1 - Thực Thi Không Quên (Context-Aware Execution)**:
   - Tuân thủ nghiêm ngặt các chỉ thị đã chốt (không hỏi lại những điều người dùng đã trả lời).
   - Khi có thông tin mới từ người dùng (như tài khoản mới, yêu cầu UI mới, logic mới), lập tức ghi nhận vào `.agents/memory/`.
3. **Pha 2 - Bàn Giao & Lưu Vết (Memory Persistence)**:
   - Cập nhật `.agents/memory/active_sprint.md` trước khi kết thúc tác vụ để chuyển giao trạng thái hoàn hảo cho các phiên chat tiếp theo hoặc các Sub-Agents khác.

---

## 2. Bản Đồ Bộ Nhớ (Memory Map)

- **Thông tin người dùng & căn dặn đặc thù**: [`.agents/memory/user_profile.md`](../../memory/user_profile.md)
- **Tiến độ sprint & backlog việc cần làm**: [`.agents/memory/active_sprint.md`](../../memory/active_sprint.md)
- **Quyết định kiến trúc & kỹ thuật bất biến**: [`.agents/memory/technical_decisions.md`](../../memory/technical_decisions.md)
- **Sổ tay lệnh kiểm thử & deploy**: [`.agents/memory/system_patterns.md`](../../memory/system_patterns.md)

---

## 3. Quy Trình Cập Nhật Trí Nhớ Khi Người Dùng Yêu Cầu Thay Đổi

Khi người dùng đưa ra một thay đổi mang tính hệ thống (ví dụ: "Từ nay không dùng nút này nữa", "Đổi tên tài khoản...", "Đây là mật khẩu SFTP mới..."):
1. Agent **KHÔNG CHỈ** sửa code ở vị trí đó.
2. Agent **BẮT BUỘC** mở file `.agents/memory/user_profile.md` hoặc `.agents/memory/technical_decisions.md` để ghi nhận sự thay đổi này.
3. Điều này đảm bảo dù cuộc hội thoại có bị compact 10 lần hay người dùng mở chat mới vào ngày mai, Agent vẫn nhớ chính xác 100%.
