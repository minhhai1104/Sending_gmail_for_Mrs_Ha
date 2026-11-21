---
name: repo-map
description: "Tự động quét cấu trúc mã nguồn toàn bộ repository, trích xuất cây thư mục, số dòng code và các exported symbols (hàm, class, interface, route) thành bản đồ mã nguồn REPO_MAP.md. Giúp Agent có cái nhìn tổng quan ngay lập tức mà không tốn token đọc mò từng file."
---

# Deterministic Repo Map Skill (`repo-map`)

Kỹ năng quét và kiến tạo bản đồ mã nguồn dạng cây symbol AST (dựa trên mô hình của Aider Repo-Map và `cyanheads/repo-map`).

---

## 1. Mục Đích

- Giảm thiểu 90% chi phí tìm kiếm file trong các phiên làm việc của AI Agent.
- Tự động thống kê toàn bộ các file mã nguồn của Backend (`server/src`), Frontend (`client/src`) và Scripts (`scripts/`).
- Trích xuất tự động các exported symbols:
  - `fn <tên_hàm>`: Các hàm logic được xuất khẩu.
  - `class <tên_lớp>`: Các Controller, Service, Repository, Cache classes.
  - `interface <tên_interface>` / `type <tên_type>`: Các kiểu dữ liệu cốt lõi.
  - `route <METHOD> <PATH>`: Các API endpoints Express đã khai báo.

---

## 2. Cách Sử Dụng

Khi Agent cần cập nhật bản đồ mã nguồn sau khi tạo thêm file mới hoặc refactor:

```bash
# Chạy script tự động quét và sinh file REPO_MAP.md
node scripts/generate_repo_map.mjs

# Hoặc qua npm script
npm run map
```

Bản đồ được xuất tự động tại `.agents/knowledge/REPO_MAP.md` (đồng thời có thể tham chiếu từ `.planning/codebase/REPO_MAP.md`).
Agent có thể đọc file này để định vị tức thì module cần can thiệp.
