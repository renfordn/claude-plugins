#!/usr/bin/env python3
"""Audit test files for bloat: counts, near-duplicate clusters, churn, runtime share."""
import argparse
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

TEST_PATTERNS = [
    re.compile(r"^\s*(?:async\s+)?def\s+(test\w*)\s*\("),          # pytest/unittest
    re.compile(r"^\s*(?:it|test)(?:\.only|\.each\([^)]*\))?\s*\(\s*[`'\"](.+?)[`'\"]"),  # jest/vitest/mocha
    re.compile(r"^func\s+(Test\w+)\s*\("),                          # go
    re.compile(r"^\s*(?:public\s+)?void\s+(test\w+|should\w+)\s*\("),  # junit
]
SETUP_RE = re.compile(r"@pytest\.fixture|def setUp\b|beforeEach\(|beforeAll\(|func TestMain|@Before\b")
TEST_FILE_RE = re.compile(r"(^test_.*\.py$|_test\.(py|go)$|\.(test|spec)\.[jt]sx?$|Test\.java$)")


def extract_test_names(text):
    names = []
    for line in text.splitlines():
        for pat in TEST_PATTERNS:
            m = pat.match(line)
            if m:
                names.append(m.group(1))
                break
    return names


def stem(name):
    """Normalize a test name so near-duplicates collapse to one key."""
    name = re.sub(r"^test_?", "", name, flags=re.I)
    words = [w for w in re.split(r"[_\s]+|(?<=[a-z])(?=[A-Z])", name) if w]
    return tuple(w.lower() for w in words[:3]) if len(words) > 3 else tuple(w.lower() for w in words[:2])


def clusters(names, min_size=3):
    groups = defaultdict(list)
    for n in names:
        groups[stem(n)].append(n)
    return {k: v for k, v in groups.items() if k and len(v) >= min_size}


def churn(path):
    try:
        out = subprocess.run(
            ["git", "log", "--format=%ct", "--", str(path)],
            capture_output=True, text=True, cwd=path.parent, timeout=15,
        ).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return None, None
    if not out:
        return 0, None
    return len(out), int((time.time() - int(out[0])) / 86400)


def junit_runtime(xml_path):
    times = defaultdict(float)
    for case in ET.parse(xml_path).getroot().iter("testcase"):
        key = (case.get("file") or case.get("classname") or "").replace(".", "/")
        times[key] += float(case.get("time") or 0)
    return times


def share_for(path, times):
    total = sum(times.values())
    if not total:
        return None
    stem_path = path.with_suffix("").as_posix()
    mine = sum(t for k, t in times.items() if k and (k in stem_path or stem_path.endswith(k)))
    return 100 * mine / total


def collect(target):
    if target.is_file():
        return [target]
    return sorted(p for p in target.rglob("*") if p.is_file() and TEST_FILE_RE.search(p.name))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("target", type=Path)
    ap.add_argument("--junit", type=Path, help="JUnit XML report for runtime share")
    ap.add_argument("--min-cluster", type=int, default=3)
    args = ap.parse_args(argv)

    if not args.target.exists():
        print(f"not found: {args.target}", file=sys.stderr)
        return 2
    times = junit_runtime(args.junit) if args.junit else {}
    rows = []
    for f in collect(args.target):
        text = f.read_text(errors="replace")
        names = extract_test_names(text)
        if not names:
            continue
        n_commits, age = churn(f.resolve())
        rows.append((len(names), f, text, names, n_commits, age))
    rows.sort(key=lambda r: -r[0])
    for count, f, text, names, n_commits, age in rows:
        line = f"{f}: {count} tests, {len(text.splitlines())} lines, {len(SETUP_RE.findall(text))} setup hooks"
        if n_commits is not None:
            line += f", {n_commits} commits" + (f", last touched {age}d ago" if age is not None else "")
        share = share_for(f.resolve(), times) if times else None
        if share is not None:
            line += f", {share:.0f}% of runtime"
        print(line)
        for key, group in sorted(clusters(names, args.min_cluster).items(), key=lambda kv: -len(kv[1])):
            print(f"  consolidation candidate ({len(group)}): {', '.join(group[:6])}{' ...' if len(group) > 6 else ''}")
    if not rows:
        print("no tests found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
