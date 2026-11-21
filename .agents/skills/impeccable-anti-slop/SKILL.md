---
name: impeccable-anti-slop
description: >-
  Chuyên gia "soi" và loại trừ lỗi thiết kế AI kinh điển (pbakaus/impeccable - 90.2k stars): 24 lệnh kiểm định
  và 61 quy tắc vàng giúp phát hiện và cải thiện giao diện rập khuôn, diệt tận gốc gradient tím rịm sáo rỗng,
  viền phát sáng neon, hiệu ứng chuyển động lố, khoảng cách lộn xộn, chữ mờ thiếu tương phản, nút bấm tròn ủng,
  và ép giao diện đạt độ hoàn thiện của sản phẩm thương mại thật. Kích hoạt khi UI Audit, review component, hoặc trước khi release.
---

# Impeccable Anti-Slop Skill (pbakaus/impeccable - 24 Lệnh & 61 Quy Tắc Vàng)

Kế thừa nguyên bản tinh hoa từ repository **`pbakaus/impeccable`** (hơn 90.200 sao trên GitHub), bộ kỹ năng này đóng vai trò là "Thanh tra Thẩm mỹ Cấp cao", rà soát từng dòng code CSS/Tailwind để phát hiện và triệt tiêu toàn bộ các mẫu thiết kế "lười biếng", giả tạo mà AI thường tự động sinh ra.

---

## 🛠️ 24 Lệnh Kiểm Định Giao Diện Nhanh (Audit Commands)

Khi tiến hành kiểm định một màn hình hoặc component, `designer-agent` và `qa-agent` thực thi 24 lệnh soi xét:
1. `audit:contrast` — Đo tỷ lệ tương phản văn bản theo chuẩn WCAG (chữ thường >= 4.5:1, chữ lớn >= 3.0:1).
2. `audit:hierarchy` — Kiểm tra phân cấp thị giác: Đâu là điểm nhìn đầu tiên (Hero), thứ hai và thứ ba?
3. `audit:colors` — Kiểm tra số lượng màu sắc: Có vượt quá 3 nhóm màu chính không? Có bị gradient tím/xanh AI Slop không?
4. `audit:spacing` — Kiểm tra nhịp điệu khoảng trắng (Spatial Rhythm): Có tuân thủ hệ số 8pt (8, 16, 24, 32, 48, 64px) không?
5. `audit:typography` — Kiểm tra cặp font chữ: Đã dùng đúng font Serif di sản và font Sans-Serif công thái học chưa?
6. `audit:elevation` — Kiểm tra bóng đổ: Có dùng bóng 3 lớp tự nhiên thay vì viền đen thô kệch không?
7. `audit:borders` — Kiểm tra viền: Có viền vi mô bắt sáng (Inner Highlights) 1px không?
8. `audit:touch-targets` — Kiểm tra vùng chạm di động: Mọi nút bấm và link có đạt tối thiểu 44x44px không?
9. `audit:empty-states` — Kiểm tra trạng thái rỗng: Khi chưa có dữ liệu giỗ, phả hệ hoặc thu chi có hiển thị ấm áp không?
10. `audit:loading-states` — Kiểm tra trạng thái chờ: Có Skeleton loader cùng kích thước với dữ liệu thật không?
11. `audit:error-states` — Kiểm tra trạng thái lỗi: Có báo lỗi inline tức thời dưới ô nhập liệu không?
12. `audit:motion` — Kiểm tra chuyển động: Thời gian phản hồi có dưới 200ms và dùng đường cong vật lý lò xo không?
13. `audit:focus-visible` — Kiểm tra tiêu điểm bàn phím: Bấm phím Tab có hiển thị vòng `ring-2` rõ nét không?
14. `audit:active-states` — Kiểm tra cảm giác xúc giác: Bấm chuột/chạm tay có lún nhẹ `active:scale-[0.98]` không?
15. `audit:line-length` — Kiểm tra độ dài dòng đọc: Có giới hạn từ 60–75 ký tự/dòng (`max-w-prose`) không?
16. `audit:padding-consistency` — Kiểm tra lề trong: Padding trên/dưới, trái/phải của các thẻ card có đồng nhất không?
17. `audit:semantic-html` — Kiểm tra ngữ nghĩa HTML: Có dùng đúng `<article>`, `<time>`, `<header>` thay vì lạm dụng `<div>` không?
18. `audit:image-aspect` — Kiểm tra tỷ lệ khung ảnh: Khung ảnh có định sẵn `aspect-ratio` để triệt tiêu giật layout (CLS) không?
19. `audit:icon-clutter` — Kiểm tra mật độ icon: Có bị nhét icon bừa bãi trước mọi danh từ không?
20. `audit:badge-overuse` — Kiểm tra mật độ tag: Có bị lạm dụng tag màu mè xanh đỏ tím vàng không?
21. `audit:footer-cleanliness` — Kiểm tra chân trang: Footer có tinh gọn, tôn nghiêm, tránh nhồi nhét link rác không?
22. `audit:dark-light-balance` — Kiểm tra cân bằng sáng tối: Màu đen có phải than đen ấm (`#1c1917`) thay vì đen kịt `#000` không?
23. `audit:layout-break` — Kiểm tra phá vỡ lưới: Có áp dụng Bento Grid / Split Screen thay vì lưới 3 cột đều chằn chặn không?
24. `audit:senior-friendly` — Kiểm tra thân thiện người cao tuổi: Cỡ chữ có đủ lớn và ngôn từ có thuần Việt không?

---

## 📋 61 Quy Tắc Vàng Loại Trừ Giao Diện Rập Khuôn

### I. Màu Sắc & Ánh Sáng (12 Quy Tắc)
1. Cấm tiệt gradient tím - xanh AI mặc định (`from-purple-600 to-indigo-600`).
2. Cấm viền phát sáng Neon (`0 0 25px rgba(...)`).
3. Chỉ dùng kính mờ (Glassmorphism) cho Thanh điều hướng cố định; cấm dùng kính mờ trên card nội dung.
4. Chữ chính luôn là than ấm (`#1c1917`), chữ phụ là xám đá đậm (`#44403c`); cấm dùng chữ mờ tịt `#9ca3af`.
5. Không dùng màu đen tuyệt đối `#000000`; dùng đen ấm hoặc than trầm `#18181b`.
6. Tỷ lệ tương phản chữ/nền tối thiểu 4.5:1 (WCAG AA).
7. Màu điểm nhấn (Accent) không chiếm quá 10% diện tích bề mặt.
8. Màu sắc phải có ý nghĩa biểu đạt: Đỏ son thờ cúng, Vàng kim tôn vinh, Xanh ngọc bích sinh sôi.
9. Không dùng màu sắc làm dấu hiệu phân biệt duy nhất (phải đi kèm chữ/icon).
10. Màu viền luôn mảnh và tế vi (`border-stone-200` hoặc alpha 60%).
11. Bề mặt các card nằm trên canvas phải có sự phân tầng rõ rệt (Surface Elevation).
12. Các trạng thái hover chỉ thay đổi sắc độ liền kề (ví dụ: đỏ son 800 sang đỏ son 900).

### II. Bố Cục & Không Gian (15 Quy Tắc)
13. Cấm nút con nhộng (`rounded-full`) bừa bãi cho mọi form và card.
14. Bo góc tinh tế: `sm: 6px`, `md: 10px`, `lg: 16px`, `xl: 24px`.
15. Khoảng trắng là một thành phần thiết kế có chủ đích (Generous Whitespace).
16. Bố cục theo hệ số 8pt Grid: toàn bộ padding, margin, gap chia hết cho 4 hoặc 8.
17. Bẻ gãy lưới 3 cột đơn điệu bằng Asymmetric Bento Grid (ô chính rộng gấp đôi ô phụ).
18. Luôn giới hạn độ rộng đọc văn bản phả ký `max-w-2xl` hoặc `max-w-prose`.
19. Bố cục Mobile-First: Mọi giao diện phải hoàn hảo trên màn hình điện thoại 375px.
20. Không bao giờ hardcode kích thước pixel cố định (`w-[600px]`) gây vỡ layout mobile.
21. Thao tác bảng biểu dữ liệu nhiều cột phải có thanh cuộn ngang `overflow-x-auto`.
22. Cột mốc thế hệ phả hệ phải giữ khoảng cách an toàn tối thiểu 72px với thẻ thành viên gần nhất.
23. Thanh công cụ phả hệ phải tinh gọn trên 1 dòng duy nhất.
24. Căn giữa Khởi Tổ (Nút Home) phải neo chính xác tâm viewport màn hình.
25. Các nút hành động chính (CTA) phải nằm trong vùng ngón tay cái (Thumb Zone) trên điện thoại.
26. Khung ảnh di tích Từ đường phải phủ lớp chuyển tiếp gradient tinh tế với chữ tiêu đề.
27. Footer tinh gọn, trang nghiêm, tôn vinh Tộc ước và cội nguồn tiên tổ.

### III. Typography & Văn Bản (12 Quy Tắc)
28. Tiêu đề trang trọng dùng font có chân chuẩn quốc gia: `Noto Serif` (hỗ trợ 100% dấu tiếng Việt hoa).
29. Dữ liệu danh bạ dùng font không chân hiện đại: `Be Vietnam Pro`.
30. Cấm lỗi nhảy font chữ (Font Fallback Clash) khi gõ dấu tiếng Việt phức hợp (`NGUYỄN BÁ`).
31. Chiều cao dòng (Line Height) thoáng đãng: 1.5 - 1.6 cho body text; 1.15 - 1.25 cho tiêu đề.
32. Cấm văn bản giả kiểu `Lorem Ipsum` hoặc `Test 123` trong mã nguồn xuất xưởng.
33. Ngôn từ phải thuần Việt, trang trọng: "Sổ Quỹ Dòng Họ", "Cây Phả Hệ", "Ban Trị Sự".
34. Phân cấp cỡ chữ rõ ràng: Display (36-40px), Heading (20-26px), Body (14-16px), Caption (11-12px).
35. Chữ hoa chỉ dùng cho tên riêng trang trọng hoặc huy hiệu; cấm viết hoa toàn bộ đoạn văn.
36. Tên thành viên đã khuất phải đi kèm dải băng tang đen tưởng niệm trang nghiêm.
37. Dòng phối ngẫu Hiền Thê phải được gắn kết thẩm mỹ liền kề thẻ người chồng.
38. Khoảng cách chữ (Letter Spacing) âm nhẹ cho tiêu đề lớn (`-0.5px`) để chữ chắc chắn.
39. Ô nhập liệu form trên mobile phải có cỡ chữ tối thiểu 16px để chống tự động zoom vỡ khung.

### IV. Chuyển Động & Xúc Giác (10 Quy Tắc)
40. Cấm hiệu ứng chuyển động thô cứng `hover:scale-110 duration-500`.
41. Áp dụng chuyển động vật lý lò xo (Spring Physics) của Emil Kowalski: `cubic-bezier(0.16, 1, 0.3, 1)`.
42. Thời gian phản hồi tương tác vi mô luôn dưới 200ms (`duration-150` đến `duration-200`).
43. Chỉ animate trên thuộc tính `transform` và `opacity` để đạt hiệu năng 60fps trên GPU.
44. Hiệu ứng xúc giác lún xuống khi bấm chuột/chạm tay: `active:scale-[0.98] active:duration-75`.
45. Nút bấm quan trọng có viền vi mô bắt sáng mép trên (`inset 0 1px 0 rgba(255,255,255,0.25)`).
46. Modal trượt trên điện thoại sử dụng Bottom Drawer Sheet có thanh kéo tự nhiên.
47. Đồng hồ đếm ngược Giỗ Tổ có hiệu ứng lật số dát vàng êm ái.
48. Thao tác kéo rê chuột (Pan) trên Cây gia phả phải mượt mà không khựng hình.
49. Luôn có phương án tắt chuyển động cho người dùng nhạy cảm (`motion-reduce:transition-none`).

### V. Trạng Thái & Khả Tiếp Cận (12 Quy Tắc)
50. Đầy đủ 4 trạng thái hệ thống: Loading Skeleton, Empty State, Error Inline, Success Feedback.
51. Skeleton loader phải có cùng kích thước và hình khối với card dữ liệu thật.
52. Báo lỗi form phải nằm ngay dưới ô nhập liệu với hướng dẫn khắc phục cụ thể.
53. Điều hướng bàn phím 100%: Mọi chức năng dùng chuột được thì phải dùng phím Tab/Enter được.
54. Vòng chỉ báo tiêu điểm bàn phím phải rõ nét (`focus-visible:ring-2 focus-visible:ring-amber-500`).
55. Phím Escape (Esc) phải đóng ngay các modal, drawer hoặc popup đang mở.
56. Vùng chạm tối thiểu trên mobile luôn là 44x44px.
57. Triệt tiêu 100% hiện tượng xô lệch bố cục khi tải trang (Zero CLS < 0.1).
58. Ảnh di sản phải có thuộc tính `loading="lazy"` (trừ Hero banner dùng `fetchpriority="high"`).
59. Đảm bảo bảo vệ dữ liệu cá nhân Nghị định 13/2023/NĐ-CP: Ẩn SĐT/địa chỉ người còn sống với khách.
60. Trạng thái rỗng (Empty State) phải có lời nhắn ấm áp kèm nút kêu gọi hành động cụ thể.
61. Điểm kiểm định chất lượng tổng thể qua công cụ Reviewer tự động phải đạt **100/100 (Hạng A+)**.
