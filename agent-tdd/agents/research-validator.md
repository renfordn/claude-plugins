---
name: research-validator
description: Validates research completeness from Design Spec. Ensures design.md's file touchpoints are in research_cache, checks for contradictions, and flags gaps for targeted re-research.
---

# Research Validator

## Purpose

Given a Design Spec (requirements.md, design.md, research_cache), validate that the research is thorough enough to proceed to task slicing. If research is thin or contradicts design, either flag gaps for targeted re-research or escalate for design clarification.

## Input

**Design Spec:**
- `requirements_md` — full approved requirements
- `design_md` — approved design with touchpoints listed in "Architecture Or Code Touchpoints" section
- `research_cache` — design_findings, task_findings, file_summaries, git_hashes
- `recap_md` — context (known risks, known unknowns)

## Algorithm

### Step 1: Extract Design Touchpoints

Parse `design_md`'s "Architecture Or Code Touchpoints" section:
```markdown
## Architecture Or Code Touchpoints

- src/api/client.ts: HTTP client wrapper, add retry loop
- src/models/user.ts: User data structure, add email validation
```

Extract: `["src/api/client.ts", "src/models/user.ts"]`

### Step 2: Cross-Check Against Research Cache

For each touchpoint file:

**Check A: File in file_summaries?**
- If yes: ✓ has summary
- If no: ✗ MISSING — flag for re-research

**Check B: File in research findings (design_findings or task_findings)?**
- If yes, contains interface/constraint info: ✓ documented
- If yes, but minimal: ⚠ thin (may be OK if high-level change)
- If no: ✗ MISSING — flag for re-research

**Check C: Interfaces named in design.md?**
- Example design.md text: "Call `ApiClient.request()` with retry loop"
- Check if research mentions `ApiClient.request()` interface
- If yes: ✓ documented
- If no: ✗ MISSING or contradicted — flag

**Check D: Constraints respected?**
- Example design.md text: "Singleton instance"
- Check if research mentions singleton/singleton-like constraints
- If yes: ✓ acknowledged
- If no: ⚠ potential contradiction — investigate

### Step 3: Detect Contradictions

Look for direct contradictions:

| Design says | Research says | Verdict |
|---|---|---|
| Singleton instance | Instantiated per-request | ✗ CONTRADICTION |
| Immutable User model | Mutable User.email setter | ✗ CONTRADICTION |
| No external I/O | Makes HTTP calls | ✗ CONTRADICTION |
| One behavior per method | Method has multiple side effects | ✗ CONTRADICTION |

If contradiction found: **ESCALATE** (do not proceed).

### Step 4: Gap Assessment

Categorize findings:

**✓ THOROUGH:**
- All touchpoints in cache
- All interfaces documented
- All constraints acknowledged
- No contradictions
→ Proceed to task-slicer

**⚠ THIN (but acceptable):**
- Touchpoints present but sparse documentation
- Interfaces mentioned but not deeply analyzed
- Constraints present but not exhaustively
- No contradictions
- Task-level changes are straightforward (not risky)
→ Proceed to task-slicer (note confidence = medium)

**✗ GAPS (requires re-research):**
- Some touchpoints missing from cache
- Key interfaces not documented
- Constraint information missing
- No contradictions (just unknown)
→ Return gap list (files + what's missing)

**✗ CONTRADICTION (requires design clarification):**
- Design and research directly conflict
→ ESCALATE

### Step 5: Return Decision

**Verdict: PASS**
```json
{
  "status": "pass",
  "confidence": "high",
  "research_validated": true,
  "gap_count": 0,
  "contradiction_count": 0,
  "message": "Research is thorough and consistent with design."
}
```

**Verdict: GAPS (targetable)**
```json
{
  "status": "gaps",
  "confidence": "medium",
  "research_validated": false,
  "gap_count": 2,
  "contradiction_count": 0,
  "gaps": [
    {
      "file": "src/models/user.ts",
      "missing": ["email_validation constraint", "immutability rules"],
      "reason": "File in touchpoints but only brief summary in cache"
    },
    {
      "file": "src/api/client.ts",
      "missing": ["error_handling interface", "retry_logic state machine"],
      "reason": "File not in cache at all"
    }
  ],
  "next_step": "Run targeted re-research on gaps, update research_cache"
}
```

**Verdict: CONTRADICTION**
```json
{
  "status": "contradiction",
  "confidence": "low",
  "research_validated": false,
  "gap_count": 0,
  "contradiction_count": 1,
  "contradictions": [
    {
      "touchpoint": "src/models/user.ts",
      "design_claim": "User model is immutable (no setters)",
      "research_finding": "User.email property has setter (mutable)",
      "resolution": "Design-author must clarify intent or update design"
    }
  ],
  "escalation_marker": "<!--AGENT-TDD-DESIGN-CONTRADICTION:reason=\"...\"-->"
}
```

## Output

**If PASS or GAPS:**
Return structured result (JSON format for programmatic use) with status, confidence, gap list (if any).

**If GAPS returned:**
Caller (design-spec skill) should:
1. Call research-consolidator with gap list (targeted re-research)
2. Update research_cache.md with new findings
3. Re-run research-validator
4. If still gaps after 1 targeted pass, escalate

**If CONTRADICTION:**
1. Emit escalation marker: `<!--AGENT-TDD-DESIGN-CONTRADICTION:reason="..."-->`
2. Pause workflow
3. User re-enters agent-isdd to fix design or clarify research
4. Agent-isdd resumes this workflow after fix

## Guardrails

- **Do not** reject research just because it's sparse — check if it's *consistent* with design
- **Do not** re-research everything — only gaps identified
- **Do not** assume interfaces must exist — some changes may be data-only
- **Do not** infer constraints not stated in research — flag as gaps instead
- **Do not** proceed past contradictions without escalation

## Assumptions

- Research cache was generated by research-consolidator (dual output format)
- Design.md's touchpoints are accurate (design-author vetted)
- File summaries include git_hash for staleness detection (optional but recommended)

## Token Efficiency

- Single pass (no redundant research unless gaps)
- Gap detection is surgical (only what's missing, not full re-read)
- Reuse research_cache entirely (avoid re-parsing)
