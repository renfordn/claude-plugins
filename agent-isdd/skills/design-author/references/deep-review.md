# Design Validation: Deep Review detail

Read by `design-author` when running the Deep Review (Design Validation) pass after the Design Gate passes: plan-mode scoping, the invocation parameters and focus areas, and where findings are folded.

**Corrected 2026-09-24 [plan/design gap]**: the Design Gate passing does not by itself mean
`design.md`/`research/cache.md` are on disk — per "Plan-Mode Drafting" above, that only happens
once the user approves the plan, which can be after this step (Design Gate approval and the
implementation request that triggers `ExitPlanMode` are separate events — see `workflow-manager`'s
"Native Plan Mode Gate"). So while plan mode is still active, point `/code-reviewer` at the
in-context draft / plan file content directly rather than at `design.md`/`research/cache.md`
file paths; only use the file-path scope once those files have actually been persisted (plan mode
was skipped or has already exited).

**Step: Design Coherence Validation**

1. Invoke `/code-reviewer` skill with:
   - **Mode**: `direct-review` (or `review-improve` if piping findings into user review)
   - **Scope**: the design content and research basis — as `design.md` + `research/cache.md` file
     paths once persisted, or as inline content from the plan file / context while plan mode is
     still active and those files don't yet exist on disk
   - **`review_level`**: `Deep` (design pattern validation, coherence checks)

2. Focus areas for Deep review in design context:
   - Design pattern alignment (is the implementation matching the stated patterns?)
   - Single Responsibility Principle (SRP) validation (do modules/classes have focused scope?)
   - File touchpoint correctness (are the right files being touched for the right reasons?)
   - Slice feasibility (can the proposed slices be implemented independently?)
   - Interface consistency (do stated contracts match across touchpoints?)
   - Architecture coherence (do design decisions hang together or conflict?)

(Gate logic stays in SKILL.md under "Design Validation: Deep Review".)

4. **Corrected 2026-09-24**: there is no separate `task-slicer`/"next phase" handoff on
   `agent-isdd`'s side to attach findings to — per Phase 2+3, task slicing happens entirely
   inside `agent-tdd` during the Design Spec handoff (see `INTEROP.md`'s "→ agent-tdd" section),
   and the Design Spec's fixed fields (`requirements_md`, `design_md`, `research_cache`,
   `recap_md`) carry no dedicated review-findings field. Output: fold any Deep review findings
   worth preserving into the design content itself (e.g. its Design Summary or a Risks/Constraints
   note) before the Design Spec is constructed, so they travel with `design_md` — do not rely on a
   separate handoff channel that no longer exists. **Corrected 2026-09-24 [plan/design gap]**: if
   plan mode is still active, fold findings into the plan file's draft (the same in-context/
   plan-file content this step reviewed), not into `design.md` directly — it isn't writable yet.

**Rationale**: This upfront Deep review catches wrong-shape designs early, before task slicing 
and implementation, reducing rework during Red-Green-Refactor cycles. See 
`code-reviewer/skills/code-reviewer/references/parameters.md`'s "Review Levels" section for Deep level definition.
