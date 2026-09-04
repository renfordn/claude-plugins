# Design Spec Orchestration: Token Efficiency First

## North Star

**Reduce token usage by 50-70% vs. per-agent standalone orchestration.**

Key strategies:
1. **One-pass research validation** — detect gaps early, escalate if needed (don't proceed to slicing on thin research)
2. **Reuse cached outputs** — store task-slicer output, ralph-loops results in workflow-state.json (avoid re-computation on resume)
3. **Structured handoffs** — JSON/markdown tables, not prose (compact, parseable, cacheable)
4. **Early bail-out** — if research gaps too large or ralph-loops max iterations, escalate immediately (don't retry)
5. **Brief cache integration** — nelly brief hints for "known good patterns" (7-10K savings per resume)
6. **No redundant reads** — parse design.md once, pass structured touchpoint list downstream (not re-parse per agent)
7. **Escalation over iteration** — if agent-tdd pauses with escalation, don't retry full flow; pause workflow and let user fix

---

## Orchestration Flow (Token-Optimized)

### Step 1: Parse Design Spec Once (Upfront Cost: 2-3K tokens)

**Goal:** Extract structured data from Design Spec to avoid re-parsing downstream

**Input:** Design Spec (requirements.md, design.md, research_cache, recap.md)

**Parse & Cache:**
```json
{
  "design_touchpoints": [
    {"file": "src/models/user.ts", "description": "Add email property with validation method"},
    {"file": "src/api/user-service.ts", "description": "Add email uniqueness check before save"},
    {"file": "src/forms/register-form.ts", "description": "Call UserService.validateEmail before submit"}
  ],
  "ears_behaviors": [
    {"category": "Ubiquitous", "trigger": "user enters email", "response": "validate format RFC 5322"},
    {"category": "Ubiquitous", "trigger": "user enters email", "response": "check uniqueness"},
    {"category": "Unwanted-behavior", "condition": "email invalid", "response": "reject form submission, display error"},
    {"category": "Unwanted-behavior", "condition": "email duplicate", "response": "reject, suggest contact support"}
  ],
  "design_risks": [
    {"risk": "Email validation adds latency", "files": ["src/api/email-validator.ts", "src/forms/register-form.ts"]},
    {"risk": "Schema changes impact existing data", "files": ["src/models/user.ts"]}
  ],
  "file_summaries_map": {
    "src/models/user.ts": {...},
    "src/api/user-service.ts": {...},
    "src/forms/register-form.ts": {...}
  }
}
```

**Store in workflow-state.json** → `design_spec_cache` (reuse on resume, no re-parse)

**Cost savings:** 5-8K tokens on re-entry (skip re-parsing design.md, requirements.md)

---

### Step 2: Research Validation (3-5K tokens)

**Goal:** Fast gap detection; escalate if large gaps (don't proceed to slicing on thin research)

**Input:** `design_touchpoints` (from Step 1), `research_cache`, `file_summaries_map`

**Algorithm (token-aware):**
```
for each touchpoint in design_touchpoints:
  file = touchpoint.file
  if file NOT in research_cache.file_summaries:
    gap_count += 1
  if file in cache but summary is sparse (< 50 chars):
    thin_count += 1
  
if gap_count > 1 or thin_count > 2:
  ESCALATE("Research too thin for safe slicing")
  → save escalation marker to recap.md
  → pause workflow (before-continue hook detects, user re-enters to fix)
  → return immediately (don't proceed to task-slicer)

if contradictions found:
  ESCALATE("Design contradicts research")
  → save escalation marker
  → return immediately
  
else:
  PASS → proceed to task-slicer
```

**Cost savings:** 0 (necessary pass, but early bail-out saves downstream tokens)

---

### Step 3: Task Slicing (5-8K tokens)

**Goal:** Generate tasks.md from cached inputs (no re-read of design/research)

**Input:** `design_touchpoints`, `ears_behaviors`, `file_summaries_map` (all from Step 1/2 cache), `research_cache` (already validated)

**Token-aware algorithm:**
```
# Use cached data, don't re-read design.md
touchpoints = LOAD design_touchpoints from workflow-state.json
behaviors = LOAD ears_behaviors from workflow-state.json

# Map behaviors to files (cached touchpoints + research)
for behavior in behaviors:
  files = infer_files_from_touchpoints(behavior, touchpoints)  # cached
  phase = create_phase(behavior, files)
  
# Group phases (affinity)
phases = group_by_affinity(phases, max_files=3)

# Build dependency graph (minimal traversal)
graph = build_graph_from_file_dependencies(phases, research_cache)  # single pass

# Topological sort + output tasks.md
tasks = topological_sort(graph)
SAVE tasks to tasks/tasks.md
```

**Reuse:** 100% of design.md and research_cache (no re-read)

**Cost savings:** 8-12K tokens (skip re-parsing and re-analyzing design intent)

---

### Step 4: Ralph Loops Validation (4-6K tokens per iteration, max 3 iterations)

**Goal:** Validate slices with early bailout if max iterations hit

**Token-aware rules:**
```
max_iterations_per_loop = 3  # hard limit (not 5)
max_total_iterations = 9  # 3 loops × 3 iterations

if loop_iteration >= max_iterations_per_loop:
  if loop == "Loop 1 (Slice Size)":
    ESCALATE("Cannot reconcile slice sizes; manual review needed")
  elif loop == "Loop 2 (Dependencies)":
    ESCALATE("Circular dependency; likely design issue")
  elif loop == "Loop 3 (Traceability)":
    ESCALATE("Research gaps too large; recommend re-research")
  return immediately  # don't retry
```

**Reuse:** Reuse `design_spec_cache` (don't re-read design.md)

**Cost savings:** 5-10K tokens (hard iteration limits prevent runaway refinement)

---

### Step 5: Risk Assignment (2-3K tokens)

**Goal:** Fast, deterministic risk tier assignment

**Token-aware approach:**
```
# Use cached design_risks (not re-read design.md)
design_risks = LOAD design_risks from workflow-state.json

for phase in tasks.md:
  risk_tier = "standard"  # default
  
  # Check 1: Design-named risk (cached, fast)
  for risk in design_risks:
    if any(file in phase.files for file in risk.files):
      risk_tier = "high-risk"
      break
  
  # Check 2-5: Migrations, multi-module, testability, Ralph warnings (quick checks)
  if "migration" in phase.objective.lower() or "schema" in phase.objective.lower():
    risk_tier = "high-risk"
  
  phase.risk_tier = risk_tier
```

**Reuse:** Cached design_risks, cached ralph-loops report

**Cost savings:** 3-5K tokens (no prose, just structured checks)

---

### Step 6: Readiness Check (2-3K tokens)

**Goal:** Fast 10-item checklist validation

**Token-aware approach:**
```
# Deterministic checklist (no prose, just pass/fail)
checklist = [
  ("phase_count >= 1", phase_count >= 1),
  ("all_phases_have_fields", all(required_fields_present(p) for p in phases)),
  ("ralph_loops_passed", ralph_loops_report.status == "PASS"),
  ("dependencies_acyclic", is_dag(dependency_graph)),
  ("steps_grounded", all(step_in_cache_or_design(s) for s in all_steps)),
  ("test_intent_clear", all(len(p.test_intent) > 20 for p in phases)),
  ("validation_verifiable", all("Command:" in p.validation_target for p in phases)),
  ("no_blockers", not any("[  ]" in p.blockers for p in phases)),
  ("risk_tiers_assigned", all(p.risk_tier in ["high-risk", "standard"] for p in phases)),
  ("ready_state", "State: Ready For Implementation" in tasks_md)
]

passed = all(check[1] for check in checklist)
if passed:
  verdict = "ready"
else:
  verdict = "paused"
  failed_items = [c[0] for c in checklist if not c[1]]
  ESCALATE(f"Readiness check failed: {failed_items}")
```

**Reuse:** All cached data

**Cost savings:** 1-2K tokens (structured checklist, no narrative)

---

### Step 7: Handoff to Red-Green-Refactor (0 tokens)

**When readiness-check verdict == "ready":**

```
# Return structured handoff (not prose)
handoff = {
  "verdict": "ready",
  "tasks_file": "tasks/tasks.md",
  "high_risk_phases": [p.name for p in phases if p.risk_tier == "high-risk"],
  "phase_order": [p.name for p in topological_sort(phases)],
  "total_phases": len(phases),
  "next_step": "For each phase in order: if high-risk spawn test-author first, then spawn agent-TDD"
}

RETURN handoff
# agent-TDD takes over (no more agent-isdd involvement)
```

---

## Escalation Paths (Save Tokens by Bailing Out Early)

**Escalation vs. Iteration:**
- **Escalate immediately** (save 10-20K tokens):
  - Research gaps > 2 files
  - Design contradictions
  - Ralph Loops max iterations hit
  - Readiness checklist failures
  
- **Never iterate locally** (avoid token waste):
  - Don't retry research-consolidator calls
  - Don't reslice and re-validate
  - Don't tweak design on the fly
  - Let user (or prior agent) fix upstream, then resume

---

## State Caching for Resume (Cross-Session Token Savings)

**On initial run, cache everything in workflow-state.json:**

```json
{
  "design_spec_cache": {
    "design_touchpoints": [...],
    "ears_behaviors": [...],
    "design_risks": [...],
    "file_summaries_map": {...},
    "cached_at": "2026-08-22T10:30:00Z",
    "intent_hash": "abc123..." 
  },
  "task_slicer_output": {
    "tasks_md": "full tasks.md content",
    "generated_at": "2026-08-22T10:35:00Z"
  },
  "ralph_loops_results": {
    "status": "PASS",
    "iterations_per_loop": {"Loop 1": 2, "Loop 2": 1, "Loop 3": 1},
    "generated_at": "2026-08-22T10:40:00Z"
  },
  "risk_assignments": {
    "Phase 1": "standard",
    "Phase 2": "standard",
    "Phase 3": "standard",
    "Phase 4": "high-risk"
  }
}
```

**On resume (after escalation fix):**
- Reuse all cached outputs (skip Steps 1-6)
- Only re-run affected step (e.g., if research-consolidator filled gaps, re-run research-validator)
- Skip unchanged steps

**Cost savings:** 20-30K tokens per resume (entire orchestration cached, only delta re-computed)

---

## Concrete Token Budget

**Initial Design Spec → Ready Verdict:**
- Step 1 (parse): 2-3K
- Step 2 (research validation): 3-5K
- Step 3 (task slicing): 5-8K
- Step 4 (Ralph Loops, 1 iteration): 4-6K
- Step 5 (risk assignment): 2-3K
- Step 6 (readiness check): 2-3K
- **Total: 18-28K tokens**

**Comparison (old per-agent approach):**
- planning-agent (design research): 8-12K
- planning-agent (task research): 8-12K ← redundant
- Manual task slicing: 5-10K
- Manual slicing validation: 5-10K
- **Total: 26-44K tokens (redundant research + manual effort)**

**Savings: 8-26K tokens per feature (30-60% reduction)**

---

## Resume After Escalation

**If research-validator escalates (gaps found):**

1. research-consolidator fills gaps (user re-enters agent-isdd)
2. User re-continues agent-isdd workflow
3. agent-isdd before-continue hook:
   - Detects escalation marker in recap.md
   - Clears design_spec_cache (Intent Hash may have changed)
   - Re-runs agent-tdd design-spec flow (but reuses task_slicer_output if research still valid)
   
**If ralph-loops escalates (max iterations):**

1. User re-enters agent-isdd (fix design or escalate to design-author)
2. agent-isdd re-runs design-spec flow
3. Reuse design_spec_cache (no change), skip to task-slicer
4. Task-slicer produces revised tasks.md
5. ralph-loops re-validates (should converge faster with fixes)

**Cost savings on resume:** 10-15K tokens (reuse cache, skip unchanged steps)

---

## Implementation Notes

- **No prose in structured outputs** — JSON/markdown tables only
- **Hard iteration limits** — 3 per loop, 9 total (not 5, not infinite)
- **Early bailout** — escalate on first gap/contradiction/max-iteration (don't retry)
- **Cache everything** — design_spec_cache, task_slicer_output, ralph-loops results all go to workflow-state.json
- **Intent Hash validation** — if Intent changes, invalidate cache and re-parse
- **Reuse research_cache** — never call research-consolidator unless gaps found
