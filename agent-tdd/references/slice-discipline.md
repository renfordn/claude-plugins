# Slice discipline (R7, R8, R9, R11)

Read by `agent-TDD` at the start of every slice, before writing the Red test. Entry schema: `references/evidence-log.md`. Commands below are `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/tdd_check.py"` (shown as `tdd_check.py`); add `--slice-id N --base <sha>` in parallel mode.

## 1. Gap discovery (R8), before Red

Skip it when the Pre-Slice Brief contains `<!--TEST-STRATEGY-REPORT-->`: test-strategist already did it. Still log `start`, using that report's counts.

Otherwise go risk by risk (each way this behavior could break), and for each ask whether an existing test would fail. Use test-strategist's definitions of "pinned", "inspected" and the mutation check (`agents/test-strategist.md`); do not restate them.

- Judge **assertions, not names**: open the test and read what it asserts. A test called `test_login` may assert nothing about the failure you fear.
- Keep **inspected** (read the assertions) separate from **run** (executed the test, or a mutant of the code under it).
- A finding you could not run is reported as **unverified**, never as covered.

Then open the slice (always, even with zero risks):

```
tdd_check.py start --slice "<title>" --kind feature --risks 3 --inspected 3 --run 2
```

`--kind` is one of `feature`, `fix`, `refactor`, `contract`, `validation`, `ui` (default `feature`).

## 2. First-run pass (R7): the new test passes on its first run

Never contrive a Red. Check the test really pins the behavior with `coverage --mutant`, run against a throwaway copy:

```
tdd_check.py coverage --slice "<title>" --mutant "<command that changes the behavior in a mktemp -d copy and runs the same test there>" -- pytest tests/test_x.py
```

- Confirmed (test passes, mutant fails): copy the `coverage` `TDD-EVIDENCE` line into **Validation Evidence**, report `<!--AGENT-TDD-OUTCOME: coverage-only-->` next to the phase marker, make **no production change**, and still stop at `green_pause` for the independent review (a test is in scope). A confirmed `coverage` also unlocks edits for a refactor slice's characterization test.
- Not confirmed (mutant survived or did not run): the test does not pin the behavior. Strengthen it and retry; do not report coverage.

## 3. Red-first guard (R9)

`hooks/red_first_guard.py` denies a Write/Edit while a slice is open in this worktree (after `start`, until `done` or the next `start`; a `start` older than 4h is ignored) and no unlock exists yet.

- **Unlocks:** a confirmed `red` logged after the latest `start`; a confirmed `coverage`; a logged `bypass`. An older Red never counts.
- **Always exempt:** test files, docs, and paths outside the repo; the exact rules are in the docstring of `hooks/path_kinds.py`. Key exceptions: plugin product markdown (`SKILL.md`, `CLAUDE.md`, `AGENTS.md`, any `.md` under `agents/`, `skills/`, `commands/`, `output-styles/`) is production, and non-doc files under `docs/` are production. Manifests, CI and config are production.
- **Bypass** only when Red cannot come first, and say why: `tdd_check.py bypass --slice "<title>" --reason "<why>"`. Valid reasons: contract stubs, scaffolding, test-author stub blockers (the Red test needs a stub to import), genuine blockers. Never to skip a Red you could write. Copy every `coverage` and `bypass` `TDD-EVIDENCE` line into **Validation Evidence**, the same as red/green; the SubagentStop hook surfaces the bypasses the report carries to the caller.
- Refactor/contract slices: run `coverage` on the characterization test before changing code, then refactor, then `green`; with `start --kind refactor|contract` a confirmed `coverage` stands in for Red (other kinds still need Red), only these kinds unlock the guard with coverage, and the report carries `<!--AGENT-TDD-OUTCOME: refactor-->`, else the stop hook flags the slice unproven.
- Close the slice at the end, and on every stop that ends it early (BLOCKED, Mid-Slice Research Request, MODEL-ESCALATE, Plan Validity Flag, any escalation pause): `tdd_check.py done --slice "<title>"` (add `--slice-id`/`--base` if `start` had them). The guard's deny text prints this command.

## 4. UI slices (R11)

1. Before Red, run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/e2e_harness.py" ui <planned files>` (the Slice Spec / tasks Files; exit 0 = a UI path). If the Slice Spec has `ui: true`, the slice is UI whatever this says. Not UI: nothing more to do.
2. UI: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/e2e_harness.py" harness` (exit 0 = found; JSON `{harness: {name, evidence}}`). A result with `name` `puppeteer` and evidence containing "library, not a test runner" is only a library: confirm with the repo before using it.
3. Harness found: the Red test is an E2E test in that harness.
4. No harness: add no tooling. Stop with `<!--AGENT-TDD-REPORT-->` and `<!--AGENT-TDD-BLOCKED: reason="no e2e harness: <what you searched>"-->` and **no** `AGENT-TDD-PHASE` marker (so no `green_pause`). The caller skips this slice and its dependents, runs independent slices, then asks the user: add a harness slice, accept without E2E as a recorded fallback, or pause.
