# Tasks: auto-code-reviewer-high-risk-slices

**Feature:** Automatic Code-Reviewer Invocation on High-Risk Slices  
**Generated:** 2026-08-24  
**Status:** Ready For Implementation  

---

## Slice 1: Parse green_pause Marker

**Risk Tier:** standard  
**Depends On:** (none)  
**Files:** `agent-isdd/hooks/high_risk_reviewer.py`  

### Test Intent
Extract `--AGENT-TDD-PHASE:green_pause--` marker from agent-tdd SubagentStop report output; correctly distinguish green_pause from other phase markers (refactor_complete, slicing_complete, all_slices_complete).

### Validation Target
`pytest tests/test_high_risk_reviewer.py::test_parse_green_pause_marker`

### Ordered Steps
1. Add `parse_green_pause_marker(transcript: str) -> bool` pure function to high_risk_reviewer.py
2. Implement regex: `--AGENT-TDD-PHASE:green_pause--` (exact match; case-sensitive)
3. Write unit tests: present (marker found), absent (no marker), malformed (incorrect marker format)
4. Verify marker correctly returns True only for green_pause, False for refactor_complete/slicing_complete/all_slices_complete

---

## Slice 2: Extract High-Risk and Applicable Standard Phases

**Risk Tier:** standard  
**Depends On:** Slice 1  
**Files:** `agent-isdd/hooks/high_risk_reviewer.py`  

### Test Intent
Parse tasks.md Risk Tier and files[] fields to identify high-risk phases and standard phases whose touched files intersect with configured high-risk file paths.

### Validation Target
`pytest tests/test_high_risk_reviewer.py::test_extract_applicable_phases`

### Ordered Steps
1. Add `extract_applicable_phases(tasks_md_path: str, config_high_risk_paths: List[str]) -> List[str]` function
2. Parse tasks.md for Risk Tier field (per design spec's tasks.md schema); extract phase names and files[]
3. Collect all phases marked `high-risk: true`
4. Collect standard phases whose files[] intersect with config_high_risk_paths (wildcard/glob matching per design)
5. Write unit tests: high-risk phases only, standard + high-risk mix, file-path intersection logic, empty config (default to high-risk only)
6. Verify returned phase list is ordered by appearance in tasks.md

---

## Slice 3: Implement Code-Reviewer Subprocess Invocation with Timeout

**Risk Tier:** high-risk  
**Depends On:** Slices 1, 2  
**Files:** `agent-isdd/hooks/high_risk_reviewer.py`  

### Test Intent
Invoke `/code-reviewer` subprocess with configurable timeout; handle timeout, subprocess.CalledProcessError, and graceful degradation on invocation failure.

### Validation Target
`pytest tests/test_high_risk_reviewer.py::test_invoke_code_reviewer_*`

### Ordered Steps
1. Add `invoke_code_reviewer(phase_name: str, slice_spec: dict, timeout_seconds: int) -> dict` function
2. Build subprocess arguments: phase name, slice spec (objective, test intent, files), design/requirements/tasks context
3. Invoke `/code-reviewer` via subprocess.run with timeout; capture stdout (JSON) and stderr (errors)
4. Parse JSON output into dict (validate schema matches code-reviewer's dimensions structure)
5. Handle timeout: catch subprocess.TimeoutExpired, log warning, return {"status": "timeout", "skip_review": true}
6. Handle crash: catch subprocess.CalledProcessError, log error with exit code/stderr, return {"status": "error", "error_msg": "..."}
7. Write unit tests:
   - Mock subprocess.run for successful invocation (return valid code-reviewer JSON)
   - Mock subprocess.run for timeout (raise subprocess.TimeoutExpired)
   - Mock subprocess.run for crash (raise subprocess.CalledProcessError)
   - Verify error logging captures command, args, exit code, stderr
8. Verify timeout_seconds is configurable; default to 600 (10 min per design proposal)

---

## Slice 4: Classify Severity from Code-Reviewer Dimensions

**Risk Tier:** standard  
**Depends On:** Slice 3  
**Files:** `agent-isdd/hooks/high_risk_reviewer.py`  

### Test Intent
Map code-reviewer's per-dimension status (PASS/FAIL/WARN) to synthetic major/non-major/clean severity classification per design's mapping: Intent/Regressions/Security FAIL/WARN = major; BestPractices/Naming/Scalability FAIL/WARN = non-major; all PASS = clean.

### Validation Target
`pytest tests/test_high_risk_reviewer.py::test_classify_severity_*`

### Ordered Steps
1. Add `classify_severity(dimensions_dict: dict) -> str` pure function returning "major", "non-major", or "clean"
2. Implement algorithm per design: check if any of Intent, Regressions, Security has status != PASS → "major"
3. Else if any dimension has status in [FAIL, WARN] → "non-major"
4. Else all PASS → "clean"
5. Write comprehensive parametrized unit tests covering:
   - All 6 dimensions with all 3 statuses (PASS, FAIL, WARN) in combinations
   - Intent FAIL/WARN → always major
   - Regressions FAIL/WARN → always major
   - Security FAIL/WARN → always major
   - BestPractices FAIL/WARN → non-major
   - Naming FAIL/WARN → non-major
   - Scalability FAIL/WARN → non-major
   - All PASS → clean
   - Mixed: major dimensions + non-major dimensions → major
6. Verify docstring explains mapping rationale

---

## Slice 5: Populate workflow-state.json Reviewed Phases

**Risk Tier:** standard  
**Depends On:** Slice 4  
**Files:** `agent-isdd/hooks/high_risk_reviewer.py`  

### Test Intent
Write reviewed_phases data to workflow-state.json with severity, findings_count, findings[], timestamp, and reviewer_version per design schema.

### Validation Target
`pytest tests/test_high_risk_reviewer.py::test_track_reviewed_phases`

### Ordered Steps
1. Add `track_reviewed_phases(workflow_state: dict, phase_name: str, severity: str, findings: list, reviewer_version: str)` function
2. Create reviewed_phase dict: `{"phase_name": phase_name, "severity": severity, "findings_count": len(findings), "findings": findings, "reviewed_at": ISO8601_timestamp, "reviewer_version": reviewer_version}`
3. Append to workflow_state["code_reviewer_tracking"]["reviewed_phases"]
4. Write unit tests:
   - Verify schema matches design (all required fields present)
   - Verify timestamp is ISO8601 format
   - Verify findings count matches len(findings) list
   - Verify multiple reviewed_phases can be appended
   - Verify backward compatibility: existing workflow-state.json keys unchanged
5. Test fixture: sample workflow-state.json with and without code_reviewer_tracking pre-existing

---

## Slice 6: Emit SDD-ROLLBACK-REQUEST Marker for Major Findings

**Risk Tier:** standard  
**Depends On:** Slice 4  
**Files:** `agent-isdd/hooks/high_risk_reviewer.py`  

### Test Intent
Generate SDD-ROLLBACK-REQUEST marker (HTML comment) when code-reviewer severity classification yields "major"; marker format matches subagent_report.py's regex expectation.

### Validation Target
`pytest tests/test_high_risk_reviewer.py::test_emit_rollback_marker`

### Ordered Steps
1. Add `emit_rollback_marker(findings_summary: str) -> str` function
2. Return HTML comment: `<!--SDD-ROLLBACK-REQUEST:reason="Code-review major findings: <summary>"-->` per design/INTEROP.md format
3. Write unit tests:
   - Marker emitted when severity = "major"
   - Marker format valid (matches existing subagent_report.py regex: `<!--SDD-ROLLBACK-REQUEST:.*-->`)
   - findings_summary text properly escaped/safe for HTML comment
   - Marker not emitted for "non-major" or "clean" severity
4. Verify marker text is logged to workflow-state.json for audit trail

---

## Slice 7: Emit SendMessage Resume for Non-Major/Clean Findings

**Risk Tier:** standard  
**Depends On:** Slice 4  
**Files:** `agent-isdd/hooks/high_risk_reviewer.py`  

### Test Intent
Generate resume message (SendMessage format) when code-reviewer severity is "non-major" or "clean"; message signals refactor phase can proceed without blocking.

### Validation Target
`pytest tests/test_high_risk_reviewer.py::test_emit_resume_message`

### Ordered Steps
1. Add `emit_resume_message(severity: str, findings_count: int) -> str` function
2. Return SendMessage resume: `"Code review complete: <severity> findings (<n> item(s)). Proceeding to refactor phase."`
3. Write unit tests:
   - Message emitted when severity = "non-major" or "clean"
   - Message includes findings_count
   - Message not emitted for "major" severity
   - Message format parseable by spec-driven-development skill layer
4. Verify message is structured so caller can distinguish from other messages (e.g., prefix with `[code-review]`)

---

## Slice 8: Create Follow-Up Tasks via TaskCreate

**Risk Tier:** high-risk  
**Depends On:** Slice 5  
**Files:** `agent-isdd/hooks/high_risk_reviewer.py`  

### Test Intent
Call TaskCreate API for each non-major finding; verify titles, bodies, and tags match findings; mock TaskCreate to avoid external dependency; handle partial failures (TaskCreate fails, but tracking continues).

### Validation Target
`pytest tests/test_high_risk_reviewer.py::test_create_followup_tasks`

### Ordered Steps
1. Add `create_followup_tasks(findings: list, phase_name: str)` function
2. For each finding in findings list: extract dimension, status, finding_text
3. Build task item: title=`"[Code Review] <dimension>: <finding_summary>"`, body=`"From code-reviewer on <phase_name> after green. Severity: non-major. Full finding: <finding_text>"`, tags=`["code-review-finding", "follow-up", "<phase_name>"]`
4. Call TaskCreate API (or mock for testing)
5. Capture returned task ID; log to audit trail
6. Write unit tests:
   - Mock TaskCreate; verify call arguments match spec
   - Verify tasks created for all non-major findings
   - Verify task title/body/tags format matches design
   - Verify partial failure: TaskCreate raises exception; log error, continue (don't block refactor)
   - Verify empty findings list (no tasks created)
7. Constraint: order matters (TaskCreate first, before recap/GitHub per design Follow-Up Tracking Implementation)

---

## Slice 9: Log Findings to recap.md

**Risk Tier:** standard  
**Depends On:** Slice 8  
**Files:** `agent-isdd/hooks/high_risk_reviewer.py`  

### Test Intent
Append non-major findings to recap.md in structured format under "## Code-Review Findings (Post-Refactor)" section; handle recap.md creation (if new) and append (if exists).

### Validation Target
`pytest tests/test_high_risk_reviewer.py::test_log_recap_findings`

### Ordered Steps
1. Add `log_recap_findings(recap_path: str, findings: list, phase_name: str)` function
2. If recap.md exists: append to "## Code-Review Findings (Post-Refactor)" section; if section not present, create it
3. Format entry: `- Phase <name>: <dimension> — <finding_text> (non-major; tracked as task <task_id> and issue <url>)`
4. If recap.md doesn't exist: create with header and findings section
5. Write unit tests:
   - Append to existing recap.md (section exists)
   - Create new recap.md if absent
   - Create findings section if absent
   - Verify format matches spec
   - Verify multiple findings appended in correct order
   - Verify file is written with correct permissions
6. Constraint: recap.md write is local (always succeeds if disk available); designed to never block refactor

---

## Slice 10: Create GitHub Issues for Findings

**Risk Tier:** high-risk  
**Depends On:** Slice 9  
**Files:** `agent-isdd/hooks/high_risk_reviewer.py`  

### Test Intent
Invoke `gh issue create` CLI for each non-major finding; verify issue creation, labels, and linking to slice/phase; mock gh CLI to avoid external dependency; handle partial/best-effort failures (skip on error, log warning, don't block).

### Validation Target
`pytest tests/test_high_risk_reviewer.py::test_create_github_issues`

### Ordered Steps
1. Add `create_github_issues(findings: list, phase_name: str, repo_url: str) -> list` function
2. For each finding: extract dimension, status, finding_text
3. Build issue: title=`"Code Review Finding: <dimension> in Phase <name>"`, body=`"Found during automatic code review after green phase. Dimension: <dimension>. Finding: <finding_text>. Link to slice: ..."`, labels=`["code-review", "follow-up", "non-major"]`
4. Invoke `gh issue create` subprocess in target repo (inferred from repo_url or from git remote)
5. Capture issue URL; log to audit trail
6. Write unit tests:
   - Mock subprocess.run for gh CLI; verify call arguments (title, body, labels)
   - Verify issues created for all non-major findings
   - Mock gh CLI failure (subprocess.CalledProcessError); verify error logged, continue (best-effort)
   - Verify empty findings list (no issues created)
   - Verify repo_url handling (same repo vs. separate follow-ups project)
7. Constraint: GitHub tagging is best-effort (lowest priority per Follow-Up Tracking design); errors logged but don't block refactor

---

## Slice 11: Update SKILL.md Documentation

**Risk Tier:** standard  
**Depends On:** Slices 1-10  
**Files:** `agent-isdd/skills/spec-driven-development/SKILL.md`  

### Test Intent
Replace "Code Review Gate" section with automatic invocation description; clarify severity-based auto-advance, rollback on major findings, mandatory review constraint, no override mechanism.

### Validation Target
Manual review of SKILL.md consistency and accuracy.

### Ordered Steps
1. Locate existing "Code Review Gate" section in SKILL.md
2. Replace with:
   - Heading: "## Automatic Code-Reviewer Invocation on High-Risk Slices"
   - Subsection: "When This Runs" — post-green phase, high-risk slices always, standard slices if touching configured high-risk file paths
   - Subsection: "Severity Classification" — explain major (Intent/Regression/Security FAIL/WARN) vs. non-major (others)
   - Subsection: "Auto-Advance Behavior" — non-major/clean findings → automatic proceed to refactor; major findings → return to red, developer must fix and re-test
   - Subsection: "Follow-Up Tracking" — non-major findings tracked as tasks + recap.md entries + GitHub issues (best-effort)
   - Subsection: "Timeout & Error Handling" — timeout skips review, error returns to red
   - Subsection: "No Override" — mandatory review for applicable slices; developers cannot skip
3. Add link to new INTEROP.md "Auto Code-Reviewer Integration" section
4. Add example: sample phase marked high-risk, sample code-reviewer output, sample severity classification result
5. Verify documentation is clear and matches implementation

---

## Slice 12: Update INTEROP.md Documentation

**Risk Tier:** standard  
**Depends On:** Slices 1-10  
**Files:** `agent-isdd/INTEROP.md`  

### Test Intent
New section documenting auto-code-reviewer integration: severity taxonomy, subprocess invocation mechanism, rollback vs. severity findings distinction, integration points with agent-tdd + code-reviewer.

### Validation Target
Manual review of INTEROP.md consistency and accuracy.

### Ordered Steps
1. Add new section to INTEROP.md: "## Auto Code-Reviewer Integration on High-Risk Slices"
2. Document subsections:
   - **Integration Flow:** red-green → green_pause marker → SubagentStop fires high_risk_reviewer hook → code-reviewer subprocess invoked → severity classified → rollback marker OR resume message emitted
   - **Severity Taxonomy:** Explain Intent/Regression/Security = major; BestPractices/Naming/Scalability = non-major; all PASS = clean. Rationale: correctness-level vs. refactoring-safe improvements
   - **Code-Reviewer Invocation (Subprocess-Based):** Explain /code-reviewer slash command invoked via subprocess; timeout default 10 min; graceful degradation on error
   - **Rollback vs. Findings:** Clarify SDD-ROLLBACK-REQUEST (task-level escalation) is orthogonal to severity findings; rollback can be requested by code-reviewer's rollback_request field OR triggered by major severity classification
   - **Follow-Up Tracking:** TaskCreate → recap.md → GitHub (in order; partial success acceptable)
   - **Configuration:** High-risk file paths parsed from design.md Risks section; override in workflow-state.json
   - **Future Enhancements:** When code-reviewer adds native severity field, prefer over synthetic classification; async invocation if latency becomes issue
3. Add data contracts:
   - agent-tdd output format (green_pause marker)
   - code-reviewer JSON schema (dimensions, findings)
   - workflow-state.json tracking schema (reviewed_phases)
   - SDD-ROLLBACK-REQUEST marker format
4. Add examples: sample agent-tdd report → code-reviewer invocation → severity classification → reviewed_phases write
5. Link to SKILL.md for user-facing documentation

---

**Phase Completion Summary**

- **Research Validation:** Thorough; all touchpoints covered; no gaps or contradictions
- **Task Slicing:** 12 TDD-sized slices across 4 phases (Foundation → Markers → Follow-Up Tracking → Docs)
- **Ralph Loops:** All 3 pass (size, dependencies, traceability)
- **Risk Tiers:** 3 high-risk (Slices 3, 8, 10), 9 standard
- **Readiness:** Ready For Implementation

**Execution Order (Recommended)**
1. Phase 1 (Foundation): Slices 1, 2, 3, 4, 5, 6, 7 (sequential)
2. Phase 2 (High-Risk Follow-Ups): Slices 8, 9, 10 (sequential; stage in order per design)
3. Phase 3 (Documentation): Slices 11, 12 (parallel)

**High-Risk Slice Notes**
- Slice 3: Subprocess invocation; test with mocked subprocess; verify timeout + error handling
- Slice 8: TaskCreate API call; mock external API; handle partial failures (TaskCreate fails, continue)
- Slice 10: GitHub CLI invocation; mock subprocess; best-effort semantics (skip on error, log warning)
