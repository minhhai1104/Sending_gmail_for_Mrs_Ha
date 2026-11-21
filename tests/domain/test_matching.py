"""Bộ kiểm thử đối kháng cho Động cơ Khớp File 3 Tầng (Zero Wrong-Vendor Delivery)."""

from __future__ import annotations

import unicodedata
from datetime import date
from pathlib import Path

import pytest

from app.domain.matching import (
    detect_send_kind,
    extract_period_from_text,
    is_junk_filename,
    match_files_for_suppliers,
    suggest_period,
)
from app.domain.models import (
    DEFAULT_EXCEL_TEMPLATE,
    DEFAULT_PDF_TEMPLATE,
    MAX_TOTAL_ATTACHMENT_BYTES,
    FileType,
    MatchStatus,
    ScannedFile,
    SendKind,
    Supplier,
)


def _sf(name: str, size: int = 4096, sha: str = "") -> ScannedFile:
    p = Path("C:/reports") / name
    return ScannedFile(
        path=p,
        name=unicodedata.normalize("NFC", name),
        ext=p.suffix.lower(),
        size_bytes=size,
        sha256=sha or f"sha_{name}",
    )


def _sup(idx: int, name: str, aliases: list[str] | None = None, enabled: bool = True) -> Supplier:
    return Supplier(
        id=idx,
        name=name,
        recipients=[f"{name.lower().replace(' ', '')}@example.com"],
        aliases=aliases or [],
        enabled=enabled,
    )


class TestJunkAndPeriodExtraction:
    @pytest.mark.parametrize(
        "filename,expected_junk",
        [
            ("~$Bảng phí 09.2026 ACE.xlsx", True),
            (".~lock.PO ACE 09.2026.pdf#", True),
            ("._ACE.xlsx", True),
            ("desktop.ini", True),
            ("Thumbs.db", True),
            (".DS_Store", True),
            ("Cau_hinh.xlsx", True),
            ("Lich_su_gui.xlsx", True),
            ("PO ACE 09.2026.pdf.exe", True),
            ("temp.xlsx.tmp", True),
            ("backup.bak", True),
            ("   ", True),
            ("Bảng phí 09.2026 ACE.xlsx", False),
            ("PO ACE 09.2026.PDF", False),
            ("Bang_phi_ACE.xls", False),
        ],
    )
    def test_junk_filter(self, filename: str, expected_junk: bool) -> None:
        assert is_junk_filename(filename) is expected_junk

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("Bảng phí kiểm tra 09.2026 ACE.xlsx", (9, 2026)),
            ("PO ACE 9.2026.pdf", (9, 2026)),
            ("2026-09", (9, 2026)),
            ("2026_9_BaoCao", (9, 2026)),
            ("T09-2026_ACE.xlsx", (9, 2026)),
            ("Bao cao Tháng 9 năm 2026.xlsx", (9, 2026)),
            ("Bao cao Thang 12 2026.xlsx", (12, 2026)),
            # Không được khớp nhầm số dính liền!
            ("PO 19.2026 ACE.pdf", None),
            ("PO_90_ACE.pdf", None),
            ("Bao cao ACE.xlsx", None),
        ],
    )
    def test_extract_period(self, text: str, expected: tuple[int, int] | None) -> None:
        assert extract_period_from_text(text) == expected

    def test_suggest_period_priorities(self) -> None:
        # 1. Majority vote từ files
        s1 = suggest_period(
            [_sf("PO ACE 08.2026.pdf"), _sf("PO AHC 08.2026.pdf"), _sf("PO T&T 09.2026.pdf")]
        )
        assert (s1.month, s1.year) == (8, 2026)

        # 2. Từ tên thư mục
        s2 = suggest_period([], folder_name="BaoCao_2026-07")
        assert (s2.month, s2.year) == (7, 2026)

        # 3. Từ thư mục kỳ mới nhất
        s3 = suggest_period([], known_subfolders=["2026-05", "2026-10", "notes"])
        assert (s3.month, s3.year) == (10, 2026)
        assert s3.source_dir == "2026-10"

        # 4a. Fallback đầu tháng (ngày 1-15 -> tháng trước, kể cả tháng 1 -> tháng 12 năm trước)
        s4a = suggest_period([], today=date(2026, 1, 5))
        assert (s4a.month, s4a.year) == (12, 2025)
        s4b = suggest_period([], today=date(2026, 10, 10))
        assert (s4b.month, s4b.year) == (9, 2026)

        # 4b. Fallback cuối tháng (ngày >=16 -> tháng hiện tại)
        s4c = suggest_period([], today=date(2026, 10, 20))
        assert (s4c.month, s4c.year) == (10, 2026)

    def test_detect_send_kind(self) -> None:
        k1, w1 = detect_send_kind([_sf("ACE.xlsx"), _sf("AHC.xlsx")])
        assert k1 == SendKind.DRAFT and w1 is False

        k2, w2 = detect_send_kind([_sf("ACE.xlsx"), _sf("AHC.xlsx"), _sf("PO ACE.pdf")])
        assert k2 == SendKind.FINAL and w2 is True

        k3, w3 = detect_send_kind([_sf("ACE.xlsx"), _sf("PO ACE.pdf")])
        assert k3 == SendKind.FINAL and w3 is False


class TestZeroWrongVendorMatching:
    """Ma trận kiểm thử chống gửi nhầm nhà cung cấp (100% bất biến an toàn)."""

    def test_ace_present_ahc_missing_never_cross_matches(self) -> None:
        """BẪY CHÍ MẠNG HAESUNG VINA: ACE và AHC giống nhau >96% tiền tố!
        Khi AHC thiếu file, TUYỆT ĐỐI KHÔNG được gán hay gợi ý file của ACE cho AHC."""
        sups = [_sup(1, "ACE"), _sup(2, "AHC")]
        files = [_sf("Bảng phí kiểm tra, phân loại hàng hóa 09.2026 ACE.xlsx")]

        matches, discovered = match_files_for_suppliers(
            sups, files, 9, 2026, SendKind.DRAFT, DEFAULT_EXCEL_TEMPLATE, DEFAULT_PDF_TEMPLATE
        )
        assert matches[0][0].status == MatchStatus.EXACT
        assert matches[0][0].file is not None and "ACE" in matches[0][0].file.name
        assert matches[1][0].status == MatchStatus.MISSING
        assert matches[1][0].file is None
        assert discovered == []

    @pytest.mark.parametrize(
        "sup_names,filename,expected_owner_idx",
        [
            (["A", "AB", "ABC"], "Bang phi 09.2026 AB.xlsx", 1),
            (["ACE", "ACE2", "ACE-VN"], "PO ACE2 09.2026.xlsx", 1),
            (["T&T", "T&T Logistics"], "Bang phi 09.2026 T&T Logistics.xlsx", 1),
            (["HR", "HR Partner"], "09.2026_HR_Partner.xlsx", 1),
            (["HR", "HR Partner"], "09.2026 HR.xlsx", 0),
        ],
    )
    def test_longest_match_prevents_substring_collision(
        self, sup_names: list[str], filename: str, expected_owner_idx: int
    ) -> None:
        sups = [_sup(i + 1, n) for i, n in enumerate(sup_names)]
        files = [_sf(filename)]
        matches, _ = match_files_for_suppliers(
            sups, files, 9, 2026, SendKind.DRAFT, DEFAULT_EXCEL_TEMPLATE, DEFAULT_PDF_TEMPLATE
        )
        for idx in range(len(sups)):
            if idx == expected_owner_idx:
                assert matches[idx][0].is_ready is True
                assert matches[idx][0].file is not None
            else:
                assert matches[idx][0].status == MatchStatus.MISSING
                assert matches[idx][0].file is None

    def test_unicode_nfd_and_single_digit_month_auto_matches(self) -> None:
        sups = [_sup(1, "Hòa Phát"), _sup(2, "DiaMond")]
        nfd_name = unicodedata.normalize("NFD", "Bảng phí 9.2026 Hòa Phát.xlsx")
        files = [_sf(nfd_name), _sf("Bang phi 9.2026 DIAMOND.xlsx")]
        matches, _ = match_files_for_suppliers(
            sups, files, 9, 2026, SendKind.DRAFT, DEFAULT_EXCEL_TEMPLATE, DEFAULT_PDF_TEMPLATE
        )
        assert matches[0][0].status == MatchStatus.AUTO_MATCHED
        assert matches[1][0].status == MatchStatus.AUTO_MATCHED

    def test_alias_auto_matches(self) -> None:
        sups = [_sup(1, "HR Partner", aliases=["HRP"])]
        files = [_sf("Bang_phi_09.2026_HRP.xlsx"), _sf("PO_HRP_09.2026.pdf")]
        matches, _ = match_files_for_suppliers(
            sups, files, 9, 2026, SendKind.FINAL, DEFAULT_EXCEL_TEMPLATE, DEFAULT_PDF_TEMPLATE
        )
        assert matches[0][0].status == MatchStatus.AUTO_MATCHED
        assert matches[0][1].status == MatchStatus.AUTO_MATCHED

    def test_fuzzy_typo_is_yellow_needs_review_never_auto_ready(self) -> None:
        """Lỗi gõ nhẹ 'DiaMon' cho 'DiaMond' -> chỉ lên Tầng Vàng NEEDS_REVIEW (chưa sendable)."""
        sups = [_sup(1, "DiaMond")]
        files = [_sf("Bang phi 09.2026 DiaMon.xlsx")]
        matches, _ = match_files_for_suppliers(
            sups, files, 9, 2026, SendKind.DRAFT, DEFAULT_EXCEL_TEMPLATE, DEFAULT_PDF_TEMPLATE
        )
        att = matches[0][0]
        assert att.status == MatchStatus.NEEDS_REVIEW
        assert att.needs_review is True
        assert att.is_ready is False
        assert att.file is not None and "DiaMon" in att.file.name

    def test_ambiguous_multiple_files_hard_blocked(self) -> None:
        sups = [_sup(1, "ACE")]
        files = [_sf("Bang phi 09.2026 ACE v1.xlsx"), _sf("Bang phi 09.2026 ACE final.xlsx")]
        matches, _ = match_files_for_suppliers(
            sups, files, 9, 2026, SendKind.DRAFT, DEFAULT_EXCEL_TEMPLATE, DEFAULT_PDF_TEMPLATE
        )
        assert matches[0][0].status == MatchStatus.AMBIGUOUS
        assert matches[0][0].is_blocked is True
        assert len(matches[0][0].candidates) == 2

    def test_wrong_period_file_hard_blocked(self) -> None:
        sups = [_sup(1, "ACE")]
        files = [_sf("Bang phi 08.2026 ACE.xlsx")]
        matches, _ = match_files_for_suppliers(
            sups, files, 9, 2026, SendKind.DRAFT, DEFAULT_EXCEL_TEMPLATE, DEFAULT_PDF_TEMPLATE
        )
        assert matches[0][0].status == MatchStatus.WRONG_PERIOD
        assert matches[0][0].is_blocked is True

    def test_cross_vendor_filename_conflict_hard_blocked(self) -> None:
        sups = [_sup(1, "ACE"), _sup(2, "Mansa")]
        files = [_sf("Bang phi 09.2026 ACE Mansa.xlsx")]
        matches, _ = match_files_for_suppliers(
            sups, files, 9, 2026, SendKind.DRAFT, DEFAULT_EXCEL_TEMPLATE, DEFAULT_PDF_TEMPLATE
        )
        assert matches[0][0].status == MatchStatus.CONFLICT
        assert matches[1][0].status == MatchStatus.CONFLICT

    def test_global_disjoint_sha256_invariant_blocks_duplicate_content(self) -> None:
        """Hai file tên khác nhau nhưng nội dung (SHA-256) giống hệt nhau -> khóa cả 2 NCC!"""
        sups = [_sup(1, "ACE"), _sup(2, "AHC")]
        same_sha = "deadbeef" * 8
        files = [
            _sf("Bảng phí kiểm tra, phân loại hàng hóa 09.2026 ACE.xlsx", sha=same_sha),
            _sf("Bảng phí kiểm tra, phân loại hàng hóa 09.2026 AHC.xlsx", sha=same_sha),
        ]
        matches, _ = match_files_for_suppliers(
            sups, files, 9, 2026, SendKind.DRAFT, DEFAULT_EXCEL_TEMPLATE, DEFAULT_PDF_TEMPLATE
        )
        assert matches[0][0].status == MatchStatus.CONFLICT
        assert matches[1][0].status == MatchStatus.CONFLICT

    def test_global_disjoint_path_invariant_on_manual_override(self) -> None:
        sups = [_sup(1, "ACE"), _sup(2, "AHC")]
        shared = _sf("shared_file.xlsx", sha="1111" * 16)
        matches, _ = match_files_for_suppliers(
            sups,
            [shared],
            9,
            2026,
            SendKind.DRAFT,
            DEFAULT_EXCEL_TEMPLATE,
            DEFAULT_PDF_TEMPLATE,
            manual_overrides={(0, FileType.EXCEL): shared, (1, FileType.EXCEL): shared},
        )
        assert matches[0][0].status == MatchStatus.CONFLICT
        assert matches[1][0].status == MatchStatus.CONFLICT

    def test_zero_byte_and_oversized_with_logo_blocked(self) -> None:
        sups = [_sup(1, "ACE"), _sup(2, "Mansa")]
        files = [
            _sf("Bảng phí kiểm tra, phân loại hàng hóa 09.2026 ACE.xlsx", size=0),
            _sf(
                "Bảng phí kiểm tra, phân loại hàng hóa 09.2026 Mansa.xlsx",
                size=MAX_TOTAL_ATTACHMENT_BYTES - 500,
            ),
        ]
        matches, _ = match_files_for_suppliers(
            sups,
            files,
            9,
            2026,
            SendKind.DRAFT,
            DEFAULT_EXCEL_TEMPLATE,
            DEFAULT_PDF_TEMPLATE,
            logo_size_bytes=1024,  # Đẩy tổng > 18MB!
        )
        assert matches[0][0].status == MatchStatus.INVALID_FILE
        assert "0 KB" in matches[0][0].note
        assert matches[1][0].status == MatchStatus.INVALID_FILE
        assert "18 MB" in matches[1][0].note

    def test_discover_unknown_suppliers_from_unmatched_files(self) -> None:
        sups = [_sup(1, "ACE")]
        files = [
            _sf("Bảng phí kiểm tra, phân loại hàng hóa 09.2026 ACE.xlsx"),
            _sf("Bảng phí kiểm tra, phân loại hàng hóa 09.2026 Samsung Vina.xlsx"),
            _sf("PO Samsung Vina 09.2026.pdf"),
            _sf("~$Bảng phí 09.2026 Ghost.xlsx"),  # File rác phải bị bỏ qua
        ]
        _, discovered = match_files_for_suppliers(
            sups, files, 9, 2026, SendKind.FINAL, DEFAULT_EXCEL_TEMPLATE, DEFAULT_PDF_TEMPLATE
        )
        assert len(discovered) == 1
        assert discovered[0].suggested_name == "Samsung Vina"
        assert len(discovered[0].files) == 2

    def test_additional_edge_branches_zero_byte_manual_and_multi_fuzzy(self) -> None:
        sups = [_sup(1, "DiaMond"), _sup(2, "ACE")]
        zero_manual = _sf("manual_zero.xlsx", size=0)
        zero_auto = _sf("Bang phi 09.2026 ACE.xlsx", size=0)
        matches, _ = match_files_for_suppliers(
            sups,
            [zero_auto],
            9,
            2026,
            SendKind.DRAFT,
            DEFAULT_EXCEL_TEMPLATE,
            DEFAULT_PDF_TEMPLATE,
            manual_overrides={(0, FileType.EXCEL): zero_manual},
        )
        assert matches[0][0].status == MatchStatus.INVALID_FILE
        assert matches[1][0].status == MatchStatus.INVALID_FILE

        # Nhiều file fuzzy gần giống -> AMBIGUOUS (khóa cứng)
        f_amb1 = _sf("Bang phi 09.2026 DiaMon.xlsx")
        f_amb2 = _sf("Bang phi 09.2026 DiaMonds.xlsx")
        m2, _ = match_files_for_suppliers(
            [_sup(1, "DiaMond")],
            [f_amb1, f_amb2],
            9,
            2026,
            SendKind.DRAFT,
            DEFAULT_EXCEL_TEMPLATE,
            DEFAULT_PDF_TEMPLATE,
        )
        assert m2[0][0].status == MatchStatus.AMBIGUOUS

        # File fuzzy 0-byte -> INVALID_FILE
        f_zero_fuz = _sf("Bang phi 09.2026 DiaMon.xlsx", size=0)
        m3, _ = match_files_for_suppliers(
            [_sup(1, "DiaMond")],
            [f_zero_fuz],
            9,
            2026,
            SendKind.DRAFT,
            DEFAULT_EXCEL_TEMPLATE,
            DEFAULT_PDF_TEMPLATE,
        )
        assert m3[0][0].status == MatchStatus.INVALID_FILE
