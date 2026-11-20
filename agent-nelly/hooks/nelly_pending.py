#!/usr/bin/env python3
"""Pending findings queue: findings on uncommitted files, readiness, resolve (R18).

Release 5 slice 0 stub: reads the hook payload and exits 0 silently (fail-open). Wave 1 slice
1C implements it; the contract is in INTEROP.md "Source evidence, staleness, capture and
safe writes"."""
import json
import sys

def session_hint(cwd):
    """Return SessionStart lines about pending findings (at most 2 ready, 2 changed)."""
    return []


def main():
    try:
        json.load(sys.stdin)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
