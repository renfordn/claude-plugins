# Migration Guide: Phase 2+3 (0.1.14)

This guide helps users migrate from agent-isdd 0.1.13 (tdd-planner) to 0.1.14+ (agent-tdd owns slicing).

## TL;DR

- **0.1.13:** tdd-planner exists in agent-isdd; workflow works as before
- **0.1.14:** tdd-planner removed; agent-tdd must handle task slicing
- **Timeline:** 1-week deprecation window to migrate agent-tdd before 0.1.14 drops tdd-planner

## What Changed

### Workflow Phases

**Before (0.1.13):**
```
Requirements → Design → Tasks → Implementation
(agent-isdd)              ↓
                    tdd-planner (agent-isdd)
                    per-slice Slice Spec
                         ↓
                    agent-tdd (implements)
```

**After (0.1.14+):**
```
Requirements → Design → Implementation
(agent-isdd)               ↓
                    research-consolidator (agent-isdd)
                    unified research pass
                    Design Spec (full specs)
                         ↓
                    agent-tdd (slicing + implements)
```

### Handoff Change

**Old Handoff: Slice Spec (per-task)**
```
agent-isdd → builds one Slice Spec from tasks.md
          → spawns agent-tdd for one slice
          → waits for implementation
          → repeats for next slice
```

**New Handoff: Design Spec (full at once)**
```
agent-isdd → builds one Design Spec (requirements + design + research cache + file summaries)
          → spawns agent-tdd ONCE
          → agent-tdd owns task slicing + all implementation
          → no return to agent-isdd (except escalations)
```

## Migration Steps

### For agent-tdd Users (Most Important)

**Step 1: Update agent-tdd (before 0.1.14 ships)**

Agent-tdd must implement three new phases before Red-Green-Refactor:

1. **Research Validation Phase**
   - Input: Design Spec (requirements.md, design.md, research/cache.md, file_summaries)
   - Validate research completeness
   - Optional: re-research gaps only
   - Escalate if design contradicts research

2. **Task Slicing Phase**
   - Input: Requirements + Design + validated research
   - Output: tasks.md (phased, TDD-sized slices)
   - Apply three Ralph Loops:
     - Slice Size Validation (≤ 3 files, testable)
     - Dependency Correctness (acyclic)
     - Research-to-Implementation Traceability (grounded)
   - Assign Risk Tiers

3. **Readiness Check**
   - Task Readiness Checklist
   - No blockers, all dependencies resolved
   - Ready to proceed to Red-Green-Refactor

**See `INTEROP.md` "Agent-tdd Implementation Requirements" for full specification.**

**Step 2: Test New Handoff**

Once agent-tdd is updated:
1. Run a test feature end-to-end with 0.1.13 agent-isdd (sends Design Spec)
2. Verify agent-tdd:
   - Validates research
   - Slices into TDD-sized phases
   - Produces tasks.md
   - Proceeds to implementation OR escalates appropriately
3. Verify escalation paths work (design contradicts research, research too thin)

**Step 3: Upgrade to 0.1.14**

Once agent-tdd is ready:
1. Upgrade agent-isdd to 0.1.14+
2. tdd-planner is no longer available
3. All new features use agent-tdd's slicing

### For agent-isdd Users (No Action Required)

If you're just using agent-isdd without touching tdd-planner internals:

1. In 0.1.13: workflow works as before, no changes
2. In 0.1.14: handoff changes, but from your perspective:
   - Approval flow: Requirements → Design (unchanged)
   - After Design approved: agent-tdd takes over (instead of tdd-planner)
   - You may see new escalation reasons (research validation, slicing blockers)
3. No workflow changes needed; just upgrade when agent-tdd is ready

## What's Better

### Token Efficiency

- **Research Consolidation:** One unified pass instead of two (design-author + tdd-planner)
  - Saves 15-25K tokens per feature
  
- **Research Caching:** design-author caches research in research/cache.md
  - Agent-tdd reuses cache; skips re-research unless invalid
  - Saves 15-25K tokens on resumed workflows

- **Cross-Feature Cache:** File summaries cached in agent-nelly
  - 70-80% cache hit rate on related features
  - Saves 15-25K tokens per reuse

- **Intent Hashing:** Drift detection via hash, not full brief re-fetch
  - Saves 5-10K tokens per resume

- **Total:** ~80-100K tokens saved (50-70% reduction per feature)

### Cleaner Architecture

- **Clear Responsibility:** agent-isdd owns WHAT, agent-tdd owns HOW
- **One Research Pass:** Dual output (design_findings + task_findings) eliminates redundancy
- **Graceful Escalations:** Design contradictions, research gaps handled between plugins
- **Ralph Loops:** Automated slicing validation catches errors early

## Troubleshooting

### Q: Will my existing tasks.md files break?

**A:** No. tasks.md format is unchanged. However:
- In 0.1.13: tdd-planner generates tasks.md
- In 0.1.14: agent-tdd generates tasks.md
- The output format is the same, but agent-tdd's slicing may differ

### Q: What if design contradicts research?

**A:** Agent-tdd will escalate back to agent-isdd with a specific reason:
- Agent-isdd pauses
- User re-enters and fixes the design contradiction
- Agent-isdd continues, re-hands off to agent-tdd

### Q: What if research is too thin?

**A:** Agent-tdd can do targeted re-research on gaps only:
- Doesn't re-research everything (saves tokens)
- Updates research/cache.md
- Continues to slicing

### Q: Can I rewind to Tasks phase?

**A:** No. In 0.1.14+, no Tasks phase for agent-isdd:
- Rewind only goes to Requirements or Design
- Task changes happen inside agent-tdd (via escalations)

## Testing Checklist

- [ ] agent-tdd built and installed locally
- [ ] agent-tdd can receive Design Spec handoff
- [ ] agent-tdd validates research successfully
- [ ] agent-tdd produces tasks.md
- [ ] agent-tdd slicing Ralph Loops work
- [ ] agent-tdd Risk Tier assignment works
- [ ] agent-tdd escalation paths work (back to agent-isdd)
- [ ] End-to-end feature workflow completes
- [ ] Cross-feature file cache (agent-nelly) hits are observed

## Questions or Issues?

See INTEROP.md for the full contract, CHANGELOG.md for detailed changes, and agent-tdd's own documentation for implementation details.
