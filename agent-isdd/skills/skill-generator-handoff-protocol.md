# Skill-Generator Handoff Protocol

## Overview

The skill-generator has been split into two complementary skills to improve token efficiency and enable plan reusability:

1. **`plan-skill-generator`** — Fast discovery, outputs JSON plan
2. **`run-skill-generator-execute`** — Execution phase, accepts optional plan

This document explains how they work together and when to use each.

## Architecture

```
User Request
    ↓
[plan-skill-generator]
    ├─ Analyzes project structure
    ├─ Detects technologies, build system, launch method
    └─ Outputs: project-plan.json (3-5k tokens)
    ↓
[Plan Review by User/Agent]
    ├─ Optional: Modify plan if needed
    └─ Approve to proceed
    ↓
[run-skill-generator-execute --plan project-plan.json]
    ├─ Skips discovery (uses provided plan)
    ├─ Builds, launches, and drives the app
    ├─ Generates SKILL.md + driver
    └─ Outputs: .claude/skills/run-<name>/ (8-13k tokens)
    ↓
[run-<name> skill created and ready to use]
```

## Plan Format

The plan is a JSON document following `plan-skill-generator/references/plan_schema.json`:

```json
{
  "unit_path": ".",
  "unit_type": "web-app",
  "detected_technologies": ["react", "vite", "node"],
  "build_system": "npm",
  "test_framework": "vitest",
  "launch_method": "dev-server",
  "device_type": "headless",
  "key_findings": ["Uses Vite for build", "Dev server on port 5173"],
  "potential_issues": ["Requires npm install"],
  "recommended_driver_pattern": "playwright",
  "confidence_level": 0.95,
  "discovery_metadata": { /* ... */ }
}
```

## Usage Scenarios

### Scenario 1: Quick Skill Generation (Normal Path)

User wants to create a run skill for a project:

```bash
# Step 1: Discover
claude plan-skill-generator
# Output: project-plan.json in current directory

# Step 2: Execute (plan is auto-detected)
claude run-skill-generator-execute --plan project-plan.json
# Output: .claude/skills/run-<project>/SKILL.md + driver
```

**Token cost:** 3-5k (plan) + 8-13k (execute) = 11-18k total

### Scenario 2: Standalone Execution (Backward Compatible)

User wants the old all-in-one experience:

```bash
claude run-skill-generator-execute
```

The execute skill runs discovery internally (no plan needed). Works exactly like the monolithic version.

**Token cost:** 12-20k (discovery + execution combined)

### Scenario 3: Iterative Development

User is developing a skill and wants to try multiple drivers/approaches with the same plan:

```bash
# Step 1: Plan once
claude plan-skill-generator > plan.json

# Step 2: Try approach A
claude run-skill-generator-execute --plan plan.json --output-dir trial-1/

# Step 3: Try approach B (reuses same plan)
claude run-skill-generator-execute --plan plan.json --output-dir trial-2/

# Step 4: Compare and pick the better one
```

**Token savings:** 50-60% vs. rediscovering each time

### Scenario 4: Plan Review Before Execution

User wants to review discovery findings before committing to full execution:

```bash
# Generate plan
claude plan-skill-generator

# Human/agent reviews project-plan.json
# Can manually edit confidence_level, add custom_notes, fix detected_technologies

# Then execute with confidence
claude run-skill-generator-execute --plan project-plan.json
```

**Benefit:** Avoids wasted execution effort if plan is obviously wrong.

### Scenario 5: Sharing Plans Across Teams

A team member discovers how to run a complex project, commits the plan:

```bash
git add projects/billing/discovery-plan.json
git commit -m "docs: add discovery plan for billing project"

# Other team members can reuse it:
cd projects/billing
claude run-skill-generator-execute --plan discovery-plan.json
```

## API / Integration

### plan-skill-generator

**Input:**
```
<directory> — project to analyze
[--output <file>] — where to write plan.json (default: stdout + ./project-plan.json)
```

**Output:**
```json
// Written to <output> file
{
  "unit_path": ".",
  "unit_type": "web-app",
  // ... (see plan_schema.json)
}
```

**Exit codes:**
- 0 = Success
- 1 = Could not determine project type (confidence very low)
- 2 = Ambiguous monorepo (user clarification needed)

### run-skill-generator-execute

**Input:**
```
<directory> — project to build skill for (default: current dir)
[--plan <file>] — optional pre-computed plan (skips discovery)
[--output-dir <path>] — where to write .claude/skills/ (default: <directory>/.claude/skills/)
[--no-verify] — skip end-to-end test (faster, riskier)
[--show-all-attempts] — include all failed attempts in Troubleshooting
```

**Output:**
```
<output-dir>/run-<project-name>/
  ├─ SKILL.md
  ├─ driver.mjs (or .sh, depending on project type)
  ├─ references/ (optional supporting docs)
  └─ logs/ (build/launch logs)
```

**Exit codes:**
- 0 = Success, skill generated
- 1 = Build failed
- 2 = Launch failed
- 3 = Verification failed (driver doesn't work)
- 4 = SKILL.md generation failed (shouldn't happen)

## Confidence Levels

The plan includes a `confidence_level` (0.0–1.0) reflecting discovery certainty:

| Level | Meaning | What to do |
|-------|---------|-----------|
| 0.95–1.0 | Very confident | Proceed directly to execute |
| 0.80–0.94 | Confident, minor ambiguity | Review key_findings; usually safe to execute |
| 0.60–0.79 | Moderate, some ambiguity | Review and possibly edit plan before executing |
| 0.40–0.59 | Low confidence | Edit plan manually; double-check unit_type and build_system |
| <0.40 | Very low | Likely need to investigate manually; plan may not be useful |

## Modification Guidelines

Users/agents can edit `project-plan.json` before passing to execute:

**Safe to change:**
- `custom_notes` — add context
- `key_findings` — add observations
- `potential_issues` — add known gotchas
- `confidence_level` — adjust if user has domain knowledge

**Risky to change (but possible):**
- `unit_type` — if plan got this wrong, fix it
- `build_system` — if multiple exist, pick the primary one
- `launch_method` — if docs contradict the plan

**Do NOT change:**
- `detected_technologies` — this is used to pick driver templates
- `device_type` — switching from headless to GUI (or vice versa) changes entire approach
- `recommended_driver_pattern` — if you change this, the execute skill may pick the wrong driver

## Backward Compatibility

**Old workflow (monolithic skill-generator):**
```
claude /run-skill-generator
```

**New workflow (split, recommended):**
```
claude /plan-skill-generator
claude /run-skill-generator-execute --plan project-plan.json
```

**New workflow (backward-compatible):**
```
claude /run-skill-generator-execute  # still works, does discovery internally
```

The `run-skill-generator-execute` skill is backward compatible — it works standalone without a plan, just less efficiently.

## Performance Comparison

| Workflow | Token Cost | Use Case |
|----------|-----------|----------|
| `plan` + `execute --plan` | 11-18k | Recommended default |
| `execute` alone (no plan) | 12-20k | One-off, backward compatible |
| `execute` + iterative (5 attempts with same plan) | 3-5k (plan) + 5×(8-13k) = 43-68k vs. 60-100k | Iterative development, 30-40% savings |

## Common Patterns

### Pattern 1: Team Onboarding

```bash
# One person creates the plan
cd project-x
claude plan-skill-generator
git add project-x/discovery-plan.json
git commit -m "docs: add discovery plan"

# Team members use it to build skills
claude run-skill-generator-execute --plan discovery-plan.json
```

### Pattern 2: Monitoring Discovery Quality

```bash
# Generate multiple plans from different branches/versions
for branch in main develop feature-x; do
  git checkout $branch
  claude plan-skill-generator --output plan-$branch.json
done

# Compare findings
diff plan-main.json plan-develop.json
```

### Pattern 3: Skill Validation

```bash
# Build skill with current plan
claude run-skill-generator-execute --plan known-good-plan.json

# Later: regenerate plan to verify project structure hasn't changed
claude plan-skill-generator > new-plan.json

# Compare
diff known-good-plan.json new-plan.json

# If similar, skill is likely still valid
```

## Migration from Monolithic Version

If you were using the old monolithic `/run-skill-generator`:

1. **No action needed** — it still works (backward compatible)
2. **To adopt the new split workflow**, simply start with `plan-skill-generator`:
   ```bash
   claude plan-skill-generator
   claude run-skill-generator-execute --plan project-plan.json
   ```
3. **Token efficiency improves** for iterative work or team onboarding

## Troubleshooting

### Plan confidence is too low

**Symptom:** `confidence_level < 0.7` after running plan-skill-generator

**Causes:**
- Monorepo with ambiguous structure
- Non-standard build system
- Sparse project documentation

**Solutions:**
1. Manually review `key_findings` and `potential_issues`
2. Edit the JSON to correct `unit_type` or `build_system` if needed
3. Proceed with execute (it will validate during build)
4. If execute fails, you'll have more specific errors to debug

### Execute fails even with a good plan

**Causes:**
- Plan was correct, but environment differs (missing OS package, network access, etc.)
- Project has hidden dependencies not detected in plan

**Solutions:**
1. Check execute's error logs in `logs/` directory
2. Fix the issue (install package, set env var, etc.)
3. Re-run execute — it will use the same plan and skip re-discovery
4. Update `potential_issues` in the plan for next time

### Plan and execute give different results

This shouldn't happen, but if it does:

1. Check if project files changed between plan and execute
2. Regenerate plan: `claude plan-skill-generator`
3. Compare old and new plans with `diff`
4. Use the newer plan with execute

---

## Design Rationale

### Why Split?

1. **Token efficiency** — Discovery is ~30% of total cost, now reusable
2. **User agency** — Agents/humans can review the plan before execution commits resources
3. **Composability** — Other skills/tools can consume the plan format
4. **Offline usage** — Plans can be serialized, version-controlled, shipped
5. **Faster iteration** — Same plan can fuel multiple execution attempts

### Why Keep Backward Compatibility?

- Existing workflows don't break
- Users can adopt gradually (no forced migration)
- Simple one-off use cases remain simple

### Plan Format Choice (JSON)

- Human-readable, easy to edit
- Structured, parseable by other tools
- Version-controllable (works with git diff)
- No dependency on custom serialization

---

**Last updated:** 2026-08-22  
Generated by Claude Code for the agent-isdd project.
