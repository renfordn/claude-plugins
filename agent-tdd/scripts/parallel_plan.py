#!/usr/bin/env python3
"""Turn tasks.md into safe parallel waves. Stdlib only.

  parallel_plan.py check <tasks.md>
  parallel_plan.py waves <tasks.md> [--width N] [--json|--table] [--write]
  parallel_plan.py verify-branch <base> <branch> --owned f1 f2 ... [--repo DIR]
"""
import argparse
import json
import posixpath
import re
import subprocess
import sys

ID = r"\d+[A-Za-z]*"  # consistent with hooks/markers.py ID
SLICE_RE = re.compile(r"^## Slice (" + ID + r"):\s*(.*?)\s*$")
SLICE_ANY_RE = re.compile(r"^##\s+Slice\b", re.IGNORECASE)
FIELD_RE = re.compile(r"^\*\*([A-Za-z ]+):\*\*\s*(.*?)\s*$")
BULLET_RE = re.compile(r"^\s*[-*]\s+(.*?)\s*$")
LIST_FIELDS = {"files": "files", "test files": "test_files", "shared files": "shared_files"}


def _key(n):
    m = re.match(r"(\d+)(.*)", str(n))
    return (int(m.group(1)), m.group(2))


def _num(raw):
    return int(raw) if raw.isdigit() else raw


def _norm_path(p):
    """Canonical repo-relative path; directories keep a trailing '/'."""
    p = p.strip().strip("`").strip()
    p = re.sub(r"\s*\([^)]*\)\s*$", "", p).strip().strip("`").strip()
    if not p:
        return ""
    is_dir = p.endswith("/")
    p = posixpath.normpath(p)
    if p == ".":
        return ""
    return p + "/" if is_dir else p


def _expand_braces(s):
    m = re.search(r"\{([^{}]*)\}", s)
    if not m:
        return [s]
    out = []
    for alt in m.group(1).split(","):
        out.extend(_expand_braces(s[:m.start()] + alt.strip() + s[m.end():]))
    return out


def _split_list(value):
    parts, depth, cur = [], 0, ""
    for ch in value:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    out = []
    for part in parts:
        part = part.strip()
        if not part or part.startswith("("):
            continue
        for item in _expand_braces(part):
            n = _norm_path(item)
            if n:
                out.append(n)
    return out


def _parse_deps(val, cur):
    val = re.sub(r"\([^)]*\)", "", val)
    for m in re.finditer(r"(" + ID + r")(?:\s*[-\u2013]\s*(" + ID + r"))?", val):
        a, b = m.group(1), m.group(2)
        if b is None:
            cur["depends_on"].append(_num(a))
        elif a.isdigit() and b.isdigit() and int(a) <= int(b):
            cur["depends_on"].extend(range(int(a), int(b) + 1))
        else:
            cur["errors"].append(f"unparseable Depends On range {a}-{b}")


def parse(text):
    slices = []
    cur = None
    in_header = False
    list_field = None
    for line in text.splitlines():
        m = SLICE_RE.match(line)
        if m or SLICE_ANY_RE.match(line):
            cur = {"number": _num(m.group(1)) if m else None,
                   "title": m.group(2) if m else line.strip(),
                   "kind": "feature", "risk_tier": "standard", "depends_on": [],
                   "files": [], "test_files": [], "shared_files": [], "wave": None,
                   "errors": [] if m else [f"unparseable slice heading: {line.strip()!r}"]}
            slices.append(cur)
            in_header, list_field = True, None
            continue
        if cur is None or not in_header:
            continue
        if line.startswith("#"):
            in_header = False
            continue
        f = FIELD_RE.match(line)
        if not f:
            b = BULLET_RE.match(line)
            if b and list_field:
                cur[list_field].extend(_split_list(b.group(1)))
            elif line.strip():
                list_field = None
            continue
        name, val = f.group(1).strip().lower(), f.group(2)
        list_field = LIST_FIELDS.get(name)
        if name == "kind":
            cur["kind"] = val.strip().lower() or "feature"
        elif name == "risk tier":
            cur["risk_tier"] = val.strip().lower()
        elif name == "depends on":
            _parse_deps(val, cur)
        elif list_field:
            cur[list_field].extend(_split_list(val))
        elif name == "wave":
            nums = re.findall(r"\d+", val)
            cur["wave"] = int(nums[0]) if nums else None
    return slices


def _owned(s):
    return set(s["files"]) | set(s["test_files"])


def _touched(s):
    return _owned(s) | set(s["shared_files"])


def _pconflict(a, b):
    if a == b:
        return True
    return (a.endswith("/") and b.startswith(a)) or (b.endswith("/") and a.startswith(b))


def _sets_conflict(xs, ys):
    return any(_pconflict(x, y) for x in xs for y in ys)


def _index(slices):
    by = {}
    for s in slices:
        if s["number"] in by:
            raise ValueError(f"duplicate slice number {s['number']}")
        by[s["number"]] = s
    return by


def _ancestors(by):
    memo = {}

    def anc(n):
        if n in memo:
            return memo[n]
        memo[n] = set()  # guards recursion; cycles are rejected before use
        out = set()
        for d in by[n]["depends_on"]:
            if d in by:
                out.add(d)
                out |= anc(d)
        memo[n] = out
        return out

    return {n: anc(n) for n in by}


def _find_cycle(by):
    state = {}

    def visit(n, path):
        state[n] = 1
        for d in by[n]["depends_on"]:
            if d not in by:
                continue
            if state.get(d) == 1:
                return path + [n, d]
            if d not in state:
                r = visit(d, path + [n])
                if r:
                    return r
        state[n] = 2
        return None

    for n in sorted(by, key=_key):
        if n not in state:
            r = visit(n, [])
            if r:
                return r
    return None


def check(slices):
    errors = []
    good = []
    for s in slices:
        for e in s.get("errors", []):
            errors.append(f"Slice {s['number']}: {e}" if s["number"] is not None else e)
        if s["number"] is not None:
            good.append(s)
    seen = set()
    for s in good:
        if s["number"] in seen:
            errors.append(f"duplicate slice number {s['number']}")
        seen.add(s["number"])
    if errors:
        return errors
    by = _index(good)
    for s in good:
        n = s["number"]
        for d in s["depends_on"]:
            if d == n:
                errors.append(f"Slice {n}: depends on itself")
            elif d not in by:
                errors.append(f"Slice {n}: unknown dependency Slice {d}")
        if s["kind"] != "contract" and not s["files"]:
            errors.append(f"Slice {n}: no Files listed (non-contract slice must own files)")
    cyc = _find_cycle(by)
    if cyc:
        errors.append("dependency cycle: " + " -> ".join(f"Slice {n}" for n in cyc))
        return errors
    anc = _ancestors(by)
    nums = sorted(by, key=_key)
    for i, a in enumerate(nums):
        for b in nums[i + 1:]:
            if a in anc[b] or b in anc[a]:
                continue
            for x in sorted(_owned(by[a])):
                if any(_pconflict(x, y) for y in _owned(by[b])):
                    errors.append(f"undeclared overlap: {x} owned by Slice {a} and Slice {b} "
                                  "(not ordered by depends_on)")
    contract_paths = {f for s in good if s["kind"] == "contract" for f in _touched(s)}
    for f in sorted({f for s in good for f in s["shared_files"]}):
        who = sorted((s["number"] for s in good if _sets_conflict({f}, _touched(s))), key=_key)
        if len(who) >= 2 and not _sets_conflict({f}, contract_paths):
            errors.append(f"shared file {f} touched by Slices "
                          f"{', '.join(map(str, who))} with no contract slice declaring it")
    return errors


def _conflict(a, b):
    return (_sets_conflict(_owned(a), _owned(b))
            or _sets_conflict(set(a["shared_files"]), _touched(b))
            or _sets_conflict(set(b["shared_files"]), _touched(a)))


def _alone(s):
    return s["kind"] == "contract" or s["risk_tier"] == "high-risk"


def waves(slices, width=4):
    if width < 1:
        raise ValueError("width must be >= 1")
    errs = check(slices)
    if errs:
        raise ValueError("; ".join(errs))
    by = _index(slices)
    done = set()
    remaining = sorted(by, key=_key)
    out = []
    while remaining:
        ready = [n for n in remaining if all(d in done for d in by[n]["depends_on"])]
        wave = []
        for n in ready:
            s = by[n]
            if len(wave) >= width:
                break
            if _alone(s):
                if not wave:
                    wave.append(n)
                    break
                continue
            if any(_conflict(s, by[m]) for m in wave):
                continue
            wave.append(n)
        out.append(wave)
        done.update(wave)
        remaining = [n for n in remaining if n not in done]
    return out


def verify_branch(base, branch, owned, repo="."):
    r = subprocess.run(["git", "diff", "--name-only", "--no-renames", "-z", f"{base}...{branch}"],
                       cwd=repo, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "git diff failed")
    allowed = {n for n in (_norm_path(o) for o in owned) if n}
    changed = [f for f in r.stdout.split("\0") if f]
    return [f for f in changed if not _sets_conflict({_norm_path(f)}, allowed)]


def stamp(text, wave_of):
    lines = text.splitlines()
    out = []
    i = 0
    n = len(lines)
    while i < n:
        m = SLICE_RE.match(lines[i])
        if not m:
            out.append(lines[i])
            i += 1
            continue
        num = _num(m.group(1))
        j = i + 1
        while j < n and not lines[j].startswith("#"):
            j += 1
        block = [l for l in lines[i:j] if not re.match(r"^\*\*Wave:\*\*", l)]
        last, in_list = 0, False
        for k, l in enumerate(block[1:], 1):
            f = FIELD_RE.match(l)
            if f:
                last = k
                in_list = f.group(1).strip().lower() in LIST_FIELDS
            elif in_list and BULLET_RE.match(l):
                last = k
            elif l.strip():
                in_list = False
        if num in wave_of:
            block.insert(last + 1, f"**Wave:** {wave_of[num]}")
        out.extend(block)
        i = j
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def _width(v):
    try:
        n = int(v)
    except ValueError:
        raise argparse.ArgumentTypeError("width must be an integer >= 1")
    if n < 1:
        raise argparse.ArgumentTypeError("width must be >= 1")
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(prog="parallel_plan.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("tasks")
    w = sub.add_parser("waves")
    w.add_argument("tasks")
    w.add_argument("--width", type=_width, default=4)
    fmt = w.add_mutually_exclusive_group()
    fmt.add_argument("--json", action="store_true")
    fmt.add_argument("--table", action="store_true")
    w.add_argument("--write", action="store_true")
    v = sub.add_parser("verify-branch")
    v.add_argument("base")
    v.add_argument("branch")
    v.add_argument("--owned", nargs="*", default=[])
    v.add_argument("--repo", default=".")
    a = ap.parse_args(argv)

    if a.cmd == "verify-branch":
        try:
            bad = verify_branch(a.base, a.branch, a.owned, a.repo)
        except RuntimeError as e:
            print(f"verify-branch failed: {e}", file=sys.stderr)
            return 1
        for f in bad:
            print(f"outside owned files: {f}")
        return 1 if bad else 0

    with open(a.tasks) as fh:
        text = fh.read()
    slices = parse(text)
    if a.cmd == "check":
        errs = check(slices)
        for e in errs:
            print(e)
        return 1 if errs else 0

    try:
        result = waves(slices, a.width)
    except ValueError as e:
        print(str(e).replace("; ", "\n"), file=sys.stderr)
        return 1
    if a.write:
        wave_of = {n: i for i, wv in enumerate(result) for n in wv}
        new = stamp(text, wave_of)
        if new != text:
            with open(a.tasks, "w") as fh:
                fh.write(new)
    if a.json:
        print(json.dumps(result))
    else:
        by = _index(slices)
        print("wave | slices")
        for i, wv in enumerate(result):
            print(f"{i} | " + ", ".join(f"{n} ({by[n]['title']})" for n in wv))
    return 0


if __name__ == "__main__":
    sys.exit(main())
