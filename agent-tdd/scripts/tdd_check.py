#!/usr/bin/env python3
"""Run a slice's test command and record Red/Green evidence. Stdlib only.

  tdd_check.py red   --slice "<slice title>" -- <test command...>
  tdd_check.py green --slice "<slice title>" -- <test command...>
  tdd_check.py red|green ... [--slice-id N] [--base <sha>]   (green needs a red with the same base)
  tdd_check.py integration --wave N --cmd "<suite command>"
  tdd_check.py verify <token>...          (used by hooks/tdd_subagent_stop.py)

`red` expects the command to FAIL (the new test exists and the behavior doesn't yet); `green`
expects it to PASS and requires an earlier failing `red` for the same slice. Each run appends one
line to <git common dir>/agent-tdd/evidence.jsonl and prints a token such as
`TDD-EVIDENCE red a1b2c3d4 exit=1 CONFIRMED`. Put those lines in the handoff report: the
SubagentStop hook looks the tokens up in the log, so the report shows whether Red and Green were
actually observed rather than asserted.

Exit status: 0 when the phase is confirmed, 1 when it isn't (red passed, green failed, or green
without a verified red), 2 on usage errors.
"""
import argparse
import datetime
import json
import os
import secrets
import subprocess
import sys

TAIL = 1500


try:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))
    from tdd_state import git_common_dir
except ImportError:  # standalone use without the hooks dir; mirrors tdd_state.git_common_dir
    def git_common_dir(cwd):
        env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_WORK_TREE")}
        for flags in (["--path-format=absolute", "--git-common-dir"], ["--git-common-dir"]):
            try:
                r = subprocess.run(["git", "rev-parse", *flags], cwd=cwd, capture_output=True,
                                   text=True, timeout=5, env=env)
            except (OSError, subprocess.SubprocessError):
                continue
            lines = r.stdout.strip().splitlines()
            if r.returncode != 0 or len(lines) != 1 or not lines[0]:
                continue
            p = os.path.normpath(os.path.join(os.path.abspath(cwd), lines[0]))
            if len(flags) == 2 and not os.path.isabs(lines[0]):
                continue
            if os.path.isdir(p):
                return p
        return None


def evidence_path(cwd="."):
    # The common git dir is shared by every linked worktree.
    common = git_common_dir(cwd)
    if common:
        return os.path.join(common, "agent-tdd", "evidence.jsonl")
    return None


def read_log(cwd="."):
    path = evidence_path(cwd)
    if not path or not os.path.isfile(path):
        return []
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def _append(entry, cwd="."):
    path = evidence_path(cwd)
    if not path:
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    return True


def _worktree(cwd="."):
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=cwd, capture_output=True, text=True)
    return os.path.realpath(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None


def _record(entry, cwd):
    """Stamp, append and return (token, recorded) for one evidence entry."""
    entry["token"] = secrets.token_hex(4)
    entry["at"] = datetime.datetime.now().isoformat(timespec="seconds")
    wt = _worktree(cwd)
    if wt:
        entry["worktree"] = wt
    return entry["token"], _append(entry, cwd)


def _line(phase, token, code, confirmed, note, recorded):
    status = "CONFIRMED" if confirmed else f"NOT CONFIRMED ({note})"
    line = f"TDD-EVIDENCE {phase} {token} exit={code} {status}"
    return line if recorded else line + " [unrecorded: not a git repo]"


def run_phase(phase, slice_title, cmd, cwd=".", slice_id=None, base=None):
    """Run cmd, record it, and return (confirmed, token_line, output)."""
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, shell=len(cmd) == 1)
    output = (r.stdout + r.stderr)[-TAIL:]
    failed = r.returncode != 0
    wt = _worktree(cwd)

    def matches(e):
        if e.get("slice") != slice_title or e.get("phase") != "red" or not e.get("confirmed"):
            return False
        if base is not None:
            return e.get("base") == base
        return e.get("worktree") is None or e.get("worktree") == wt

    prior_red = [e for e in read_log(cwd) if matches(e)]
    if phase == "red":
        confirmed, note = failed, "" if failed else "test passed before implementation"
    else:
        confirmed = not failed and bool(prior_red)
        no_red = "no confirmed red with this base" if base is not None else "no verified red for this slice"
        note = "" if confirmed else ("tests still fail" if failed else no_red)
    entry = {"phase": phase, "slice": slice_title, "cmd": " ".join(cmd), "exit": r.returncode,
             "confirmed": confirmed, "note": note}
    if slice_id is not None:
        entry["slice_id"] = slice_id
    if base is not None:
        entry["base"] = base
    token, recorded = _record(entry, cwd)
    return confirmed, _line(phase, token, r.returncode, confirmed, note, recorded), output


def run_integration(wave, cmd_str, cwd="."):
    """Run the wave's integration suite, record it, and return (passed, token_line, output)."""
    r = subprocess.run(cmd_str, cwd=cwd, capture_output=True, text=True, shell=True)
    output = (r.stdout + r.stderr)[-TAIL:]
    passed = r.returncode == 0
    note = "" if passed else "integration suite failed"
    token, recorded = _record({"phase": "integration", "wave": wave, "cmd": cmd_str, "exit": r.returncode,
                               "confirmed": passed, "note": note}, cwd)
    return passed, _line("integration", token, r.returncode, passed, note, recorded), output


def verify(tokens, cwd="."):
    """Map each token to its logged entry (or None if it was never recorded)."""
    by_token = {e.get("token"): e for e in read_log(cwd)}
    return {t: by_token.get(t) for t in tokens}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = []
    if "--" in argv:
        i = argv.index("--")
        argv, cmd = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="phase", required=True)
    for name in ("red", "green"):
        p = sub.add_parser(name)
        p.add_argument("--slice", required=True)
        p.add_argument("--slice-id")
        p.add_argument("--base")
    ig = sub.add_parser("integration")
    ig.add_argument("--wave", type=int, required=True)
    ig.add_argument("--cmd", dest="suite_cmd", required=True)
    v = sub.add_parser("verify")
    v.add_argument("tokens", nargs="+")
    a = ap.parse_args(argv)

    if a.phase == "verify":
        print(json.dumps(verify(a.tokens), indent=2))
        return 0
    if a.phase == "integration":
        ok, line, output = run_integration(a.wave, a.suite_cmd)
        print(output.rstrip())
        print(line)
        return 0 if ok else 1
    if a.slice_id is not None:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks"))
        from markers import SLICE_TITLE_RE
        m = SLICE_TITLE_RE.match(a.slice)
        if not m or m.group(1).lower() != a.slice_id.lower():
            ap.error(f"--slice-id {a.slice_id} does not match slice title {a.slice!r}")
        a.slice_id = m.group(1)
    if not cmd:
        ap.error("give the test command after --")
    confirmed, line, output = run_phase(a.phase, a.slice, cmd, slice_id=a.slice_id, base=a.base)
    print(output.rstrip())
    print(line)
    return 0 if confirmed else 1


if __name__ == "__main__":
    sys.exit(main())
