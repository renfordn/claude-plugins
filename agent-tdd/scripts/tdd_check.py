#!/usr/bin/env python3
"""Run a slice's test command and record Red/Green evidence. Stdlib only.

  tdd_check.py red   --slice "<slice title>" -- <test command...>
  tdd_check.py green --slice "<slice title>" -- <test command...>
  tdd_check.py red|green ... [--slice-id N] [--base <sha>]   (green needs a red with the same base)
  tdd_check.py start    --slice T [--slice-id N --base B] [--kind K] [--risks n --inspected n --run n]
  tdd_check.py coverage --slice T [...] --mutant "<shell cmd>" -- <test command...>
  tdd_check.py bypass   --slice T [...] --reason "<why>"
  tdd_check.py done     [--slice T]
  tdd_check.py integration --wave N --cmd "<suite command>"
  tdd_check.py verify <token>...          (used by hooks/tdd_subagent_stop.py)

`red` expects the command to FAIL (the new test exists and the behavior doesn't yet); `green`
expects it to PASS and requires an earlier failing `red` for the same slice. Each run appends one
line to <git common dir>/agent-tdd/evidence.jsonl and prints a token such as
`TDD-EVIDENCE red a1b2c3d4 exit=1 CONFIRMED`. Put those lines in the handoff report: the
SubagentStop hook looks the tokens up in the log, so the report shows whether Red and Green were
actually observed rather than asserted.

`start` opens a slice in this worktree (until `done` or another `start`; stale after 4h). While one
is open, `green` needs a confirmed `red` logged after it; with none open the legacy rule applies and
a `red` only warns on stderr. `coverage` (for tests that already pass) is confirmed when the test
exits 0 and the `--mutant` shell command runs and fails (exit > 0, not 126/127 not-runnable or 4/5
pytest usage/no-tests; a signal exit is "mutant did not run"). `start`, `bypass` and `done` always
confirm and print no `exit=`.

Exit status: 0 when the phase is confirmed, 1 when it isn't (red passed, green failed, green
without a verified red, or coverage whose test failed or whose mutant survived/did not run), 2 on usage errors.
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


def _parse_line(raw):
    """One evidence-log line (str or bytes) as a dict, or None if blank, corrupt or not an object."""
    try:
        obj = json.loads(raw)
    except ValueError:  # includes UnicodeDecodeError and JSONDecodeError
        return None
    return obj if isinstance(obj, dict) else None


def read_log(cwd="."):
    path = evidence_path(cwd)
    if not path or not os.path.isfile(path):
        return []
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            obj = _parse_line(line)
            if obj is not None:
                out.append(obj)
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
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_WORK_TREE")}
    try:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=cwd, capture_output=True,
                           text=True, timeout=5, env=env)
    except (OSError, subprocess.SubprocessError):
        return None
    return os.path.realpath(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None


MUTANT_NOT_RUN = (126, 127, 4, 5)  # not runnable / pytest usage error / no tests collected
STALE_AFTER = datetime.timedelta(hours=4)


def _open_index(entries, worktree, now=None):
    """Index in `entries` of the open start for `worktree`, or None (append order; 4h staleness)."""
    now = now or datetime.datetime.now()
    idx = None
    for i, e in enumerate(entries):
        if worktree is None or e.get("worktree") != worktree:
            continue
        if e.get("phase") == "start":
            idx = i
        elif e.get("phase") == "done":
            idx = None
    if idx is None:
        return None
    try:
        at = datetime.datetime.fromisoformat(entries[idx].get("at"))
        return idx if now - at <= STALE_AFTER else None
    except (ValueError, TypeError):  # missing, garbage or offset-aware `at`: treat as closed
        return None


def open_slice(entries, worktree, now=None):
    """The open `start` entry for this worktree (latest start not followed by done/start, <4h old), or None."""
    i = _open_index(entries, worktree, now)
    return None if i is None else entries[i]


def unlocked(entries, worktree, now=None):
    """True if a confirmed red, confirmed coverage or bypass follows the open start in this worktree."""
    i = _open_index(entries, worktree, now)
    if i is None:
        return False
    for e in entries[i + 1:]:
        if e.get("worktree") != worktree:
            continue
        if e.get("phase") == "bypass" or (e.get("phase") in ("red", "coverage") and e.get("confirmed")):
            return True
    return False


def _record(entry, cwd, wt=None):
    """Stamp, append and return (token, recorded) for one evidence entry."""
    entry["token"] = secrets.token_hex(4)
    entry["at"] = datetime.datetime.now().isoformat(timespec="seconds")
    wt = wt or _worktree(cwd)
    if wt:
        entry["worktree"] = wt
    return entry["token"], _append(entry, cwd)


def _line(phase, token, code, confirmed, note, recorded):
    try:  # lazy: serial paths that only call verify() never import markers
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))
        from markers import format_evidence_line
        line = format_evidence_line(phase, token, code, confirmed, note)
    except ImportError:
        status = "CONFIRMED" if confirmed else f"NOT CONFIRMED ({note})"
        exit_part = "" if code is None else f" exit={code}"
        line = f"TDD-EVIDENCE {phase} {token}{exit_part} {status}"
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

    log = read_log(cwd)
    oi = _open_index(log, wt)
    if oi is not None:
        # Fresh-Red rule: the red must be appended after the open start, in this worktree.
        prior_red = [e for e in log[oi + 1:] if matches(e) and e.get("worktree") == wt]
    else:
        prior_red = [e for e in log if matches(e)]
    if phase == "red" and oi is None:
        print("warning: red logged with no open slice (no `tdd_check.py start`); not enforced", file=sys.stderr)
    if phase == "red":
        confirmed, note = failed, "" if failed else "test passed before implementation"
    else:
        confirmed = not failed and bool(prior_red)
        no_red = ("no confirmed red since slice start" if oi is not None else
                  "no confirmed red with this base" if base is not None else "no verified red for this slice")
        note = "" if confirmed else ("tests still fail" if failed else no_red)
    entry = {"phase": phase, "slice": slice_title, "cmd": " ".join(cmd), "exit": r.returncode,
             "confirmed": confirmed, "note": note}
    if slice_id is not None:
        entry["slice_id"] = slice_id
    if base is not None:
        entry["base"] = base
    token, recorded = _record(entry, cwd, wt)
    return confirmed, _line(phase, token, r.returncode, confirmed, note, recorded), output


def _ids(entry, slice_id, base):
    if slice_id is not None:
        entry["slice_id"] = slice_id
    if base is not None:
        entry["base"] = base
    return entry


def run_start(slice_title, cwd=".", slice_id=None, base=None, kind="feature", risks=0, inspected=0, run=0):
    entry = _ids({"phase": "start", "slice": slice_title, "kind": kind, "confirmed": True,
                  "gaps": {"risks": risks, "inspected": inspected, "run": run}}, slice_id, base)
    token, recorded = _record(entry, cwd)
    return True, _line("start", token, None, True, "", recorded), ""


def run_bypass(slice_title, reason, cwd=".", slice_id=None, base=None):
    entry = _ids({"phase": "bypass", "slice": slice_title, "reason": reason, "confirmed": True}, slice_id, base)
    token, recorded = _record(entry, cwd)
    return True, _line("bypass", token, None, True, "", recorded), ""


def run_done(slice_title=None, cwd="."):
    entry = {"phase": "done", "confirmed": True}
    if slice_title:
        entry["slice"] = slice_title
    token, recorded = _record(entry, cwd)
    return True, _line("done", token, None, True, "", recorded), ""


def run_coverage(slice_title, mutant, cmd, cwd=".", slice_id=None, base=None):
    """Confirmed when the test passes and the mutant command (a shell string) fails."""
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, shell=len(cmd) == 1)
    m = subprocess.run(mutant, cwd=cwd, capture_output=True, text=True, shell=True)
    output = (r.stdout + r.stderr)[-TAIL:]
    ran = m.returncode > 0 and m.returncode not in MUTANT_NOT_RUN
    confirmed = r.returncode == 0 and ran
    if r.returncode != 0:
        note = "tests fail"
    elif m.returncode == 0:
        note = "mutant survived (exit 0)"
    elif not ran:
        note = "mutant did not run"
        output = (output + "\n" + (m.stdout + m.stderr)[-TAIL:])[-TAIL:]
    else:
        note = ""
    entry = _ids({"phase": "coverage", "slice": slice_title, "cmd": " ".join(cmd), "mutant": mutant,
                  "exit": r.returncode, "mutant_exit": m.returncode, "confirmed": confirmed, "note": note},
                 slice_id, base)
    token, recorded = _record(entry, cwd)
    return confirmed, _line("coverage", token, r.returncode, confirmed, note, recorded), output


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
    for name in ("start", "coverage", "bypass"):
        p = sub.add_parser(name)
        p.add_argument("--slice", required=True)
        p.add_argument("--slice-id")
        p.add_argument("--base")
        if name == "start":
            p.add_argument("--kind", default="feature", help="slice kind (default feature)",
                           choices=["feature", "fix", "refactor", "contract", "validation", "ui"])
            for g in ("risks", "inspected", "run"):
                p.add_argument("--" + g, type=int, default=0)
        elif name == "coverage":
            p.add_argument("--mutant", required=True,
                           help="shell command that runs the test against a mutated copy; must run and fail")
        else:
            p.add_argument("--reason", required=True, help="why Red-first is bypassed")
    dn = sub.add_parser("done")
    dn.add_argument("--slice", help="slice title being closed (optional)")
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
    if a.phase == "done":
        ok, line, output = run_done(a.slice)
        print(line)
        return 0
    if a.slice_id is not None:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks"))
        from markers import SLICE_TITLE_RE
        m = SLICE_TITLE_RE.match(a.slice)
        if not m or m.group(1).lower() != a.slice_id.lower():
            ap.error(f"--slice-id {a.slice_id} does not match slice title {a.slice!r}")
        a.slice_id = m.group(1)
    if a.phase in ("start", "bypass"):
        if a.phase == "start":
            _, line, _ = run_start(a.slice, slice_id=a.slice_id, base=a.base, kind=a.kind,
                                   risks=a.risks, inspected=a.inspected, run=a.run)
        else:
            _, line, _ = run_bypass(a.slice, a.reason, slice_id=a.slice_id, base=a.base)
        print(line)
        return 0
    if not cmd:
        ap.error("give the test command after --")
    if a.phase == "coverage":
        confirmed, line, output = run_coverage(a.slice, a.mutant, cmd, slice_id=a.slice_id, base=a.base)
        print(output.rstrip())
        print(line)
        return 0 if confirmed else 1
    confirmed, line, output = run_phase(a.phase, a.slice, cmd, slice_id=a.slice_id, base=a.base)
    print(output.rstrip())
    print(line)
    return 0 if confirmed else 1


if __name__ == "__main__":
    sys.exit(main())
