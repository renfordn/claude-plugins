#!/usr/bin/env python3
"""SessionEnd hook: write a lightweight `session-handoff` entry summarizing
what the session was working on, so the next session's SessionStart brief
(nelly_session_start.py) can surface it for continuity -- no LLM call, no
token cost, pure stdlib.

SessionEnd's own payload carries only `session_id`/`transcript_path`/`cwd`/
`reason` -- unlike PostToolUse hooks, it does NOT get the tool call history
inline. This hook reads `transcript_path` (the session's own JSONL
transcript) once and reconstructs, purely from that file:
  - which files were touched by Write/Edit/MultiEdit ("edited")
  - which files were touched by Read/Write/Edit/MultiEdit, most-recent-first
    ("recent focus", used to infer which area of the repo the session was in)
  - any `git commit` successes, reusing nelly_commit_extract.detect_commits
    against each Bash tool_result's text (same detection regexes, no
    duplicated logic)
  - a count of Bash commands that look like test runs (informational only --
    does not gate whether an entry gets written)

Only writes when there was file-edit or commit activity (the write gate);
a session that only read files or asked questions is a silent no-op, exactly
like nelly_auto_extract.py/nelly_commit_extract.py are silent on a clean run.

Entire body runs under one broad try/except -- any failure (missing/partial
transcript, unwritable memory dir, corrupt index) is swallowed and treated as
a silent no-op. SessionEnd's exit code/stderr are shown to the user only and
cannot block the session from ending, but a crash still has no business
spewing a traceback into an ending session.

Set env NELLY_GATE=off (or 0/false/disabled, case-insensitive) to disable
entirely, same convention as the other Nelly gate hooks.
"""
import json
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import nelly_memory  # noqa: E402
import build_index  # noqa: E402
from nelly_auto_extract import _entry_exists  # noqa: E402
from nelly_commit_extract import detect_commits  # noqa: E402

_MAX_DESCRIPTION_LEN = 140
_RECENT_N = 5
_EDIT_TOOLS = {"Write", "Edit", "MultiEdit"}
_TOUCH_TOOLS = {"Read", "Write", "Edit", "MultiEdit"}
_TEST_RUN_RE = re.compile(
    r"\b(pytest|npm\s+(run\s+)?test|yarn\s+test|go\s+test|cargo\s+test|"
    r"jest|mvn\s+test|gradle\s+test|rspec|phpunit)\b",
    re.I,
)


def _iter_transcript(transcript_path):
    """Yield one parsed JSON object per non-blank transcript line.

    Malformed lines (transcript is written asynchronously and its tail can
    be mid-write at session-end) are skipped, never raised -- a partially
    written transcript degrades to "fewer facts found", not a crash. A
    missing/unreadable file yields nothing.
    """
    try:
        fh = open(transcript_path, "r", encoding="utf-8")
    except OSError:
        return
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue


def _relativize(cwd, path):
    """Best-effort cwd-relative form of an (expected-absolute) tool path, for
    readable descriptions and top-level-dir tags. Falls back to the original
    path unchanged when it isn't under cwd (e.g. a path outside the repo) --
    never raises.
    """
    if not path:
        return path
    try:
        rel = os.path.relpath(path, cwd)
    except ValueError:
        return path
    return path if rel.startswith("..") else rel


def _top_level_dir(rel_path):
    parts = rel_path.split(os.sep)
    return parts[0] if len(parts) > 1 and parts[0] else None


def scan_transcript(transcript_path, cwd):
    """Walk `transcript_path` once and return a summary dict:
    `{"edited_files": [...], "touched_files": [...], "commit_subjects": [...],
    "test_run_count": int}`. `edited_files`/`touched_files` are cwd-relative,
    de-duplicated, first-seen order. Never raises -- a missing, empty, or
    fully-malformed transcript yields all-empty results, which the caller
    treats as "no activity" (the write gate), not an error.
    """
    tool_names_by_id = {}
    edited_files = []
    edited_seen = set()
    touched_files = []
    commit_subjects = []
    test_run_count = 0

    for obj in _iter_transcript(transcript_path):
        otype = obj.get("type")

        if otype == "assistant":
            for c in (obj.get("message") or {}).get("content") or []:
                if not isinstance(c, dict) or c.get("type") != "tool_use":
                    continue
                name = c.get("name")
                tool_id = c.get("id")
                tool_input = c.get("input") or {}
                if tool_id:
                    tool_names_by_id[tool_id] = name

                if name in _TOUCH_TOOLS:
                    fp = tool_input.get("file_path")
                    if fp:
                        touched_files.append(_relativize(cwd, fp))
                if name in _EDIT_TOOLS:
                    fp = tool_input.get("file_path")
                    rel = _relativize(cwd, fp) if fp else None
                    if rel and rel not in edited_seen:
                        edited_seen.add(rel)
                        edited_files.append(rel)
                if name == "Bash":
                    command = tool_input.get("command") or ""
                    if _TEST_RUN_RE.search(command):
                        test_run_count += 1

        elif otype == "user":
            content = (obj.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            for c in content:
                if not isinstance(c, dict) or c.get("type") != "tool_result":
                    continue
                if tool_names_by_id.get(c.get("tool_use_id")) != "Bash":
                    continue
                result_text = c.get("content")
                if isinstance(result_text, list):
                    result_text = "".join(
                        b.get("text", "") for b in result_text if isinstance(b, dict)
                    )
                if not isinstance(result_text, str):
                    continue
                for commit in detect_commits(result_text):
                    commit_subjects.append(commit["subject"])

    return {
        "edited_files": edited_files,
        "touched_files": touched_files,
        "commit_subjects": commit_subjects,
        "test_run_count": test_run_count,
    }


def _recent_focus(touched_files, n=_RECENT_N):
    """Top-level directories of the last `n` touched files, most-recent-first,
    de-duplicated. Falls back to the bare relative path when it has no
    directory component (a repo-root file).
    """
    labels = []
    seen = set()
    for rel in reversed(touched_files[-n:]):
        label = _top_level_dir(rel) or rel
        if label not in seen:
            seen.add(label)
            labels.append(label)
    return labels


def _build_description(edited_files, commit_subjects, recent_focus):
    segments = []
    if edited_files:
        shown = edited_files[:5]
        more = f" (+{len(edited_files) - 5} more)" if len(edited_files) > 5 else ""
        segments.append("active files: " + ", ".join(shown) + more)
    if commit_subjects:
        segments.append(f"Last commit: {commit_subjects[-1]}")
    if recent_focus:
        segments.append("Recent focus: " + ", ".join(recent_focus))
    if not segments:
        return "Session ended -- no significant activity detected."
    return "Session ended -- " + ". ".join(segments) + "."


def _tags_for_files(edited_files):
    return sorted({d for d in (_top_level_dir(rel) for rel in edited_files) if d})


def _write_entry(cwd, slug, description, edited_files, commit_subjects, test_run_count, reason):
    nelly_memory.ensure_entries_dir(cwd)
    path = nelly_memory.entry_path(cwd, slug)

    description = description[:_MAX_DESCRIPTION_LEN]
    tags = _tags_for_files(edited_files)
    files_field = ", ".join(edited_files) if edited_files else "none"
    commit_field = commit_subjects[-1] if commit_subjects else "none"

    body = (
        f"Session handoff: {description}\n"
        f"Files touched: {files_field}\n"
        f"Last commit: {commit_field}\n"
        f"Test runs observed: {test_run_count}\n"
        f"Context: Auto-generated at session end (reason={reason}). No LLM used.\n"
    )
    content = (
        "---\n"
        f"name: {slug}\n"
        f"description: {description}\n"
        "metadata:\n"
        "  type: technique\n"
        f"  last_referenced: {datetime.now().date().isoformat()}\n"
        "  confidence: inferred\n"
        f"  files_changed: {len(edited_files)}\n"
        f"tags: [{', '.join(tags)}]\n"
        "---\n\n"
        f"{body}"
    )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)

    nelly_memory.write_index_line(cwd, slug, description, "technique", confidence="inferred")
    build_index.upsert_project_entry(cwd, path)


def _run():
    if os.environ.get("NELLY_GATE", "").lower() in ("off", "0", "false", "disabled"):
        return

    payload = json.load(sys.stdin)
    cwd = payload.get("cwd") or os.getcwd()
    transcript_path = payload.get("transcript_path") or ""
    reason = payload.get("reason") or "other"

    summary = scan_transcript(transcript_path, cwd)
    edited_files = summary["edited_files"]
    commit_subjects = summary["commit_subjects"]

    if not edited_files and not commit_subjects:
        return  # idle session (reads/questions only) -- no-op

    recent_focus = _recent_focus(summary["touched_files"])
    description = _build_description(edited_files, commit_subjects, recent_focus)

    slug = f"session-handoff-{datetime.now().strftime('%Y-%m-%d-%H%M')}"
    if _entry_exists(cwd, slug):
        return

    _write_entry(cwd, slug, description, edited_files, commit_subjects, summary["test_run_count"], reason)
    print(f"[nelly] session handoff saved: {slug}")


def main():
    try:
        _run()
    except Exception:
        pass  # SessionEnd output is shown to the user only -- never crash it
    sys.exit(0)


if __name__ == "__main__":
    main()
