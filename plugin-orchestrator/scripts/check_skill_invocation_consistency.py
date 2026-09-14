#!/usr/bin/env python3
"""Smoke check: skill invocation claims stay consistent across the repo.

This is not a general-purpose linter — it encodes two specific, previously-
violated rules found during manual doc review of this plugin repo:

1. A subagent (anything under a plugin's agents/*.md) must never be told to
   directly "invoke a skill" — subagents run in an isolated context and
   cannot call the Skill tool themselves (see code-reviewer/SKILL.md's "Use
   This Skill When" section, and agent-isdd/skills/spec-driven-development
   /SKILL.md's Automatic Code-Reviewer Invocation section, both of which
   state this explicitly). Only an orchestrating skill in the main thread
   may invoke another skill.

2. A caller must not describe invoking `code-reviewer` as a subprocess/CLI
   call or a Task-tool subagent spawn — code-reviewer/SKILL.md is explicit
   that it is invoked as a plain Skill-tool call, never a subagent.

Exit code is non-zero (and violations are printed) if either rule is
violated anywhere in the repo. Run from anywhere; paths are resolved
relative to this script's repo root.
"""
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Phrases that indicate a subagent doc is telling itself/another subagent to
# invoke a skill directly, rather than delegating that to its orchestrator.
SUBAGENT_SKILL_INVOKE_PATTERNS = [
    re.compile(r"\binvoke[s]?\s+(?:the\s+)?[\w-]+\s+skill\b", re.IGNORECASE),
    re.compile(r"\bcall[s]?\s+the\s+Skill\s+tool\b", re.IGNORECASE),
]

# Phrases allowed nearby that make the above a *documented constraint*
# rather than an actual instruction to do the forbidden thing.
ALLOWED_CONTEXT_MARKERS = [
    "cannot", "never", "isolated context", "not from its own", "does not",
    "must never", "no subagent",
]

# Phrases indicating code-reviewer being described as a subprocess/CLI/
# subagent invocation, contradicting code-reviewer/SKILL.md.
CODE_REVIEWER_SUBPROCESS_PATTERNS = [
    re.compile(r"runs?\s+`?/code-reviewer`?\s+(as\s+a\s+)?subprocess", re.IGNORECASE),
    re.compile(r"subprocess\.[A-Za-z]+.*code-reviewer", re.IGNORECASE),
    re.compile(r"code-reviewer.*Task-tool subagent", re.IGNORECASE),
]


def find_agent_md_files():
    return sorted(REPO_ROOT.glob("*/agents/**/*.md"))


def find_skill_md_files():
    return sorted(REPO_ROOT.glob("*/skills/**/SKILL.md")) + sorted(
        REPO_ROOT.glob("*/skills/**/*.md")
    )


def check_subagent_skill_invocation(files):
    violations = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SUBAGENT_SKILL_INVOKE_PATTERNS:
            for match in pattern.finditer(text):
                start = max(0, match.start() - 200)
                end = min(len(text), match.end() + 200)
                window = text[start:end].lower()
                if any(marker in window for marker in ALLOWED_CONTEXT_MARKERS):
                    continue
                line_no = text.count("\n", 0, match.start()) + 1
                violations.append(
                    f"{path.relative_to(REPO_ROOT)}:{line_no}: subagent doc appears to "
                    f"instruct direct skill invocation: {match.group(0)!r}"
                )
    return violations


def check_code_reviewer_invocation_model(files):
    violations = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in CODE_REVIEWER_SUBPROCESS_PATTERNS:
            for match in pattern.finditer(text):
                line_no = text.count("\n", 0, match.start()) + 1
                violations.append(
                    f"{path.relative_to(REPO_ROOT)}:{line_no}: describes code-reviewer as "
                    f"subprocess/Task-tool invocation, contradicting code-reviewer/SKILL.md: "
                    f"{match.group(0)!r}"
                )
    return violations


def main():
    agent_files = find_agent_md_files()
    skill_files = find_skill_md_files()
    all_files = agent_files + skill_files

    violations = []
    violations += check_subagent_skill_invocation(agent_files)
    violations += check_code_reviewer_invocation_model(all_files)

    if violations:
        print(f"FAIL: {len(violations)} skill-invocation consistency violation(s):\n")
        for v in violations:
            print(f"  - {v}")
        return 1

    print(
        f"PASS: no skill-invocation consistency violations "
        f"({len(agent_files)} agent docs, {len(skill_files)} skill docs checked)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
