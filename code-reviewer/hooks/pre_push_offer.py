#!/usr/bin/env python3
"""PreToolUse Bash: offer a whole-diff review before a `git push` of an unreviewed HEAD (R15).
Contract stub (release 4 slice 0): fails open, no output."""
import json
import sys


def main():
    try:
        json.load(sys.stdin)
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
