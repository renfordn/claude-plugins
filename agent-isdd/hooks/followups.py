#!/usr/bin/env python3
"""Review follow-up queue: refactor / consolidation / deferred-defect items from code-reviewer.

code-reviewer writes `followups` into findings.json (default `<git dir>/code-review/findings.json`).
This module turns each into one file under `<sdd memory>/<project>/followups/<id>.md` so they
outlive the review, show up at SessionStart, can seed a new feature, and reach agent-nelly.

  followups.py ingest [FINDINGS_JSON]    import new items (idempotent; existing ids keep their status)
  followups.py list [--all]              open items (or every item) as `id  status  kind  title`
  followups.py set ID STATUS             STATUS: open | picked | done | dismissed
  followups.py recorded ID               mark nelly_recorded: yes
"""
import datetime
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdd_memory import memory_dir  # noqa: E402

STATUSES = ("open", "picked", "done", "dismissed")
KINDS = ("refactor", "consolidation", "deferred-defect")


def followups_dir(cwd):
    return os.path.join(memory_dir(cwd), "followups")


def default_findings_path(cwd):
    r = subprocess.run(["git", "rev-parse", "--absolute-git-dir"], cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return os.path.join(r.stdout.strip(), "code-review", "findings.json")


def slug(text):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:60].rstrip("-") or "item"


def _fm(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}
    return dict(re.findall(r"^(\w+):\s*(.*)$", m.group(1), re.M))


def _render(item, scope):
    files = [f for f in item.get("files", []) if isinstance(f, str)]
    steps = "\n".join(f"{i}. {s}" for i, s in enumerate(item.get("steps", []), 1))
    return (
        "---\n"
        f"source: code-reviewer\n"
        f"kind: {item['kind']}\n"
        f"status: open\n"
        f"nelly_recorded: no\n"
        f"files: {';'.join(files)}\n"
        f"scope: {scope}\n"
        f"created: {datetime.date.today().isoformat()}\n"
        "---\n\n"
        f"# {item['title']}\n\n"
        f"{item.get('why', '').strip()}\n\n"
        f"## Steps\n\n{steps}\n"
    )


def ingest(cwd, findings_path=None):
    """Import findings.json followups; return the ids created this call."""
    path = findings_path or default_findings_path(cwd)
    if not path or not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return []
    d = followups_dir(cwd)
    created = []
    for item in doc.get("followups") or []:
        if not isinstance(item, dict) or item.get("kind") not in KINDS or not item.get("title"):
            continue
        fid = slug(item["title"])
        target = os.path.join(d, f"{fid}.md")
        if os.path.exists(target):
            continue
        os.makedirs(d, exist_ok=True)
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(_render(item, doc.get("scope", "")))
        created.append(fid)
    return created


def items(cwd):
    """[(id, path, frontmatter, title)] for every queued item, oldest first."""
    d = followups_dir(cwd)
    try:
        names = sorted(n for n in os.listdir(d) if n.endswith(".md"))
    except OSError:
        return []
    out = []
    for name in names:
        path = os.path.join(d, name)
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            continue
        title = re.search(r"^# (.+)$", text, re.M)
        out.append((name[:-3], path, _fm(text), title.group(1) if title else name[:-3]))
    out.sort(key=lambda t: (t[2].get("created", ""), t[0]))
    return out


def open_items(cwd):
    return [t for t in items(cwd) if t[2].get("status") == "open"]


def pending_nelly(cwd):
    return [t for t in items(cwd) if t[2].get("nelly_recorded") == "no" and t[2].get("status") in ("open", "picked")]


def _rewrite_field(path, key, value):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    new, n = re.subn(rf"^{key}:.*$", f"{key}: {value}", text, count=1, flags=re.M)
    if not n:
        raise ValueError(f"{path}: no '{key}' field")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(new)


def _path_for(cwd, fid):
    if "/" in fid or "\\" in fid or fid in (".", ".."):
        raise ValueError(f"invalid follow-up id: {fid!r}")
    path = os.path.join(followups_dir(cwd), f"{fid}.md")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"no follow-up {fid!r} in {followups_dir(cwd)}")
    return path


def set_status(cwd, fid, status):
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    _rewrite_field(_path_for(cwd, fid), "status", status)


def mark_recorded(cwd, fid):
    _rewrite_field(_path_for(cwd, fid), "nelly_recorded", "yes")


def main(argv):
    cwd = os.getcwd()
    cmd = argv[0] if argv else "list"
    try:
        if cmd == "ingest":
            for fid in ingest(cwd, argv[1] if len(argv) > 1 else None):
                print(f"added {fid}")
        elif cmd == "list":
            rows = items(cwd) if "--all" in argv else open_items(cwd)
            for fid, _, fm, title in rows:
                print(f"{fid}  {fm.get('status', '?')}  {fm.get('kind', '?')}  {title}")
        elif cmd == "set" and len(argv) == 3:
            set_status(cwd, argv[1], argv[2])
        elif cmd == "recorded" and len(argv) == 2:
            mark_recorded(cwd, argv[1])
        else:
            print(__doc__, file=sys.stderr)
            return 2
    except (ValueError, FileNotFoundError) as e:
        print(f"followups: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
