<!-- TDD-SKIP -->
# Code Reviewer

A standalone code review skill for Claude Code — evidence-tiered findings, a required decision
model, combined-findings anti-blur rules, and a single-clarifying-question resume contract,
independent of any other plugin.

It was extracted from `spec-driven-development`'s internal `code-reviewer` skill, the same way
`agent-nelly` was extracted from SDD's memory system and `agent-tdd` was extracted from SDD's
implementation agents. SDD is its first consumer, not its only one.

## Why this is a skill, not an agent

Unlike `agent-tdd`'s `agent-TDD`/`test-author` (Task-tool subagents run in isolated context),
`code-reviewer` is invoked as a plain skill in the main thread. That's deliberate: it needs to
call `ReportFindings` and open a review-dashboard `Artifact` in the *same turn* it runs in, and
those are host-native tools a subagent can't reliably reach the way the calling skill can.

The one exception is reviewing code an agent just wrote. There, the judging runs in a fresh
context — the `agents/code-reviewer.md` agent, or `scripts/review_headless.sh` when spawning
fails — that applies this skill's rules and hands the payload back; the main thread still does
the rendering. See INTEROP.md's "Independent review (reviewer ≠ author)".

## Using it with `agent-tdd`

`agent-tdd`'s `agent-TDD` agent always pauses after Green for a mandatory caller-driven review
(see [`agent-tdd`'s INTEROP.md](../agent-tdd/INTEROP.md)). This plugin is a natural fit for that
pause — run an independent review in `review-improve` mode, scoped to the files `agent-TDD`
named, then resume `agent-TDD` with the outcome. Neither plugin hard-depends on the other; you can use `agent-tdd`
with a different reviewer, or use this skill with a different (or no) TDD implementer.

## Research briefs: explaining code, not reviewing it

The separate `code-brief` skill (`skills/code-brief/SKILL.md`) explains how existing code works
— a visual Artifact (structure/timeline diagrams plus a narrative walkthrough) for a person, not
findings for an implementation agent to act on. It keeps evidence-tier grounding (claims still
need tier-1..5 backing) but has no Decision Model, no `ReportFindings` call, and writes nothing
to review state — there's no commit to gate.

Trigger it with `/code-reviewer:code-brief <file, feature, or subsystem>`, or just ask Claude to
explain or diagram how something works. The Artifact gets a real design pass — the skill's
"Design bar" loads `frontend-design` and grounds the diagram idiom, palette, and type in the
subsystem being explained, rather than reusing one generic diagram template across every brief.

## Review state is opt-in

This skill has no memory location of its own. Pass it a review-state directory if you want
per-file state and history persisted across passes (see `references/REVIEW-STATE.md.template`
and `references/REVIEW-HISTORY.md.template`); omit it and the skill stays ephemeral for a single
pass, applying the same evidence-tier and decision rules without writing anywhere.

## Quickstart

```bash
claude plugin marketplace add renfordn/claude-plugins
claude plugin install code-reviewer@renfordn-plugins
```

Verify it loaded:

```bash
claude --print "Use the code-reviewer skill to list its four evidence tiers."
```

Expected: a brief description naming tier-1 through tier-5 evidence tiers. (Claude Code's
own built-in `/code-review` command is a separate thing — this plugin is the
`code-reviewer:code-reviewer` skill, invoked by name or by asking for a code review.) See
[docs/install-and-verify.md](../docs/install-and-verify.md) in this repo for the full
multi-plugin install/verify guide.

## Evals: does the review actually catch bugs?

`evals/` is a `claude plugin eval` suite. Each case plants one known bug in a small fixture
(off-by-one, unchecked `None`, SQL injection at `Ultra`) and grades whether the review reports
it at the right line; `clean-no-false-positive` checks a correct file doesn't get a blocking
finding. The `trigger-*` cases ask casually ("any bugs in this?") and check the skill
actually loads. Run it from the repo root after changing the skill's review rules:

```bash
claude plugin eval ./code-reviewer --trust-plugin
```

By default each case runs 3 times, with and without the plugin, so the report shows what the
skill adds over plain Claude. Add `--ablation none --runs 1` for a cheap check. It costs tokens,
so CI only checks the suite's structure (`tests/test_evals_structure.py`).

## Using Code Reviewer from another plugin

See [`INTEROP.md`](INTEROP.md) for the full integration contract if you're building a different
plugin and want to call this skill.
# code-reviewer
