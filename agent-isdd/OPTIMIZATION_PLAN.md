# Skill-Generator Token Optimization: Option 2 Implementation

## Overview
Split the monolithic skill-generator into two focused skills with structured handoff to reduce token usage and enable plan reusability.

## Architecture

### Skill 1: `plan-skill-generator`
**Purpose:** Discovery phase only  
**Input:** Directory path  
**Output:** JSON plan document  
**Token Cost:** ~3-5k tokens (vs ~8-12k in current monolithic approach)  

```json
{
  "unit_path": ".",
  "unit_type": "web-app" | "cli" | "library" | "desktop" | "server",
  "detected_technologies": ["react", "vite", "node"],
  "build_system": "npm",
  "test_framework": "vitest",
  "launch_method": "dev-server",
  "device_type": "headless",
  "key_findings": [
    "web app using react + vite",
    "runs on port 5173",
    "has chromium-cli integration"
  ],
  "potential_issues": [
    "requires npm install",
    "build step needed before launch"
  ],
  "recommended_driver_pattern": "playwright",
  "confidence_level": 0.95,
  "discovery_metadata": {
    "files_scanned": 12,
    "patterns_matched": 8,
    "discovery_time_ms": 2340
  }
}
```

### Skill 2: `run-skill-generator-execute`
**Purpose:** Execution phase given discovery findings  
**Input:** 
- Directory path
- Optional: Plan JSON from plan-skill-generator
**Output:** 
- SKILL.md
- driver.mjs (or other)
- Logs

**Token Cost:** ~5-8k tokens when given a plan (vs ~15-20k without reuse)

## Benefits

1. **Token efficiency:** Plan is discovered once, executed multiple times = 50-60% reduction for iterative work
2. **User visibility:** Agent can show plan for approval before execution commits time
3. **Error recovery:** Failed execution doesn't require re-discovery
4. **Offline capability:** Plan can be serialized, version-controlled, shared
5. **Composability:** Other skills/plugins can use the plan format

## Implementation Steps

1. ✅ Create plan-skill-generator/SKILL.md
2. ✅ Create run-skill-generator-execute/SKILL.md  
3. ✅ Create plan_schema.json (documented format)
4. ✅ Create helper scripts
5. ⬜ Test on sample repos
6. ⬜ Measure token savings
7. ⬜ Document handoff protocol

## Backward Compatibility

run-skill-generator-execute works standalone (no plan required) for existing workflows, but **strongly prefers** being given a plan for efficiency.

## Files to Create

```
./skills/
├── plan-skill-generator/
│   ├── SKILL.md
│   ├── discovery.mjs        (shared discovery logic)
│   └── references/
│       └── plan_schema.json
├── run-skill-generator-execute/
│   ├── SKILL.md
│   ├── executor.mjs         (execution logic, accepts plan)
│   └── references/
│       ├── driver-templates/
│       └── patterns.json
└── skill-generator-common/  (optional: shared utilities)
    └── plan-format.md
```
