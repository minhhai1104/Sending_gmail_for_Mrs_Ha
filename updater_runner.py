"""Tiến trình thứ 2 độc lập (`updater.exe`): Viết thuần Python stdlib (cắt 50% dung lượng OTA).

Chức năng:
1. Chờ tiến trình chính (`--pid`) thoát hoàn toàn và kiểm tra kết quả chờ (không ghi đè mù).
2. Giải nén gói ZIP an toàn (chống Zip Slip, bỏ qua toàn bộ dữ liệu người dùng).
3. Ghi đè đệ quy hỗ trợ `--onedir` kèm sao lưu `.bak` & Rollback tự động nếu lỗi.
4. Dọn sạch `.bak`, xóa gói tạm và khởi chạy lại ứng dụng chính (`--relaunch`).
"""

from __future__ import annotations

import argparse
import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Optional

PROTECTED_ITEMS_LOWER: frozenset[str] = frozenset(
    {
        "app_data.db",
        "app_data.db-wal",
        "app_data.db-shm",
        "app_data.db-journal",
        "history.db",
        "history.db-wal",
        "history.db-shm",
        "history.db-journal",
        "vault.dpapi",
        "cau_hinh.xlsx",
        "lich_su_gui.csv",
        "lich_su_gui.xlsx",
        "dinh_kem",
        "logos",
        "exports",
    }
)


def _is_protected(rel_path: Path) -> bool:
    parts = rel_path.parts
    if not parts:
        return False
    if parts[0].lower() in PROTECTED_ITEMS_LOWER or rel_path.name.lower() in PROTECTED_ITEMS_LOWER:
        return True
    return rel_path.name.lower().endswith((".db", ".db-wal", ".db-shm", ".db-journal", ".dpapi"))


def _is_process_running(pid: int) -> bool:
    if pid <= 0 or pid == os.getpid():
        return False
    if sys.platform == "win32":
        synchronize = 0x00100000
        process_query_limited = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            synchronize | process_query_limited, False, pid
        )
        if not handle:
            return False
        try:
            wait_result = ctypes.windll.kernel32.WaitForSingleObject(handle, 0)
            return bool(wait_result == 0x00000102)
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def wait_for_process_exit(pid: int, timeout: float = 20.0) -> bool:
    """Đợi tiến trình chính thoát hoàn toàn; trả về True nếu đã thoát, False nếu quá hạn."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _is_process_running(pid):
            time.sleep(0.25)
            return True
        time.sleep(0.2)
    return not _is_process_running(pid)


def safe_extract_zip(zip_path: Path, staging_dir: Path) -> list[Path]:
    staging_dir.mkdir(parents=True, exist_ok=True)
    staging_root = staging_dir.resolve()
    extracted: list[Path] = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            raw_name = member.filename
            if not raw_name or raw_name.startswith(("/", "\\")):
                raise RuntimeError(f"Unsafe zip path: {raw_name}")
            rel_path = Path(raw_name)
            if ".." in rel_path.parts:
                raise RuntimeError(f"Zip Slip detected: {raw_name}")
            target_path = (staging_root / rel_path).resolve()
            if not target_path.is_relative_to(staging_root):
                raise RuntimeError(f"Zip Slip detected: {raw_name}")
            if _is_protected(rel_path):
                continue
            if member.is_dir():
                target_path.mkdir(parents=True, exist_ok=True)
            else:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member, "r") as src, open(target_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                extracted.append(target_path)
    return extracted


def apply_staged_update(staging_dir: Path, target_dir: Path) -> list[Path]:
    staging_root = staging_dir.resolve()
    target_root = target_dir.resolve()
    target_root.mkdir(parents=True, exist_ok=True)

    staged_files = [p for p in staging_root.rglob("*") if p.is_file()]
    backups: list[tuple[Path, Path]] = []
    created: list[Path] = []
    updated: list[Path] = []

    try:
        for staged_file in staged_files:
            rel_path = staged_file.relative_to(staging_root)
            if _is_protected(rel_path):
                continue
            dest = target_root / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                bak = dest.with_name(dest.name + ".bak")
                if bak.exists():
                    bak.unlink()
                dest.replace(bak)
                backups.append((dest, bak))
            else:
                created.append(dest)
            staged_file.replace(dest)
            updated.append(dest)
    except Exception as exc:
        for new_f in created:
            try:
                new_f.unlink(missing_ok=True)
            except OSError:
                pass
        for orig, bak in reversed(backups):
            try:
                if bak.exists():
                    bak.replace(orig)
            except OSError:
                pass
        raise RuntimeError(f"Update failed and rolled back: {exc}") from exc

    for _orig, bak in backups:
        try:
            bak.unlink(missing_ok=True)
        except OSError:
            pass
    return updated


def execute_update(
    package_path: Path,
    target_dir: Path,
    wait_pid: Optional[int] = None,
    relaunch_exe: Optional[Path] = None,
    max_retries: int = 5,
) -> bool:
    if wait_pid is not None and wait_pid > 0:
        exited = wait_for_process_exit(wait_pid, timeout=20.0)
        if not exited:
            return False

    if not package_path.is_file():
        return False

    target_dir.mkdir(parents=True, exist_ok=True)
    last_error: Optional[Exception] = None

    for attempt in range(max_retries):
        staging_dir = Path(tempfile.mkdtemp(prefix=".ota_staging_", dir=str(target_dir)))
        try:
            if package_path.suffix.lower() == ".zip":
                safe_extract_zip(package_path, staging_dir)
            else:
                shutil.copy2(package_path, staging_dir / "Gui_mail_nha_cung_cap.exe")
            apply_staged_update(staging_dir, target_dir)
            last_error = None
            break
        except (RuntimeError, zipfile.BadZipFile, OSError) as exc:
            last_error = exc
            time.sleep(0.4 * (attempt + 1))
        finally:
            shutil.rmtree(staging_dir, ignore_errors=True)

    if last_error is not None:
        return False

    try:
        package_path.unlink(missing_ok=True)
    except OSError:
        pass

    if relaunch_exe is not None and relaunch_exe.is_file():
        try:
            subprocess.Popen([str(relaunch_exe)], cwd=str(target_dir), close_fds=True)  # noqa: S603
        except OSError:
            pass

    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Standalone OTA Updater for Gmail Auto Mailer")
    parser.add_argument("--pid", type=int, default=0)
    parser.add_argument("--package", type=str, required=True)
    parser.add_argument("--target", type=str, required=True)
    parser.add_argument("--relaunch", type=str, default="")
    args = parser.parse_args()

    relaunch_path = Path(args.relaunch) if args.relaunch else None
    ok = execute_update(
        package_path=Path(args.package),
        target_dir=Path(args.target),
        wait_pid=args.pid if args.pid > 0 else None,
        relaunch_exe=relaunch_path,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
