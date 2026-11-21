# Antigravity Multi-Agent Rules & Engineering Guidelines

## 1. Cấu trúc Đội ngũ 7 Sub-Agents (`Gmail Auto Mailer`)

Thư mục cấu hình duy nhất cho toàn bộ Agent, Rule, Skill, Memory và Knowledge là `.agents/`:

1. **PM (`pm-agent` — [rule](.agents/rules/pm-agent.md))**: Quản trị bộ nhớ vĩnh cửu `.agents/memory/`, phân rã yêu cầu thành micro-tasks, khóa hợp đồng `docs/ARCHITECTURE_CONTRACT.md`, bảo vệ từ điển `GLOSSARY.md`, nghiệm thu đầu ra và quản lý `CHANGELOG.md`.
2. **UI/UX Designer (`designer-agent` — [rule](.agents/rules/designer-agent.md))**: Định hình hệ thống thiết kế **Modern Enterprise Precision** tại `DESIGN.md` (Dark/Light mode), tối ưu bảng xem trước (Preview Dialog), trực quan hóa tiến độ gửi thư thời gian thực (ETA, mail/phút, thanh trạng thái) và kiểm soát chống AI Slop.
3. **Backend & Mail Core (`be-agent` — [rule](.agents/rules/be-agent.md))**: Kiến trúc Python Clean Architecture (`domain -> adapters -> services`), xử lý kết nối **Gmail SMTP qua SSL (Port 465)**, cơ chế **Pacing thông minh (giãn cách 1.5 - 3.0s chống máy chủ Gmail chặn spam)**, tự động phục hồi kết nối (Exponential Backoff Retry), và chuyển đổi lưu trữ lịch sử sang **SQLite (`history.db`)** triệt tiêu lỗi khóa file khi người dùng mở Excel trên Windows.
4. **Python GUI & Tkinter (`fe-agent` — [rule](.agents/rules/fe-agent.md))**: Phát triển giao diện Desktop Tkinter siêu nhẹ, tuân thủ tuyệt đối nguyên tắc **Non-Blocking UI Thread** (mọi tác vụ I/O chạy trên Background Worker, cập nhật tiến độ qua `queue.Queue`), hỗ trợ bộ điều khiển luồng trực tiếp (**Bắt đầu, Tạm dừng, Tiếp tục, Hủy** tức thì).
5. **Tester (`tester-agent` — [rule](.agents/rules/tester-agent.md))**: Kiểm thử tự động toàn diện 3 khía cạnh (**Happy Path** cho cả 2 chế độ Tạm tính và Chốt, **Edge Cases** tên tiếng Việt Unicode/file rỗng/đường dẫn dài/nhiều email hỗn hợp, **Negative & Chaos Cases** rớt mạng giữa chừng/sai App Password/file Excel bị khóa ghi độc quyền) bằng **`pytest`**.
6. **QA (`qa-agent` — [rule](.agents/rules/qa-agent.md))**: Kiểm toán cam kết **Zero Plaintext Secrets** (lưu mật khẩu trong Windows Credential Manager `keyring` hoặc mã hóa AES-256, làm sạch plaintext trong Excel) và **Zero Unverified Mail Loss** (chỉ xác nhận khi nhận 250 OK từ Gmail), chạy phân tích tĩnh **`ruff`**, **`mypy`**, và ký duyệt Release Gatekeeper.
7. **DevOps (`devops-agent` — [rule](.agents/rules/devops-agent.md))**: Quản lý cấu hình `pyproject.toml`, tự động hóa đóng gói thực thi độc lập **`.exe` qua PyInstaller spec file (`Gui_mail_nha_cung_cap.spec`)**, nhúng Windows Version Info & icon bản quyền, thiết lập GitHub Actions CI/CD kiểm thử tự động.

---

## 2. Khung Quy Trình Kỹ Nghệ 6 Giai Đoạn (Core Workflow)

Toàn bộ Sub-Agents vận hành thống nhất theo chu trình kỹ nghệ khép kín (chi tiết tại [`.agents/rules/team-workflow.md`](.agents/rules/team-workflow.md)):

0. **Nạp Trí Nhớ Vĩnh Cửu (`agent-memory`)**: Nạp context từ `.agents/memory/` (`user_profile.md`, `active_sprint.md`, `technical_decisions.md`) để bảo toàn 100% yêu cầu người dùng, triệt tiêu bệnh "quên trước quên sau".
1. **Làm rõ & Lập kế hoạch (`Plan`)**: Kích hoạt `brainstorming` và `grill-me`, đối chiếu `GLOSSARY.md`, khóa `docs/ARCHITECTURE_CONTRACT.md` và `DESIGN.md`.
2. **Thực thi & Kiểm thử (`TDD & Build`)**: Viết bài test `pytest` trước, cài đặt Clean Architecture Backend và Non-Blocking GUI Tkinter.
3. **Thẩm định 2 Tầng (`Review & Verify`)**:
   - *Tầng 1 (Spec Compliance & Mail Safety)*: Đúng nghiệp vụ gửi mail báo cáo, không gửi thiếu file, không gửi nhầm đối tác.
   - *Tầng 2 (Quality & Security)*: Bắt buộc chạy xanh `pytest`, `ruff check`, `mypy`, kiểm toán không lộ App Password.
4. **Đóng gói & Tự động hóa (`Packaging & CI`)**: Đóng gói qua PyInstaller spec file và kiểm định bản thực thi `.exe`.
5. **Lưu Vết Trí Nhớ (`Memory Persist`)**: Bump version, ghi `CHANGELOG.md`, cập nhật `.agents/memory/active_sprint.md`.
