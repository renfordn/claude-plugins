#!/usr/bin/env python3
"""Per-finding re-check loop (R14). Stdlib only.

After an implementer responds to one finding, re-check just that finding: snapshot it, brief a
fresh finding-verifier with the finding, the response diff and its direct tests, record the
pass, and stop on fixed conditions instead of looping on judgment.

  recheck.py start <id> [--findings PATH] [--base SHA] [--restart [--reason TEXT]]
  recheck.py run <id> [--findings PATH] [--diff-base SHA] [--paths P [P ...]]
  recheck.py status <id> [--findings PATH]

State lives in recheck.json beside findings.json (see references/recheck.md); every write of it
(and of the findings resolution) happens under an flock on recheck.json.lock. Stop conditions:
resolved (done) | needs-detailed-review (escalate) | new_evidence false (no new evidence) |
3 passes (pass limit) | missing/malformed report or verifier failure (blocked) | the finding id
no longer matches its snapshot (stale finding id). A stopped finding stays unresolved.
REVIEW_RECHECK_CMD overrides the verifier command (tests); it gets the brief as its last argument.
REVIEW_RECHECK_TIMEOUT (seconds, default 900) bounds a verifier run.
This is not a slice review: it never emits the code-reviewer or REVIEW-SCOPE markers.
"""

import argparse
import contextlib
try:
    import fcntl  # POSIX; unlocked without it (Windows)
except ImportError:  # pragma: no cover
    fcntl = None
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import review_plan  # noqa: E402

MARKER = "<!--FINDING-RECHECK-REPORT-->"
OUTCOMES = {"resolved", "still-open", "partially-resolved", "needs-detailed-review"}
MAX_PASSES = 3
ESCALATE = "escalate (blocker, earlier phase or approval boundary)"
MAX_DIFF_BYTES = 60000  # review_headless.sh takes the brief as one argv string
MAX_TESTS = 10
DEFAULT_TIMEOUT = 900
_TEST_RE = re.compile(r"(^|/)(tests?/|test_[^/]*$|[^/]*_test\.[^/]*$|[^/]*\.(test|spec)\.[^/]*$)")


def _toplevel():
    return (review_plan._git("rev-parse", "--show-toplevel") or "").strip() or None


def _git(*args):
    """git from the repo top level, so repo-relative finding paths work from any subdirectory."""
    return review_plan._git(*args, cwd=_toplevel()) or ""


def _repo_rel(p):
    """A user-given path (relative to the process cwd) as a repo-relative path."""
    top = _toplevel()
    return os.path.relpath(os.path.abspath(p), top) if top else p


def recheck_path(findings):
    return os.path.join(os.path.dirname(os.path.abspath(findings)), "recheck.json")


@contextlib.contextmanager
def _lock(path):
    """Exclusive lock for every read-modify-write of recheck.json (and the findings write)."""
    with open(path + ".lock", "w") as fh:
        if fcntl is not None:
            fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(fh, fcntl.LOCK_UN)


def _load(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path) as fh:
        return json.load(fh)


def _write_atomic(path, data):
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".recheck-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def parse_report(text, finding_id):
    """Return the report dict, or None if missing, malformed, or for another finding."""
    if MARKER not in text:
        return None
    tail = text.split(MARKER, 1)[1]
    blocks = re.findall(r"```json\s*\n(.*?)```", tail, re.S) or [tail.strip()]  # fenced, else bare
    for block in blocks:
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        if (isinstance(data, dict) and data.get("id") == finding_id and data.get("outcome") in OUTCOMES
                and isinstance(data.get("new_evidence"), bool)):
            return data
    return None


def real_passes(entry):
    """Passes only; restart markers sit in the same list but are not passes."""
    return [p for p in entry["passes"] if "outcome" in p]


def decide(report, pass_count):
    """Return (status, stop_reason) after a pass. report is None when blocked."""
    if report is None:
        return "stopped", "blocked"
    if report["outcome"] == "resolved":
        return "resolved", None
    if report["outcome"] == "needs-detailed-review":
        return "stopped", ESCALATE
    if not report["new_evidence"]:
        return "stopped", "no new evidence"
    if pass_count >= MAX_PASSES:
        return "stopped", "pass limit"
    return "open", None


def scope_material(entry, paths, base):
    """Diff (tracked changes + untracked files, limited to the response scope) and direct tests."""
    paths = [_repo_rel(p) for p in paths]
    top = _toplevel() or "."
    scope = [entry["finding"].get("file", "."), *paths]
    diff = _git("diff", base, "--", *scope)
    untracked = _git("ls-files", "--others", "--exclude-standard", "--", *scope).split()
    for u in untracked:
        try:
            with open(os.path.join(top, u), errors="replace") as fh:
                diff += f"\nUntracked file {u} (full content):\n{fh.read()}\n"
        except OSError:
            pass
    changed = _git("diff", "--name-only", base, "--", *scope).split() + untracked
    tests = [p for p in dict.fromkeys([*paths, *changed]) if _TEST_RE.search(p)]
    stem = os.path.splitext(os.path.basename(entry["finding"].get("file", "")))[0]
    if stem:
        tests += [p for p in _git("grep", "-l", "-w", "-F", stem).split() if _TEST_RE.search(p)]
    tests = list(dict.fromkeys(tests))[:MAX_TESTS]
    if len(diff.encode()) > MAX_DIFF_BYTES:
        diff = (diff.encode()[:MAX_DIFF_BYTES].decode(errors="ignore")
                + f"\n[diff truncated at {MAX_DIFF_BYTES} bytes]\n")
    return diff, tests


def make_brief(entry, diff, tests):
    f = entry["finding"]
    passes = real_passes(entry)
    return "\n".join([
        f"Mode: re-check. Re-check: {f['id']}",
        f"Pass {len(passes) + 1} of {MAX_PASSES}. Re-check scope: this finding, the response diff "
        "(limited to the finding's file and the paths the response touched) and the direct tests "
        "below. Add no new findings.",
        "",
        "Finding:", json.dumps(f, indent=2),
        "",
        "Prior passes:", json.dumps(passes, indent=2) if passes else "none",
        *[f"Previous evidence: pass {n}: {p['evidence']}" for n, p in enumerate(passes, 1)],
        "",
        "Direct tests: " + (", ".join(tests) or "none"),
        "",
        f"Response diff since {entry['base']}:", diff or "(no changes)",
    ])


def run_verifier(brief):
    """Return (stdout, error). error is set when the verifier could not run to completion."""
    cmd = os.environ.get("REVIEW_RECHECK_CMD")
    argv = shlex.split(cmd) if cmd else [os.path.join(_HERE, "review_headless.sh"), "--agent", "finding-verifier"]
    try:
        timeout = float(os.environ.get("REVIEW_RECHECK_TIMEOUT") or DEFAULT_TIMEOUT)
    except ValueError:
        timeout = DEFAULT_TIMEOUT
    try:
        r = subprocess.run([*argv, brief], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return "", f"verifier timed out after {timeout:g}s"
    except OSError as e:
        return "", f"verifier launch failed: {e}"
    return r.stdout, None


def _is_stale(snapshot, current):
    if current is None or current.get("file") != snapshot.get("file"):
        return True
    key = "summary" if "summary" in snapshot else "title"
    return current.get(key) != snapshot.get(key)


def _entry(findings, finding_id):
    state = _load(recheck_path(findings), {})
    if finding_id not in state:
        raise SystemExit(f"recheck: no re-check started for {finding_id}; run start first")
    return state[finding_id]


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def cmd_start(a):
    findings = a.findings or review_plan.findings_path()
    doc = _load(findings)
    if doc is None:
        raise SystemExit(f"recheck: {findings} not found")
    found = next((f for f in doc.get("findings", []) if f.get("id") == a.id), None)
    if found is None:
        raise SystemExit(f"recheck: finding {a.id} not in {findings}")
    path = recheck_path(findings)
    with _lock(path):
        state = _load(path, {})
        old = state.get(a.id)
        if old and a.restart:
            if old["status"] != "stopped":
                raise SystemExit(f"recheck: {a.id} is {old['status']}; only a stopped re-check can restart")
            if any("restart" in p for p in old["passes"]):
                raise SystemExit(f"recheck: {a.id} was already restarted once")
            old["passes"].append({"restart": _now(), "reason": a.reason})
            old["status"], old["stop_reason"] = "open", None
        elif old and old["status"] != "open":
            raise SystemExit(f"recheck: {a.id} is {old['status']}"
                             + (f" ({old['stop_reason']})" if old["stop_reason"] else "")
                             + "; use --restart to continue it")
        elif not old:
            base = a.base or _git("rev-parse", "HEAD").strip()
            if not base:
                raise SystemExit("recheck: could not resolve a base sha; pass --base")
            state[a.id] = {"finding": found, "base": base, "passes": [], "status": "open", "stop_reason": None}
        _write_atomic(path, state)
        print(json.dumps(state[a.id], indent=2))
    return 0


def cmd_run(a):
    findings = a.findings or review_plan.findings_path()
    path = recheck_path(findings)
    entry = _entry(findings, a.id)
    if entry["status"] != "open":
        raise SystemExit(f"recheck: {a.id} is {entry['status']}"
                         + (f" ({entry['stop_reason']})" if entry["stop_reason"] else "") + "; not re-running")
    diff, tests = scope_material(entry, a.paths or [], a.diff_base or entry["base"])
    out, err = run_verifier(make_brief(entry, diff, tests))
    report = None if err else parse_report(out, a.id)
    with _lock(path):  # reload after the verifier: other ids may have changed meanwhile
        state = _load(path, {})
        entry = state[a.id]
        entry["passes"].append({
            "outcome": report["outcome"] if report else "blocked",
            "evidence": report.get("evidence", "") if report else (err or "missing or malformed report"),
            "new_evidence": report["new_evidence"] if report else False,
            "at": _now(),
        })
        doc = _load(findings)
        current = next((f for f in doc.get("findings", []) if f.get("id") == a.id), None)
        if _is_stale(entry["finding"], current):
            entry["status"], entry["stop_reason"] = "stopped", "stale finding id"
        else:
            entry["status"], entry["stop_reason"] = decide(report, len(real_passes(entry)))
            if entry["status"] == "resolved":
                current["resolution"] = "resolved"
            elif current.get("resolution", "open") == "open":
                current["resolution"] = "open"  # a human declined/accepted decision is kept
            errs = review_plan.validate(doc)
            if errs:
                raise SystemExit("recheck: findings.json would be invalid: " + "; ".join(errs))
            _write_atomic(findings, doc)
        _write_atomic(path, state)
    print(json.dumps(entry, indent=2))
    return 0


def cmd_status(a):
    findings = a.findings or review_plan.findings_path()
    print(json.dumps(_entry(findings, a.id), indent=2))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("start", cmd_start), ("run", cmd_run), ("status", cmd_status)):
        p = sub.add_parser(name)
        p.add_argument("id")
        p.add_argument("--findings")
        if name == "start":
            p.add_argument("--base")
            p.add_argument("--restart", action="store_true")
            p.add_argument("--reason", default="restart")
        if name == "run":
            p.add_argument("--diff-base")
            p.add_argument("--paths", nargs="+")
        p.set_defaults(fn=fn)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
