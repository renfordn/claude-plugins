"""Slice 33: plan-reviewer-tier1 runs on sonnet/medium after eval 4 passed.

Eval 4 (evals/evals.json, tier1-sonnet-vs-opus), 2026-11-19, 3 runs per model via the Agent
`model` override: sonnet caught 9/9 planted claims every run (mean 9.0, 0 false positives);
opus 9, 8, 9 (mean 8.67, 0 false positives). PASS: sonnet mean >= opus mean, no planted claim
missed by sonnet in every run.
"""
import os
import re

AGENT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "agents", "plan-reviewer-tier1.md")


def _fm():
    return open(AGENT, encoding="utf-8").read().split("---", 2)[1]


def test_tier1_is_sonnet_medium():
    fm = _fm()
    assert re.search(r"^model:\s*sonnet\s*$", fm, re.M)
    assert re.search(r"^effort:\s*medium\s*$", fm, re.M)
