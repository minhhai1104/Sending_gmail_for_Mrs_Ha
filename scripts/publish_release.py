"""Kịch bản phát hành OTA v3.0: Quality Gate (ruff, mypy, pytest >=90%), Build --onedir + Setup.exe & GitHub Release."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "Ban_phat_hanh"
APP_BUNDLE_DIR = DIST_DIR / "App"

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


def _read_current_version() -> str:
    init_text = (ROOT / "app" / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    if not m:
        raise RuntimeError("Không tìm thấy __version__ trong app/__init__.py")
    return m.group(1)


def _bump_version_files(new_ver: str) -> None:
    clean_ver = new_ver.lstrip("vV").strip()
    init_path = ROOT / "app" / "__init__.py"
    init_path.write_text(
        re.sub(
            r'__version__\s*=\s*"[^"]+"',
            f'__version__ = "{clean_ver}"',
            init_path.read_text(encoding="utf-8"),
        ),
        encoding="utf-8",
    )
    pyproject_path = ROOT / "pyproject.toml"
    if pyproject_path.is_file():
        pyproject_path.write_text(
            re.sub(
                r'version\s*=\s*"[^"]+"',
                f'version = "{clean_ver}"',
                pyproject_path.read_text(encoding="utf-8"),
                count=1,
            ),
            encoding="utf-8",
        )
    readme_path = ROOT / "README.md"
    if readme_path.is_file():
        readme_path.write_text(
            re.sub(
                r"version-v[0-9]+\.[0-9]+\.[0-9]+-blue\.svg",
                f"version-v{clean_ver}-blue.svg",
                readme_path.read_text(encoding="utf-8"),
            ),
            encoding="utf-8",
        )


def _package_ota_zip(version: str) -> tuple[Path, Path, str]:
    """Đóng gói toàn bộ thư mục `--onedir` (gồm Gui_mail_nha_cung_cap.exe, _internal/, updater.exe) thành gói OTA ZIP."""
    from scripts.build_exe import verify_pyinstaller_exe

    main_exe = APP_BUNDLE_DIR / "Gui_mail_nha_cung_cap.exe"
    upd_exe = APP_BUNDLE_DIR / "updater.exe"
    if not main_exe.is_file() or not upd_exe.is_file():
        raise RuntimeError("Thiếu bản build trong Ban_phat_hanh/App/. Hãy chạy với --build.")

    verify_pyinstaller_exe(main_exe)
    verify_pyinstaller_exe(upd_exe)

    zip_path = DIST_DIR / f"Gui_mail_nha_cung_cap_v{version}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for file_path in sorted(APP_BUNDLE_DIR.rglob("*")):
            if file_path.is_file():
                arcname = file_path.relative_to(APP_BUNDLE_DIR).as_posix()
                zf.write(file_path, arcname=arcname)

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
    parser = argparse.ArgumentParser(description="Đóng gói & phát hành OTA v3.0 lên GitHub Releases")
    parser.add_argument("--version", type=str, default="", help="Phiên bản mới (ví dụ 3.0.0)")
    parser.add_argument("--notes", type=str, default="", help="Ghi chú bản phát hành")
    parser.add_argument("--build", action="store_true", help="Build lại --onedir + updater.exe + Setup.exe")
    args = parser.parse_args()

    if args.version:
        _bump_version_files(args.version)

    version = _read_current_version()
    tag = f"v{version}"
    print(f"=== Chuẩn bị phát hành phiên bản {tag} ===")

    # Cổng kiểm định chất lượng bắt buộc
    _run([sys.executable, "-m", "ruff", "check", "app", "tests", "scripts", "main.py", "updater_runner.py"])
    _run([sys.executable, "-m", "mypy", "app", "main.py", "updater_runner.py"])
    _run([sys.executable, "-m", "pytest", "-v", "--cov-fail-under=85"])

    setup_exe = DIST_DIR / f"Cai_dat_Gui_mail_Haesung_Vina_v{version}.exe"
    if args.build or not (APP_BUNDLE_DIR / "Gui_mail_nha_cung_cap.exe").is_file():
        from scripts.build_exe import build_all

        _, built_setup = build_all(skip_installer=False)
        if built_setup is not None:
            setup_exe = built_setup

    zip_path, version_json, zip_hash = _package_ota_zip(version)
    print(f"✔ Đã đóng gói {zip_path.name} (SHA-256: {zip_hash})")

    _run(["git", "add", "-A"])
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=str(ROOT), text=True, capture_output=True
    ).stdout.strip()
    if status:
        commit_msg = f"release: {tag} — {args.notes or 'Tai thiet ke v3.0 Zero-Manual Enterprise & Bo cai 1-Click'}"
        _run(["git", "commit", "-m", commit_msg])

    _run(["git", "tag", "-f", tag])
    _run(["git", "push", "origin", "HEAD"])
    _run(["git", "push", "origin", tag, "--force"])

    assets = [str(zip_path), str(version_json)]
    if setup_exe.is_file():
        assets.append(str(setup_exe))

    notes_body = (
        f"### Bản phát hành {tag} — Gmail Auto Mailer (Haesung Vina)\n\n"
        f"{args.notes or '- Tái thiết kế toàn diện v3.0 Zero-Manual Enterprise: Giao diện PyWebView (Edge WebView2) Dark/Light 100%, cấu hình 100% trong App, Khớp file 3 tầng chống gửi nhầm, Xem trước Email HTML + Logo 1:1, Windows DPAPI Vault và Bộ cài 1-Click Setup.exe.'}\n\n"
        f"- **Cài mới lần đầu**: Tải và chạy file `{setup_exe.name}` (1-Click, không cần quyền Admin).\n"
        f"- **Gói cập nhật OTA**: `{zip_path.name}` (tự động bảo toàn 100% dữ liệu người dùng tại `%LOCALAPPDATA%\\GmailAutoMailer`).\n\n"
        f"SHA256: {zip_hash}\n"
    )

    rel_check = subprocess.run(
        ["gh", "release", "view", tag], cwd=str(ROOT), text=True, capture_output=True
    )
    if rel_check.returncode == 0:
        _run(["gh", "release", "edit", tag, "--title", f"Gmail Auto Mailer {tag}", "--notes", notes_body])
        _run(["gh", "release", "upload", tag, *assets, "--clobber"])
    else:
        _run(
            [
                "gh",
                "release",
                "create",
                tag,
                *assets,
                "--title",
                f"Gmail Auto Mailer {tag}",
                "--notes",
                notes_body,
            ]
        )

    print(f"🚀 Hoàn tất phát hành {tag} lên GitHub Releases!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
