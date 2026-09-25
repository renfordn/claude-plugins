#!/usr/bin/env python3
"""Deterministic review planning for code-reviewer. Stdlib only.

  review_plan.py plan [--base REF] [--diff-file PATH] [--group-lines N]
      Parse the diff and print a JSON plan: per-file kind/churn/risk, changed and removed
      symbols, candidate tests, test gaps, and review groups for fan-out on large diffs.
      Diff source: --diff-file, else `git diff <base>...HEAD` (base defaults to the merge-base
      with origin/main or main), else the working tree against HEAD.
  review_plan.py findings-path [--state-dir DIR]
      Print where findings.json goes: DIR/findings.json, else <git-dir>/code-review/findings.json.
  review_plan.py validate FILE
      Check a findings.json against the schema in SKILL.md ("findings.json"). Exit 1 on errors.
"""

import argparse
import json
import math
import os
import re
import subprocess
import sys

LARGE_LINES = 400
LARGE_FILES = 10
GROUP_LINES = 300

_DEF_RES = [
    re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\("),              # python
    re.compile(r"^\s*class\s+([A-Za-z_]\w*)"),                              # python/js/ts/java
    re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)\s*\("),
    re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\("),
    re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)\s*\("),         # go
    re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?fn\s+([A-Za-z_]\w*)"),  # rust
]
_TEST_RE = re.compile(r"(^|/)(tests?|__tests__|spec)/|(^|/)test_[^/]+$|_test\.\w+$|\.(test|spec)\.\w+$")
_DOC_RE = re.compile(r"\.(md|rst|txt|adoc)$|(^|/)(docs?|CHANGELOG|LICENSE)", re.I)
_GEN_RE = re.compile(r"(^|/)(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|poetry\.lock|Cargo\.lock|go\.sum)$"
                     r"|\.min\.(js|css)$|(^|/)(dist|build|vendor|node_modules)/|_pb2\.py$|\.generated\.")
_CONFIG_RE = re.compile(r"\.(json|ya?ml|toml|ini|cfg|env)$|(^|/)(Dockerfile|Makefile)$")
_MIGRATION_RE = re.compile(r"(^|/)migrations?/|\.sql$")
_HOT_RE = re.compile(r"auth|login|session|token|secret|crypt|password|permission|payment|billing|price|"
                     r"sql|query|db|migration|api|security|upload|exec|shell", re.I)


def _git(*args, cwd=None):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def default_base():
    for ref in ("origin/main", "main", "origin/master", "master"):
        mb = _git("merge-base", ref, "HEAD")
        if mb and mb.strip() != (_git("rev-parse", "HEAD") or "").strip():
            return ref
    return None


def read_diff(base=None, diff_file=None):
    if diff_file:
        with open(diff_file, encoding="utf-8", errors="replace") as fh:
            return fh.read(), f"file:{diff_file}"
    base = base or default_base()
    if base:
        out = _git("diff", "--no-color", "--no-ext-diff", f"{base}...HEAD")
        if out:
            return out, f"{base}...HEAD"
    return _git("diff", "--no-color", "--no-ext-diff", "HEAD") or "", "working-tree"


def _def_name(line):
    for rx in _DEF_RES:
        m = rx.match(line)
        if m:
            return m.group(1)
    return None


def parse_diff(text):
    """Return {path: {"added": [...], "removed": [...], "touched": {symbols}, "status": str}}.

    `touched` holds every definition whose body a +/- line falls inside: the nearest preceding
    def line in the hunk (context or changed), else the hunk header's function context.
    """
    files, cur, in_hunk, enclosing = {}, None, False, None
    for line in text.splitlines():
        if line.startswith("diff --git "):
            m = re.match(r"diff --git a/(.+?) b/(.+)$", line)
            cur, in_hunk = {"added": [], "removed": [], "touched": set(), "status": "modified"}, False
            files[m.group(2) if m else line] = cur
        elif cur is None:
            continue
        elif line.startswith("@@"):
            in_hunk = True
            header = line.split("@@", 2)[-1] if line.count("@@") >= 2 else ""
            enclosing = _def_name(header.strip()) if header.strip() else None
        elif not in_hunk:
            if line.startswith("new file mode"):
                cur["status"] = "added"
            elif line.startswith("deleted file mode"):
                cur["status"] = "deleted"
        else:
            body = line[1:]
            name = _def_name(body)
            if name:
                enclosing = name
            if line.startswith("+"):
                cur["added"].append(body)
            elif line.startswith("-"):
                cur["removed"].append(body)
            else:
                continue
            if name:
                cur["touched"].add(name)
            elif enclosing and body.strip():
                cur["touched"].add(enclosing)
    return files


def classify(path):
    if _GEN_RE.search(path):
        return "generated"
    if _TEST_RE.search(path):
        return "test"
    if _DOC_RE.search(path):
        return "docs"
    if _MIGRATION_RE.search(path):
        return "migration"
    if _CONFIG_RE.search(path):
        return "config"
    return "source"


def symbol_defs(lines):
    out = {}
    for line in lines:
        for rx in _DEF_RES:
            m = rx.match(line)
            if m:
                out.setdefault(m.group(1), line.strip())
                break
    return out


def risk_score(path, kind, churn):
    base = {"source": 3, "migration": 3, "config": 2, "test": 1, "docs": 0, "generated": 0}[kind]
    hot = 2 if kind not in ("docs", "generated") and _HOT_RE.search(path) else 0
    return base + hot + round(math.log2(churn + 1), 1)


def repo_files(root="."):
    listed = _git("ls-files", cwd=root)
    if listed:
        return listed.splitlines()
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "node_modules"]
        for f in filenames:
            found.append(os.path.relpath(os.path.join(dirpath, f), root))
    return found


def candidate_tests(path, all_files):
    stem = os.path.splitext(os.path.basename(path))[0]
    if len(stem) < 3:
        return []
    return sorted(f for f in all_files if _TEST_RE.search(f) and stem in os.path.basename(f) and f != path)


def make_groups(files, group_lines):
    """Greedy-pack reviewable files into groups of ~group_lines changed lines, keeping each
    directory's files together and the riskiest directories first."""
    by_dir = {}
    for f in files:
        by_dir.setdefault(os.path.dirname(f["path"]), []).append(f)
    dirs = sorted(by_dir.values(), key=lambda fs: -max(f["risk"] for f in fs))
    groups, cur, size = [], [], 0
    for fs in dirs:
        for f in sorted(fs, key=lambda f: -f["risk"]):
            churn = f["added"] + f["removed"]
            if cur and size + churn > group_lines:
                groups.append(cur)
                cur, size = [], 0
            cur.append(f["path"])
            size += churn
    if cur:
        groups.append(cur)
    return groups


def build_plan(diff_text, source, group_lines=GROUP_LINES, root="."):
    parsed = parse_diff(diff_text)
    all_files = repo_files(root)
    changed_tests = {p for p in parsed if classify(p) == "test"}
    added_defs, removed_defs, files, skipped = {}, {}, [], []
    for path, d in parsed.items():
        kind = classify(path)
        churn = len(d["added"]) + len(d["removed"])
        adds, rems = symbol_defs(d["added"]), symbol_defs(d["removed"])
        for name, sig in adds.items():
            added_defs.setdefault(name, []).append((path, sig))
        for name, sig in rems.items():
            removed_defs.setdefault(name, []).append((path, sig))
        entry = {"path": path, "status": d["status"], "kind": kind, "added": len(d["added"]),
                 "removed": len(d["removed"]), "risk": risk_score(path, kind, churn),
                 "symbols": sorted(set(adds) | set(rems) | d["touched"])}
        if kind in ("docs", "generated"):
            skipped.append(path)
            continue
        if kind in ("source", "migration"):
            tests = candidate_tests(path, all_files)
            entry["candidate_tests"] = tests
            entry["tests_changed"] = sorted(t for t in tests if t in changed_tests)
        files.append(entry)

    changed_signatures, removed_symbols, new_symbols = [], [], []
    for name, rems in removed_defs.items():
        if name in added_defs:
            old, new = rems[0][1], added_defs[name][0][1]
            if old != new:
                changed_signatures.append({"symbol": name, "file": added_defs[name][0][0],
                                           "old": old, "new": new})
        else:
            removed_symbols.append({"symbol": name, "file": rems[0][0], "old": rems[0][1]})
    for name, adds in added_defs.items():
        if name not in removed_defs and classify(adds[0][0]) != "test":
            new_symbols.append({"symbol": name, "file": adds[0][0]})

    files.sort(key=lambda f: -f["risk"])
    reviewable_lines = sum(f["added"] + f["removed"] for f in files)
    large = reviewable_lines > LARGE_LINES or len(files) > LARGE_FILES
    test_gaps = [f["path"] for f in files
                 if f["kind"] == "source" and f["symbols"] and not f.get("tests_changed")]
    return {
        "source": source,
        "totals": {"files": len(files), "changed_lines": reviewable_lines, "skipped": len(skipped)},
        "large": large,
        "files": files,
        "skipped": sorted(skipped),
        "changed_signatures": sorted(changed_signatures, key=lambda s: s["symbol"]),
        "removed_symbols": sorted(removed_symbols, key=lambda s: s["symbol"]),
        "new_symbols": sorted(new_symbols, key=lambda s: s["symbol"]),
        "test_gaps": test_gaps,
        "groups": make_groups(files, group_lines) if large else [[f["path"] for f in files]],
    }


def findings_path(state_dir=None):
    if state_dir:
        return os.path.join(state_dir, "findings.json")
    git_dir = (_git("rev-parse", "--absolute-git-dir") or "").strip()
    if not git_dir:
        raise SystemExit("findings-path: not in a git repo and no --state-dir given")
    return os.path.join(git_dir, "code-review", "findings.json")


_ENUMS = {
    "severity": {"critical", "high", "medium", "low", "nit"},
    "decision": {"accept", "flag", "block", "defer"},
    "category": {"correctness", "security", "test-coverage", "style", "architecture",
                 "performance", "documentation"},
    "workflow_action": {"proceed", "pause_for_review", "block_commit", "require_test", "log_only"},
    "confidence": {"high", "medium", "low"},
    "evidence_tier": {"tier-1", "tier-2", "tier-3", "tier-4", "tier-5"},
}
_FOLLOWUP_KINDS = {"refactor", "consolidation", "deferred-defect"}


def validate(doc):
    errs = []
    if not isinstance(doc, dict):
        return ["top level must be an object"]
    for key in ("scope", "level", "findings", "followups"):
        if key not in doc:
            errs.append(f"missing top-level key '{key}'")
    for i, f in enumerate(doc.get("findings") or []):
        for key in ("id", "file", "summary", "failure_scenario", *_ENUMS):
            if key not in f:
                errs.append(f"findings[{i}]: missing '{key}'")
        for key, allowed in _ENUMS.items():
            if key in f and f[key] not in allowed:
                errs.append(f"findings[{i}].{key}: {f[key]!r} not in {sorted(allowed)}")
        if "verdict" in f and f["verdict"] not in ("CONFIRMED", "PLAUSIBLE"):
            errs.append(f"findings[{i}].verdict: {f['verdict']!r}")
    for i, u in enumerate(doc.get("followups") or []):
        for key in ("kind", "title", "files", "why", "steps"):
            if key not in u:
                errs.append(f"followups[{i}]: missing '{key}'")
        if u.get("kind") not in _FOLLOWUP_KINDS:
            errs.append(f"followups[{i}].kind: {u.get('kind')!r} not in {sorted(_FOLLOWUP_KINDS)}")
    return errs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--base")
    p.add_argument("--diff-file")
    p.add_argument("--group-lines", type=int, default=GROUP_LINES)
    f = sub.add_parser("findings-path")
    f.add_argument("--state-dir")
    v = sub.add_parser("validate")
    v.add_argument("file")
    a = ap.parse_args(argv)

    if a.cmd == "plan":
        text, source = read_diff(a.base, a.diff_file)
        print(json.dumps(build_plan(text, source, a.group_lines), indent=2))
    elif a.cmd == "findings-path":
        print(findings_path(a.state_dir))
    else:
        with open(a.file, encoding="utf-8") as fh:
            errs = validate(json.load(fh))
        for e in errs:
            print(e, file=sys.stderr)
        if errs:
            return 1
        print("findings.json OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
