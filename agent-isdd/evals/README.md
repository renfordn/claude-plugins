# agent-isdd evals

`evals.json` follows the skill-creator schema (`skill_name`, `evals[]` with `id`, `name`, `prompt`,
`expected_output`, `files`, `assertions`). The schema is checked by `tests/test_evals_schema.py`.

| id | name | pins down |
|----|------|-----------|
| 1 | low-risk-compact | doc tweak gets `Risk: low` + `Risk Reason`; also Track: Fast, Slice Spec, review skipped |
| 2 | tiny-auth-high-risk | small auth change is `Risk: high` (non-size reason), full path, every-slice review stated |
| 3 | user-led-coaching | mode `user` written after AskUserQuestion, isdd-coach routing, no production edits |
| 4 | tier1-sonnet-vs-opus | 9 planted false claims; sonnet must match opus. Slice 33 gates on it |

Each skill-creator run is a single prompt, so assertions cover only what is observable in the first
response and its tool calls (no assertion needs a Complete transition).

## Running with vs. without the skill

1. Baseline snapshot (there is no release tag): `git worktree add <dir> 6949c4b^`.
2. The baseline plugin lives at `<dir>/agent-isdd`. Load it with
   `claude --plugin-dir <dir>/agent-isdd` and disable the account `agent-isdd@inline` copy for
   those runs so the two do not mix.
3. With-skill runs: the same way, `claude --plugin-dir <current-checkout>/agent-isdd`, account
   copy disabled.
4. Run each prompt in a fresh session and grade the output against that eval's `assertions`.

Be honest about what discriminates: the baseline already has Track: Fast, Slice Spec and review
skip, so eval 1 discriminates on `Risk: low` + `Risk Reason`; those are its primary assertions.
Evals 2 and 3 should pass only with the skill (Risk: high with a non-size reason; AskUserQuestion
then `Implementation Mode: user` and isdd-coach routing).

## Eval 4 (tier1 model comparison)

Not a with/without comparison. The model switch is the Agent tool `model` override (`sonnet` vs
`opus`) on `agent-isdd:plan-reviewer-tier1`, with effort left at the frontmatter value. Never edit
the synced agent file.

Run at least 3 times per model, count planted claims (PLANTED-1..9) caught and false positives per
run, and compare mean caught counts. PASS = sonnet mean >= opus mean, with no planted claim missed
by sonnet in every run. Only a PASS lets slice 33 change the tier1 agent's model.
