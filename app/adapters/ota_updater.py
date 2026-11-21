"""Mô-đun tự động cập nhật OTA 2 tiến trình cứng hóa bảo mật (v3.0).

Nâng cấp an toàn so với v2.0:
1. Bắt buộc có mã băm SHA-256 hợp lệ 64 ký tự hex (`verify_sha256` trả `False` nếu rỗng!).
2. Khóa chặt Domain Allowlist HTTPS (`api.github.com`, `github.com`, `objects.githubusercontent.com`, ...).
3. Loại bỏ hoàn toàn `_PORTABLE_OTA_SECRET` hardcode trong mã nguồn.
4. Sao chép `updater.exe` ra `%TEMP%` trước khi thực thi để không bao giờ tự khóa file / tạo `.bak` rác.
5. Bảo vệ toàn bộ dữ liệu người dùng và tương thích nâng cấp `--onedir`.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Callable, Optional

from .. import __version__
from ..domain.models import ReleaseInfo
from .paths import get_app_dir

GITHUB_REPO = "minhhai1104/Sending_gmail_for_Mrs_Ha"
CHUNK_SIZE = 64 * 1024

ALLOWED_DOWNLOAD_HOSTS: frozenset[str] = frozenset(
    {
        "api.github.com",
        "github.com",
        "objects.githubusercontent.com",
        "release-assets.githubusercontent.com",
        "github-releases.githubusercontent.com",
    }
)

PROTECTED_USER_ITEMS: frozenset[str] = frozenset(
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
        "Cau_hinh.xlsx",
        "Lich_su_gui.csv",
        "Lich_su_gui.xlsx",
        "Dinh_kem",
        "logos",
        "exports",
    }
)
_PROTECTED_LOWER: frozenset[str] = frozenset(item.lower() for item in PROTECTED_USER_ITEMS)
_SHA256_RE = re.compile(r"(?:SHA-?256)\s*[:=]\s*([a-fA-F0-9]{64})", re.IGNORECASE)
_SHA256_HEX_RE = re.compile(r"^[a-fA-F0-9]{64}$")


class UpdateError(Exception):
    """Lỗi trong quá trình kiểm tra, tải hoặc cài đặt bản cập nhật OTA."""


def parse_version(version_str: str) -> tuple[int, ...]:
    clean = (version_str or "").strip().lstrip("vV").split("-")[0]
    parts = [int(n) for n in re.findall(r"\d+", clean)]
    return tuple(parts) if parts else (0,)


def is_newer_version(remote_ver: str, local_ver: str) -> bool:
    return parse_version(remote_ver) > parse_version(local_ver)


def validate_https_github_url(url: str) -> None:
    """Chỉ chấp nhận HTTPS thuộc danh sách domain chính thức của GitHub."""
    parsed = urllib.parse.urlparse(url or "")
    host = (parsed.hostname or "").lower()
    if parsed.scheme.lower() != "https" or host not in ALLOWED_DOWNLOAD_HOSTS:
        raise UpdateError(
            f"URL tải bản cập nhật không nằm trong danh sách tin cậy của GitHub: {host or '(trống)'}"
        )


def _is_protected_path(rel_path: Path) -> bool:
    parts = rel_path.parts
    if not parts:
        return False
    if parts[0].lower() in _PROTECTED_LOWER or rel_path.name.lower() in _PROTECTED_LOWER:
        return True
    lower_name = rel_path.name.lower()
    return lower_name.endswith((".db", ".db-wal", ".db-shm", ".db-journal", ".dpapi"))


def compute_sha256(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest().lower()


def verify_sha256(file_path: Path, expected_sha256: str) -> bool:
    """Bắt buộc có mã băm SHA-256 hợp lệ 64 ký tự hex — rỗng hoặc sai định dạng trả `False`."""
    clean_expected = (expected_sha256 or "").strip().lower()
    if not _SHA256_HEX_RE.match(clean_expected):
        return False
    if not file_path.is_file():
        return False
    actual = compute_sha256(file_path)
    return hmac.compare_digest(actual, clean_expected)


def check_for_update(
    current_version: str = __version__,
    repo: str = GITHUB_REPO,
    api_url: Optional[str] = None,
    timeout: float = 6.0,
    token: str = "",
) -> Optional[ReleaseInfo]:
    url = api_url or f"https://api.github.com/repos/{repo}/releases/latest"
    if api_url is None:
        validate_https_github_url(url)

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": f"GmailAutoMailer-Updater/{current_version}",
    }
    clean_token = (token or "").strip()
    if clean_token:
        headers["Authorization"] = f"Bearer {clean_token}"

    req = urllib.request.Request(url, headers=headers)  # noqa: S310
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
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
    sha_match = _SHA256_RE.search(body)
    sha256_hex = sha_match.group(1).lower() if sha_match else ""

    assets = data.get("assets") or []
    chosen: Optional[dict[str, Any]] = None
    for asset in assets:
        if isinstance(asset, dict) and str(asset.get("name") or "").lower().endswith(".zip"):
            chosen = asset
            break
    if chosen is None:
        return None

    browser_url = str(chosen.get("browser_download_url") or "").strip()
    api_asset_url = str(chosen.get("url") or "").strip()
    download_url = browser_url or api_asset_url
    asset_name = str(chosen.get("name") or f"update_v{clean_ver}.zip").strip()
    if not download_url:
        return None

    return ReleaseInfo(
        version=clean_ver,
        download_url=download_url,
        sha256=sha256_hex,
        release_notes=body,
        asset_name=asset_name,
        published_at=published_at,
        api_asset_url=api_asset_url,
    )


def download_release_asset(
    release: ReleaseInfo,
    dest_dir: Path,
    on_progress: Optional[Callable[[int, int], None]] = None,
    timeout: float = 45.0,
    token: str = "",
) -> Path:
    """Tải gói OTA qua HTTPS (khóa domain allowlist) và BẮT BUỘC xác thực SHA-256."""
    if not _SHA256_HEX_RE.match((release.sha256 or "").strip()):
        raise UpdateError(
            "Bản phát hành trên GitHub thiếu mã kiểm tra toàn vẹn SHA-256. "
            "Đã từ chối tải để bảo vệ an toàn hệ thống."
        )

    clean_token = (token or "").strip()
    target_url = (
        release.api_asset_url
        if (clean_token and release.api_asset_url)
        else release.download_url
    )
    validate_https_github_url(target_url)

    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(release.asset_name or f"update_v{release.version}.zip").name
    dest_path = dest_dir / safe_name

    headers = {"User-Agent": f"GmailAutoMailer-Updater/{release.version}"}
    if clean_token and ("api.github.com" in target_url.lower()):
        headers["Authorization"] = f"Bearer {clean_token}"
        headers["Accept"] = "application/octet-stream"

    req = urllib.request.Request(target_url, headers=headers)  # noqa: S310
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            resp_headers = getattr(resp, "headers", {}) or {}
            total_bytes = int(resp_headers.get("Content-Length") or 0)
            downloaded = 0
            with open(dest_path, "wb") as out_f:
                while True:
                    chunk = resp.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    out_f.write(chunk)
                    downloaded += len(chunk)
                    if on_progress is not None:
                        on_progress(downloaded, total_bytes)
    except (urllib.error.URLError, OSError) as exc:
        dest_path.unlink(missing_ok=True)
        raise UpdateError(f"Lỗi khi tải gói cập nhật: {exc}") from exc

    if not verify_sha256(dest_path, release.sha256):
        dest_path.unlink(missing_ok=True)
        raise UpdateError(
            "Mã kiểm tra toàn vẹn SHA-256 không khớp. Đã xóa tệp tải về để bảo vệ ứng dụng."
        )
    return dest_path


def safe_extract_zip(zip_path: Path, staging_dir: Path) -> list[Path]:
    """Giải nén gói ZIP vào `staging_dir` có kiểm soát chống Zip Slip và bảo vệ dữ liệu người dùng."""
    staging_dir.mkdir(parents=True, exist_ok=True)
    staging_root = staging_dir.resolve()
    extracted: list[Path] = []
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.infolist():
                raw_name = member.filename
                if not raw_name or raw_name.startswith(("/", "\\")):
                    raise UpdateError(f"Đường dẫn trong gói cập nhật không an toàn: {raw_name}")
                rel_path = Path(raw_name)
                if ".." in rel_path.parts:
                    raise UpdateError(f"Phát hiện lỗ hổng Zip Slip trong gói cập nhật: {raw_name}")
                target_path = (staging_root / rel_path).resolve()
                if not target_path.is_relative_to(staging_root):
                    raise UpdateError(f"Phát hiện lỗ hổng Zip Slip trong gói cập nhật: {raw_name}")
                if _is_protected_path(rel_path):
                    continue
                if member.is_dir():
                    target_path.mkdir(parents=True, exist_ok=True)
                else:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member, "r") as src, open(target_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    extracted.append(target_path)
    except zipfile.BadZipFile as exc:
        raise UpdateError("Gói cập nhật tải về bị hỏng (không phải ZIP hợp lệ).") from exc
    return extracted


def apply_staged_update(staging_dir: Path, target_dir: Path) -> list[Path]:
    """Ghi đè nguyên tử có sao lưu `.bak` và tự động Rollback nếu gặp lỗi giữa chừng."""
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
            if _is_protected_path(rel_path):
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
        raise UpdateError(f"Ghi đè bản cập nhật thất bại (đã khôi phục bản cũ): {exc}") from exc

    for _orig, bak in backups:
        try:
            bak.unlink(missing_ok=True)
        except OSError:
            pass
    return updated


def spawn_standalone_updater(
    package_path: Path,
    target_dir: Optional[Path] = None,
    current_pid: Optional[int] = None,
    relaunch_exe: Optional[Path] = None,
) -> subprocess.Popen[Any]:
    """Sao chép `updater.exe` ra `%TEMP%` rồi khởi chạy để tránh tự khóa file khi nâng cấp."""
    app_dir = target_dir if target_dir is not None else get_app_dir()
    pid = current_pid if current_pid is not None else os.getpid()
    updater_exe = app_dir / "updater.exe"

    if updater_exe.is_file():
        temp_dir = Path(tempfile.gettempdir()) / "GmailAutoMailer_OTA"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_updater = temp_dir / "updater_exec.exe"
        shutil.copy2(updater_exe, temp_updater)
        args = [str(temp_updater)]
    else:
        runner_script = get_app_dir() / "updater_runner.py"
        args = [sys.executable, str(runner_script)]

    args.extend(
        [
            "--pid",
            str(pid),
            "--package",
            str(package_path.resolve()),
            "--target",
            str(app_dir.resolve()),
        ]
    )
    if relaunch_exe is not None:
        args.extend(["--relaunch", str(relaunch_exe.resolve())])

    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0
    return subprocess.Popen(  # noqa: S603
        args,
        cwd=str(Path(tempfile.gettempdir())),
        creationflags=creation_flags,
        close_fds=True,
    )
