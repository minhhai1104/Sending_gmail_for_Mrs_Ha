"""Kịch bản đóng gói chuẩn hóa cho v3.0: Sinh Windows Version Info, build --onedir + updater.exe & bộ cài 1-Click Setup.exe."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "Ban_phat_hanh"
APP_BUNDLE_DIR = DIST_DIR / "App"
BUILD_DIR = ROOT / "build"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def read_version() -> str:
    init_text = (ROOT / "app" / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    if not m:
        raise RuntimeError("Không tìm thấy __version__ trong app/__init__.py")
    return m.group(1)


def generate_version_info(version: str, out_path: Path) -> Path:
    """Tự động sinh file Windows Version Info nhúng tên sản phẩm, công ty Haesung Vina & số phiên bản."""
    nums = [int(n) for n in re.findall(r"\d+", version)]
    while len(nums) < 4:
        nums.append(0)
    v_tuple = tuple(nums[:4])
    v_str = f"{nums[0]}.{nums[1]}.{nums[2]}.{nums[3]}"

    content = f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={v_tuple},
    prodvers={v_tuple},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          '040904B0',
          [
            StringStruct('CompanyName', 'Haesung Vina Co., Ltd.'),
            StringStruct('FileDescription', 'Gmail Auto Mailer — Gửi báo cáo nhà cung cấp tự động'),
            StringStruct('FileVersion', '{v_str}'),
            StringStruct('InternalName', 'Gui_mail_nha_cung_cap'),
            StringStruct('LegalCopyright', 'Copyright (c) 2026 Haesung Vina Co., Ltd.'),
            StringStruct('OriginalFilename', 'Gui_mail_nha_cung_cap.exe'),
            StringStruct('ProductName', 'Gmail Auto Mailer'),
            StringStruct('ProductVersion', '{version}'),
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    return out_path


def find_iscc() -> Optional[Path]:
    """Tìm trình biên dịch Inno Setup 6 (`ISCC.exe`) trên hệ điều hành Windows."""
    from_path = shutil.which("ISCC") or shutil.which("iscc")
    if from_path:
        return Path(from_path)
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def verify_pyinstaller_exe(exe_path: Path) -> int:
    from PyInstaller.archive.readers import CArchiveReader

    arch = CArchiveReader(str(exe_path))
    entries = len(arch.toc)
    if entries <= 0:
        raise RuntimeError(f"PKG archive rỗng trong {exe_path}")
    return entries


def _run(cmd: list[str]) -> None:
    print(f"▶ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(ROOT), check=True)


def build_all(skip_installer: bool = False) -> tuple[Path, Optional[Path]]:
    """Build trên ổ SSD cục bộ (%TEMP%) để tránh lỗi khóa file Google Drive, sau đó copy nguyên tử."""
    version = read_version()
    print(f"=== Đóng gói Gmail Auto Mailer v{version} (--onedir + updater.exe + 1-Click Setup.exe) ===")

    generate_version_info(version, BUILD_DIR / "version_info.txt")

    work_base = Path(tempfile.gettempdir()) / "gmail_mailer_build_v3"
    if work_base.exists():
        shutil.rmtree(work_base, ignore_errors=True)
    local_dist = work_base / "dist"
    local_dist.mkdir(parents=True, exist_ok=True)

    # 1. Build updater.exe (thuần stdlib, cực nhẹ ~5MB)
    _run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "updater.spec",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(local_dist),
            "--workpath",
            str(work_base / "updater_work"),
        ]
    )

    # 2. Build ứng dụng chính dạng --onedir (mở nhanh gấp 3 lần)
    _run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "Gui_mail_nha_cung_cap.spec",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(local_dist),
            "--workpath",
            str(work_base / "main_work"),
        ]
    )

    local_app_dir = local_dist / "Gui_mail_nha_cung_cap"
    local_main_exe = local_app_dir / "Gui_mail_nha_cung_cap.exe"
    local_updater_exe = local_dist / "updater.exe"

    n_main = verify_pyinstaller_exe(local_main_exe)
    n_upd = verify_pyinstaller_exe(local_updater_exe)
    print(f"✔ Kiểm chứng PKG archive hợp lệ (Main: {n_main} mục, Updater: {n_upd} mục).")

    # Đặt updater.exe vào cùng thư mục App để đóng gói trọn bộ
    shutil.copy2(local_updater_exe, local_app_dir / "updater.exe")

    # 3. Biên dịch Bộ cài 1-Click Setup.exe trên SSD cục bộ (tránh Google Drive khóa file)
    setup_exe_out: Optional[Path] = None
    if not skip_installer:
        iscc = find_iscc()
        if iscc is None:
            print("⚠ Không tìm thấy Inno Setup 6 (ISCC.exe) — bỏ qua bước tạo Setup.exe.")
        else:
            local_setup_dir = work_base / "installer_out"
            local_setup_dir.mkdir(parents=True, exist_ok=True)
            _run(
                [
                    str(iscc),
                    f"/DAppVersion={version}",
                    f"/DSourceDir={local_app_dir}",
                    f"/DOutputDir={local_setup_dir}",
                    str(ROOT / "installer" / "setup.iss"),
                ]
            )
            built_setup = local_setup_dir / f"Cai_dat_Gui_mail_Haesung_Vina_v{version}.exe"
            if not built_setup.is_file():
                raise RuntimeError("ISCC chạy xong nhưng không tìm thấy file Setup.exe đầu ra.")
            DIST_DIR.mkdir(parents=True, exist_ok=True)
            setup_exe_out = DIST_DIR / built_setup.name
            shutil.copy2(built_setup, setup_exe_out)
            size_mb = setup_exe_out.stat().st_size / (1024 * 1024)
            print(f"✔ Đã tạo Bộ cài 1-Click: {setup_exe_out.name} ({size_mb:.2f} MB)")

    # 4. Copy thư mục App (--onedir) sang Ban_phat_hanh/App
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    if APP_BUNDLE_DIR.exists():
        shutil.rmtree(APP_BUNDLE_DIR, ignore_errors=True)
    shutil.copytree(local_app_dir, APP_BUNDLE_DIR)
    verify_pyinstaller_exe(APP_BUNDLE_DIR / "Gui_mail_nha_cung_cap.exe")
    verify_pyinstaller_exe(APP_BUNDLE_DIR / "updater.exe")
    print(f"✔ Đã đồng bộ bản chạy đầy đủ vào: {APP_BUNDLE_DIR}")
    return APP_BUNDLE_DIR, setup_exe_out


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ứng dụng và bộ cài 1-Click Setup.exe v3.0")
    parser.add_argument("--no-installer", action="store_true", help="Chỉ build PyInstaller, không chạy Inno Setup")
    args = parser.parse_args()
    build_all(skip_installer=args.no_installer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
