"""Tiến trình thứ 2 độc lập (updater.exe): Chờ App chính đóng, giải nén ghi đè bản mới và mở lại App."""
import argparse
import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

from app.updater import UpdateError, apply_staged_update, safe_extract_zip


def _is_process_running(pid: int) -> bool:
    """Kiểm tra xem tiến trình `pid` còn đang chạy trên hệ điều hành không."""
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
            return bool(wait_result == 0x00000102)  # WAIT_TIMEOUT = vẫn đang chạy
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def wait_for_process_exit(pid: int, timeout: float = 15.0) -> bool:
    """Đợi tiến trình chính thoát hoàn toàn để Windows giải phóng khóa file .exe."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _is_process_running(pid):
            time.sleep(0.2)  # Chờ thêm 200ms để NTFS giải phóng hoàn toàn handle
            return True
        time.sleep(0.2)
    return not _is_process_running(pid)


def execute_update(
    package_path: Path,
    target_dir: Path,
    wait_pid: Optional[int] = None,
    relaunch_exe: Optional[Path] = None,
    max_retries: int = 5,
) -> bool:
    """Thực thi quy trình cập nhật từ gói `package_path` vào `target_dir`."""
    if wait_pid is not None and wait_pid > 0:
        wait_for_process_exit(wait_pid, timeout=15.0)

    if not package_path.is_file():
        return False

    target_dir.mkdir(parents=True, exist_ok=True)
    # Tạo thư mục staging ngay cùng ổ đĩa với target_dir để lệnh Path.replace() nguyên tử 100%
    staging_parent = target_dir
    last_error: Optional[Exception] = None

    for attempt in range(max_retries):
        staging_tmp = tempfile.mkdtemp(prefix=".ota_staging_", dir=str(staging_parent))
        staging_dir = Path(staging_tmp)
        try:
            if package_path.suffix.lower() == ".zip":
                safe_extract_zip(package_path, staging_dir)
            else:
                shutil.copy2(package_path, staging_dir / "Gui_mail_nha_cung_cap.exe")

            apply_staged_update(staging_dir, target_dir)
            last_error = None
            break
        except (UpdateError, OSError) as exc:
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
            subprocess.Popen([str(relaunch_exe)], cwd=str(target_dir), close_fds=True)
        except OSError:
            pass

    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Standalone OTA Updater for Gmail Auto Mailer")
    parser.add_argument("--pid", type=int, default=0, help="PID của tiến trình chính cần chờ")
    parser.add_argument("--package", type=str, required=True, help="Đường dẫn gói cập nhật (.zip)")
    parser.add_argument("--target", type=str, required=True, help="Thư mục đích cài đặt ứng dụng")
    parser.add_argument("--relaunch", type=str, default="", help="File .exe khởi chạy lại sau update")
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
