"""Validates and sanitizes code review findings for ReportFindings tool calls."""


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

    Returns:
        Sanitized finding dict with truncated fields.
    """
    result = dict(finding)

    # Enforce short_summary <= 60 chars
    if "short_summary" in result:
        result["short_summary"] = truncate_to_limit(result["short_summary"], 60)

    # Enforce summary <= 200 chars (reasonable for detailed messages)
    if "summary" in result:
        result["summary"] = truncate_to_limit(result["summary"], 200)

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


def validate_report_input(findings: list, level: str = None) -> dict:
    """
    Validate complete ReportFindings input before calling the tool.

    Args:
        findings: List of finding dicts
        level: Optional effort level (low, medium, high, xhigh, max)

    Returns:
        Dict with 'findings' and optionally 'level', all validated.
    """
    result = {"findings": validate_findings(findings)}

    if level is not None:
        valid_levels = {"low", "medium", "high", "xhigh", "max"}
        if level not in valid_levels:
            raise ValueError(f"Invalid level '{level}'. Must be one of {valid_levels}")
        result["level"] = level

    return result
