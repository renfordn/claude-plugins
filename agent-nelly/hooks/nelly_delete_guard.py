#!/usr/bin/env python3
"""PreToolUse Bash: deny hard deletes (rm/unlink/find -delete) under the memory store (R0d).

Release 5 slice 0 stub: reads the hook payload and exits 0 silently (fail-open). Wave 1 slice
1E implements it; the contract is in INTEROP.md "Source evidence, staleness, capture and
safe writes"."""
import json
import sys



def main():
    try:
        json.load(sys.stdin)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
