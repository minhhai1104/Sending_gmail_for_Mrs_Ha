"""Mô-đun tự động cập nhật OTA qua GitHub Releases theo kiến trúc 2 tiến trình (Launcher/Updater + App)."""
import hashlib
import hmac
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from . import __version__
from .config import APP_DIR

GITHUB_REPO = "minhhai1104/Sending_gmail_for_Mrs_Ha"
CHUNK_SIZE = 64 * 1024

# Danh sách các tệp và thư mục dữ liệu người dùng bất khả xâm phạm khi cập nhật OTA
PROTECTED_USER_ITEMS: frozenset[str] = frozenset(
    {
        "Cau_hinh.xlsx",
        "history.db",
        "history.db-journal",
        "history.db-wal",
        "history.db-shm",
        "Lich_su_gui.csv",
        "Lich_su_gui.xlsx",
        ".credentials.dat",
        "Dinh_kem",
        "logo.png",
    }
)
_PROTECTED_LOWER: frozenset[str] = frozenset(item.lower() for item in PROTECTED_USER_ITEMS)
_SHA256_RE = re.compile(r"(?:SHA-?256)\s*[:=]\s*([a-fA-F0-9]{64})", re.IGNORECASE)


class UpdateError(Exception):
    """Lỗi trong quá trình kiểm tra, tải hoặc cài đặt bản cập nhật OTA."""


@dataclass
class ReleaseInfo:
    version: str
    download_url: str
    sha256: str
    release_notes: str
    asset_name: str
    published_at: str = ""


def parse_version(version_str: str) -> tuple[int, ...]:
    """Chuẩn hóa chuỗi phiên bản (ví dụ 'v1.2.0' -> (1, 2, 0))."""
    clean = (version_str or "").strip().lstrip("vV").split("-")[0]
    parts = [int(n) for n in re.findall(r"\d+", clean)]
    return tuple(parts) if parts else (0,)


def is_newer_version(remote_ver: str, local_ver: str) -> bool:
    """Trả về True nếu phiên bản `remote_ver` lớn hơn `local_ver`."""
    return parse_version(remote_ver) > parse_version(local_ver)


def _is_protected_path(rel_path: Path) -> bool:
    """Kiểm tra xem đường dẫn tương đối có thuộc diện dữ liệu người dùng cần bảo vệ không."""
    parts = rel_path.parts
    if not parts:
        return False
    if parts[0].lower() in _PROTECTED_LOWER or rel_path.name.lower() in _PROTECTED_LOWER:
        return True
    if rel_path.name.lower().endswith(".vault.dat"):
        return True
    return False


def check_for_update(
    current_version: str = __version__,
    repo: str = GITHUB_REPO,
    api_url: Optional[str] = None,
    timeout: float = 5.0,
) -> Optional[ReleaseInfo]:
    """Kiểm tra bản phát hành mới nhất từ GitHub Releases API. Trả về None nếu đã ở bản mới nhất."""
    url = api_url or f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": f"GmailAutoMailer-Updater/{current_version}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise UpdateError(f"Không kiểm tra được bản cập nhật từ GitHub: {exc}") from exc

    if not isinstance(data, dict):
        return None

    tag_name = str(data.get("tag_name") or "").strip()
    clean_ver = tag_name.lstrip("vV")
    if not clean_ver or not is_newer_version(clean_ver, current_version):
        return None

    body = str(data.get("body") or "").strip()
    published_at = str(data.get("published_at") or "").strip()
    sha256_match = _SHA256_RE.search(body)
    sha256_hex = sha256_match.group(1).lower() if sha256_match else ""

    assets = data.get("assets") or []
    chosen_asset: Optional[dict[str, Any]] = None
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name") or "")
        if name.lower().endswith(".zip"):
            chosen_asset = asset
            break
    if chosen_asset is None:
        for asset in assets:
            if isinstance(asset, dict) and str(asset.get("name") or "").lower().endswith(".exe"):
                chosen_asset = asset
                break

    if chosen_asset is None:
        return None

    download_url = str(chosen_asset.get("browser_download_url") or "").strip()
    asset_name = str(chosen_asset.get("name") or f"update_v{clean_ver}.zip").strip()
    if not download_url:
        return None

    return ReleaseInfo(
        version=clean_ver,
        download_url=download_url,
        sha256=sha256_hex,
        release_notes=body,
        asset_name=asset_name,
        published_at=published_at,
    )


def compute_sha256(file_path: Path) -> str:
    """Tính mã băm SHA-256 của tệp theo từng chunk 64KB."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest().lower()


def verify_sha256(file_path: Path, expected_sha256: str) -> bool:
    """Kiểm tra mã băm SHA-256 của tệp có khớp với mã chuẩn không."""
    clean_expected = (expected_sha256 or "").strip().lower()
    if not clean_expected:
        return True
    actual = compute_sha256(file_path)
    return hmac.compare_digest(actual, clean_expected)


def download_release_asset(
    release: ReleaseInfo,
    dest_dir: Path,
    on_progress: Optional[Callable[[int, int], None]] = None,
    timeout: float = 30.0,
) -> Path:
    """Tải gói cập nhật về `dest_dir` qua HTTPS và kiểm tra cổng toàn vẹn SHA-256."""
    if not release.download_url.lower().startswith("https://"):
        raise UpdateError("Đường dẫn tải bản cập nhật bắt buộc phải dùng giao thức bảo mật HTTPS.")

    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(release.asset_name or f"update_v{release.version}.zip").name
    dest_path = dest_dir / safe_name

    req = urllib.request.Request(
        release.download_url,
        headers={"User-Agent": f"GmailAutoMailer-Updater/{release.version}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            headers = getattr(resp, "headers", {}) or {}
            total_bytes = int(headers.get("Content-Length") or 0)
            downloaded = 0
            with open(dest_path, "wb") as out_file:
                while True:
                    chunk = resp.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    downloaded += len(chunk)
                    if on_progress is not None:
                        on_progress(downloaded, total_bytes)
    except (urllib.error.URLError, OSError) as exc:
        dest_path.unlink(missing_ok=True)
        raise UpdateError(f"Lỗi khi tải gói cập nhật: {exc}") from exc

    if release.sha256 and not verify_sha256(dest_path, release.sha256):
        dest_path.unlink(missing_ok=True)
        raise UpdateError(
            "Mã kiểm tra toàn vẹn SHA-256 của gói cập nhật không khớp. "
            "Đã hủy cập nhật và xóa tệp tạm để bảo vệ ứng dụng."
        )

    return dest_path


def safe_extract_zip(zip_path: Path, staging_dir: Path) -> list[Path]:
    """Giải nén gói zip vào `staging_dir` có kiểm soát chống Zip Slip và lọc bỏ file người dùng."""
    staging_dir.mkdir(parents=True, exist_ok=True)
    staging_root = staging_dir.resolve()
    extracted_files: list[Path] = []

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.infolist():
                raw_name = member.filename
                if not raw_name or raw_name.startswith(("/", "\\")):
                    raise UpdateError(f"Đường dẫn trong gói cập nhật không an toàn: {raw_name}")

                rel_path = Path(raw_name)
                if ".." in rel_path.parts:
                    raise UpdateError(
                        f"Phát hiện đường dẫn thoát thư mục không an toàn (Zip Slip): {raw_name}"
                    )

                target_path = (staging_root / rel_path).resolve()
                if not target_path.is_relative_to(staging_root):
                    raise UpdateError(
                        f"Phát hiện đường dẫn thoát thư mục không an toàn (Zip Slip): {raw_name}"
                    )

                if _is_protected_path(rel_path):
                    continue

                if member.is_dir():
                    target_path.mkdir(parents=True, exist_ok=True)
                else:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member, "r") as src, open(target_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    extracted_files.append(target_path)
    except zipfile.BadZipFile as exc:
        raise UpdateError("Gói cập nhật tải về bị hỏng (không phải định dạng ZIP hợp lệ).") from exc

    return extracted_files


def apply_staged_update(staging_dir: Path, target_dir: Path) -> list[Path]:
    """Ghi đè các tệp mới từ `staging_dir` sang `target_dir` kèm cơ chế sao lưu `.bak` & Rollback."""
    staging_root = staging_dir.resolve()
    target_root = target_dir.resolve()
    target_root.mkdir(parents=True, exist_ok=True)

    staged_files = [p for p in staging_root.rglob("*") if p.is_file()]
    backups: list[tuple[Path, Path]] = []
    created_files: list[Path] = []
    updated_targets: list[Path] = []

    try:
        for staged_file in staged_files:
            rel_path = staged_file.relative_to(staging_root)
            if _is_protected_path(rel_path):
                continue

            dest_file = target_root / rel_path
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            if dest_file.exists():
                bak_file = dest_file.with_name(dest_file.name + ".bak")
                if bak_file.exists():
                    bak_file.unlink()
                dest_file.replace(bak_file)
                backups.append((dest_file, bak_file))
            else:
                created_files.append(dest_file)

            staged_file.replace(dest_file)
            updated_targets.append(dest_file)
    except Exception as exc:
        # Rollback toàn bộ về trạng thái cũ nếu có bất kỳ lỗi nào xảy ra giữa chừng
        for new_f in created_files:
            try:
                if new_f.exists():
                    new_f.unlink()
            except OSError:
                pass
        for orig_dest, bak_file in reversed(backups):
            try:
                if bak_file.exists():
                    bak_file.replace(orig_dest)
            except OSError:
                pass
        raise UpdateError(
            f"Không thể ghi đè tệp cập nhật (đã tự động khôi phục phiên bản cũ): {exc}"
        ) from exc

    # Xóa các tệp .bak sau khi tất cả các tệp đã cập nhật thành công 100%
    for _orig_dest, bak_file in backups:
        try:
            bak_file.unlink(missing_ok=True)
        except OSError:
            pass

    return updated_targets


def spawn_standalone_updater(
    package_path: Path,
    target_dir: Path = APP_DIR,
    current_pid: Optional[int] = None,
    relaunch_exe: Optional[Path] = None,
) -> subprocess.Popen[Any]:
    """Khởi chạy tiến trình thứ 2 độc lập (`updater.exe` hoặc `updater_runner.py`) để cập nhật."""
    pid = current_pid if current_pid is not None else os.getpid()
    updater_exe = target_dir / "updater.exe"

    args: list[str] = []
    if updater_exe.is_file():
        args = [str(updater_exe)]
    else:
        runner_script = APP_DIR / "updater_runner.py"
        args = [sys.executable, str(runner_script)]

    args.extend(
        [
            "--pid",
            str(pid),
            "--package",
            str(package_path.resolve()),
            "--target",
            str(target_dir.resolve()),
        ]
    )
    if relaunch_exe is not None:
        args.extend(["--relaunch", str(relaunch_exe.resolve())])

    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    return subprocess.Popen(
        args,
        cwd=str(target_dir),
        creationflags=creation_flags,
         close_fds=True,
    )
