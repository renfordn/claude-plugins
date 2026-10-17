# Scaffolding (folded from the former artifact-scaffolder skill)

Read by `workflow-manager` on `start` and whenever it scaffolds, creates or updates a feature's folder (the `--spec-path` resolution line stays in SKILL.md; verbatim from SKILL.md).

On `start`, create the per-feature structure; on later phases, update files in place:

```text
<sdd-memory-dir>/
  spec/
    <YYYY-MM-DD-feature-slug>/
      workflow-state.md
      workflow-state.json
      requirements/requirements.md
      design/design.md
      tasks/tasks.md       # Track: Standard only -- never written for Track: Fast
      recap/recap.md
```

Rules: one feature folder per feature, named with local start date plus slug; use the exact
template bodies from `${CLAUDE_PLUGIN_ROOT}/references/artifact-templates.md` (search for
`references/artifact-templates.md` if that path does not resolve) and
`${CLAUDE_PLUGIN_ROOT}/references/workflow-state.template.json`; preserve section order so later
agents can rely on stable parsing; `workflow-state.json` is scaffolded together with
`workflow-state.md` every time the latter is created or updated (field schema in
`${CLAUDE_PLUGIN_ROOT}/references/workflow-state.template.json`).
The `tasks/` folder itself can still be created up front alongside the others (cheap, keeps
scaffolding uniform); only `tasks.md` inside it is conditional on `Track`.
