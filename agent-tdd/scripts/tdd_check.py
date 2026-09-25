#!/usr/bin/env python3
"""Run a slice's test command and record Red/Green evidence. Stdlib only.

  tdd_check.py red   --slice "<slice title>" -- <test command...>
  tdd_check.py green --slice "<slice title>" -- <test command...>
  tdd_check.py verify <token>...          (used by hooks/tdd_subagent_stop.py)

`red` expects the command to FAIL (the new test exists and the behavior doesn't yet); `green`
expects it to PASS and requires an earlier failing `red` for the same slice. Each run appends one
line to <git dir>/agent-tdd/evidence.jsonl and prints a token such as
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


def evidence_path(cwd="."):
    r = subprocess.run(["git", "rev-parse", "--absolute-git-dir"], cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return os.path.join(r.stdout.strip(), "agent-tdd", "evidence.jsonl")


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


def run_phase(phase, slice_title, cmd, cwd="."):
    """Run cmd, record it, and return (confirmed, token_line)."""
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, shell=len(cmd) == 1)
    output = (r.stdout + r.stderr)[-TAIL:]
    failed = r.returncode != 0
    prior_red = [e for e in read_log(cwd) if e.get("slice") == slice_title and e.get("phase") == "red"
                 and e.get("confirmed")]
    if phase == "red":
        confirmed, note = failed, "" if failed else "test passed before implementation"
    else:
        confirmed = not failed and bool(prior_red)
        note = "" if confirmed else ("tests still fail" if failed else "no verified red for this slice")
    token = secrets.token_hex(4)
    entry = {"token": token, "phase": phase, "slice": slice_title, "cmd": " ".join(cmd),
             "exit": r.returncode, "confirmed": confirmed, "note": note,
             "at": datetime.datetime.now().isoformat(timespec="seconds")}
    recorded = _append(entry, cwd)
    status = "CONFIRMED" if confirmed else f"NOT CONFIRMED ({note})"
    line = f"TDD-EVIDENCE {phase} {token} exit={r.returncode} {status}"
    if not recorded:
        line += " [unrecorded: not a git repo]"
    return confirmed, line, output


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
    v = sub.add_parser("verify")
    v.add_argument("tokens", nargs="+")
    a = ap.parse_args(argv)

    if a.phase == "verify":
        print(json.dumps(verify(a.tokens), indent=2))
        return 0
    if not cmd:
        ap.error("give the test command after --")
    confirmed, line, output = run_phase(a.phase, a.slice, cmd)
    print(output.rstrip())
    print(line)
    return 0 if confirmed else 1


if __name__ == "__main__":
    sys.exit(main())
