# Interop: agent-isdd

This plugin owns Requirements → Design → Tasks only. It hands off to three sibling plugins
rather than owning their work. This document is the authoritative description of each boundary,
for both agent-isdd's own maintainers and the sibling plugins' maintainers to cross-check.

> Status: skeleton written in Phase 1 of the `agent-isdd` scope refactor; the concrete Slice
> Spec mapping below is implemented and finalized in Phase 3. See
> `~/.claude/sdd-memory/users-jay-nelson-codebase-ai-plugins-claude-agent-isdd/spec/2026-08-12-isdd-plugin-scope-refactor/`
> for the full requirements/design/tasks this repo was built from.

## → agent-tdd (implementation, Phase 2+3 revised)

**[Phase 2+3]** At the end of Design, once Design is approved and implementation is requested,
`agent-isdd` constructs a **Design Spec** from the approved `requirements.md`/`design.md`, the
cached research findings, and pre-fetched file summaries, then spawns `agent-tdd` for research
validation, task slicing, and implementation.

**Design Spec** includes:
- Full `requirements.md` (approved)
- Full `design.md` (approved, with Research Basis section)
- `research/cache.md` (design_findings, task_findings, file_summaries, git_hashes)
- Pre-fetched file summaries from agent-nelly cache (if available)
- `recap.md` (summary, known risks, blockers, Goal alignment notes)

**Agent-tdd responsibilities** (Phase 2+3):
1. **Research Validation** (optional re-research gaps only)
   - Validate design.md's file touchpoints against research cache
   - If cache is thin or inconsistent: run targeted deep-read only on gaps
   - If design contradicts research: escalate back to agent-isdd

2. **Task Slicing** (produce `tasks.md`)
   - Produce phased, TDD-sized slices from Design + task_findings
   - Validate slice safety (3 files max, testable, acyclic dependencies)
   - Assign Risk Tiers (high-risk → spawn test-author first)

3. **Implementation** (Red-Green-Refactor per slice, existing behavior)

This is a **one-directional handoff**: agent-isdd does not resume or monitor agent-tdd past
the initial spawn. Task slicing happens inside agent-tdd (not handed back to agent-isdd as
Slice Specs). Escalations back to agent-isdd (design contradicts research, research too thin)
pause with explicit reason; agent-isdd resumes via its `before-continue` hook when user
re-enters after addressing the escalation.

**Exception — Code-Review Gate**: When agent-tdd pauses mid-refactor (waiting for mandatory
code-review on a high-risk slice), the user runs `/code-reviewer` in a separate context. When
the user returns via `/isdd-continue`, the `before-continue` hook detects agent-tdd's paused
state and sends a continuation message (via `SendMessage`) to the existing agent-tdd session,
passing full context. agent-tdd resumes from its internal refactor state. This is the ONLY
continuation path — no per-phase instructions, no reconstructed Slice Specs, no incremental
phase-by-phase requests.

### Agent-tdd Implementation Requirements (Phase 2+3)

Agent-tdd must implement three new phases before Red-Green-Refactor:

**Phase 1: Research Validation**
- Input: Design Spec (requirements.md, design.md, research/cache.md, file_summaries)
- Validate research completeness:
  - Are design.md's file touchpoints in research/cache.md?
  - Are interfaces documented?
  - Are constraints captured?
- Decision:
  - ✓ Research thorough: proceed to slicing
  - ✗ Research thin: run targeted research-consolidator (on gaps only)
  - ✗ Design contradicts research: escalate back to agent-isdd (pause, surface reason)

**Phase 2: Task Slicing**
- Input: Requirements + Design + validated research + task_findings
- Produce tasks.md with:
  - Phased, TDD-sized slices (one behavior change, one file/module touched if possible)
  - Risk Tiers per slice (high-risk → spawn test-author first)
  - Depends On graph (topological sort, acyclic)
  - Test Intent + Validation Target per slice
- Rules: One behavior per slice, safe for Red-Green-Refactor isolation
- Apply Ralph Loops (see below)

**Phase 3: Validation (Ralph Loops)**

Three autonomous validation loops, max 3-5 iterations each:

1. **Slice Size Validation Loop**
   - For each slice: count files, estimate test surface, verify Red-Green-Refactor feasibility
   - If oversized: split, adjust dependencies
   - Exit when: all slices ≤ 3 files, testable, no slice depends on > 2 others

2. **Dependency Correctness Loop**
   - Build Depends On graph, run topological sort
   - Verify: acyclic, no hidden dependencies
   - If cycle/missing dep: reorganize, re-slice
   - Exit when: acyclic, complete

3. **Research-to-Implementation Traceability Loop**
   - For each slice's "Ordered Steps": validate against research/cache.md
   - Verify: file/interface exists, constraint respected
   - If missed research: run targeted deep-read, update cache, call agent-nelly
   - If contradiction: flag as known risk in slice
   - Exit when: traceable or flagged

**Phase 4: Risk Tier Assignment**
- high-risk when:
  - design.md's Risks And Tradeoffs names a risk touching this slice's files
  - Slice is a migration (schema, API breaking change)
  - Touches multiple independent modules
  - Weak testability
- Default: standard

**Phase 5: Ready-to-Implement Check**
- Readiness checklist:
  - [ ] At least one concrete phase exists
  - [ ] Each phase has objective, Risk Tier, steps, test intent, validation target
  - [ ] Slices are safe for TDD (≤ 3 files, acyclic dependencies)
  - [ ] No unresolved blocker
  - [ ] State: Ready For Implementation

**Escalation Paths Back to agent-isdd:**
- Research gap too large: pause, provide specific files needing research
- Design contradicts research: pause, surface contradiction (design-author fixes)
- Slicing requires product decision: pause, ask user which strategy
- High-risk slice cannot be split: pause, confirm oversized + high-risk acceptable

**Handoff Report Format:**
```
Verdict: ready | paused (with specific reason)
Phase breakdown: 1-line summary
Tasks file path: tasks/tasks.md
Slicing confidence: high | medium (if research feels incomplete)
Ralph Loops results: all passed | <loop name> iteration X of max
```

**After Tasks readiness passes:**
- If verdict == `ready`: proceed to Red-Green-Refactor per slice (existing agent-tdd behavior)
- If verdict == `paused`: return reason; user re-enters agent-isdd to address it
- Do NOT proceed to implementation until readiness checklist fully passes

**Availability check**: unlike `agent-nelly`, which is checked eagerly at `before-requirements`
and cached in `workflow-state.json` because it is used throughout the workflow, `agent-tdd` is
only needed once — at the handoff. Check availability inline at that point by scanning the
current session's `<system-reminder>` agent-types block for the string `agent-tdd:agent-TDD`.
No caching or `workflow-state.json` field is needed. If absent, pause with a concrete,
actionable message (e.g. "agent-tdd is not installed in this session — install it before
requesting implementation") rather than attempting the work internally.

## ← agent-tdd / code-reviewer (rollback request)

Sometimes `agent-tdd`'s Green→Refactor review pause (or `code-reviewer`) discovers that the
*task* itself — not just the implementation — was wrong. There is no cross-plugin IPC to build
a live push channel for this, so the return path is a documented marker convention plus a
check `agent-isdd` performs on its own re-entry, not agent-isdd reaching into `agent-tdd`'s
active loop. Two genuinely different marker formats feed two different paths below — this used
to be documented as one marker with two delivery paths, which was wrong: `agent-tdd` never emits
SDD-specific vocabulary (see its own `INTEROP.md`), so it cannot literally emit the human-relay
marker below itself. That was a real gap, not just a documentation gap — closed by giving
`agent-tdd` its own generic marker instead of assuming it would speak agent-isdd's.

**Automatic path** (agent-tdd's own generic signal): `agent-tdd`'s **Plan Validity Flag** (see
`agent-tdd/INTEROP.md`'s section of the same name) is a caller-agnostic marker —
`<!--AGENT-TDD-PLAN-FLAG:reason="..."-->` — with no target phase, since `agent-tdd` has no
concept of agent-isdd's phase vocabulary. When `agent-tdd:agent-TDD`'s spawn report contains it,
`hooks/subagent_report.py`'s `SubagentStop` handler recognizes it (independently of its normal
narrative-report capture, which excludes implementation-phase reports otherwise), defaults the
rewind target to `Requirements` — per `references/rollback-guide.md`'s existing "Which target
phase to name" policy: an unclear or absent target defaults to the more conservative (earlier)
phase, since it's always safer to re-confirm a phase that may have been fine than to skip past
one that actually needs revision — and writes `rollback_pending` to `workflow-state.json` plus a
`Pending Rollback Request` line to `workflow-state.md`, with the reason text tagged so a later
reader (or `workflow-manager`'s own "Rollback Request Intake," which reads the reason and can
re-target forward per its documented rule) knows `Requirements` was defaulted, not derived from
the reason. The next `before-continue` hook checks for it first and routes into the Rewind
Contract.

**Human-relay path** (agent-isdd's own vocabulary, for a human relaying a finding): a human (or
whichever context is driving) who already knows agent-isdd's phase names can paste this marker
directly into a message re-entering agent-isdd:

```
<!--SDD-ROLLBACK-REQUEST: target=<Requirements|Design|Tasks> reason="..."-->
```

`before-continue` recognizes it in user input the same way, when present — this is the path for
`code-reviewer`'s findings, or any `agent-tdd` resume happening via `SendMessage` in a session
agent-isdd isn't part of, since neither has an automatic hook of its own. For step-by-step
instructions on both paths, see [`references/rollback-guide.md`](references/rollback-guide.md).

Do not treat either path as a fully automatic guarantee on its own: the automatic path only
fires when `agent-tdd` actually raises a Plan Validity Flag on its *initial* spawn report (not
on a later `SendMessage` resume, which this hook does not observe), and only ever targets
`Requirements` by default — human-relay remains the only path with an explicit target, and the
only path for `code-reviewer` altogether.

## → code-reviewer (review gate)

agent-isdd never invokes `code-reviewer` directly. It is `agent-tdd`'s responsibility (per
`agent-tdd`'s own `INTEROP.md`) to arrange the review gate with whichever context is driving
implementation after the handoff above.

## → agent-ux (UX rendering)

At every phase transition, section-confirmation checkpoint, review-dashboard threshold, and
out-of-scope-task flag, `agent-isdd` delegates to `agent-ux:ux-agent` instead of an in-process
agent, constructing the UX Event Envelope (`caller: agent-isdd`, `event_type`, `phase_state`,
`delta`, `artifact_path`) defined in `agent-ux`'s own `INTEROP.md` — that document is the
authoritative schema (envelope shape, the five per-`event_type` delta shapes, and the
pull-over-push invariant); this section only states how `agent-isdd` uses it, not a duplicate
definition.

`agent-ux:ux-agent` is a **soft dependency**, same pattern as `agent-nelly` below: if it is not
installed or otherwise unreachable, `agent-isdd` catches the missing-plugin condition, surfaces
one plain notice for the session (not one per event), and continues without blocking — see
`agent-ux`'s `INTEROP.md` "Unavailability and fallback contract" section for the full generic
contract (including its own internal fallback when a specific rendering tool like `Artifact` is
unavailable), referenced here by name rather than restated.

The `TaskCreate`/`TaskUpdate`/`TaskList` checklist is not part of this delegation — `agent-ux`'s
isolated subagent context cannot reach deferred tools, so the calling skill renders/refreshes the
checklist directly, unchanged from today's local-agent behavior.

## → agent-nelly (memory)

Before starting or continuing meaningful phase work, `agent-isdd` delegates to
`agent-nelly:nelly-orchestrator` for a goal-aware brief — nelly's four output sections are
`Intent`, `Relevant entries`, `Intent alignment`, and `Written`; agent-isdd uses `Intent` to
seed/check the feature's `Goal` field, and `Intent alignment` as the divergence signal — rather
than reading `~/.claude/sdd-memory/` cross-feature index files directly. If `agent-nelly` is
unavailable, agent-isdd surfaces one plain notice and continues without the Intent-alignment
check — never a hard dependency.

agent-isdd still owns writing its own per-feature `spec/` artifacts
(`workflow-state.md`/`.json`, `requirements.md`, `design.md`, `tasks.md`, `recap.md`) under
`~/.claude/sdd-memory/<project-slug>/spec/<feature-slug>/` directly — that scaffolding
(`hooks/sdd_memory.py`) is not part of what `agent-nelly` owns.

Within a continuous stretch of phase work, agent-isdd does not re-call
`agent-nelly:nelly-orchestrator` on every step once a brief has already been fetched and is
still visible in context — it reuses the in-session brief instead. The full re-fetch-trigger
convention lives in `skills/spec-driven-development/SKILL.md`'s Goal-Aware Memory section (this
is a documentation pointer, not a duplicate definition). `workflow-state.json` is intentionally
unchanged by this dedup convention — it carries no brief-caching field.

**Write-back during spec phases**: at each `after-*` hook (`after-requirements`,
`after-design`, `after-tasks`), when `agent_nelly_available` is `true`, agent-isdd calls
`agent-nelly:nelly-orchestrator` with a `new facts` batch containing any project-level
discoveries worth persisting across future sessions — for example: interface assumptions
confirmed or denied during requirements, coverage gaps or unexpected interfaces found during
design research, risk flags raised. The criterion is "would a future conversation benefit from
knowing this independently of this feature's own artifacts?" — ephemeral workflow state (user
confirmed step N, phase advanced) never qualifies. Choose the call shape by content: a positive
discovery (a confirmed interface, a constraint, a risk) is a `new fact`/`new facts` batch; a
discovery that a specific approach was tried and rejected is an `error lesson` instead. If the
call fails or nelly is unavailable, log a one-line note in `recap.md` and continue — it is never
a blocking condition.

**[Phase 2+3] File-level cache via `new facts` batches**: after `research-consolidator` completes
during Design phase, `design-author` extracts `file_summaries` from the research output and
persists them to agent-nelly via a `new facts` batch with type: `"file_summary"`. Schema per
summary:

```json
{
  "type": "file_summary",
  "path": "src/api/client.ts",
  "summary": "HTTP client wrapper with retry logic",
  "exports": ["class ApiClient { request() }", "function retry<T>(...)"],
  "constraints": ["Singleton: initialized once", "Not re-entrant"],
  "tech_debt": ["Retry backoff hardcoded"],
  "dependencies": ["axios", "events"],
  "test_surface": ["Mock ApiClient.request()", "Test retry behavior"],
  "migration_risks": ["Request state cached; changes to error handling must clear cache"],
  "git_hash": "abc123def456",
  "touched_by": [{"feature": "payment-flow", "date": "2026-08-22"}]
}
```

Agent-nelly caches file summaries in `~/.claude/agent-nelly-memory/<project>/files/<slug>.json`
for cross-feature reuse. When `agent-isdd` needs file context during a later feature (Design
phase or agent-tdd slicing phase), it queries agent-nelly for cached summaries by file path;
agent-nelly returns cache hits with git_hash validation and cache misses.

Agent-nelly's file cache is optional and transparent to agent-isdd: if unavailable, agent-isdd
continues without pre-loaded file context (slower, but correct). The integration assumes
agent-nelly:nelly-orchestrator supports:
- `type: "file_summary"` in `new facts` batches (storage)
- A query interface to retrieve file summaries by path (retrieval, with git_hash validity check)

This is documented here as the contract both plugins can cross-check; agent-nelly's own `INTEROP.md`
is authoritative for its side of the contract.

## → agent-cache-plugin (phase state caching — optional)

agent-isdd optionally integrates with agent-cache-plugin to cache workflow phase state and render
token-optimized breadcrumbs. This is a soft dependency with graceful degradation: agent-isdd
works correctly without agent-cache-plugin installed, but renders breadcrumbs faster when it is
available.

**Integration Points**:

1. **Phase Transition Caching** (`hooks/cache_hook.py` → `SubagentStop`):
   - On phase change: POST to `localhost:7771/cache/write` with `{prompt, output, metadata}`
   - On rollback/rewind: POST to `localhost:7771/cache/invalidate` with `{scope}`
   - Cache scope: `agent-isdd:<feature-slug>`
   - Cache TTL: 3600 seconds (1 hour)
   - **If unavailable**: Logs to stderr and continues; phase state always tracked in markdown

2. **Breadcrumb Rendering Optimization** (`hooks/ux_render.py` → `SubagentStop`):
   - Before rendering: POST to `localhost:7771/cache/read` with `{key, scope}`
   - Cache hit: Returns cached phase state in ~100 tokens (fast path)
   - Cache miss: Derives from markdown in ~500 tokens (slow path)
   - Expected hit rate: 70-90% on typical workflow (same phase checked multiple times)
   - **If unavailable**: Always renders full breadcrumb (no optimization, but correct)

**Cache Entry Schema**:
```json
{
  "prompt": "description of cached content",
  "output": {
    "current_phase": "Design|Requirements|Tasks|Implementation",
    "phase_state": "In Progress|Approved|Blocked|...",
    "workflow_status": "...",
    "last_updated": "ISO8601 timestamp"
  },
  "metadata": {
    "cacheKey": "phase_state|breadcrumb_state",
    "scope": "agent-isdd:feature-slug",
    "ttl": 3600000,
    "type": "phase_state|breadcrumb_state"
  }
}
```

**Availability Check**:
- agent-cache-plugin is declared as an optional dependency in `plugin.json`
- Hooks attempt HTTP requests to `localhost:7771` with 1-3 second timeouts
- On URLError/TimeoutError: graceful degradation (log and continue)
- **Never** a blocking condition; workflow always completes correctly

**Token Efficiency**:
- **Without cache**: ~2-5K tokens per session (breadcrumb rendered every status check)
- **With cache + hits**: ~300-800 tokens per session (70-90% cache hit rate)
- **Savings**: 70-85% reduction in breadcrumb rendering costs

This integration is transparent to the user: no configuration needed, no API changes, full backward
compatibility. If agent-cache-plugin is installed and running, performance improves automatically.

---

## Auto Code-Reviewer Invocation (Review Gate, High-Risk Slices)

**[Phase 2+3]** Automatic code-reviewer invocation on high-risk slices during Green→Refactor pauses.

### High-Level Workflow

```
agent-tdd: Green phase complete → emit green_pause marker
    ↓
high_risk_reviewer hook (SubagentStop):
  1. Detect green_pause marker
  2. Extract high-risk phases + file-path-scoped standard phases
  3. Invoke /code-reviewer subprocess → JSON findings
  4. Classify severity: major | non-major | clean
  5. On MAJOR: emit rollback marker → pause at Tasks
     On NON-MAJOR/CLEAN: emit resume msg + create follow-ups → auto-advance to refactor
    ↓
agent-tdd: Resume refactoring (or pause for rollback handling)
```

### Severity Taxonomy

**MAJOR** (blocks refactor):
- Any FAIL or WARN on: intent, regressions, security
- Rationale: Critical dimension; requires re-evaluation
- Action: Emit rollback marker to Tasks phase

**NON-MAJOR** (proceed with follow-ups):
- Any FAIL/WARN on: best_practices, naming, scalability (AND no major issues)
- Rationale: Standard dimension; doesn't block logical correctness
- Action: Create follow-up tasks, append to recap.md, resume to refactor

**CLEAN**:
- All dimensions: PASS
- Action: No follow-ups, resume to refactor immediately

### Rollback vs. Severity Distinction

Rollback and severity are orthogonal:
- **Severity** classifies the findings (major/non-major/clean)
- **Rollback** is an orchestration decision (whether to pause work)
  - MAJOR severity → emit rollback marker (pause at Tasks, return to developer)
  - NON-MAJOR/CLEAN severity → no rollback (continue to refactor)

### Integration with Code-Reviewer Plugin

**Subprocess Invocation**:
- Command: `/code-reviewer --slice-spec '<JSON>'`
- Timeout: 600 seconds (configurable)
- Output: JSON with dimensions: {intent, regressions, security, best_practices, naming, scalability}
- Each dimension: {status: PASS|FAIL|WARN, findings: [{dimension, status, finding_text}]}

**Error Handling**:
- Timeout: Log and continue (non-blocking)
- Exit non-zero: Log and continue (non-blocking)
- Invalid JSON: Log and treat as no findings
- Command not found: Log and continue

### Integration with Agent-TDD

**Marker Detection**:
- Pattern: `<!--AGENT-TDD-PHASE:green_pause-->`
- Emitted by: agent-tdd's SubagentStop report
- Consumed by: high_risk_reviewer hook SubagentStop event

**Resume Path**:
- Non-major/clean findings: emit "Code review complete" message → before-continue hook
  detects green_pause and resumes agent-tdd
- Major findings: emit rollback marker → dev addresses findings → /isdd-continue restarts
  at Tasks phase

### Follow-Up Tracking Stages

1. **TaskCreate**: Create tasks for non-major findings (non-blocking)
   - Title: "[Code Review] <dimension>: <summary>"
   - Tags: ["code-review-finding", "follow-up", "<phase-slug>"]
   - Error: Log and continue

2. **recap.md**: Log findings with severity, task IDs, issue URLs
   - Section: "## Code-Review Findings"
   - Format: "- <phase> / <dimension> (<status>): <text> [task:id] [issue:url]"
   - Idempotent: duplicate findings skipped

3. **GitHub Issues**: Create issues for post-implementation triage (non-blocking)
   - Command: `gh issue create -R <repo> --title "..." --body "..." --label "..."`
   - Labels: ["code-review", "follow-up", "<phase-slug>"]
   - Error: Log and continue

### File-Path Scoping

**High-Risk File Paths** (from design.md Risks section or config):
- Parsed at invocation time from design.md "Risks And Tradeoffs" section
- Fallback: workflow-state.json config.high_risk_file_paths

**Standard Slices Scoping**:
- Standard-risk slices touching high-risk paths are also reviewed
- Reduces noise: limits review to critical changes only
- Example: if design.md lists `src/models/user.py` as high-risk,
  standard slices modifying it trigger automatic review

### Configuration

**workflow-state.json Schema**:
```json
{
  "code_reviewer_tracking": {
    "high_risk_phases": ["Phase 1: ...", "Phase 2: ...", ...],
    "reviewed_phases": [
      {
        "phase_name": "Phase 1: ...",
        "severity": "clean|non-major|major",
        "findings_count": 3,
        "findings": [{dimension, status, finding_text}, ...],
        "reviewed_at": "2026-08-24T12:00:00Z",
        "reviewer_version": "code-reviewer@0.1.0"
      },
      ...
    ],
    "config": {
      "high_risk_file_paths": ["src/models/user.py", "src/api/endpoints.py"],
      "review_timeout_seconds": 600,
      "skip_on_timeout": true,
      "github_repo": "https://github.com/org/repo"  // Optional
    }
  }
}
```

**Backward Compatibility**:
- Old schema (no config): treated as empty config
- Defensive reads: `.get("code_reviewer_tracking", {})` safe if key absent
- Missing fields default to sensible values (empty lists, 600s timeout)

### Future Deprecation Plan

When code-reviewer adds native severity classification (planned):
- Retire synthetic severity logic (MAJOR/NON-MAJOR categories)
- Consume code-reviewer's native severity field directly
- Update this section and spec-driven-development SKILL.md
