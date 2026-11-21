"""Trình quét tệp đính kèm trên hệ thống tệp kèm tính mã băm SHA-256 chống TOCTOU."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

from ..domain.matching import is_junk_filename
from ..domain.models import ScannedFile
from ..domain.validation import normalize_unicode

_HASH_CHUNK = 64 * 1024


def compute_file_sha256(file_path: Path) -> str:
    """Tính mã băm SHA-256 của tệp theo từng chunk 64KB."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(_HASH_CHUNK)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest().lower()


class OsFileScanner:
    """Triển khai `FileScanner` thực tế trên hệ điều hành Windows."""

    def inspect_file(self, file_path: Path) -> Optional[ScannedFile]:
        try:
            resolved = file_path.resolve()
            if not resolved.is_file():
                return None
            stat = resolved.stat()
            norm_name = normalize_unicode(resolved.name)
            ext = resolved.suffix.lower()
            sha = compute_file_sha256(resolved) if stat.st_size > 0 else ""
            return ScannedFile(
                path=resolved,
                name=norm_name,
                ext=ext,
                size_bytes=stat.st_size,
                sha256=sha,
                mtime=stat.st_mtime,
            )
        except OSError:
            return None

    def scan_directory(self, folder: Path) -> list[ScannedFile]:
        if not folder.is_dir():
            return []
        root = folder.resolve()
        scanned: list[ScannedFile] = []
        try:
            entries = sorted(root.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            return []
        for entry in entries:
            if not entry.is_file():
                continue
            if is_junk_filename(entry.name):
                continue
            try:
                resolved = entry.resolve()
                if not resolved.is_relative_to(root):
                    continue
            except OSError:
                continue
            item = self.inspect_file(resolved)
            if item is not None:
                scanned.append(item)
        return scanned

    def scan_paths(self, paths: list[Path]) -> list[ScannedFile]:
        """Quét tổng hợp danh sách hỗn hợp gồm thư mục và/hoặc tệp rời (từ Drag & Drop)."""
        seen: set[Path] = set()
        scanned: list[ScannedFile] = []
        for raw_path in paths:
            try:
                resolved = raw_path.resolve()
            except OSError:
                continue
            if resolved.is_dir():
                for item in self.scan_directory(resolved):
                    if item.path not in seen:
                        seen.add(item.path)
                        scanned.append(item)
            elif resolved.is_file() and not is_junk_filename(resolved.name):
                if resolved not in seen:
                    inspected = self.inspect_file(resolved)
                    if inspected is not None:
                        seen.add(resolved)
                        scanned.append(inspected)
        return scanned

    def list_period_subfolders(self, root_dir: Path) -> list[str]:
        """Liệt kê tên các thư mục con có chứa ít nhất 1 file Excel/PDF thật."""
        if not root_dir.is_dir():
            return []
        found: list[str] = []
        try:
            for entry in root_dir.iterdir():
                if not entry.is_dir():
                    continue
                has_valid = any(
                    child.is_file() and not is_junk_filename(child.name)
                    for child in entry.iterdir()
                )
                if has_valid:
                    found.append(normalize_unicode(entry.name))
        except OSError:
            return []
        return found
