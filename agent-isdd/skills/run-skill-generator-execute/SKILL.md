---
name: run-skill-generator-execute
description: Build and launch a project to create a reusable run skill. Generates SKILL.md and a driver (driver.mjs, .sh, etc.) that lets agents start the app, interact with it, and take screenshots. Takes an optional discovery plan from plan-skill-generator for 50% faster execution. Use when you've figured out how to run a project and want to package that knowledge as a skill, or when you want to drive an app directly to verify it works.
---

# Run Skill Generator — Execute Phase

**Purpose:** Build the driver and SKILL.md for a project using either discovery findings or an optional pre-generated plan.

This is the execution phase of skill generation. It:
1. **Discovers** how to run the project (or accepts a pre-computed plan)
2. **Builds** and launches the app to interact with it
3. **Generates** SKILL.md + driver code (chromium-cli for web, tmux-wrapped REPL for desktop, etc.)
4. **Verifies** the skill works with a test interaction

## Quick Start (Standalone)

```bash
cd /path/to/project
claude run-skill-generator-execute
```

Generates `.claude/skills/run-<project-name>/SKILL.md` and a driver.

## Fast Path: Use a Pre-Computed Plan

If you've already run `plan-skill-generator`:

```bash
claude run-skill-generator-execute --plan project-plan.json
```

This **skips discovery** and goes straight to building, saving ~50% of tokens.

## What Gets Built

### SKILL.md
A reference guide for agents that explains:
- What the project is and how it's driven
- Prerequisites (OS packages, runtimes)
- Build steps (exact commands that worked)
- Run instructions — agent path first (the driver), then human path
- Gotchas and troubleshooting discovered during execution
- The driver location and usage

### Driver
Depends on project type:

| Type | Driver | Location |
|------|--------|----------|
| Web (React, Vue, etc.) | `chromium-cli` script (inline in SKILL.md) | Heredoc in SKILL.md |
| Desktop (Electron) | Playwright REPL under tmux | `.claude/skills/run-<name>/driver.mjs` |
| CLI tool | Shell smoke script | `.claude/skills/run-<name>/driver.sh` |
| Server/API | `curl`-based health check + smoke script | `.claude/skills/run-<name>/driver.sh` |
| Library | Import-and-call Node/Python script | `.claude/skills/run-<name>/driver.mjs` |

## Workflow

### 1. Discovery (Skipped if --plan provided)

If no plan is given, the skill discovers:
- Unit boundaries (mono-repo vs. single)
- Build system (npm, cargo, python, etc.)
- Launch method (dev server, binary, import, etc.)
- Device type (headless, GUI, TUI)

**Token cost:** ~3-5k (discovery only)

### 2. Build & Launch

Installs dependencies, builds the project, launches the app, and records any errors.

**Token cost:** ~2-3k

### 3. Harness Development

Writes code to drive the app. For web apps, this is a `chromium-cli` script. For desktop/TUI, it's a tmux-wrapped REPL with commands like `launch`, `ss` (screenshot), `click`, `eval`.

**Token cost:** ~3-5k

### 4. Interaction & Verification

Runs one real user flow end-to-end (e.g., click a button, fill a form, observe result) to prove the harness works.

**Token cost:** ~2-3k (execution only)

### 5. Generate SKILL.md

Documents everything discovered, built, and tested.

**Token cost:** ~1-2k

**Total (without plan):** 12-20k tokens  
**Total (with plan):** 8-13k tokens  
**Savings with plan:** 40-50%

## Output Location

Skills are created at:
```
<unit>/.claude/skills/run-<unit-name>/
  SKILL.md         ← Agent instructions + driver heredoc (or reference to driver file)
  driver.mjs       ← (or driver.sh, etc.) optional driver script
  references/      ← Optional supporting docs
```

## Prerequisites

You must provide:
- **Project directory** — can be a fresh clone
- **A way to run the project** — documented in README or discoverable from config files
- **Base OS packages** — the skill will install what's needed (apt-get, brew, etc.)

## Options

```
--plan <file>              Pre-computed discovery plan (JSON from plan-skill-generator)
--output-dir <path>        Where to write the skill (default: ./.claude/skills/)
--no-verify                Skip the end-to-end interaction test (faster, but riskier)
--show-all-attempts        Include all failed attempts in Troubleshooting section (verbose)
```

## Edge Cases

**Monorepo:** If the project has multiple apps, the skill asks which one to create a skill for. (Or pass `--unit-path apps/billing` to skip the question.)

**Missing README:** If docs are sparse, the skill relies on file-scanning heuristics and may have low confidence. Review the generated SKILL.md carefully.

**Requires authentication:** If the app needs API keys or credentials, the skill documents the gate and how to patch it locally. (It does not store credentials.)

**Platform-specific:** If the README says "macOS only," the skill tries anyway on Linux. Success varies — native modules may fail, but the core app often works with `--disable-gpu` or `--no-sandbox` flags.

## Troubleshooting

**"Build failed"**
- Check the `Build` section of the generated SKILL.md. The exact command that failed is listed.
- Common fixes: `apt-get install <missing-lib>`, update Node/Python, check for private npm packages.

**"Launch timed out"**
- The app is hanging on startup. Check `.claude/skills/run-<name>/logs/launch.log` for the stack trace.
- Try adding `--disable-gpu`, `--no-sandbox`, or other flags documented in the Gotchas section.

**"Driver commands don't work"**
- The driver assumes a specific app state (e.g., "button is visible"). If the app structure changed, re-run the skill to regenerate the driver.
- For web apps, check that the port matches the dev server port (Gotchas section).

**"Skill works locally but fails in container"**
- Likely missing OS packages (libc, X11 libs for GUI). See the Prerequisites section and run the exact `apt-get` lines.

---

## Comparison: With Plan vs. Without

| Phase | Without Plan | With Plan | Savings |
|-------|--------------|-----------|---------|
| Discovery | ~3-5k tokens | Skipped | 3-5k |
| Build | ~2-3k tokens | ~2-3k tokens | None |
| Harness | ~3-5k tokens | ~3-5k tokens | None |
| Verification | ~2-3k tokens | ~2-3k tokens | None |
| SKILL.md | ~1-2k tokens | ~1-2k tokens | None |
| **Total** | **12-20k** | **8-13k** | **40-50%** |

## Next Steps After Generation

1. **Review the SKILL.md** — Read it as if you were an agent using it. Does it make sense? Are all the gotchas captured?
2. **Commit to your repo** — `git add .claude/skills/run-<name>/ && git commit -m "feat: add run-<name> skill"`
3. **Share with your team** — Agents and humans in your repo can now use `/run-<name>` to launch the project

---

_Generated by [Claude Code](https://claude.ai/code)_
