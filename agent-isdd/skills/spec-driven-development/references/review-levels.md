# Review Level Guidance per Phase

Each ISDD phase uses specific `/code-reviewer` review levels to validate artifacts at appropriate
depth. Review levels balance comprehensiveness with token efficiency and are tailored to each
phase's concerns.

| Phase | Review Level | Purpose | When | Invoked By |
|-------|--------------|---------|------|-----------|
| Requirements | Standard | Clarity check | After requirements draft, before approval | not implemented (`requirements-agent` does not invoke `/code-reviewer`; level shown is what code-reviewer's Auto-Detection Rules would pick) |
| Design | Deep | Coherence validation | After design complete, before Tasks | design-author (mandatory) |
| Tasks | Standard | Clarity check | After task slicing, before implementation | not implemented (task slicing happens inside agent-TDD's Design Spec Mode, not as an agent-isdd phase, and it requests no review at this point; see `INTEROP.md`'s "→ agent-tdd" section) |
| Implementation (per-slice, Red) | Quick | Test clarity | After test written, before implementation | not implemented (neither `test-author` nor agent-TDD requests a Red-stage review) |
| Implementation (per-slice, Green) | Standard or Deep | Implementation check | After slice passes tests | agent-tdd requests the level (Deep if high-risk); the caller runs the review |
| Implementation (post-slices coherence) | Deep (the caller may raise it to Ultra) | Cross-slice validation | After all slices complete | agent-tdd requests `Deep`; the caller may raise it to `Ultra` if most slices are high-risk |

**Review Level Definitions** (see `code-reviewer/skills/code-reviewer/SKILL.md` for full details;
no token budgets are asserted here, since that file states none):

- **Quick**: Minimal checks, fact-finding, test clarity
- **Standard**: Comprehensive checks, impact analysis (default)
- **Deep**: Thorough design validation, coherence checks
- **Ultra**: Comprehensive + security/regression/duplicates (multi-agent capable)

**How findings guide each phase**:

- **Requirements review findings** → update requirements doc, clarify scope before Design
- **Design review findings** → resolve design contradictions or document as task follow-ups
- **Tasks review findings** → not applicable today (no Tasks-phase review is run; see the Tasks row above)
- **Per-slice review findings** → guide implementation focus and refactoring priorities
- **Coherence review findings** → validate cross-slice interactions, regressions

See `INTEROP.md`'s "Strategic Review Placement via Review Levels" for the placement rationale and
`agent-tdd/agents/agent-TDD.md`'s Green and Review sections for implementation-phase details.
