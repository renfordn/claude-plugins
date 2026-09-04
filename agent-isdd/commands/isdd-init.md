---
description: First-run onboarding — confirm how this project should use SDD, then scaffold
---

This is the guided first-contact command for the plugin: a short `AskUserQuestion` flow instead
of asking the user to read docs before their first feature.

1. Resolve `~/.claude/sdd-memory/<project-slug>/` via
   `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/sdd_memory.py" --path`, and check whether any
   `spec/<date-slug>/workflow-state.md` already exists under it, or whether it already has other
   entries. If either is true, this project is already onboarded — report its current state
   (delegate to `spec-driven-development`'s status path) instead of re-scaffolding, and stop.
2. Otherwise, briefly explain the workflow (Requirements → Design → Tasks, with a
   one-directional handoff to `agent-tdd` at the end) and confirm the user wants to start here —
   this plugin has no phase-gate toggle of its own to configure (it never edits source files;
   that discipline belongs to `agent-tdd`).
3. Scaffold nothing yet beyond what's needed to confirm the above — actual feature scaffolding
   happens on the first real `/isdd <feature>` call, via `workflow-manager`.
4. Confirm the statusline wiring is optional and point at the README's snippet rather than
   editing `~/.claude/settings.json` automatically — that file is outside this project and
   editing it without being asked is not this command's job.
5. Close with exactly one next step: run `/isdd <feature description>` to start the first
   feature.
