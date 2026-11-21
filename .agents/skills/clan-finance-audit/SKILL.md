---
name: clan-finance-audit
description: >-
  Quy chuẩn và hướng dẫn nghiệp vụ quản lý tài chính, quỹ dòng họ minh bạch: phân loại quỹ (Quỹ Thường niên,
  Quỹ Khuyến học, Quỹ Tu bổ), quy trình tạo - duyệt - hủy chứng từ (PENDING / APPROVED / VOIDED),
  nguyên tắc bất biến Soft-Void kèm hoàn nguyên số dư tự động, và bảo vệ quỹ đã phát sinh giao dịch.
---

# Clan Finance & Audit Skill (Quản lý Sổ Quỹ & Minh Bạch Tài Chính)

Tài chính dòng họ là khu vực cực kỳ nhạy cảm, dễ phát sinh tranh cãi nếu thiếu minh bạch. Bộ kỹ năng này định nghĩa các nguyên tắc kế toán nội bộ và thiết kế giao diện giúp xây dựng niềm tin tuyệt đối trong họ tộc (chi tiết quyết định kiến trúc tại `docs/adr/0003-finance-soft-void-immutability.md`).

## 1. Phân loại Cơ cấu Quỹ Dòng họ

Hệ thống quản lý tài chính tách bạch rõ ràng các quỹ chuyên biệt, không gộp lẫn:
1. **Quỹ Thường Niên & Giỗ Chạp**:
   - Nguồn thu: Đóng góp định mức theo suất đinh hoặc hộ gia đình hàng năm.
   - Mục đích chi: Hương hoa, lễ vật giỗ tổ hàng năm, thăm viếng người đau ốm, hiếu hỷ.
2. **Quỹ Tu Bổ Từ Đường**:
   - Nguồn thu: Các khoản công đức tự nguyện của con cháu, dâu rể và các chi họ.
   - Mục đích chi: Sơn sửa nhà thờ tổ, tu bổ bia mộ tiền nhân, sắm sửa đồ thờ cúng.
3. **Quỹ Khuyến Học & Tài Năng Trẻ**:
   - Nguồn thu: Các mạnh thường quân, con cháu tài trợ chuyên biệt cho giáo dục.
   - Mục đích chi: Phần thưởng học sinh giỏi các cấp, thi đỗ đại học, thủ khoa, thạc sĩ, tiến sĩ.

## 2. Nguyên tắc Bất biến & Hủy Chứng từ Có Lưu Vết (`Soft-Void`)

- **Quy tắc Vàng**:
  1. **Cấm sửa chứng từ đã duyệt**: Mọi giao dịch thu - chi (`transactions`) hoặc công đức (`donations`) ở trạng thái `APPROVED` hoặc `VOIDED` đều từ chối chỉnh sửa với mã lỗi `409 IMMUTABLE_APPROVED`. Chỉ chứng từ đang `PENDING` mới được phép chỉnh sửa nội dung.
  2. **Cấm xóa vật lý chứng từ đã duyệt (No Hard Delete)**: Thao tác hủy trên chứng từ `APPROVED` thực hiện **Soft-Void** — chuyển `status = 'VOIDED'`, ghi nhận đầy đủ `voidedAt`, `voidedBy`, `voidReason`, đồng thời **tự động hoàn nguyên số dư quỹ (`funds.balance`)** trong cùng một SQLite transaction nguyên tử. Nếu gọi hủy lần hai trên chứng từ đã `VOIDED`, trả về `409 ALREADY_VOIDED`.
  3. **Bảo vệ Quỹ có lịch sử giao dịch**: Cấm xóa quỹ (`DELETE /api/funds/:id`) nếu quỹ đã có bất kỳ giao dịch nào liên kết (`409 FUND_HAS_TRANSACTIONS`).
- **Quy trình Vòng đời Chứng từ**:
  - `PENDING`: Con cháu báo công đức hoặc thủ quỹ lập phiếu chờ kiểm tra (chưa cộng/trừ vào `funds.balance`, chưa hiển thị trên sổ công khai).
  - `APPROVED`: Ban Trị Sự đối soát và phê duyệt -> cộng/trừ `funds.balance` nguyên tử và công khai trên trang Sổ Quỹ / Công Đức.
  - `VOIDED`: Chứng từ hủy có lý do kiểm toán -> hoàn nguyên `funds.balance`, ẩn khỏi báo cáo công khai nhưng hiển thị gạch ngang kèm nhãn `ĐÃ HỦY` trong trang Quản Trị để hậu kiểm.

## 3. Quản lý Chứng từ & Hóa đơn (Offload Storage)

- Khuyến khích đính kèm ảnh hóa đơn, biên nhận hoặc chứng từ chuyển khoản (`evidenceImage` / `receiptUrl`).
- Tuyệt đối không lưu file media dung lượng lớn tràn ổ đĩa container; ưu tiên nén ảnh WebP hoặc dùng URL lưu trữ ngoài để bảo vệ hạn mức **2 GB Storage** trên Botkeep.cloud.

## 4. Báo cáo Tài chính & Đối soát

1. **Dashboard Trực quan**:
   - Hiển thị thẻ tổng hợp: Số dư hiện tại theo từng quỹ, tổng thu, tổng chi (chỉ tính các chứng từ `APPROVED`).
   - Trong Quản Trị (`AdminFinanceLedgerSection`), hỗ trợ lọc theo trạng thái (`Tất cả`, `APPROVED`, `PENDING`, `VOIDED`) và xem rõ lý do hủy chứng từ.
2. **Tích hợp VietQR / Thông tin Chuyển khoản**:
   - Hỗ trợ hiển thị thông tin tài khoản thủ quỹ và cú pháp chuyển khoản rõ ràng để con cháu phương xa đóng góp thuận tiện.
