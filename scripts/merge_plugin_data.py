#!/usr/bin/env python3
"""Merge one plugin data directory into another without losing anything.

Plugin data (${CLAUDE_PLUGIN_DATA}) is local disk, per plugin identity and per machine --
it is never synced. The same plugin loaded as both `<plugin>@inline` (account-synced copy)
and `<plugin>@<marketplace>` gets two separate data dirs on one machine, and every machine
has its own. This script folds SRC into DST:

  - files only in SRC               -> copied
  - identical files                 -> left alone
  - MEMORY.md indexes               -> union of lines (missing lines appended)
  - GLOBAL-MEMORY.md                -> union of `---`-separated memory blocks
  - *HISTORY*.md, *.jsonl logs      -> lines missing from DST appended
  - any other differing file        -> newer copy wins; the older one is kept next to it
                                       as `<name>.conflict-<its dir name>` for review
  - test leftovers (var-folders-*, tmp-*, *some-project*, *test-project*) and .DS_Store
    are skipped

SRC is never modified unless --delete-source is given (and then only after a clean merge).

Same machine, two identities:
    python3 scripts/merge_plugin_data.py \\
        ~/.claude/plugins/data/agent-nelly-inline ~/.claude/plugins/data/agent-nelly-renfordn-plugins

Across machines: copy the data dir to a folder both machines can see (a git repo, iCloud
Drive, a USB stick), then on the other machine merge that copy into its local data dir:
    rsync -a ~/.claude/plugins/data/agent-nelly-renfordn-plugins/ /path/to/synced/agent-nelly/
    python3 scripts/merge_plugin_data.py /path/to/synced/agent-nelly \\
        ~/.claude/plugins/data/agent-nelly-renfordn-plugins

Stdlib only. Run with --dry-run first to see what would change.
"""

import argparse
import filecmp
import os
import re
import shutil
import sys

_JUNK_COMPONENT = re.compile(r"^(var-folders-.*|tmp-.*|.*some-project.*|.*test-project.*)$")
_BLOCK_SEP = "\n---\n"


def is_skipped(rel_path):
    parts = rel_path.split(os.sep)
    if parts[-1] == ".DS_Store" or ".conflict-" in parts[-1]:
        return True
    return any(_JUNK_COMPONENT.match(p) for p in parts[:-1])


def classify(rel_path):
    name = os.path.basename(rel_path)
    if name == "MEMORY.md":
        return "line-union"
    if name == "GLOBAL-MEMORY.md":
        return "block-union"
    if ("HISTORY" in name.upper() and name.endswith(".md")) or name.endswith(".jsonl"):
        return "append"
    return "newer-wins"


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def merge_lines(dst_text, src_text):
    """Append SRC's non-blank lines that DST doesn't already have, in SRC order."""
    have = set(dst_text.splitlines())
    extra = [l for l in src_text.splitlines() if l.strip() and l not in have]
    if not extra:
        return dst_text, 0
    base = dst_text if dst_text.endswith("\n") or not dst_text else dst_text + "\n"
    return base + "\n".join(extra) + "\n", len(extra)


def merge_blocks(dst_text, src_text):
    """Append SRC's `---`-separated blocks that DST doesn't already contain."""
    have = {b.strip() for b in dst_text.split(_BLOCK_SEP)}
    extra = [b.strip() for b in src_text.split(_BLOCK_SEP) if b.strip() and b.strip() not in have]
    if not extra:
        return dst_text, 0
    return dst_text.rstrip("\n") + _BLOCK_SEP + _BLOCK_SEP.join(extra) + "\n", len(extra)


def merge(src, dst, dry_run=False):
    """Merge directory SRC into DST. Returns a list of (action, rel_path, detail)."""
    src, dst = os.path.abspath(src), os.path.abspath(dst)
    report = []
    for root, _dirs, files in os.walk(src):
        for name in sorted(files):
            s = os.path.join(root, name)
            if os.path.islink(s):
                report.append(("skip-link", os.path.relpath(s, src), ""))
                continue
            rel = os.path.relpath(s, src)
            if is_skipped(rel):
                continue
            d = os.path.join(dst, rel)

            if not os.path.exists(d):
                report.append(("copy", rel, ""))
                if not dry_run:
                    os.makedirs(os.path.dirname(d), exist_ok=True)
                    shutil.copy2(s, d)
                continue
            if filecmp.cmp(s, d, shallow=False):
                continue

            kind = classify(rel)
            if kind in ("line-union", "append", "block-union"):
                fn = merge_blocks if kind == "block-union" else merge_lines
                merged, n = fn(_read(d), _read(s))
                if n:
                    report.append((kind, rel, f"+{n}"))
                    if not dry_run:
                        _write(d, merged)
                continue

            # newer-wins, keeping the loser beside it
            if os.path.getmtime(s) > os.path.getmtime(d):
                backup = f"{d}.conflict-{os.path.basename(dst)}"
                report.append(("replace", rel, f"older kept as {os.path.basename(backup)}"))
                if not dry_run:
                    shutil.copy2(d, backup)
                    shutil.copy2(s, d)
            else:
                backup = f"{d}.conflict-{os.path.basename(src)}"
                report.append(("keep", rel, f"older kept as {os.path.basename(backup)}"))
                if not dry_run:
                    shutil.copy2(s, backup)
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("src", help="data dir to merge from (left untouched)")
    p.add_argument("dst", help="data dir to merge into")
    p.add_argument("--dry-run", action="store_true", help="show what would change, write nothing")
    p.add_argument("--delete-source", action="store_true",
                   help="delete SRC after a merge with no conflicts")
    args = p.parse_args(argv)

    for label, path in (("src", args.src), ("dst", args.dst)):
        if not os.path.isdir(path):
            print(f"{label} is not a directory: {path}", file=sys.stderr)
            return 2
    if os.path.realpath(args.src) == os.path.realpath(args.dst):
        print("src and dst are the same directory", file=sys.stderr)
        return 2

    report = merge(args.src, args.dst, dry_run=args.dry_run)
    for action, rel, detail in report:
        print(f"{action:<12} {rel}" + (f"  ({detail})" if detail else ""))
    conflicts = [r for r in report if r[0] in ("replace", "keep")]
    print(f"\n{len(report)} change(s), {len(conflicts)} conflict(s)"
          + (" -- dry run, nothing written" if args.dry_run else ""))

    if args.delete_source and not args.dry_run:
        if conflicts:
            print("Not deleting source: review the .conflict-* files first.", file=sys.stderr)
            return 1
        shutil.rmtree(args.src)
        print(f"deleted {args.src}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
