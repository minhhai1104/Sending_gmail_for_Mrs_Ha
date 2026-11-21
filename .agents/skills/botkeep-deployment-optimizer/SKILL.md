---
name: botkeep-deployment-optimizer
description: >-
  Kỹ năng tối ưu hóa tài nguyên và quy trình đóng gói, triển khai ứng dụng trên nền tảng Botkeep.cloud:
  kiểm soát hạn mức hạ tầng (2 GB RAM, 2 GB Storage, 1.5 vCPU), mô hình Single-Process Node.js 22 + Express + node:sqlite,
  lắng nghe cổng 0.0.0.0:$PORT, bảo toàn CSDL SQLite production qua versioned migrations + SFTP deploy an toàn,
  và tự động backup qua Telegram Bot. Kích hoạt khi build, cấu hình môi trường, kiểm tra tài nguyên hoặc triển khai web.
---

# Botkeep Deployment & Resource Optimization Skill

Bộ kỹ năng này hướng dẫn đóng gói và vận hành ứng dụng trên nền tảng đám mây Botkeep.cloud bảo đảm hiệu năng cao và an toàn dữ liệu tuyệt đối trong giới hạn tài nguyên máy chủ (**2 GB RAM, 2 GB Storage, 1.5 vCPU**).

## 1. Đặc thù Hạ tầng Botkeep.cloud

- **Cấu hình tài nguyên**: **2 GB RAM, 2 GB Storage, 1.5 vCPU**.
- **Môi trường thực thi**:
  - Chạy dạng **Single-Process Lean Monolith** (Node.js 22 LTS + Express + native `node:sqlite`), không cần Nginx hay DB server riêng.
  - Ứng dụng phục vụ đồng thời REST API (`/api/*`) và giao diện tĩnh (`client/dist`) trên cùng cổng `process.env.PORT || process.env.SERVER_PORT || 5000` gắn vào `0.0.0.0` (cổng phụ `3000` mặc định tắt, chỉ mở khi `ENABLE_SECONDARY_PORT=true`).
  - Endpoint giám sát sức khỏe: `/health` và `/api/health` trả về phiên bản động đọc từ `package.json`.

## 2. Kiến trúc Tối ưu Bộ nhớ, Ổ cứng & Bảo toàn SQLite Production

```mermaid
flowchart LR
    Browser["Client (Điện thoại / Máy tính)"] -->|HTTPS / Cloudflare| BotkeepNode["Botkeep.cloud (2GB RAM · 2GB Storage · 1.5 vCPU)"]

    subgraph Botkeep ["Lean Monolith Runtime (~65–100MB RAM thực tế)"]
        BotkeepNode -->|Serve Static| FrontendBundle["client/dist/ (Vite React Bundle)"]
        BotkeepNode -->|REST API| BackendAPI["server/dist/index.cjs (Express + node:sqlite)"]
        BackendAPI -->|PRAGMA journal_mode=DELETE| SQLiteFile["data/giapha.db (Single Authoritative DB)"]
        SQLiteFile -.->|Pre-migration VACUUM INTO| Snapshots["data/snapshots/*.db"]
    end

    BackendAPI -->|Cron Auto-Backup (.db.gz)| TelegramBot["Telegram Private Channel"]
```

### Các quy tắc sống còn:
1. **Bảo toàn 100% `data/giapha.db` trên Production**:
   - `scripts/build.mjs` **không bao giờ** copy `data/giapha.db` vào `server/dist/`.
   - `scripts/auto_deploy_sftp.py` chỉ đồng bộ `server/dist/index.cjs`, `client/dist/`, `package.json`, `package-lock.json` — **tuyệt đối không chạm vào `data/giapha.db` trên máy chủ từ xa**.
   - Mọi thay đổi cấu trúc bảng phải viết thành migration có đánh số phiên bản trong `runVersionedMigrations()` (`server/src/db/database.ts`): hệ thống tự tạo bản chụp `VACUUM INTO` tại `data/snapshots/` trước khi chạy DDL trong transaction và lưu lịch sử vào `schema_migrations` (xem `docs/adr/0001-safe-production-sqlite-migrations.md`).
2. **Tối ưu RAM & SQLite**:
   - Khởi chạy với cờ `--experimental-sqlite --max-old-space-size=512` (giữ heap V8 tối đa 512 MB; thực tế vận hành ổn định ~65–100 MB RAM).
   - Dùng `PRAGMA journal_mode = DELETE`, `PRAGMA foreign_keys = ON`, `PRAGMA busy_timeout = 5000` để toàn bộ dữ liệu luôn nằm gọn trong một tệp `data/giapha.db` duy nhất, tránh phát sinh file phụ `-wal`/`-shm` khi sao lưu hoặc truyền SFTP (xem `docs/adr/0002-sqlite-journal-mode-delete.md`).
3. **Không lưu rác trên ổ cứng 2 GB**:
   - Giữ tối đa 5 bản snapshot pre-migration gần nhất trong `data/snapshots/`; ưu tiên lưu ảnh dung lượng lớn qua dịch vụ ngoài hoặc nén gọn WebP.

## 3. Chiến lược Sao lưu Dự phòng Tự động (Disaster Recovery)

1. **Tự động hàng ngày qua Telegram**: Dịch vụ `telegramBackupService` tạo bản snapshot nhất quán bằng `VACUUM INTO`, nén `.gz` và gửi về kênh Telegram riêng tư của Ban Trị Sự.
2. **Thủ công qua SuperAdmin Console**: Tài khoản `Administrator` tải trực tiếp bản sao lưu qua `GET /api/admin/backup` (xác thực Bearer token) hoặc phục hồi an toàn từ giao diện Quản trị Hệ thống.
