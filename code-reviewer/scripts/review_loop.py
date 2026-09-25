#!/usr/bin/env python3
"""Sweep-until-dry review driver: repeated independent reviewer passes, merged. Stdlib only.

One read of a large diff misses a different defect each time, and the model won't reliably run
extra passes when a skill merely asks, so this script owns the loop:

  1. Build the plan (review_plan.py) and brief a fresh read-only reviewer
     (review_headless.sh --agent code-reviewer) with the scope and plan facts.
  2. Brief the next fresh reviewer with the findings so far; it reports only new ones.
  3. Stop when a pass adds nothing new, or after --max-passes. Print the merged result as JSON.

  review_loop.py [--base REF] [--diff-file PATH] [--level Standard] [--max-passes 3]
                 [--out-dir DIR] [--brief TEXT]

A finding is "new" unless an earlier one has the same file and a line within 3 of it.
REVIEW_LOOP_CMD overrides the reviewer command (tests); it gets the brief as its last argument.
"""

import argparse
import json
import os
import re
import shlex
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import review_plan  # noqa: E402

MARKER = "<!--CODE-REVIEWER-REPORT-->"
LINE_SLACK = 3


def plan_facts(plan):
    def names(key):
        return ", ".join(f"{s['symbol']} ({s['file']})" for s in plan[key]) or "none"
    return "\n".join([
        f"Diff: {plan['source']} — {plan['totals']['files']} files, "
        f"{plan['totals']['changed_lines']} changed lines (docs/lockfiles excluded).",
        "Files, riskiest first: " + ", ".join(f["path"] for f in plan["files"]),
        "Changed signatures: " + names("changed_signatures"),
        "Removed symbols: " + names("removed_symbols"),
        "New symbols: " + names("new_symbols"),
        "Test gaps (changed functions whose tests didn't change): " + (", ".join(plan["test_gaps"]) or "none"),
    ])


def make_brief(scope, level, facts, prior, pass_no, extra):
    parts = [f"Mode: direct-review. review_level: {level}. Scope: {scope}.", "", facts]
    if extra:
        parts += ["", extra]
    if prior:
        listed = "\n".join(f"- {f['file']}:{f.get('line', '?')} — {f.get('short_summary') or f['summary']}"
                           for f in prior)
        parts += ["", f"This is sweep {pass_no}. Earlier independent passes already reported:", listed, "",
                  "Report ONLY defects not in that list. Go file by file through every changed hunk, "
                  "especially the ones that look mechanical. An empty findings array is the right "
                  "answer if you find nothing new."]
    return "\n".join(parts)


def parse_report(text):
    """Return the findings list from a code-reviewer report, or None if there's no payload."""
    tail = text.split(MARKER, 1)[1] if MARKER in text else text
    for block in re.findall(r"```json\s*\n(.*?)```", tail, re.S):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and isinstance(data.get("findings"), list):
            return data["findings"]
    return None


def is_new(finding, known):
    for k in known:
        if k.get("file") == finding.get("file"):
            a, b = k.get("line"), finding.get("line")
            if a is None or b is None or abs(int(a) - int(b)) <= LINE_SLACK:
                return False
    return True


def run_reviewer(brief):
    cmd = os.environ.get("REVIEW_LOOP_CMD")
    argv = shlex.split(cmd) if cmd else [os.path.join(_HERE, "review_headless.sh"), "--agent", "code-reviewer"]
    r = subprocess.run([*argv, brief], capture_output=True, text=True)
    return r.returncode, r.stdout + (("\n" + r.stderr) if r.returncode else "")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base")
    ap.add_argument("--diff-file")
    ap.add_argument("--level", default="Standard")
    ap.add_argument("--max-passes", type=int, default=3)
    ap.add_argument("--out-dir")
    ap.add_argument("--brief", default="", help="extra context for every pass (acceptance criteria, etc.)")
    a = ap.parse_args(argv)

    diff, source = review_plan.read_diff(a.base, a.diff_file)
    plan = review_plan.build_plan(diff, source)
    scope = f"the diff {source}" + (f" (saved in {a.diff_file})" if a.diff_file else "")
    facts = plan_facts(plan)
    if a.out_dir:
        os.makedirs(a.out_dir, exist_ok=True)

    merged, passes = [], []
    for n in range(1, a.max_passes + 1):
        code, out = run_reviewer(make_brief(scope, a.level, facts, merged, n, a.brief))
        if a.out_dir:
            with open(os.path.join(a.out_dir, f"pass-{n}.md"), "w") as fh:
                fh.write(out)
        found = parse_report(out)
        if found is None:
            passes.append({"pass": n, "error": f"no findings payload (exit {code})"})
            break
        new = [f for f in found if is_new(f, merged)]
        merged += new
        passes.append({"pass": n, "reported": len(found), "new": len(new)})
        if not new:
            break

    result = {"scope": source, "level": a.level, "passes": passes, "findings": merged}
    print(json.dumps(result, indent=2))
    return 0 if merged or all("error" not in p for p in passes) else 1


if __name__ == "__main__":
    sys.exit(main())
