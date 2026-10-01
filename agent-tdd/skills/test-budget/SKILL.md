---
name: test-budget
description: Check the test file a TDD slice is about to grow, before planning new tests. Flags bloated or stale test files, tests that should be merged into a parametrized/table-driven test, unit tests that duplicate behavior already covered at a higher level, and good candidates to promote to a regression or e2e test instead of another unit test. Use whenever planning tests for a slice, running /tdd or slice-spec on a long-running project, when CI or the test suite is getting slow, or when the user mentions test bloat, too many tests, slow pipeline, consolidating tests, pruning tests, or "should this be an e2e test". Use it even if the user only says "add tests for X" and the target test file is already large.
---

# Test budget: check the file before adding to it

TDD adds tests every slice and nothing ever removes them. On a long-running project the suite
grows until the pipeline is slow, and slow pipelines get skipped or ignored, which defeats the
reason for the tests. The cheapest moment to push back is when a new test is being planned,
because the target file is already open and the new behavior is fresh in mind. This skill is a
short pre-flight on that file; it never blocks the slice.

## When it runs

Before the Red test is written, after the Slice Spec's acceptance criteria are known. Skip it for
brand-new test files (nothing to bloat) and for hot-fix slices where speed matters more.

## Step 1: measure the target file

Run the bundled script on the test file(s) the slice would touch:

```bash
python3 <skill-dir>/scripts/test_audit.py <test-file-or-dir> [--junit report.xml]
```

It reports per file: test count, lines, setup/fixture count, clusters of near-duplicate test
names (consolidation candidates), git churn and last-modified age, and, if a JUnit XML report is
passed, the runtime share. Supports pytest/unittest, Jest/Vitest/Mocha, Go, and JUnit-style
names. Treat the numbers as signals to read the file, not verdicts. If the script can't parse
the framework, read the file directly and apply the same questions.

## Step 2: judge, using these questions

| Signal | What it suggests |
|---|---|
| Many tests, same arrange step, differing only in input/expected value | **Consolidate** into one parametrized / table-driven test |
| Tests asserting the same behavior through different layers | **Drop the lower one** if a higher-level test already pins it |
| Test pins an internal helper that has since been inlined, renamed, or deleted | **Stale**: delete or rewrite against public behavior |
| Test asserts implementation details (call counts, private state) | **Brittle**: rewrite to assert outcomes |
| File is large AND slow (top runtime share) AND mostly one-behavior-per-test | **Split or trim**, and check for avoidable I/O, sleeps, heavy fixtures |
| Behavior spans several components/services, or the failure that matters only shows up when wired together | **Regression/e2e candidate**: one e2e or integration test beats five mocked unit tests |
| Slice fixes a reported bug | **Regression test**: keep it, name it for the bug, put it in the project's existing regression location, if any |
| Fast, pure, one function, new edge case | **Plain unit test**: add it; no ceremony needed |

Two guardrails keep this from becoming over-pruning. Never delete a test just because it is
old; delete it because you can name the test that covers the same behavior better. And never
promote to e2e something that is cheap and deterministic as a unit test, since e2e tests are
the slowest and flakiest, so each one has to earn its place.

## Step 3: report in this shape

Keep it to a few lines so it fits inside the slice workflow:

```
Test budget: tests/test_orders.py — 84 tests, 1,240 lines, 31% of suite runtime
- Consolidate: test_total_with_{tax,discount,both,none} (4) → 1 parametrized
- Stale: test_legacy_price_helper (helper removed in a1b2c3d)
- Plan for this slice: add 1 case to the parametrized total test; no new file
- Regression/e2e candidate: checkout → payment → receipt flow (new slice spans 3 modules)
Verdict: ok to proceed | consolidate first | promote to e2e
```

Then act on the verdict:

- **ok to proceed**: continue to the Red test as planned.
- **consolidate first**: the caller runs this skill and gets the user's OK *before* spawning
  agent-TDD, then does the merge as its own step under green tests, outside agent-TDD's
  Red/Green/Refactor (a consolidation must leave the same behaviors asserted, so run the file
  before and after, and confirm the test count dropped but coverage of behaviors did not).
  Keep it in a separate commit from the slice.
- **promote to e2e**: write the e2e/integration test as the slice's acceptance test and keep
  only the unit tests that pin logic the e2e can't cheaply reach.

Surface deletions and merges to the user rather than silently removing tests; removing a test is
a decision about what the project stops protecting.

## Periodic sweep (optional)

When the user asks about overall suite health rather than one slice, run the script on the whole
test directory with a JUnit report, list the top files by runtime and by cluster count, and
propose a ranked consolidation backlog (biggest runtime saved per effort first).
