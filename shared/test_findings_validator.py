"""Tests for findings_validator module."""

import pytest
from .findings_validator import (
    truncate_to_limit,
    validate_finding,
    validate_findings,
    validate_report_input,
)


class TestTruncateToLimit:
    """Tests for truncate_to_limit function."""

    def test_text_within_limit(self):
        """Text under limit should not be modified."""
        text = "short text"
        assert truncate_to_limit(text, 20) == text

    def test_text_at_limit(self):
        """Text at exact limit should not be modified."""
        text = "exactly twenty chars!"
        assert truncate_to_limit(text, len(text)) == text

    def test_text_exceeds_limit_no_word_boundary(self):
        """Text exceeding limit without word boundary should be hard-truncated."""
        result = truncate_to_limit("verylongwordwithoutspaces", 10)
        assert len(result) <= 10
        assert result == "verylongwo"

    def test_text_exceeds_limit_with_word_boundary(self):
        """Text exceeding limit with word boundary should break at space."""
        result = truncate_to_limit("short word that is long", 12)
        assert len(result) <= 12
        assert result == "short word"

    def test_preserves_word_boundary_quality(self):
        """Should not break word if space is too early."""
        result = truncate_to_limit("a verylongword", 10)
        # Should hard-truncate rather than break at "a "
        assert len(result) <= 10

    def test_empty_string(self):
        """Empty string should be handled gracefully."""
        assert truncate_to_limit("", 10) == ""

    def test_limit_of_one(self):
        """Single character limit."""
        assert truncate_to_limit("hello", 1) == "h"


class TestValidateFinding:
    """Tests for validate_finding function."""

    def test_short_summary_within_limit(self):
        """short_summary under 60 chars should not be modified."""
        finding = {"file": "test.py", "short_summary": "Brief summary"}
        result = validate_finding(finding)
        assert result["short_summary"] == "Brief summary"

    def test_short_summary_exceeds_limit(self):
        """short_summary over 60 chars should be truncated."""
        finding = {
            "file": "test.py",
            "short_summary": "This is a very long summary that definitely exceeds the sixty character limit for sure",
        }
        result = validate_finding(finding)
        assert len(result["short_summary"]) <= 60

    def test_summary_truncated_to_200(self):
        """summary field should be truncated to 200 chars."""
        long_summary = "x" * 300
        finding = {"file": "test.py", "summary": long_summary}
        result = validate_finding(finding)
        assert len(result["summary"]) <= 200

    def test_missing_optional_fields(self):
        """Finding without optional fields should pass through."""
        finding = {"file": "test.py", "line": 42}
        result = validate_finding(finding)
        assert result["file"] == "test.py"
        assert result["line"] == 42

    def test_preserves_all_fields(self):
        """Validation should preserve non-truncated fields."""
        finding = {
            "file": "test.py",
            "line": 10,
            "category": "correctness",
            "short_summary": "Brief",
        }
        result = validate_finding(finding)
        assert result["file"] == "test.py"
        assert result["line"] == 10
        assert result["category"] == "correctness"


class TestValidateFindings:
    """Tests for validate_findings function."""

    def test_empty_list(self):
        """Empty findings list should return empty list."""
        assert validate_findings([]) == []

    def test_multiple_findings(self):
        """Multiple findings should all be validated."""
        findings = [
            {"file": "a.py", "short_summary": "Short"},
            {
                "file": "b.py",
                "short_summary": "This is a very long summary that definitely exceeds the limit",
            },
            {"file": "c.py", "summary": "x" * 300},
        ]
        result = validate_findings(findings)
        assert len(result) == 3
        assert all(len(f.get("short_summary", "")) <= 60 for f in result)
        assert all(len(f.get("summary", "")) <= 200 for f in result)

    def test_preserves_order(self):
        """Validation should preserve finding order."""
        findings = [
            {"file": "z.py", "short_summary": "Z"},
            {"file": "a.py", "short_summary": "A"},
        ]
        result = validate_findings(findings)
        assert result[0]["file"] == "z.py"
        assert result[1]["file"] == "a.py"


class TestValidateReportInput:
    """Tests for validate_report_input function."""

    def test_findings_only(self):
        """Should accept findings without level."""
        findings = [{"file": "test.py", "short_summary": "Test"}]
        result = validate_report_input(findings)
        assert "findings" in result
        assert result["findings"] == findings

    def test_with_valid_level(self):
        """Should accept valid level values."""
        findings = [{"file": "test.py", "short_summary": "Test"}]
        for level in ["low", "medium", "high", "xhigh", "max"]:
            result = validate_report_input(findings, level=level)
            assert result["level"] == level

    def test_invalid_level(self):
        """Should reject invalid level values."""
        findings = [{"file": "test.py", "short_summary": "Test"}]
        with pytest.raises(ValueError) as exc_info:
            validate_report_input(findings, level="invalid")
        assert "invalid" in str(exc_info.value)

    def test_sanitizes_findings_before_return(self):
        """Should sanitize findings in the returned dict."""
        findings = [
            {
                "file": "test.py",
                "short_summary": "x" * 100,  # exceeds limit
            }
        ]
        result = validate_report_input(findings)
        assert len(result["findings"][0]["short_summary"]) <= 60
