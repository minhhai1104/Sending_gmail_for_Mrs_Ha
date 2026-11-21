# Rule: DevOps Agent (Packaging & Infrastructure Engineer)

Áp dụng cho vai trò: `devops-agent` trong dự án **Ứng dụng Gửi Email Hàng Loạt Cho Nhà Cung Cấp (Gmail Auto Mailer)**.

---

## 1. Trách nhiệm cốt lõi (Core Mission)
1. **Quản lý Cấu hình & Môi trường Dự án (`pyproject.toml`)**:
   - Thiết lập và quản lý cấu hình phụ thuộc, build system chuẩn hiện đại qua `pyproject.toml`.
   - Cấu hình rõ ràng các nhóm dependencies: Nhóm chạy runtime và nhóm phát triển (`pytest`, `ruff`, `mypy`, `pyinstaller`).
2. **Quy chuẩn Đóng gói Thực thi Windows (`PyInstaller .spec`)**:
   - Thay thế việc chạy file batch thô sơ bằng tệp đặc tả đóng gói chuyên nghiệp `Gui_mail_nha_cung_cap.spec`.
   - Cấu hình đóng gói độc lập `--onefile` hoặc `--onedir` tối ưu:
     - Tự động nhúng thông tin bản quyền và phiên bản hệ điều hành Windows (`version_info.txt`).
     - Tự động nhúng icon ứng dụng và file cấu hình mẫu.
     - Loại trừ các thư viện nặng không sử dụng (như `tkinter.test`, `test`, `unittest`, `matplotlib`...) để tối ưu dung lượng tệp thực thi `< 15MB` và tăng tốc độ khởi động lên gấp đôi.
3. **Tự động hóa CI/CD qua GitHub Actions (`.github/workflows/ci.yml`)**:
   - Thiết lập workflow tự động chạy trên môi trường `windows-latest` mỗi khi có commit hoặc Pull Request:
     - Bước 1: Setup Python môi trường sạch.
     - Bước 2: Kiểm tra định dạng và phân tích tĩnh với `ruff`.
     - Bước 3: Kiểm tra kiểu dữ liệu với `mypy`.
     - Bước 4: Chạy toàn bộ bộ kiểm thử tự động với `pytest`.
     - Bước 5: Thử nghiệm đóng gói PyInstaller và lưu trữ artifact tệp `.exe`.
4. **Phát hành & Phân phối Ứng dụng**:
   - Đảm bảo thư mục phát hành `Ban_phat_hanh/` luôn có tệp thực thi hoàn chỉnh và tài liệu hướng dẫn kèm theo.
   - Viết kịch bản tự động hóa build độc lập `scripts/build_exe.py`.

---

## 2. Tiêu chí Hoàn thành (DoD)
- [ ] Tệp `Gui_mail_nha_cung_cap.spec` được cấu hình chuẩn mực và build thành công không lỗi.
- [ ] Tệp `.exe` tạo ra chạy được độc lập trên máy Windows sạch không cài đặt sẵn Python.
- [ ] File cấu hình GitHub Actions CI `.github/workflows/ci.yml` hoạt động tự động.
- [ ] Không có file rác (`build/`, `dist/`, `.spec` dư thừa) làm bẩn working directory.

5. **Tự động Đẩy Phiên Bản & Phát hành OTA Lên GitHub Releases (`scripts/publish_release.py`)**:
   - Mỗi khi người dùng yêu cầu cập nhật / phát hành phiên bản mới:
     - Chạy `python scripts/publish_release.py --version <X.Y.Z> --build` (hoặc không cần `--build` nếu vừa đóng gói xong).
     - Kịch bản tự động chạy Quality Gate (`ruff`, `mypy`, `pytest`), đóng gói `Gui_mail_nha_cung_cap_vX.Y.Z.zip` + `version.json`, tính mã băm `SHA-256`, commit & push code + git tag lên `origin`, và xuất bản GitHub Release qua `gh release create/upload` kèm dòng `SHA256: <hash>` để người dùng cuối nhận bản cập nhật OTA ngay lập tức.
