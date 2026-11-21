---
name: genealogy-tree-engine
description: >-
  Hướng dẫn và quy chuẩn thiết kế, xử lý dữ liệu gia phả dòng họ: mô hình quan hệ huyết thống
  (Đời, Chi, Phái, Thê/Thiếp, Cha-Con), thuật toán chống lặp vô tận, hiển thị sơ đồ cây tương tác (D3/SVG),
  và cơ chế xuất/nhập dữ liệu Excel/GEDCOM/JSON. Kích hoạt khi phát triển hoặc sửa đổi tính năng Cây gia phả.
---

# Genealogy Tree Engine Skill (Quy chuẩn Xử lý Phả hệ Dòng họ)

Bộ kỹ năng này hướng dẫn cách tổ chức mô hình dữ liệu, xử lý thuật toán phả hệ và biểu diễn giao diện cây gia phả chuẩn văn hóa dòng họ Việt Nam.

## 1. Cấu trúc Mô hình Dữ liệu (Genealogy Schema)

Dữ liệu thành viên trong họ tộc Việt Nam cần phân tách rõ giữa huyết thống dòng họ (nội tộc) và phối ngẫu (dâu/rể):

### Các trường cốt lõi của mỗi Thành viên (`Member`):
- `id`: Định danh duy nhất (UUID hoặc mã thành viên `DH-xxxxx`).
- `fullName`: Họ và tên đầy đủ.
- `gender`: Giới tính (`MALE`, `FEMALE`).
- `generation`: Đời thứ mấy tính từ Thủy tổ (Đời 1, Đời 2, ...).
- `branch`: Chi / Ngành / Phái (Ví dụ: "Chi Trưởng", "Chi Hai", "Chi Ba").
- `fatherId`: ID người cha (Khóa ngoại trỏ về `Member`, huyết thống nối dõi).
- `motherId`: ID người mẹ.
- `orderInFamily`: Thứ bậc sinh trong gia đình (Con trưởng, Con thứ 2, Con út...).
- `isAlive`: Còn sống (`true`) hay Đã khuất (`false`).
- `birthDate`: Ngày tháng năm sinh (Dương lịch hoặc Âm lịch).
- `deathDate`: Ngày mất (ghi rõ ngày Âm lịch để tính ngày giỗ).
- `burialPlace`: Nơi an táng / Mộ phần (tọa độ GPS, sơ đồ khu mộ dòng họ).
- `avatarUrl`: Đường dẫn ảnh chân dung (lưu trên Cloudinary / R2, không lưu trên host).
- `biography`: Phả ký, tiểu sử, sự nghiệp, học hàm học vị, công đức.

### Bảng Quan hệ Phối ngẫu (`Marriage`):
- Hỗ trợ quan hệ hôn nhân: `husbandId`, `wifeId`, `marriageOrder` (Vợ cả, Vợ thứ/Kế thất).

## 2. Quy tắc Nghiệp vụ Phả hệ (Business Rules)

1. **Chống vòng lặp tổ tiên (Cycle Detection)**:
   - Trước khi lưu `fatherId` hoặc `motherId`, luôn chạy thuật toán DFS/BFS để đảm bảo người cha/mẹ không phải là con cháu của thành viên đó (`fatherId` không nằm trong danh sách hậu duệ).
2. **Quy tắc phân nhánh đời (Generational Leveling)**:
   - Thế hệ con (`child.generation`) luôn bằng `father.generation + 1`.
3. **Phân chia hiển thị theo Đời & Chi**:
   - Khi cây phả hệ lớn (trên 500 người), không tải toàn bộ cây một lúc. Hỗ trợ lazy-loading (mở rộng/thu gọn nhánh theo từng Chi hoặc tải tối đa 3-4 thế hệ kế tiếp khi người dùng bấm vào node).

## 3. Thư viện & Kỹ thuật Vẽ Cây Tương tác (UI/UX)

- Sử dụng thư viện trực quan hóa: `d3-org-chart`, `family-chart` hoặc SVG Canvas tùy biến.
- **Tính năng UI bắt buộc**:
  - Zoom in / Zoom out / Reset view.
  - Pan (kéo rê toàn màn hình).
  - Tìm kiếm thành viên trên cây (nhập tên -> tự động zoom tới node đó).
  - Phân màu node: Nam (Xanh), Nữ (Hồng), Đã mất (Viền xám/icon dải lụa), Người có công (Huy hiệu vàng).
  - Nút xuất file: Hỗ trợ xuất cây gia phả ra file ảnh PNG chất lượng cao hoặc PDF khổ lớn (A0/A1) để in treo từ đường.
