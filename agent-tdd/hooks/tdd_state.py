#!/usr/bin/env python3
"""Shared state utilities for the agent-tdd plugin.

Owns:
  - TDD memory directory derivation (~/.claude/agent-tdd-state/<project-slug>/)
  - tdd-progress.json read/write (slice tracking)
  - last-stop.json write (session boundary marker)

Intentionally self-contained: slug algorithm is copied verbatim from
agent-isdd/hooks/sdd_memory.py rather than imported, to avoid a cross-plugin
dependency. The two modules must stay in sync if the slug algorithm ever changes.
"""
import datetime
import json
import os
import re

BASE = os.path.join(os.path.expanduser("~"), ".claude", "agent-tdd-state")


def project_slug(cwd):
    """Deterministic collision-resistant slug from an absolute project path.
    Algorithm is identical to agent-isdd/hooks/sdd_memory.py — kept in sync manually.
    """
    absp = os.path.abspath(cwd)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", absp).strip("-").lower()
    return slug or "root"


def tdd_memory_dir(cwd):
    return os.path.join(BASE, project_slug(cwd))


def read_tdd_progress(cwd):
    """Read tdd-progress.json. Returns {"slices": []} on missing or malformed file."""
    path = os.path.join(tdd_memory_dir(cwd), "tdd-progress.json")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict) or not isinstance(data.get("slices"), list):
            return {"slices": []}
        return data
    except (OSError, json.JSONDecodeError, ValueError):
        return {"slices": []}


def write_tdd_progress(cwd, data):
    """Write tdd-progress.json, creating parent dirs as needed."""
    d = tdd_memory_dir(cwd)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "tdd-progress.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


def write_last_stop(cwd):
    """Write last-stop.json as a session-boundary mtime marker. Best-effort: silently
    ignores all OSError so a disk-full or permission error never blocks the Stop hook."""
    try:
        d = tdd_memory_dir(cwd)
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, "last-stop.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"timestamp": datetime.datetime.now().isoformat()}, fh)
    except OSError:
        pass
