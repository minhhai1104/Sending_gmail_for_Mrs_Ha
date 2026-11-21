---
name: vercel-react-best-practices
description: >-
  Tập hợp các quy chuẩn kỹ thuật cao cấp về React & Next.js/Vite theo tiêu chuẩn kỹ nghệ của Vercel:
  kiến trúc component sạch, phân tách logic và UI, tối ưu render & re-render, triệt tiêu Layout Shift (CLS),
  quản lý state cục bộ thông minh, lazy-loading và chuẩn hóa TypeScript.
  Kích hoạt khi viết code React, tối ưu hiệu năng frontend hoặc review mã nguồn FE.
---

# Vercel React Best Practices (Kỹ nghệ React Chuẩn Mực & Hiệu Năng Cao)

Bộ kỹ năng này đảm bảo mã nguồn React trong dự án đạt tiêu chuẩn kỹ thuật cấp doanh nghiệp, chạy mượt mà ngay cả trên các thiết bị cấu hình yếu và đường truyền mạng hạn chế.

## 1. Kiến trúc Thành phần (Component Composition & Architecture)

- **Nguyên tắc Trách nhiệm Đơn lẻ (Single Responsibility Principle)**:
  - Một component không được vừa gọi API, vừa xử lý logic tính toán ngày âm, vừa dàn dựng giao diện 500 dòng.
  - Tách bạch: `Container / Page` (lấy dữ liệu qua hook) -> `Presentational Components` (chỉ nhận props và render UI thuần túy).
- **Phân tách Custom Hooks**:
  - Đóng gói toàn bộ logic phức tạp vào hook riêng biệt: `useLunarDate()`, `useFamilyTree()`, `useFinanceSummary()`, `useAuthSession()`.

## 2. Quản lý State Thông minh (State Colocation)

- **Đặt State ở vị trí thấp nhất có thể (State Colocation)**:
  - Không nhét tất cả vào Context hoặc Zustand/Redux toàn cục. Nếu ô tìm kiếm thành viên chỉ dùng trong trang Cây Gia Phả, hãy giữ state trong trang đó.
- **Dẫn xuất State (Derived State) thay vì tạo state dư thừa**:
  - Không tạo `const [filteredMembers, setFilteredMembers] = useState([])`.
  - Thay vào đó: `const filteredMembers = useMemo(() => members.filter(...), [members, searchKeyword])`.

## 3. Tối ưu Hiệu năng Render (Performance & Zero Layout Shift)

1. **Khóa Key Ổn định trong Danh sách (Stable Keys)**:
   - **Tuyệt đối không dùng `index` làm `key`** trong vòng lặp `map()` của danh sách phả hệ hoặc thu chi:
     ```tsx
     // ❌ Sai: <MemberCard key={index} ... />
     // ✅ Đúng: <MemberCard key={member.id} ... />
     ```
2. **Triệt tiêu hiện tượng Giật bố cục (Zero Cumulative Layout Shift - CLS)**:
   - Luôn định nghĩa trước tỷ lệ khung hình hoặc kích thước khung ảnh cho ảnh chân dung thành viên:
     ```tsx
     <div className="w-16 h-16 rounded-full overflow-hidden bg-stone-100 aspect-square shrink-0">
       <img src={avatarUrl} alt={fullName} loading="lazy" className="w-full h-full object-cover" />
     </div>
     ```
3. **Lazy Loading cho các Thư viện Nặng (Code Splitting)**:
   - Thư viện vẽ cây phả hệ (D3 / SVG Canvas) và thư viện xuất Excel/PDF khá nặng (~300KB - 500KB).
   - Bắt buộc dùng `React.lazy()` và `Suspense` để chỉ tải mã nguồn khi người dùng mở trang Cây Gia Phả hoặc bấm xuất báo cáo:
     ```tsx
     const FamilyTreeCanvas = React.lazy(() => import('@/features/tree/FamilyTreeCanvas'));
     ```

## 4. Chuẩn mực TypeScript (Strict Typing)

- Không bao giờ dùng `any`. Luôn định nghĩa rõ ràng `interface` / `type` cho các thực thể:
  ```typescript
  export interface Member {
    id: string;
    fullName: string;
    gender: 'MALE' | 'FEMALE';
    generation: number;
    branch: string;
    fatherId?: string | null;
    motherId?: string | null;
    birthLunarYear?: number;
    deathLunarDate?: {
      day: number;
      month: number;
      isLeap: boolean;
    };
    isAlive: boolean;
  }
  ```
- Props của component luôn được đặt tên rõ ràng, có giá trị mặc định hợp lý và kiểu dữ liệu tường minh.
