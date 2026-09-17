# Findings Validator Usage

The `findings_validator` module prevents `ReportFindings` tool errors by validating and sanitizing finding objects before they're reported.

## Problem

The ReportFindings tool enforces strict field constraints:
- `short_summary`: max 60 characters (required)
- `summary`: typically 200 characters (recommended)

When agents/skills generate findings with text exceeding these limits, ReportFindings fails with:
```
Failed to report review findings
code: "too_big"
path: ["findings", N, "short_summary"]
```

## Solution

Use `validate_report_input()` before calling ReportFindings:

```python
from shared.findings_validator import validate_report_input

findings = [
    {
        "file": "app.py",
        "line": 42,
        "summary": "This function is too long and should be refactored...",
        "short_summary": "This is a very long summary that definitely exceeds the 60 character maximum limit set by ReportFindings",
        "category": "refactoring",
    }
]

# Validate and sanitize before reporting
report = validate_report_input(findings, level="medium")

# report["findings"] now has truncated short_summary and summary
# Use report["findings"] in ReportFindings call
```

## API

### `truncate_to_limit(text: str, limit: int) -> str`
Truncates text to a character limit while respecting word boundaries when possible.

```python
text = "This is a long sentence that needs truncation"
truncated = truncate_to_limit(text, 20)  # "This is a long"
```

### `validate_finding(finding: dict) -> dict`
Sanitizes a single finding object.

- Truncates `short_summary` to ≤60 chars
- Truncates `summary` to ≤200 chars
- Preserves all other fields

```python
finding = {"file": "test.py", "short_summary": "x" * 100}
valid = validate_finding(finding)
# valid["short_summary"] is now ≤60 chars
```

### `validate_findings(findings: list) -> list`
Validates a list of findings.

```python
findings = [
    {"file": "a.py", "short_summary": "x" * 100},
    {"file": "b.py", "short_summary": "y" * 100},
]
valid = validate_findings(findings)
# All findings sanitized
```

### `validate_report_input(findings: list, level: str = None) -> dict`
Validates complete ReportFindings input, optionally with effort level.

```python
# Validate findings only
report = validate_report_input(findings)

# Validate with effort level
report = validate_report_input(findings, level="high")

# Returns:
# {
#   "findings": [...],  # All sanitized
#   "level": "high"     # If provided
# }
```

Valid levels: `low`, `medium`, `high`, `xhigh`, `max`

## Integration Points

### For Skill Authors (Claude-Native Skills)

Add validation in your skill's instructions before calling ReportFindings:

```markdown
Use the ReportFindings tool with this input:
- findings: array of review finding objects
- Validate short_summary ≤60 chars and summary ≤200 chars before calling
```

### For Agent-Based Plugins

In hooks or before_continue logic, use `validate_findings()`:

```python
from shared.findings_validator import validate_findings

# After generating findings, before tool call
findings_data = generate_findings(code)
validated = validate_findings(findings_data)
# Now safe to report
```

## Testing

Run the validation tests:

```bash
pytest shared/test_findings_validator.py -v
```

All 19 tests verify edge cases including:
- Text at exact limit
- Text exceeding limit with/without word boundaries
- Empty findings lists
- Invalid level values
- Field preservation
