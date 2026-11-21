"""Kiểm thử Domain Templating (nh3 HTML Sanitization, XSS, Chips) & Validation."""

from __future__ import annotations

from app.domain.models import GmailSettings, Supplier
from app.domain.templating import (
    build_html_body,
    build_logo_data_uri,
    render,
    sanitize_html_fragment,
    suggest_variable_fix,
    unknown_variables,
)
from app.domain.validation import (
    detect_duplicate_emails_across_suppliers,
    diagnose_app_password,
    is_valid_email,
    normalize_name,
    redact_secrets,
    split_emails,
    validate_gmail_settings,
    validate_supplier,
)


class TestTemplatingAndSanitization:
    def test_render_and_css_not_flagged_as_unknown_var(self) -> None:
        tpl = "<style>p { color: red; }</style><p>Tháng {thang}/{nam} - {nha_cung_cap}</p>"
        assert unknown_variables(tpl) == []
        out = render(tpl, {"thang": "09", "nam": "2026", "nha_cung_cap": "ACE", "loai": "Chốt"})
        assert "Tháng 09/2026 - ACE" in out

    def test_unknown_variable_and_vietnamese_typo_suggestion(self) -> None:
        assert unknown_variables("Tháng {tháng} {sai_roi}") == ["sai_roi", "tháng"]
        assert suggest_variable_fix("tháng") == "thang"
        assert suggest_variable_fix("NCC") == "nha_cung_cap"
        assert suggest_variable_fix("unknown") is None

    def test_xss_payload_completely_stripped_by_nh3(self) -> None:
        evil = (
            '<p>Xin chào</p><script>window.pywebview.api.steal()</script>'
            '<img src="x" onerror="alert(1)" />'
            '<a href="javascript:alert(2)">Bấm</a>'
            '<img src="https://tracker.evil.com/pixel.png" />'
        )
        cleaned = sanitize_html_fragment(evil, allow_external_images=False)
        assert "<script" not in cleaned.lower()
        assert "onerror" not in cleaned.lower()
        assert "javascript:" not in cleaned.lower()
        assert "tracker.evil.com" not in cleaned.lower()
        assert "Xin chào" in cleaned

    def test_build_html_body_plaintext_and_preview_csp(self) -> None:
        body = "Kính gửi ACE,\nChi phí A < B & C > D.\n---\nMs. Ha\nHR Staff"
        data_uri = build_logo_data_uri(b"\x89PNG\r\n", "image/png")
        html_doc = build_html_body(body, logo_src=data_uri, for_preview=True)
        assert "Content-Security-Policy" in html_doc
        assert "A &lt; B &amp; C &gt; D." in html_doc
        assert data_uri in html_doc
        assert "Ms. Ha" in html_doc

        # Khi nội dung là HTML có thẻ <p>/<b> + XSS -> sanitize sạch và vẫn gắn logo
        html_input = "<p>Kính gửi <b>ACE</b></p><script>alert(1)</script>"
        html_doc2 = build_html_body(html_input, logo_src=data_uri, for_preview=True)
        assert "<b>ACE</b>" in html_doc2
        assert "<script" not in html_doc2.lower()
        assert data_uri in html_doc2


class TestValidationAndRedaction:
    def test_normalize_name_nfc_case_whitespace(self) -> None:
        assert normalize_name("  Ho\u0300a   Phát ") == normalize_name("Hòa Phát")

    def test_split_emails_deduplicates_and_handles_separators(self) -> None:
        raw = "a@x.com; b@x.com,\nA@X.COM   c@x.com"
        assert split_emails(raw) == ["a@x.com", "b@x.com", "c@x.com"]
        assert is_valid_email("hr@haesung.vn") is True
        assert is_valid_email("bad-email") is False

    def test_diagnose_app_password_cases(self) -> None:
        ok, clean, _ = diagnose_app_password("abcd efgh-ijkl mnop")
        assert ok is True and clean == "abcdefghijklmnop"

        ok2, _, msg2 = diagnose_app_password("MyPass@2026!")
        assert ok2 is False and "mật khẩu đăng nhập Gmail thường" in msg2

        ok3, _, msg3 = diagnose_app_password("abc123")
        assert ok3 is False and "6/16" in msg3

    def test_validate_supplier_and_cross_vendor_duplicate_email(self) -> None:
        errs = validate_supplier("ACE/bad", ["not-an-email"], {"ace/bad"})
        assert len(errs) == 3

        sups = [
            Supplier(1, "ACE", ["shared@vendor.com", "a@ace.com"], enabled=True),
            Supplier(2, "AHC", ["SHARED@vendor.com"], enabled=True),
            Supplier(3, "OffCo", ["shared@vendor.com"], enabled=False),
        ]
        dups = detect_duplicate_emails_across_suppliers(sups)
        assert dups == {"shared@vendor.com": ["ACE", "AHC"]}

    def test_validate_gmail_settings_and_secret_redaction(self) -> None:
        s = GmailSettings(sender="bad", cc=["badcc"], pacing_seconds=99, max_retries=10)
        issues = validate_gmail_settings(s, has_password=False)
        assert len(issues) == 5

        raw = "Auth failed for ghp_1234567890abcdefghijklmno and Bearer tok_abcdef123456 with mysecretpw123456"
        safe = redact_secrets(raw, ("mysecretpw123456",))
        assert "ghp_" not in safe
        assert "tok_abcdef123456" not in safe
        assert "mysecretpw123456" not in safe
        assert safe.count("[REDACTED]") == 3
