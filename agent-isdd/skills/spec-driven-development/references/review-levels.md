# Review Level Guidance per Phase

Each ISDD phase uses specific `/code-reviewer` review levels to validate artifacts at appropriate
depth. Review levels balance comprehensiveness with token efficiency and are tailored to each
phase's concerns.

| Phase | Review Level | Purpose | When | Invoked By |
|-------|--------------|---------|------|-----------|
| Requirements | Standard | Clarity check | After requirements draft, before approval | requirements-agent (optional) |
| Design | Deep | Coherence validation | After design complete, before Tasks | design-author (mandatory) |
| Tasks | Standard | Clarity check | After tasks.md generation, before implementation | task-slicer |
| Implementation (per-slice, Red) | Quick | Test clarity | After test written, before implementation | test-author (high-risk only) |
| Implementation (per-slice, Green) | Standard or Deep | Implementation check | After slice passes tests | agent-tdd (Deep if high-risk) |
| Implementation (post-slices coherence) | Deep or Ultra | Cross-slice validation | After all slices complete | agent-tdd (Ultra if majority high-risk) |

**Review Level Definitions** (see `code-reviewer/SKILL.md` for full details):

- **Quick**: Minimal checks, fact-finding, test clarity — < 50k tokens
- **Standard**: Comprehensive checks, impact analysis — 50-150k tokens (default)
- **Deep**: Thorough design validation, coherence checks — 150-300k tokens
- **Ultra**: Comprehensive + security/regression/duplicates — 300k+ tokens (multi-agent capable)

**How findings guide each phase**:

- **Requirements review findings** → update requirements doc, clarify scope before Design
- **Design review findings** → resolve design contradictions or document as task follow-ups
- **Tasks review findings** → inform ralph loops Dependency Correctness validation
- **Per-slice review findings** → guide implementation focus and refactoring priorities
- **Coherence review findings** → validate cross-slice interactions, regressions

See `design.md` §ISDD Workflow Integration for design rationale and `agent-tdd/SKILL.md`
§Review-Level Strategy for implementation-phase details.
