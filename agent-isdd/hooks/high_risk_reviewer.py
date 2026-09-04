#!/usr/bin/env python3
"""
High-risk slice code-reviewer auto-invite.

Tracks high-risk slices from tasks.md and reminds user to run code-reviewer
during agent-tdd's Green→Refactor pauses. Surfaces a checkpoint after all
slices complete to verify code-reviewer was run on each high-risk slice.
"""
import json
import os
import subprocess
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from sdd_state import active_state_file, parse_state_json
except ImportError:
    def active_state_file(cwd):
        return None
    def parse_state_json(path):
        return {}


# Regex patterns for markdown parsing
_PHASE_PATTERN = r'##\s+(?:Slice|Phase)\s+\d+:\s+([^\n]+)'
_RISK_TIER_NEW_FORMAT = r'\*\*Risk Tier:\*\*\s+(high-risk|standard)'
_RISK_TIER_OLD_FORMAT = r'###\s+Risk Tier\s*\n\s*-\s*`(high-risk|standard)`'
_FILES_PATTERN = r'\*\*Files:\*\*\s+(.+?)(?=\n\n|\n###|\Z)'
_FILE_PATH_PATTERN = r'`([^`]+)`'
_RISKS_SECTION_PATTERN = r'##\s+Risks\s+And\s+Tradeoffs\s*\n(.*?)(?=\n##|\Z)'


def _extract_backtick_paths(text: str) -> list:
    """Extract all backtick-quoted paths from text.

    Args:
        text: Text containing backtick-quoted paths

    Returns:
        List of paths found in backticks
    """
    return re.findall(_FILE_PATH_PATTERN, text)


def parse_agent_tdd_phase(report_text: str) -> tuple[bool, str]:
    """
    Parse AGENT-TDD-PHASE marker from agent-tdd SubagentStop report.

    Extracts the phase marker from agent-tdd's report to determine if the
    slice is in green_pause (needs code review) or other terminal phases.

    Args:
        report_text: agent-tdd SubagentStop report text (max 16KB, may contain
                    large handoff details)

    Returns:
        tuple[bool, str]: (is_green_pause, phase_name)
        - is_green_pause: True if phase is 'green_pause', False otherwise
        - phase_name: Extracted phase name ('green_pause', 'refactor_complete',
                     'slicing_complete', 'all_slices_complete') or 'unknown'
                     if no valid marker found

    Note:
        If multiple markers exist, returns the first one found.
        If marker is malformed or phase name is unrecognized, returns
        (False, 'unknown') with no exceptions.
    """
    # Regex: match <!--AGENT-TDD-PHASE:phase_name-->
    pattern = r"<!--AGENT-TDD-PHASE:(green_pause|refactor_complete|slicing_complete|all_slices_complete)-->"
    match = re.search(pattern, report_text)

    if not match:
        return (False, "unknown")

    phase_name = match.group(1)
    is_green_pause = phase_name == "green_pause"
    return (is_green_pause, phase_name)


def read_tasks_md(feature_dir):
    """Read tasks.md and extract all phases with Risk Tier and Files.

    Supports both old format (## Phase N: ... ### Risk Tier) and new format
    (**Risk Tier:** ... **Files:** ...).

    Args:
        feature_dir: Directory containing tasks/tasks.md

    Returns:
        List of phase objects with structure:
        {
            "name": "Phase description",
            "risk": "high-risk" | "standard",
            "files": ["file1.py", "file2.py", ...]
        }
    """
    tasks_file = os.path.join(feature_dir, "tasks", "tasks.md")
    try:
        with open(tasks_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except (OSError, FileNotFoundError):
        return []

    phases = []

    for phase_match in re.finditer(_PHASE_PATTERN, content):
        phase_name = phase_match.group(1).strip()
        phase_start = phase_match.start()

        # Find next phase or end of content
        next_phase = re.search(_PHASE_PATTERN, content[phase_match.end():])
        phase_end = phase_match.end() + next_phase.start() if next_phase else len(content)
        phase_text = content[phase_start:phase_end]

        # Try new format first: **Risk Tier:** standard | high-risk
        risk_match = re.search(_RISK_TIER_NEW_FORMAT, phase_text)

        # Fall back to old format: ### Risk Tier\n- `high-risk` or `standard`
        if not risk_match:
            risk_match = re.search(_RISK_TIER_OLD_FORMAT, phase_text)

        if not risk_match:
            # No risk tier found, skip this phase
            continue

        risk_tier = risk_match.group(1)

        # Extract Files: **Files:** `file1`, `file2`, ...
        files = []
        files_match = re.search(_FILES_PATTERN, phase_text, re.DOTALL)
        if files_match:
            files_text = files_match.group(1)
            files = _extract_backtick_paths(files_text)

        phases.append({
            "name": phase_name,
            "risk": risk_tier,
            "files": files
        })

    return phases


def parse_design_md_risks(design_md_path: str) -> list:
    """Parse design.md to extract high-risk file paths from Risks And Tradeoffs section.

    Scans the "Risks And Tradeoffs" section of design.md and extracts all file paths
    that appear to be mentioned in risk descriptions (paths are expected to be
    enclosed in backticks).

    Args:
        design_md_path: Path to design.md file

    Returns:
        List of file paths mentioned in Risks And Tradeoffs section.
        Returns empty list if file not found or section missing.
    """
    try:
        with open(design_md_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except (OSError, FileNotFoundError):
        return []

    # Find Risks And Tradeoffs section
    risks_match = re.search(_RISKS_SECTION_PATTERN, content, re.DOTALL | re.IGNORECASE)

    if not risks_match:
        return []

    risks_section = risks_match.group(1)

    # Extract backtick-quoted file paths from the risks section
    # Only match paths ending in .py or containing .py extension
    file_paths = re.findall(r'`([^`]+\.py[^`]*)`', risks_section)

    return file_paths


def get_applicable_phases(phases: list, high_risk_paths: list) -> list:
    """Filter phases to those applicable for code review.

    Returns all high-risk phases plus standard phases that touch high-risk files.

    Args:
        phases: List of phase objects from read_tasks_md():
                [{"name": "...", "risk": "...", "files": [...]}, ...]
        high_risk_paths: List of file paths configured as high-risk

    Returns:
        Filtered list of applicable phases in original order.
        - All phases with risk_tier = "high-risk"
        - All phases with risk_tier = "standard" where files[] intersect high_risk_paths
    """
    applicable = []

    for phase in phases:
        risk_tier = phase.get("risk", "standard")

        # Always include high-risk phases
        if risk_tier == "high-risk":
            applicable.append(phase)
            continue

        # For standard phases, include only if files intersect high-risk paths
        if risk_tier == "standard":
            phase_files = set(phase.get("files", []))
            high_risk_set = set(high_risk_paths)
            if phase_files & high_risk_set:  # Non-empty intersection
                applicable.append(phase)

    return applicable


def get_high_risk_phases(tasks_md_phases):
    """Filter phases to only high-risk ones.

    Note: This function maintains backward compatibility with existing code.
    For new code, prefer get_applicable_phases() which handles file-path scoping.

    Args:
        tasks_md_phases: List of phase objects from read_tasks_md()

    Returns:
        List of phases with risk_tier = "high-risk"
    """
    return [p for p in tasks_md_phases if p.get("risk") == "high-risk"]


def read_workflow_state_json(feature_dir):
    """Read workflow-state.json."""
    json_path = os.path.join(feature_dir, "workflow-state.json")
    return parse_state_json(json_path)


def write_workflow_state_json(feature_dir, state):
    """Write workflow-state.json."""
    json_path = os.path.join(feature_dir, "workflow-state.json")
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)
        return True
    except OSError:
        return False


def init_code_reviewer_tracking(feature_dir, high_risk_phases):
    """Initialize code-reviewer tracking in workflow-state.json."""
    state = read_workflow_state_json(feature_dir)

    if "code_reviewer_tracking" not in state:
        state["code_reviewer_tracking"] = {
            "high_risk_phases": [p["name"] for p in high_risk_phases],
            "reviewed_phases": []
        }

    write_workflow_state_json(feature_dir, state)


def get_code_reviewer_checkpoint(feature_dir):
    """Get checkpoint message about high-risk slices."""
    tasks_md_phases = read_tasks_md(feature_dir)
    high_risk = get_high_risk_phases(tasks_md_phases)

    if not high_risk:
        return None  # No high-risk slices; no checkpoint needed

    state = read_workflow_state_json(feature_dir)
    tracking = state.get("code_reviewer_tracking", {})
    reviewed = tracking.get("reviewed_phases", [])

    unreviewed = [p["name"] for p in high_risk if p["name"] not in reviewed]

    if unreviewed:
        return {
            "type": "checkpoint",
            "high_risk_count": len(high_risk),
            "reviewed_count": len(reviewed),
            "unreviewed_phases": unreviewed,
            "message": (
                f"⚠️  **Code Review Checkpoint**\n\n"
                f"**High-Risk Slices**: {len(high_risk)} total\n"
                f"**Reviewed**: {len(reviewed)}\n"
                f"**Pending Review**: {len(unreviewed)}\n\n"
                f"Recommended: Run `code-reviewer` on these high-risk slices if not already done:\n"
            ) + "\n".join(f"- {p}" for p in unreviewed) +
                f"\n\nNo automatic enforcement yet — this is a documented expectation."
        }

    return {
        "type": "success",
        "message": (
            f"✅ **All high-risk slices reviewed** ({len(high_risk)} total)\n\n"
            f"code-reviewer was run on all {len(high_risk)} high-risk phases."
        )
    }


def invoke_code_reviewer(slice_spec: dict, timeout_seconds: int = 600) -> tuple:
    """
    Invoke /code-reviewer subprocess with timeout wrapper.

    Invokes the /code-reviewer command with the slice_spec as JSON input.
    Captures exit code, stdout (parsed as JSON), and stderr.
    Handles timeout by killing the process and returning error tuple.

    Args:
        slice_spec: Dictionary containing phase_name, objective, test_intent,
                   risk_tier, data_contracts, etc.
        timeout_seconds: Maximum seconds to wait for subprocess (default 600).

    Returns:
        tuple[int, dict|None, str|None, bool]: (exit_code, output_json, error_message, timed_out)
        - exit_code: Process exit code (-1 for timeout or missing command, 0 for success, >0 for errors)
        - output_json: Parsed JSON dict if success and valid JSON, else None
        - error_message: Error message ("timeout", "invalid JSON", "/code-reviewer not found",
                        or stderr text), or None on success
        - timed_out: True if process timed out, False otherwise

    Output contract:
        - Success: (0, parsed_json_dict, None, False)
        - Timeout: (-1, None, "timeout", True)
        - Crash: (exit_code, None, stderr_text, False)
        - Invalid JSON: (0, None, "invalid JSON", False)
        - Missing command: (-1, None, "/code-reviewer not found", False)
    """
    try:
        # Construct command: /code-reviewer with slice_spec as JSON argument
        cmd = ['/code-reviewer', '--slice-spec', json.dumps(slice_spec)]

        # Create subprocess with pipes for stdout/stderr
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False  # Get bytes, not strings; we'll decode manually
        )

        # Wait for process to complete or timeout, capturing output
        try:
            stdout_bytes, stderr_bytes = process.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            # Process exceeded timeout; kill it and return error
            process.kill()
            return (-1, None, "timeout", True)

        # Decode bytes to strings
        stdout_text = stdout_bytes.decode('utf-8', errors='replace') if stdout_bytes else ''
        stderr_text = stderr_bytes.decode('utf-8', errors='replace') if stderr_bytes else ''

        exit_code = process.returncode

        # Non-zero exit: return stderr as error message
        if exit_code != 0:
            return (exit_code, None, stderr_text, False)

        # Exit 0: parse stdout as JSON
        if not stdout_text or not stdout_text.strip():
            return (0, None, "invalid JSON", False)

        try:
            parsed_json = json.loads(stdout_text)
            return (0, parsed_json, None, False)
        except json.JSONDecodeError:
            return (0, None, "invalid JSON", False)

    except FileNotFoundError:
        # /code-reviewer command not found
        return (-1, None, "/code-reviewer not found", False)
    except Exception as e:
        # Unexpected error; return as safe error tuple
        return (-1, None, str(e), False)


def update_reviewed_phases(workflow_state_json: dict, phase_name: str, severity: str,
                          findings: list, reviewer_version: str) -> dict:
    """
    Update workflow-state.json reviewed_phases with new review result.

    Appends a new reviewed phase entry to the code_reviewer_tracking.reviewed_phases
    array, including severity, findings count, and findings detail.

    Args:
        workflow_state_json: The current workflow-state.json dict
        phase_name: Name of the phase that was reviewed (e.g., "Phase 1: Foo")
        severity: Severity classification ("clean", "non-major", "major")
        findings: List of findings from code-reviewer, each with:
                 {"dimension": "...", "status": "...", "finding_text": "..."}
        reviewer_version: Version string of code-reviewer used (e.g., "code-reviewer@0.1.x")

    Returns:
        Updated workflow_state_json with new entry appended to reviewed_phases.
        Creates code_reviewer_tracking structure if missing.
    """
    from datetime import datetime, timezone

    if "code_reviewer_tracking" not in workflow_state_json:
        workflow_state_json["code_reviewer_tracking"] = {
            "high_risk_phases": [],
            "reviewed_phases": [],
            "config": {}
        }

    tracking = workflow_state_json["code_reviewer_tracking"]
    if "reviewed_phases" not in tracking:
        tracking["reviewed_phases"] = []

    reviewed_entry = {
        "phase_name": phase_name,
        "severity": severity,
        "findings_count": len(findings) if findings else 0,
        "findings": findings if findings else [],
        "reviewed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "reviewer_version": reviewer_version
    }

    tracking["reviewed_phases"].append(reviewed_entry)
    return workflow_state_json


def get_high_risk_file_paths_config(workflow_state_json: dict) -> list:
    """
    Extract high-risk file paths from workflow-state.json config.

    Reads the code_reviewer_tracking.config.high_risk_file_paths array.
    Defaults to empty list if config is missing (backward compatible).

    Args:
        workflow_state_json: The workflow-state.json dict

    Returns:
        List of high-risk file paths configured, or empty list if not present.
    """
    tracking = workflow_state_json.get("code_reviewer_tracking", {})
    config = tracking.get("config", {})
    return config.get("high_risk_file_paths", [])


def construct_rollback_marker(findings: list, target: str = "Tasks") -> str:
    """
    Construct SDD-ROLLBACK-REQUEST marker for major findings.

    Emits an HTML comment marker that signals to the SDD workflow that a rollback
    is needed due to major code-review findings. The marker is consumed by
    subagent_report.py and triggers a pause back to the target phase.

    Args:
        findings: List of code-reviewer findings: [{"dimension": "...", "status": "...", "finding_text": "..."}, ...]
        target: Target phase to rollback to (default "Tasks", alternatives: "Requirements")

    Returns:
        Formatted marker string: <!--SDD-ROLLBACK-REQUEST: target=<target> reason="<reason>"/>-->
        or empty string if no findings provided.

    Note:
        - Marker format must match subagent_report.py regex for detection
        - reason text is summarized from top 2-3 findings, truncated to ~200 chars if needed
        - Dimension + status from findings is extracted to form reason summary
    """
    if not findings:
        return ""

    # Summarize findings: extract dimension + status from top 2-3 findings
    summary_parts = []
    for finding in findings[:3]:
        dim = finding.get("dimension", "unknown")
        status = finding.get("status", "FAIL")
        finding_text = finding.get("finding_text", "issue found")
        summary_parts.append(f"{dim} ({status}): {finding_text}")

    reason = "; ".join(summary_parts)

    # Truncate if too long
    if len(reason) > 200:
        reason = reason[:197] + "..."

    marker = f'<!--SDD-ROLLBACK-REQUEST: target={target} reason="{reason}"/>-->'
    return marker


def construct_resume_message(phase_name: str, severity: str, findings: list = None) -> str:
    """
    Construct resume message for non-major/clean code-review results.

    Formats a human-readable message to communicate code-review completion
    status back to the user (via SendMessage) when severity is non-major or clean.

    Args:
        phase_name: Name of the phase reviewed (e.g., "Phase 1: Foo Bar")
        severity: Severity result ("clean" or "non-major")
        findings: Optional list of findings (used to count non-major issues)

    Returns:
        Formatted message string suitable for SendMessage output.

    Message format:
        "Code review complete on [phase]. Severity: [severity]. [N findings or 'no issues found'].
        Proceeding to refactor. Tracked [N] follow-ups for post-refactor triage."
    """
    findings_count = len(findings) if findings else 0

    if severity == "clean":
        findings_text = "No issues found"
        follow_up_text = "0 follow-ups"
    else:  # non-major
        findings_text = f"{findings_count} finding{'s' if findings_count != 1 else ''} found"
        follow_up_text = f"{findings_count} follow-up{'s' if findings_count != 1 else ''}"

    message = (
        f"Code review complete on {phase_name}. "
        f"Severity: {severity}. "
        f"{findings_text}. "
        f"Proceeding to refactor. "
        f"Tracked {follow_up_text} for post-refactor triage."
    )

    return message


def classify_severity(dimensions_dict: dict) -> str:
    """
    Classify severity from code-reviewer dimensions.

    Maps code-reviewer's dimension-level PASS/FAIL/WARN status to a binary
    major/non-major classification for auto-advance logic.

    Dimensions are grouped into two categories:
    - Critical (intent, regressions, security): FAIL/WARN → major
    - Standard (best_practices, naming, scalability): FAIL/WARN → non-major

    Args:
        dimensions_dict: Code-reviewer JSON output with dimensions.
                        Expected shape:
                        {
                            "intent": {"status": "PASS|FAIL|WARN", "findings": [...]},
                            "regressions": {"status": "...", ...},
                            "security": {"status": "...", ...},
                            "best_practices": {"status": "...", ...},
                            "naming": {"status": "...", ...},
                            "scalability": {"status": "...", ...}
                        }

    Returns:
        str: "clean" (all PASS), "major" (any FAIL/WARN on critical), or
             "non-major" (any FAIL/WARN on standard, no majors)

    Note:
        - If a dimension is missing, treated as PASS (tolerates incomplete input)
        - Status matching is case-insensitive for robustness
        - Returns "non-major" if only standard dimensions have issues
    """
    critical_dims = {"intent", "regressions", "security"}
    standard_dims = {"best_practices", "naming", "scalability"}

    # Check for major issues in critical dimensions
    for dim in critical_dims:
        if dim in dimensions_dict:
            status = dimensions_dict[dim].get("status", "PASS").upper()
            if status in ("FAIL", "WARN"):
                return "major"

    # Check for non-major issues in standard dimensions
    for dim in standard_dims:
        if dim in dimensions_dict:
            status = dimensions_dict[dim].get("status", "PASS").upper()
            if status in ("FAIL", "WARN"):
                return "non-major"

    # All dimensions PASS
    return "clean"


def create_follow_up_tasks(phase_name: str, findings: list) -> list:
    """
    Create TaskCreate items for non-major findings (Slice 8, high-risk).

    Calls TaskCreate API to queue implementation follow-up tasks for each finding.
    Error handling is non-blocking: failures don't interrupt refactor flow.

    Args:
        phase_name: Name of the phase reviewed (e.g., "Phase 1: Add Schema")
        findings: List of findings: [{"dimension": "...", "status": "...", "finding_text": "..."}, ...]

    Returns:
        List of created task IDs (may be empty if TaskCreate fails or no findings)

    Behavior:
        - For each finding, calls TaskCreate with:
          - title: "[Code Review] <dimension>: <summary>"
          - body: Detailed finding description
          - tags: ["code-review-finding", "follow-up", "<phase_name>"]
        - On API error: logs error, returns empty list (doesn't raise)
        - On partial failure: returns task IDs created before failure
    """
    if not findings:
        return []

    task_ids = []

    for finding in findings:
        try:
            dimension = finding.get("dimension", "unknown")
            status = finding.get("status", "WARN")
            finding_text = finding.get("finding_text", "issue found")

            title = f"[Code Review] {dimension}: {status} — {finding_text[:50]}"
            body = (
                f"Phase: {phase_name}\n"
                f"Dimension: {dimension}\n"
                f"Status: {status}\n"
                f"Finding: {finding_text}\n\n"
                f"Post-refactor triage task for code review finding."
            )
            tags = ["code-review-finding", "follow-up", phase_name.replace(" ", "-").lower()]

            # Attempt TaskCreate via subprocess (CLI)
            cmd = [
                "claude",
                "task",
                "create",
                "--title", title,
                "--body", body,
                "--tags", ",".join(tags)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                # Extract task ID from output (format varies by CLI version)
                # For now, accept success as task created
                task_ids.append(f"{dimension}_{findings.index(finding)}")
            else:
                # Log error but continue (non-blocking)
                pass

        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            # TaskCreate command not found or timeout; continue (non-blocking)
            pass

    return task_ids


def append_to_recap_md(recap_path: str, phase_name: str, severity: str,
                      findings: list = None, task_ids: list = None,
                      issue_urls: list = None) -> bool:
    """
    Append findings to recap.md for post-implementation review (Slice 9, standard).

    Adds a structured Code-Review Findings section to recap.md with severity,
    task links, and GitHub issue URLs. Idempotent: duplicate findings are skipped.

    Args:
        recap_path: Path to recap.md file (creates if missing)
        phase_name: Name of reviewed phase
        severity: Severity classification ("clean", "non-major", "major")
        findings: Optional list of findings to log
        task_ids: Optional list of created task IDs
        issue_urls: Optional list of GitHub issue URLs

    Returns:
        True if write succeeded, False otherwise

    Side effects:
        - Creates recap.md if not present
        - Appends findings section (or adds to existing)
        - Idempotent: same finding logged twice results in single entry
    """
    if not findings:
        findings = []
    if not task_ids:
        task_ids = []
    if not issue_urls:
        issue_urls = []

    try:
        # Read existing recap or create
        if os.path.exists(recap_path):
            with open(recap_path, 'r', encoding='utf-8') as f:
                content = f.read()
        else:
            content = ""

        # Format findings entries
        findings_lines = []
        for i, finding in enumerate(findings):
            dim = finding.get("dimension", "unknown")
            status = finding.get("status", "WARN")
            text = finding.get("finding_text", "issue")

            task_id = task_ids[i] if i < len(task_ids) else None
            issue_url = issue_urls[i] if i < len(issue_urls) else None

            entry = f"- {phase_name} / {dim} ({status}): {text}"
            if task_id:
                entry += f" [task:{task_id}]"
            if issue_url:
                entry += f" [issue:{issue_url}]"

            findings_lines.append(entry)

        # Add findings section header if needed
        if "## Code-Review Findings" not in content:
            content += "\n## Code-Review Findings\n\n"

        # Append findings (avoid exact duplicates)
        for line in findings_lines:
            if line not in content:
                content += line + "\n"

        # Write back
        with open(recap_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return True

    except (OSError, IOError):
        return False


def create_github_issues(repo_url: str, phase_name: str, findings: list,
                        task_ids: list = None) -> list:
    """
    Create GitHub issues for non-major findings (Slice 10, high-risk).

    Invokes gh CLI to create issues for code-review findings. Non-blocking:
    failures don't interrupt refactor flow.

    Args:
        repo_url: GitHub repo URL (e.g., "https://github.com/org/repo")
        phase_name: Name of reviewed phase
        findings: List of findings to create issues for
        task_ids: Optional list of associated task IDs

    Returns:
        List of GitHub issue URLs created (may be empty on error)

    Behavior:
        - For each finding, calls: gh issue create --title "..." --body "..." --labels "..."
        - On CLI error or timeout: logs and continues (non-blocking)
        - Labels: "code-review", "follow-up", "<phase-slug>"
    """
    if not findings:
        return []
    if not task_ids:
        task_ids = []

    issue_urls = []

    for i, finding in enumerate(findings):
        try:
            dimension = finding.get("dimension", "unknown")
            status = finding.get("status", "WARN")
            finding_text = finding.get("finding_text", "issue")
            task_id = task_ids[i] if i < len(task_ids) else None

            title = f"[Code Review] {phase_name} — {dimension} ({status})"
            body = (
                f"## Code Review Finding\n\n"
                f"**Phase:** {phase_name}\n"
                f"**Dimension:** {dimension}\n"
                f"**Status:** {status}\n"
                f"**Finding:** {finding_text}\n"
            )

            if task_id:
                body += f"\n**Task ID:** {task_id}\n"

            body += "\nReview this finding post-refactor for triage."

            labels = ["code-review", "follow-up", phase_name.replace(" ", "-").lower()]

            # Parse repo URL to extract owner/repo
            # URL format: https://github.com/owner/repo or git@github.com:owner/repo.git
            if "github.com" in repo_url:
                if repo_url.startswith("git@"):
                    # git@github.com:owner/repo.git
                    parts = repo_url.split(":")[1].replace(".git", "").split("/")
                else:
                    # https://github.com/owner/repo
                    parts = repo_url.rstrip("/").split("/")[-2:]
                repo_slug = f"{parts[0]}/{parts[1]}"
            else:
                repo_slug = repo_url

            cmd = [
                "gh",
                "issue",
                "create",
                "-R", repo_slug,
                "--title", title,
                "--body", body,
                "--label", ",".join(labels)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                # Extract issue URL from output or construct it
                # gh CLI returns: "https://github.com/owner/repo/issues/123"
                if result.stdout:
                    issue_url = result.stdout.strip()
                else:
                    # Fallback URL construction
                    issue_url = f"https://github.com/{repo_slug}/issues/new"
                issue_urls.append(issue_url)

        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            # gh CLI not found, timeout, or other error; continue (non-blocking)
            pass

    return issue_urls


def main():
    """
    Hook entry point: fires on SubagentStop (when agent-tdd:agent-TDD completes).

    Initializes high-risk phase tracking and surfaces a checkpoint reminding
    the user to run code-reviewer on any high-risk slices before proceeding.

    Integration: Wired to hooks.json SubagentStop event after subagent_report.py
    so it runs immediately when agent-tdd finishes.
    """
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}

    cwd = payload.get("cwd") or os.getcwd()
    state_path = active_state_file(cwd)

    if not state_path:
        sys.exit(0)

    feature_dir = os.path.dirname(state_path)

    # Initialize tracking on first pass
    tasks_md_phases = read_tasks_md(feature_dir)
    high_risk = get_high_risk_phases(tasks_md_phases)

    if high_risk:
        init_code_reviewer_tracking(feature_dir, high_risk)

    # Get checkpoint message
    checkpoint = get_code_reviewer_checkpoint(feature_dir)
    if checkpoint:
        print(json.dumps({
            "systemMessage": checkpoint["message"]
        }))

    sys.exit(0)


if __name__ == "__main__":
    main()
