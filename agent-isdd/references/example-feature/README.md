# Example Feature

This folder contains a filled end-to-end specimen for the SDD workflow.

Use it as a reference for:
- expected artifact quality
- phase progression
- checklist completion
- workflow-state transitions
- recap tone and density

Example features:
- title: Session Timeout Warning Banner
- slug: `2026-07-01-session-timeout-warning-banner`
- pattern: new feature planning through ready-for-implementation tasks

- title: Profile State Schema Migration
- slug: `2026-07-01-profile-state-schema-migration`
- pattern: migration planning with compatibility and rollout concerns

- title: Duplicate Toast On Retry
- slug: `2026-07-01-duplicate-toast-on-retry`
- pattern: bugfix planning with unclear reproduction details tightened into regression-focused tasks

Structure:

```text
example-feature/
  2026-07-01-session-timeout-warning-banner/
    workflow-state.md
    requirements/
      requirements.md
    design/
      design.md
    tasks/
      tasks.md
    recap/
      recap.md
  2026-07-01-profile-state-schema-migration/
    workflow-state.md
    requirements/
      requirements.md
    design/
      design.md
    tasks/
      tasks.md
    recap/
      recap.md
  2026-07-01-duplicate-toast-on-retry/
    workflow-state.md
    requirements/
      requirements.md
    design/
      design.md
    tasks/
      tasks.md
    recap/
      recap.md
```

Paused-state reference:

```text
paused-states/
  missing-repro-details/
    workflow-state.md
    requirements.md
    recap.md
```
