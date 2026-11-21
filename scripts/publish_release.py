"""Kịch bản tự động kiểm thử, mã hóa OTA token, đóng gói trên ổ SSD cục bộ, kiểm chứng PKG archive & phát hành GitHub Release."""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "Ban_phat_hanh"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    print(f"▶ Running: {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=str(ROOT), text=True, check=check)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().lower()


def _verify_pyinstaller_exe(exe_path: Path) -> int:
    """Kiểm chứng cổng toàn vẹn PKG Archive của PyInstaller (chống lỗi thiếu COOKIE magic trên Google Drive)."""
    from PyInstaller.archive.readers import CArchiveReader

    arch = CArchiveReader(str(exe_path))
    entries = len(arch.toc)
    if entries <= 0:
        raise RuntimeError(f"PKG archive rỗng trong file {exe_path}")
    return entries


def _provision_embedded_ota_token() -> bool:
    """Tự động nạp GitHub Token (từ biến môi trường hoặc `gh auth token`) và mã hóa vào `.ota_token.dat`."""
    from app import security

    raw_token = (
        os.environ.get("GMAIL_MAILER_GH_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
        or ""
    ).strip()
    if not raw_token:
        try:
            res = subprocess.run(
                ["gh", "auth", "token"],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                raw_token = res.stdout.strip()
        except OSError:
            pass

    token_path = ROOT / security.OTA_TOKEN_FILENAME
    if raw_token:
        ok = security.save_embedded_ota_token(raw_token, token_path)
        if ok:
            DIST_DIR.mkdir(parents=True, exist_ok=True)
            (DIST_DIR / security.OTA_TOKEN_FILENAME).write_bytes(token_path.read_bytes())
        return ok
    return token_path.is_file()


def _read_current_version() -> str:
    init_text = (ROOT / "app" / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    if not m:
        raise RuntimeError("Không tìm thấy __version__ trong app/__init__.py")
    return m.group(1)


def _bump_version_files(new_ver: str) -> None:
    clean_ver = new_ver.lstrip("vV").strip()
    init_path = ROOT / "app" / "__init__.py"
    init_text = init_path.read_text(encoding="utf-8")
    init_path.write_text(
        re.sub(r'__version__\s*=\s*"[^"]+"', f'__version__ = "{clean_ver}"', init_text),
        encoding="utf-8",
    )

    pyproject_path = ROOT / "pyproject.toml"
    if pyproject_path.is_file():
        py_text = pyproject_path.read_text(encoding="utf-8")
        pyproject_path.write_text(
            re.sub(r'version\s*=\s*"[^"]+"', f'version = "{clean_ver}"', py_text, count=1),
            encoding="utf-8",
        )

    readme_path = ROOT / "README.md"
    if readme_path.is_file():
        rm_text = readme_path.read_text(encoding="utf-8")
        readme_path.write_text(
            re.sub(
                r"version-v[0-9]+\.[0-9]+\.[0-9]+-blue\.svg",
                f"version-v{clean_ver}-blue.svg",
                rm_text,
            ),
            encoding="utf-8",
        )


def _build_executables_safely() -> None:
    """Build trên ổ SSD cục bộ (%TEMP%) rồi copy nguyên tử sang Ban_phat_hanh để tránh Google Drive làm hỏng PKG archive."""
    work_base = Path(tempfile.gettempdir()) / "gmail_mailer_build"
    local_dist = work_base / "dist"
    local_dist.mkdir(parents=True, exist_ok=True)
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    _run([
        sys.executable, "-m", "PyInstaller", "updater.spec",
        "--noconfirm", "--clean", "--distpath", str(local_dist),
        "--workpath", str(work_base / "updater"),
    ])
    _run([
        sys.executable, "-m", "PyInstaller", "Gui_mail_nha_cung_cap.spec",
        "--noconfirm", "--clean", "--distpath", str(local_dist),
        "--workpath", str(work_base / "main"),
    ])

    local_main = local_dist / "Gui_mail_nha_cung_cap.exe"
    local_upd = local_dist / "updater.exe"
    n_main = _verify_pyinstaller_exe(local_main)
    n_upd = _verify_pyinstaller_exe(local_upd)
    print(f"✔ Kiểm chứng PKG archive trên SSD cục bộ thành công (Main: {n_main} mục, Updater: {n_upd} mục).")

    shutil.copy2(local_main, DIST_DIR / "Gui_mail_nha_cung_cap.exe")
    shutil.copy2(local_upd, DIST_DIR / "updater.exe")
    _verify_pyinstaller_exe(DIST_DIR / "Gui_mail_nha_cung_cap.exe")
    _verify_pyinstaller_exe(DIST_DIR / "updater.exe")
    print("✔ Đã sao chép và xác thực PKG archive trong Ban_phat_hanh/ hợp lệ 100%.")


def _package_ota_zip(version: str) -> tuple[Path, Path, str]:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    main_exe = DIST_DIR / "Gui_mail_nha_cung_cap.exe"
    upd_exe = DIST_DIR / "updater.exe"
    guide_md = ROOT / "HUONG_DAN.md"
    ota_dat = ROOT / ".ota_token.dat"
    if guide_md.is_file():
        (DIST_DIR / "HUONG_DAN.md").write_bytes(guide_md.read_bytes())
    if ota_dat.is_file():
        (DIST_DIR / ".ota_token.dat").write_bytes(ota_dat.read_bytes())

    if not main_exe.is_file() or not upd_exe.is_file():
        raise RuntimeError("Thiếu file thực thi trong Ban_phat_hanh/. Hãy chạy với --build.")

    # Bắt buộc kiểm chứng PKG archive hợp lệ trước khi cho phép nén vào file .zip
    _verify_pyinstaller_exe(main_exe)
    _verify_pyinstaller_exe(upd_exe)

    zip_path = DIST_DIR / f"Gui_mail_nha_cung_cap_v{version}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(main_exe, arcname="Gui_mail_nha_cung_cap.exe")
        zf.write(upd_exe, arcname="updater.exe")
        if (DIST_DIR / "HUONG_DAN.md").is_file():
            zf.write(DIST_DIR / "HUONG_DAN.md", arcname="HUONG_DAN.md")
        if (DIST_DIR / ".ota_token.dat").is_file():
            zf.write(DIST_DIR / ".ota_token.dat", arcname=".ota_token.dat")

    zip_hash = _sha256(zip_path)
    meta = {
        "version": version,
        "release_date": str(date.today()),
        "asset_name": zip_path.name,
        "sha256": zip_hash,
        "exe_sha256": _sha256(main_exe),
        "updater_sha256": _sha256(upd_exe),
    }
    version_json = DIST_DIR / "version.json"
    version_json.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return zip_path, version_json, zip_hash


def main() -> int:
    parser = argparse.ArgumentParser(description="Tự động đóng gói & đẩy bản cập nhật OTA lên GitHub")
    parser.add_argument("--version", type=str, default="", help="Phiên bản mới (ví dụ 2.0.0)")
    parser.add_argument("--notes", type=str, default="", help="Ghi chú bản phát hành")
    parser.add_argument("--build", action="store_true", help="Build lại file .exe bằng PyInstaller")
    args = parser.parse_args()

    if args.version:
        _bump_version_files(args.version)

    version = _read_current_version()
    tag = f"v{version}"
    print(f"=== Chuẩn bị phát hành phiên bản {tag} ===")

    if _provision_embedded_ota_token():
        print("✔ Đã mã hóa và nhúng GitHub OTA Token vào .ota_token.dat (hỗ trợ Private Repo).")

    _run([sys.executable, "-m", "ruff", "check", "app", "tests", "main.py", "updater_runner.py"])
    _run([sys.executable, "-m", "mypy", "app", "main.py", "updater_runner.py"])
    _run([sys.executable, "-m", "pytest", "tests/test_app.py", "-v"])

    main_exe = DIST_DIR / "Gui_mail_nha_cung_cap.exe"
    upd_exe = DIST_DIR / "updater.exe"
    need_build = args.build or not main_exe.is_file() or not upd_exe.is_file()
    if not need_build:
        try:
            _verify_pyinstaller_exe(main_exe)
            _verify_pyinstaller_exe(upd_exe)
        except Exception:
            need_build = True

    if need_build:
        _build_executables_safely()

    zip_path, version_json, zip_hash = _package_ota_zip(version)
    print(f"✔ Đã đóng gói {zip_path.name} (SHA-256: {zip_hash})")

    _run(["git", "add", "-A"])
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=str(ROOT), text=True, capture_output=True
    ).stdout.strip()
    if status:
        commit_msg = f"release: {tag} — {args.notes or 'Cap nhat phien ban moi va kiem chung toan ven PKG archive'}"
        _run(["git", "commit", "-m", commit_msg])

    _run(["git", "tag", "-f", tag])
    _run(["git", "push", "origin", "HEAD"])
    _run(["git", "push", "origin", tag, "--force"])

    notes_body = (
        f"### Bản phát hành {tag} — Gmail Auto Mailer (Haesung Vina)\n\n"
        f"{args.notes or '- Nâng cấp bảo mật Hybrid App Password, SQLite history.db, Smart Pacing, Mẫu Email HTML + Logo CID và Tự động cập nhật OTA 2 tiến trình (hỗ trợ Private Repo Token).'}\n\n"
        f"- **Tệp đính kèm**: `{zip_path.name}` (gồm `Gui_mail_nha_cung_cap.exe`, `updater.exe`, `.ota_token.dat`, `HUONG_DAN.md`).\n"
        f"- **Bảo toàn dữ liệu**: Giữ nguyên 100% `Cau_hinh.xlsx`, `history.db`, `Lich_su_gui.xlsx` và `Dinh_kem/` khi cập nhật OTA.\n\n"
        f"SHA256: {zip_hash}\n"
    )

    rel_check = subprocess.run(
        ["gh", "release", "view", tag], cwd=str(ROOT), text=True, capture_output=True
    )
    if rel_check.returncode == 0:
        _run(["gh", "release", "edit", tag, "--title", f"Gmail Auto Mailer {tag}", "--notes", notes_body])
        _run(["gh", "release", "upload", tag, str(zip_path), str(version_json), "--clobber"])
    else:
        _run([
            "gh", "release", "create", tag,
            str(zip_path), str(version_json),
            "--title", f"Gmail Auto Mailer {tag}",
            "--notes", notes_body,
        ])

    print(f"🚀 Hoàn tất đẩy code và phát hành OTA {tag} lên GitHub Releases!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
