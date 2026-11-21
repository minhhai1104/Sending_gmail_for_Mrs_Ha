"""Động cơ Khớp File Thông Minh 3 Tầng — Cam kết Zero Wrong-Vendor Delivery (Pure Domain).

Rào chắn an toàn bắt buộc:
1. Lọc bỏ 100% file tạm Office (`~$*`, `.~lock*`), file hệ thống (`desktop.ini`, `Thumbs.db`), file rỗng.
2. Chuẩn hóa Unicode NFC (giải quyết lỗi dấu tiếng Việt macOS/Drive/Zalo).
3. Tầng Xanh (`EXACT` / `AUTO_MATCHED`): CHỈ tự động chấp nhận khi khớp 100% ranh giới từ
   (Word-Boundary Token, Longest-Match-First chống `A` vs `AB`, `ACE` vs `ACE2`, `T&T` vs `T&T Logistics`)
   VÀ đúng kỳ tháng/năm (nếu tên file có ghi kỳ).
4. Tầng Vàng (`NEEDS_REVIEW`): Khớp gần đúng (fuzzy trên phần tên NCC đã tước tiền tố chung) ->
   CHỈ GỢI Ý, MẶC ĐỊNH KHÔNG TICK GỬI, tuyệt đối diệt bẫy `ACE` vs `AHC` giống nhau 96% tiền tố!
5. Tầng Đỏ (`AMBIGUOUS` / `CONFLICT` / `WRONG_PERIOD` / `MISSING` / `INVALID_FILE`): Khóa cứng.
6. Bất biến Song ánh 1-1: 0 file nào (cả theo path lẫn nội dung SHA-256) được gắn cho >= 2 NCC.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

from .models import (
    MAX_TOTAL_ATTACHMENT_BYTES,
    AttachmentMatch,
    DiscoveredSupplier,
    FileType,
    MatchStatus,
    PeriodSuggestion,
    ScannedFile,
    SendKind,
    Supplier,
)
from .templating import render
from .validation import normalize_name, normalize_unicode

_JUNK_NAMES: frozenset[str] = frozenset(
    {
        "desktop.ini",
        "thumbs.db",
        ".ds_store",
        "cau_hinh.xlsx",
        "lich_su_gui.xlsx",
        "lich_su_gui.csv",
    }
)
_JUNK_PREFIXES: tuple[str, ...] = ("~$", ".~lock", "._")
_JUNK_SUFFIXES: tuple[str, ...] = (".tmp", ".bak", ".crdownload", ".part")
_ALLOWED_EXTS: frozenset[str] = frozenset({".xlsx", ".xls", ".xlsm", ".pdf"})

# Bắt tháng/năm an toàn có ranh giới không phải chữ số:
# - 2026-09, 2026_9, 2026.09
# - 09.2026, 9.2026, 09-2026, 09_2026, T09.2026, T9-2026
# - Tháng 9 năm 2026, Thang 09 nam 2026
_PERIOD_YMD_RE = re.compile(r"(?<!\d)(20\d{2})[\-_.](0?[1-9]|1[0-2])(?!\d)")
_PERIOD_MY_RE = re.compile(r"(?<!\d)(?:[tT])?(0?[1-9]|1[0-2])[\-_./](20\d{2})(?!\d)")
_PERIOD_VN_RE = re.compile(
    r"th[aá]ng\s*(0?[1-9]|1[0-2])\s*(?:n[aă]m\s*)?(20\d{2})(?!\d)",
    re.IGNORECASE,
)

# Các cụm từ chung thường xuất hiện trong tên file báo cáo — tước đi khi tính fuzzy trên tên NCC
_BOILERPLATE_RE = re.compile(
    r"(?:b[aả]ng\s*ph[ií](?:\s*ki[eể]m\s*tra,?\s*ph[aâ]n\s*lo[aạ]i\s*h[aà]ng\s*h[oó]a)?"
    r"|b[aá]o\s*c[aá]o|chi\s*ph[ií]|t[aạ]m\s*t[ií]nh|ch[oố]t|final|draft|po\b"
    r"|th[aá]ng|n[aă]m)",
    re.IGNORECASE,
)


def is_junk_filename(name: str) -> bool:
    """Trả về True nếu là tệp rác hệ thống, tệp tạm Office hoặc phần mở rộng không được phép."""
    norm = normalize_unicode(name).strip()
    if not norm:
        return True
    low = norm.lower()
    if low in _JUNK_NAMES:
        return True
    if any(low.startswith(pref) for pref in _JUNK_PREFIXES):
        return True
    if any(low.endswith(suf) for suf in _JUNK_SUFFIXES):
        return True
    ext = Path(low).suffix
    return ext not in _ALLOWED_EXTS


def filter_valid_files(files: list[ScannedFile]) -> list[ScannedFile]:
    """Lọc giữ lại danh sách tệp Excel/PDF hợp lệ (chưa loại 0 byte để vẫn báo lỗi 0 KB rõ ràng)."""
    return [f for f in files if not is_junk_filename(f.name) and f.file_type is not None]


def extract_period_from_text(text: str) -> Optional[tuple[int, int]]:
    """Trích xuất `(month, year)` từ tên file hoặc tên thư mục; trả về `None` nếu không rõ."""
    norm = normalize_unicode(text)
    for pattern, order in (
        (_PERIOD_VN_RE, "my"),
        (_PERIOD_YMD_RE, "ym"),
        (_PERIOD_MY_RE, "my"),
    ):
        match = pattern.search(norm)
        if match:
            if order == "ym":
                year, month = int(match.group(1)), int(match.group(2))
            else:
                month, year = int(match.group(1)), int(match.group(2))
            if 1 <= month <= 12 and 2000 <= year <= 2100:
                return month, year
    return None


def suggest_period(
    files: list[ScannedFile],
    folder_name: str = "",
    known_subfolders: list[str] | None = None,
    today: Optional[date] = None,
) -> PeriodSuggestion:
    """Tự động gợi ý kỳ gửi `(tháng, năm)` thông minh theo 3 mức ưu tiên."""
    # Ưu tiên 1: Bỏ phiếu đa số từ tên các file vừa chọn/kéo-thả
    valid = filter_valid_files(files)
    votes: Counter[tuple[int, int]] = Counter()
    for f in valid:
        period = extract_period_from_text(f.name)
        if period is not None:
            votes[period] += 1
    if votes:
        (month, year), count = votes.most_common(1)[0]
        return PeriodSuggestion(
            month=month,
            year=year,
            reason=f"Tự nhận diện từ {count} tệp đính kèm ({month:02d}/{year}).",
        )

    # Ưu tiên 2: Tên thư mục hiện tại vừa chọn
    if folder_name:
        folder_period = extract_period_from_text(folder_name)
        if folder_period is not None:
            m, y = folder_period
            return PeriodSuggestion(
                month=m,
                year=y,
                reason=f"Tự nhận diện từ tên thư mục '{folder_name}'.",
            )

    # Ưu tiên 3: Thư mục kỳ mới nhất trong thư mục gốc đính kèm
    if known_subfolders:
        parsed: list[tuple[int, int, str]] = []
        for sub in known_subfolders:
            p = extract_period_from_text(sub)
            if p is not None:
                parsed.append((p[1], p[0], sub))
        if parsed:
            parsed.sort(reverse=True)
            y, m, sub = parsed[0]
            return PeriodSuggestion(
                month=m,
                year=y,
                reason=f"Tự phát hiện thư mục kỳ mới nhất '{sub}'.",
                source_dir=sub,
            )

    # Ưu tiên 4: Chu kỳ Kế toán/HR (ngày 1–15 thường gửi báo cáo tháng trước)
    ref = today or date.today()
    if ref.day <= 15:
        if ref.month == 1:
            return PeriodSuggestion(12, ref.year - 1, "Đầu tháng — tự gợi ý kỳ báo cáo tháng trước.")
        return PeriodSuggestion(
            ref.month - 1, ref.year, "Đầu tháng — tự gợi ý kỳ báo cáo tháng trước."
        )
    return PeriodSuggestion(ref.month, ref.year, "Nửa cuối tháng — gợi ý kỳ báo cáo tháng hiện tại.")


def detect_send_kind(files: list[ScannedFile]) -> tuple[SendKind, bool]:
    """Tự nhận diện chế độ gửi (`Tạm tính` vs `Chốt`) và cảnh báo thiếu PDF không đồng đều."""
    valid = filter_valid_files(files)
    excel_count = sum(1 for f in valid if f.file_type == FileType.EXCEL)
    pdf_count = sum(1 for f in valid if f.file_type == FileType.PDF)
    if pdf_count > 0:
        partial_warning = excel_count > 0 and pdf_count < excel_count
        return SendKind.FINAL, partial_warning
    return SendKind.DRAFT, False


def _strip_accents(text: str) -> str:
    nfd = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")


def _token_boundary_pattern(term: str) -> re.Pattern[str]:
    """Biểu thức chính quy khớp nguyên token có ranh giới không phải chữ/số.

    Hỗ trợ tên có ký tự đặc biệt như `T&T`, `HR Partner`, `A.B` mà không dính `A` vào `AB`.
    """
    escaped = re.escape(normalize_name(term))
    # Cho phép nhiều khoảng trắng hoặc _ / - giữa các từ trong tên nhiều từ (vd "HR Partner" ~ "HR_Partner")
    flexible = re.sub(r"\\\s+", r"[\\s_\\-]+", escaped)
    return re.compile(rf"(?<![A-Za-z0-9À-ỹ]){flexible}(?![A-Za-z0-9À-ỹ])", re.IGNORECASE)


def _match_terms_in_stem(stem_norm: str, term_entries: list[tuple[str, int, str]]) -> set[int]:
    """Tìm các `supplier_idx` khớp ranh giới từ trong `stem_norm` theo nguyên tắc Longest-Match-First.

    Khi một chuỗi dài hơn (`T&T Logistics`, `HR Partner`, `ACE2`, `AB`) đã khớp tại vị trí `[start, end)`,
    khoảng vị trí đó bị chiếm dụng để chuỗi con ngắn hơn (`T&T`, `HR`, `ACE`, `A`) không khớp ké!
    """
    claimed_spans: list[tuple[int, int]] = []
    matched_suppliers: set[int] = set()

    # Sắp xếp giảm dần theo độ dài từ khóa -> Longest-Match-First
    ordered = sorted(term_entries, key=lambda item: len(item[0]), reverse=True)
    for term_norm, sup_idx, _raw_term in ordered:
        if not term_norm:
            continue
        pattern = _token_boundary_pattern(term_norm)
        for m in pattern.finditer(stem_norm):
            span = (m.start(), m.end())
            if any(not (span[1] <= cs[0] or span[0] >= cs[1]) for cs in claimed_spans):
                continue
            claimed_spans.append(span)
            matched_suppliers.add(sup_idx)
    return matched_suppliers


def _extract_vendor_residual(filename: str) -> str:
    """Tước phần mở rộng, kỳ tháng/năm và từ khóa mẫu chung để chỉ còn lại phần tên NCC."""
    stem = normalize_unicode(Path(filename).stem)
    stem = _PERIOD_VN_RE.sub(" ", stem)
    stem = _PERIOD_YMD_RE.sub(" ", stem)
    stem = _PERIOD_MY_RE.sub(" ", stem)
    stem = _BOILERPLATE_RE.sub(" ", stem)
    stem = re.sub(r"[_\-\.\(\)\[\],]+", " ", stem)
    return re.sub(r"\s+", " ", stem).strip()


def _fuzzy_vendor_score(residual: str, supplier_terms: list[str]) -> float:
    """Tính độ tương đồng CHỈ trên phần tên NCC đã tước hết tiền tố chung.

    Ngăn chặn triệt để bẫy tiền tố chung (`Bảng phí ... 09.2026 ACE` vs `AHC`).
    Chặn fuzzy với tên quá ngắn (<= 3 ký tự như `ACE`, `AHC`, `T&T`) để không bao giờ gợi ý nhầm 1 ký tự!
    """
    res_clean = _strip_accents(residual).lower().strip()
    if not res_clean:
        return 0.0
    best = 0.0
    for term in supplier_terms:
        t_clean = _strip_accents(normalize_name(term))
        # Tên ngắn <= 3 ký tự (ACE vs AHC khác đúng 1/3 ký tự) -> CẤM fuzzy, chỉ chấp nhận khớp chính xác!
        if len(t_clean) <= 3:
            continue
        if abs(len(res_clean) - len(t_clean)) > max(3, len(t_clean) // 2):
            continue
        ratio = SequenceMatcher(None, res_clean, t_clean).ratio()
        if ratio > best:
            best = ratio
    return best


def match_files_for_suppliers(
    suppliers: list[Supplier],
    scanned_files: list[ScannedFile],
    month: int,
    year: int,
    kind: SendKind,
    excel_template: str,
    pdf_template: str,
    manual_overrides: Optional[dict[tuple[int, FileType], ScannedFile]] = None,
    logo_size_bytes: int = 0,
) -> tuple[dict[int, list[AttachmentMatch]], list[DiscoveredSupplier]]:
    """Khớp tệp đính kèm an toàn 3 tầng cho toàn bộ nhà cung cấp.

    Args:
        suppliers: Danh sách NCC (khóa kết quả trả về là chỉ số `idx` trong danh sách này).
        scanned_files: Danh sách tệp tin đã quét được (từ thư mục hoặc kéo-thả).
        month, year, kind: Kỳ gửi và chế độ (`Tạm tính` hoặc `Chốt`).
        excel_template, pdf_template: Mẫu tên file dự kiến.
        manual_overrides: Bản đồ `{(supplier_idx, FileType): ScannedFile}` do người dùng đã duyệt/chọn tay.
        logo_size_bytes: Dung lượng logo (nếu có) để tính chung vào trần 18 MB Gmail.

    Returns:
        `(matches_by_supplier_idx, discovered_unknown_suppliers)`
    """
    overrides = manual_overrides or {}
    valid_files = filter_valid_files(scanned_files)
    required_types = [FileType.EXCEL] if kind == SendKind.DRAFT else [FileType.EXCEL, FileType.PDF]

    # Xây bảng từ khóa toàn cục (tên NCC + aliases) cho toàn bộ NCC đang bật (để kiểm tra chéo âm tính)
    term_entries: list[tuple[str, int, str]] = []
    terms_by_sup: dict[int, list[str]] = {}
    for idx, sup in enumerate(suppliers):
        sup_terms = [sup.name, *sup.aliases]
        clean_terms = [normalize_name(t) for t in sup_terms if normalize_name(t)]
        terms_by_sup[idx] = clean_terms
        for raw_t in sup_terms:
            tn = normalize_name(raw_t)
            if tn:
                term_entries.append((tn, idx, raw_t))

    # Gắn nhãn từng file với tập NCC mà nó khớp ranh giới từ + kỳ tháng/năm trích xuất được
    file_matched_sups: dict[Path, set[int]] = {}
    file_periods: dict[Path, Optional[tuple[int, int]]] = {}
    files_by_norm_name: dict[str, list[ScannedFile]] = {}
    for f in valid_files:
        norm_fname = normalize_name(f.name)
        files_by_norm_name.setdefault(norm_fname, []).append(f)
        stem_norm = normalize_name(Path(f.name).stem)
        file_matched_sups[f.path] = _match_terms_in_stem(stem_norm, term_entries)
        file_periods[f.path] = extract_period_from_text(f.name)

    results: dict[int, list[AttachmentMatch]] = {idx: [] for idx in range(len(suppliers))}
    claimed_paths: set[Path] = set()

    for idx, sup in enumerate(suppliers):
        values = {
            "thang": f"{month:02d}",
            "nam": str(year),
            "nha_cung_cap": sup.name,
            "loai": kind.value,
        }
        for ftype in required_types:
            tpl = excel_template if ftype == FileType.EXCEL else pdf_template
            expected_name = render(tpl, values)
            expected_norm = normalize_name(expected_name)

            # 0) Ưu tiên cao nhất: Người dùng đã chọn tay / bấm duyệt thủ công
            if (idx, ftype) in overrides:
                chosen = overrides[(idx, ftype)]
                if chosen.size_bytes <= 0:
                    results[idx].append(
                        AttachmentMatch(
                            file_type=ftype,
                            expected_name=expected_name,
                            status=MatchStatus.INVALID_FILE,
                            file=chosen,
                            note=f"File đính kèm bị rỗng (0 KB): {chosen.name}",
                        )
                    )
                else:
                    claimed_paths.add(chosen.path)
                    results[idx].append(
                        AttachmentMatch(
                            file_type=ftype,
                            expected_name=expected_name,
                            status=MatchStatus.MANUAL_CONFIRMED,
                            file=chosen,
                            note="Người dùng đã chọn/xác nhận thủ công.",
                            score=1.0,
                        )
                    )
                continue

            typed_files = [f for f in valid_files if f.file_type == ftype]

            # 1) Tầng Xanh 1: EXACT match theo tên file mẫu đã render (NFC)
            exact_hits = [f for f in files_by_norm_name.get(expected_norm, []) if f.file_type == ftype]
            if len(exact_hits) == 1:
                hit = exact_hits[0]
                if hit.size_bytes <= 0:
                    results[idx].append(
                        AttachmentMatch(
                            file_type=ftype,
                            expected_name=expected_name,
                            status=MatchStatus.INVALID_FILE,
                            file=hit,
                            note=f"File đính kèm bị rỗng (0 KB): {hit.name}",
                        )
                    )
                else:
                    claimed_paths.add(hit.path)
                    results[idx].append(
                        AttachmentMatch(
                            file_type=ftype,
                            expected_name=expected_name,
                            status=MatchStatus.EXACT,
                            file=hit,
                            note="Khớp chính xác 100% tên mẫu.",
                            score=1.0,
                        )
                    )
                continue
            if len(exact_hits) > 1:
                results[idx].append(
                    AttachmentMatch(
                        file_type=ftype,
                        expected_name=expected_name,
                        status=MatchStatus.AMBIGUOUS,
                        candidates=exact_hits,
                        note=f"Có {len(exact_hits)} file trùng tên '{expected_name}'. Vui lòng chọn tay.",
                    )
                )
                continue

            # 2) Tầng Xanh 2: Word-Boundary Token Match + Longest-Match-First + Period Gate
            token_hits = [f for f in typed_files if idx in file_matched_sups[f.path]]
            if token_hits:
                # Kiểm tra xung đột: có file nào khớp đồng thời >= 2 NCC khác nhau không?
                cross_conflicts = [f for f in token_hits if len(file_matched_sups[f.path]) >= 2]
                if cross_conflicts:
                    results[idx].append(
                        AttachmentMatch(
                            file_type=ftype,
                            expected_name=expected_name,
                            status=MatchStatus.CONFLICT,
                            candidates=cross_conflicts,
                            note="File chứa tên của nhiều nhà cung cấp cùng lúc — đã khóa gửi để chống gửi nhầm.",
                        )
                    )
                    continue

                # Kiểm tra kỳ tháng/năm trên các file khớp token
                period_ok: list[ScannedFile] = []
                period_wrong: list[ScannedFile] = []
                for f in token_hits:
                    fp = file_periods[f.path]
                    if fp is None or fp == (month, year):
                        period_ok.append(f)
                    else:
                        period_wrong.append(f)

                if len(period_ok) == 1:
                    hit = period_ok[0]
                    if hit.size_bytes <= 0:
                        results[idx].append(
                            AttachmentMatch(
                                file_type=ftype,
                                expected_name=expected_name,
                                status=MatchStatus.INVALID_FILE,
                                file=hit,
                                note=f"File đính kèm bị rỗng (0 KB): {hit.name}",
                            )
                        )
                    else:
                        claimed_paths.add(hit.path)
                        results[idx].append(
                            AttachmentMatch(
                                file_type=ftype,
                                expected_name=expected_name,
                                status=MatchStatus.AUTO_MATCHED,
                                file=hit,
                                note="Tự khớp thông minh theo tên NCC & kỳ gửi.",
                                score=0.95,
                            )
                        )
                    continue

                if len(period_ok) > 1:
                    results[idx].append(
                        AttachmentMatch(
                            file_type=ftype,
                            expected_name=expected_name,
                            status=MatchStatus.AMBIGUOUS,
                            candidates=period_ok,
                            note=(
                                f"Tìm thấy {len(period_ok)} file cùng khớp '{sup.name}' "
                                "(ví dụ bản nháp và bản sửa). Bắt buộc chọn tay."
                            ),
                        )
                    )
                    continue

                # Chỉ có file khớp tên NCC nhưng lệch kỳ tháng/năm
                wrong_desc = ", ".join(
                    f"{f.name} ({file_periods[f.path][0]:02d}/{file_periods[f.path][1]})"  # type: ignore[index]
                    for f in period_wrong
                )
                results[idx].append(
                    AttachmentMatch(
                        file_type=ftype,
                        expected_name=expected_name,
                        status=MatchStatus.WRONG_PERIOD,
                        candidates=period_wrong,
                        note=f"Nghi ngờ file kỳ cũ/sai tháng (đang gửi {month:02d}/{year}): {wrong_desc}",
                    )
                )
                continue

            # 3) Tầng Vàng: Gợi ý gần đúng (Fuzzy trên phần tên NCC đã tước tiền tố chung)
            # CHỈ xét các file chưa khớp token của BẤT KỲ NCC nào khác và đúng kỳ (hoặc không ghi kỳ)
            fuzzy_candidates: list[tuple[float, ScannedFile]] = []
            for f in typed_files:
                if file_matched_sups[f.path]:
                    continue  # File thuộc NCC khác -> TUYỆT ĐỐI KHÔNG gợi ý sang NCC này!
                fp = file_periods[f.path]
                if fp is not None and fp != (month, year):
                    continue
                residual = _extract_vendor_residual(f.name)
                score = _fuzzy_vendor_score(residual, terms_by_sup[idx])
                if score >= 0.78:
                    fuzzy_candidates.append((score, f))

            fuzzy_candidates.sort(key=lambda item: item[0], reverse=True)
            if len(fuzzy_candidates) == 1:
                best_score, best_file = fuzzy_candidates[0]
                if best_file.size_bytes <= 0:
                    results[idx].append(
                        AttachmentMatch(
                            file_type=ftype,
                            expected_name=expected_name,
                            status=MatchStatus.INVALID_FILE,
                            file=best_file,
                            note=f"File gợi ý bị rỗng (0 KB): {best_file.name}",
                        )
                    )
                else:
                    results[idx].append(
                        AttachmentMatch(
                            file_type=ftype,
                            expected_name=expected_name,
                            status=MatchStatus.NEEDS_REVIEW,
                            file=best_file,
                            candidates=[best_file],
                            note=(
                                f"Gợi ý gần đúng ({int(best_score * 100)}%) — "
                                "vui lòng đối chiếu tên file và bấm duyệt trước khi gửi."
                            ),
                            score=best_score,
                        )
                    )
                continue
            if len(fuzzy_candidates) > 1:
                results[idx].append(
                    AttachmentMatch(
                        file_type=ftype,
                        expected_name=expected_name,
                        status=MatchStatus.AMBIGUOUS,
                        candidates=[f for _, f in fuzzy_candidates[:4]],
                        note="Có nhiều file tên gần giống. Vui lòng chọn tay đúng file.",
                    )
                )
                continue

            # 4) Tầng Đỏ: Không tìm thấy file
            results[idx].append(
                AttachmentMatch(
                    file_type=ftype,
                    expected_name=expected_name,
                    status=MatchStatus.MISSING,
                    note=f"Không tìm thấy file: {expected_name}",
                )
            )

    # 5) Bất biến Song ánh 1-1 Toàn cục (Global Disjoint Invariant theo cả Path lẫn SHA-256)
    _enforce_global_disjoint_invariant(results, suppliers)

    # 6) Kiểm tra tổng dung lượng đính kèm + logo không vượt 18 MB
    for matches in results.values():
        ready_files = [m.file for m in matches if m.file is not None and m.is_ready]
        total_size = sum(f.size_bytes for f in ready_files) + logo_size_bytes
        if ready_files and total_size > MAX_TOTAL_ATTACHMENT_BYTES:
            mb = total_size / (1024 * 1024)
            for m in matches:
                if m.is_ready:
                    m.status = MatchStatus.INVALID_FILE
                    m.note = (
                        f"Tổng dung lượng đính kèm (+ logo) vượt giới hạn 18 MB của Gmail ({mb:.1f} MB)."
                    )

    # 7) Auto-Discovery: Các file hợp lệ chưa thuộc NCC nào -> gom gợi ý thêm NCC mới
    all_used_paths = set(claimed_paths)
    for matches in results.values():
        for m in matches:
            if m.file is not None:
                all_used_paths.add(m.file.path)
            for cand in m.candidates:
                all_used_paths.add(cand.path)

    discovered = discover_unknown_suppliers(
        [f for f in valid_files if f.path not in all_used_paths and not file_matched_sups[f.path]],
        excel_template=excel_template,
        pdf_template=pdf_template,
        month=month,
        year=year,
    )
    return results, discovered


def _enforce_global_disjoint_invariant(
    results: dict[int, list[AttachmentMatch]],
    suppliers: list[Supplier],
) -> None:
    """Đảm bảo tuyệt đối 0 có tệp nào (cùng path HOẶC cùng SHA-256) được gắn cho >= 2 NCC bật."""
    path_owners: dict[Path, list[tuple[int, AttachmentMatch]]] = {}
    hash_owners: dict[str, list[tuple[int, AttachmentMatch]]] = {}

    for idx, matches in results.items():
        if not suppliers[idx].enabled:
            continue
        for m in matches:
            if m.file is None or not (m.is_ready or m.needs_review):
                continue
            path_owners.setdefault(m.file.path, []).append((idx, m))
            if m.file.sha256:
                hash_owners.setdefault(m.file.sha256, []).append((idx, m))

    for owners in path_owners.values():
        distinct_sups = {idx for idx, _ in owners}
        if len(distinct_sups) >= 2:
            names = ", ".join(suppliers[i].name for i in sorted(distinct_sups))
            for _idx, m in owners:
                m.status = MatchStatus.CONFLICT
                m.note = (
                    f"Xung đột bảo mật: cùng 1 file '{m.file.name if m.file else ''}' "
                    f"đang gắn cho nhiều NCC ({names}). Đã khóa gửi!"
                )

    for owners in hash_owners.values():
        distinct_sups = {idx for idx, _ in owners}
        if len(distinct_sups) >= 2:
            names = ", ".join(suppliers[i].name for i in sorted(distinct_sups))
            for _idx, m in owners:
                m.status = MatchStatus.CONFLICT
                m.note = (
                    f"Xung đột nội dung (trùng SHA-256): file của nhiều NCC ({names}) "
                    "có nội dung giống hệt nhau. Đã khóa để tránh gửi nhầm!"
                )


def _template_to_vendor_regex(template: str, month: int, year: int) -> Optional[re.Pattern[str]]:
    """Đảo ngược mẫu tên file (thay `{nha_cung_cap}` thành capture group) để bóc tên NCC mới."""
    if "{nha_cung_cap}" not in template:
        return None
    sentinel = "__SUPPLIER_TOKEN__"
    rendered = render(
        template,
        {
            "thang": f"{month:02d}",
            "nam": str(year),
            "nha_cung_cap": sentinel,
            "loai": "Tạm tính",
        },
    )
    escaped = re.escape(normalize_unicode(Path(rendered).stem))
    # Cho phép tháng 09 hoặc 9 linh hoạt khi nhận diện
    month_padded = f"{month:02d}"
    escaped = escaped.replace(re.escape(month_padded), rf"0?{month}")
    pattern_str = escaped.replace(re.escape(sentinel), r"(?P<supplier>.+?)")
    return re.compile(rf"^{pattern_str}$", re.IGNORECASE)


def discover_unknown_suppliers(
    unmatched_files: list[ScannedFile],
    excel_template: str,
    pdf_template: str,
    month: int,
    year: int,
) -> list[DiscoveredSupplier]:
    """Gợi ý thêm nhà cung cấp mới từ các tệp Excel/PDF chưa thuộc NCC nào."""
    excel_re = _template_to_vendor_regex(excel_template, month, year)
    pdf_re = _template_to_vendor_regex(pdf_template, month, year)

    grouped: dict[str, tuple[str, list[ScannedFile]]] = {}
    for f in unmatched_files:
        if f.size_bytes <= 0:
            continue
        stem = normalize_unicode(Path(f.name).stem)
        extracted = ""
        regex = excel_re if f.file_type == FileType.EXCEL else pdf_re
        if regex is not None:
            m = regex.match(stem)
            if m:
                extracted = m.group("supplier").strip(" -_.")
        if not extracted:
            extracted = _extract_vendor_residual(f.name)
        if not extracted or len(extracted) < 2:
            continue
        key = normalize_name(extracted)
        if key not in grouped:
            grouped[key] = (extracted, [f])
        else:
            grouped[key][1].append(f)

    return [
        DiscoveredSupplier(suggested_name=display, files=flist)
        for display, flist in sorted(grouped.values(), key=lambda x: x[0].lower())
    ]
