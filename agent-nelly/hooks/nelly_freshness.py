#!/usr/bin/env python3
"""SessionStart helper: mark entries whose sources changed as stale, never delete (R17).

Release 5 slice 0 stub: reads the hook payload and exits 0 silently (fail-open). Wave 1 slice
1B implements it; the contract is in INTEROP.md "Source evidence, staleness, capture and
safe writes"."""
import json
import sys

def scan(cwd, budget=1.5):
    """Return SessionStart lines about entries newly marked stale."""
    return []


def main():
    try:
        json.load(sys.stdin)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
