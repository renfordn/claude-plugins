"""
Validates and sanitizes code review findings for ReportFindings tool calls.

Supports both Evidence Tier (tier-1..5, verification directness) and Review Level
(Quick/Standard/Deep/Ultra, analysis depth). These are orthogonal axes; all findings
carry both fields independently.

Evidence Tier Expectations per Review Level:
- Quick: tier-1..2 (basic checks, direct observation)
- Standard: tier-2..3 (standard checks, direct + some inference)
- Deep: tier-3..4 (thorough checks, inference acceptable)
- Ultra: tier-3..5 (comprehensive checks, includes speculative findings)

Note: Tier expectations are documented for reference; validation is informational only.
Findings with tiers outside the expected range for their review level are still accepted.
"""


# Evidence Tier expectations per review level
REVIEW_LEVEL_TIER_EXPECTATIONS = {
    "Quick": {"min": 1, "max": 2},
    "Standard": {"min": 2, "max": 3},
    "Deep": {"min": 3, "max": 4},
    "Ultra": {"min": 3, "max": 5},
}


def truncate_to_limit(text: str, limit: int) -> str:
    """Truncate text to character limit, preserving word boundaries when possible."""
    if len(text) <= limit:
        return text

    truncated = text[:limit]
    last_space = truncated.rfind(" ")

    if last_space > limit * 0.7:  # Only use word boundary if it's not too early
        return truncated[:last_space].rstrip()

    return truncated.rstrip()


def validate_finding(finding: dict) -> dict:
    """
    Validate and sanitize a single finding object.

    Args:
        finding: A finding dict with keys like 'file', 'summary', 'short_summary', etc.
                 May include 'review_level' (Quick/Standard/Deep/Ultra) and 'evidence_tier' (1-5).

    Returns:
        Sanitized finding dict with truncated fields.

    Note:
        Evidence Tier expectations are documented per review level, but validation is
        informational only; tier values outside the expected range are preserved as-is
        (callers interpret tier-level mapping based on review context).
    """
    result = dict(finding)

    # Enforce short_summary <= 60 chars
    if "short_summary" in result:
        result["short_summary"] = truncate_to_limit(result["short_summary"], 60)

    # Enforce summary <= 200 chars (reasonable for detailed messages)
    if "summary" in result:
        result["summary"] = truncate_to_limit(result["summary"], 200)

    # Preserve review_level if present
    if "review_level" in result:
        level = result["review_level"]
        if level in REVIEW_LEVEL_TIER_EXPECTATIONS:
            # Evidence Tier expectations are documented for reference
            # (validation is informational; tiers outside range are still accepted)
            pass

    return result


def validate_findings(findings: list) -> list:
    """
    Validate and sanitize all findings for ReportFindings.

    Args:
        findings: List of finding dicts

    Returns:
        List of sanitized findings, all meeting ReportFindings constraints.
    """
    return [validate_finding(f) for f in findings]


def get_tier_expectations(review_level: str) -> dict:
    """
    Get Evidence Tier expectations for a given review level.

    Args:
        review_level: One of "Quick", "Standard", "Deep", "Ultra"

    Returns:
        Dict with 'min' and 'max' tier values expected for this level.
        Returns (min: 2, max: 3) as default if review_level not recognized.

    Note:
        Tier expectations reflect typical verification patterns at each review level:
        - Quick (1-2): Basic checks, direct observation
        - Standard (2-3): Standard checks, direct + some inference
        - Deep (3-4): Thorough checks, inference acceptable
        - Ultra (3-5): Comprehensive checks, includes speculative findings
    """
    return REVIEW_LEVEL_TIER_EXPECTATIONS.get(review_level, REVIEW_LEVEL_TIER_EXPECTATIONS["Standard"])


def validate_report_input(findings: list, level: str = None, review_level: str = None) -> dict:
    """
    Validate complete ReportFindings input before calling the tool.

    Args:
        findings: List of finding dicts
        level: Optional effort level (low, medium, high, xhigh, max)
        review_level: Optional review level (Quick, Standard, Deep, Ultra) for tier expectations context

    Returns:
        Dict with 'findings' and optionally 'level'/'review_level', all validated.
    """
    result = {"findings": validate_findings(findings)}

    if level is not None:
        valid_levels = {"low", "medium", "high", "xhigh", "max"}
        if level not in valid_levels:
            raise ValueError(f"Invalid level '{level}'. Must be one of {valid_levels}")
        result["level"] = level

    if review_level is not None:
        valid_review_levels = {"Quick", "Standard", "Deep", "Ultra"}
        if review_level not in valid_review_levels:
            raise ValueError(f"Invalid review_level '{review_level}'. Must be one of {valid_review_levels}")
        result["review_level"] = review_level

    return result
