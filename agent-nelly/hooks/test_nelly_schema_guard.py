"""Tests for hooks/nelly_schema_guard.py -- PreToolUse evidence/schema rules for memory entries (R16)."""
import json
import os
import subprocess
import sys

import pytest

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nelly_schema_guard.py")

GOOD_EVIDENCE = (
    "  sources: [{path: src/a.py, hash: abc123}]\n"
    "  revision: deadbeef\n  verified: 2026-11-20\n  basis: observed\n"
)


def fm(name="my-fact", meta="", typ="reference"):
    return (f"---\nname: {name}\ndescription: d\nmetadata:\n  type: {typ}\n"
            f"  last_referenced: 2026-11-20\n{meta}---\n\nbody\n")


def run_hook(payload, env=None):
    return subprocess.run([sys.executable, HOOK], input=json.dumps(payload), capture_output=True,
                          text=True, env=dict(os.environ, **(env or {})))


def target(tmp_path, name="my-fact", sub=None, inside=True):
    import nelly_memory
    cwd = str(tmp_path / "project")
    root = nelly_memory.memory_dir(cwd) if inside else str(tmp_path / "elsewhere")
    parts = [root, "entries"] + ([sub] if sub else []) + [name + ".md"]
    return cwd, os.path.join(*parts)


def write_payload(tmp_path, content, **kw):
    cwd, path = target(tmp_path, **kw)
    return {"tool_name": "Write", "tool_input": {"file_path": path, "content": content}, "cwd": cwd}


def decision(proc):
    assert proc.returncode == 0, proc.stderr
    if not proc.stdout.strip():
        return None, ""
    hso = json.loads(proc.stdout)["hookSpecificOutput"]
    return hso["permissionDecision"], hso.get("permissionDecisionReason", "")


@pytest.mark.parametrize("meta,fragment", [
    ("  sources: [{path: src/a.py, hash: abc}]\n  verified: 2026-11-20\n  basis: observed\n", "revision"),
    ("  sources: [{path: src/a.py, hash: abc}]\n  revision: x\n  basis: observed\n", "verified"),
    ("  sources: [{path: src/a.py, hash: abc}]\n  revision: x\n  verified: 20 Nov\n  basis: observed\n", "verified"),
    ("  sources: [{path: src/a.py, hash: abc}]\n  revision: x\n  verified: 2026-11-20\n", "basis"),
    ("  sources: [{path: src/a.py, hash: abc}]\n  revision: x\n  verified: 2026-11-20\n  basis: guessed\n", "basis"),
    (GOOD_EVIDENCE.replace("src/a.py", "/abs/a.py"), "/abs/a.py"),
    (GOOD_EVIDENCE.replace("src/a.py", "../a.py"), "../a.py"),
    (GOOD_EVIDENCE.replace("src/a.py", "~/a.py"), "~/a.py"),
    (GOOD_EVIDENCE + "  files: [/etc/passwd]\n", "/etc/passwd"),
    (GOOD_EVIDENCE + "  stale_paths: [../x]\n", "../x"),
    ("  sources:\n    - path: /abs/b.py\n      hash: abc\n  revision: x\n  verified: 2026-11-20\n  basis: observed\n",
     "/abs/b.py"),
])
def test_denies_bad_evidence(tmp_path, meta, fragment):
    d, reason = decision(run_hook(write_payload(tmp_path, fm(meta=meta))))
    assert d == "deny"
    assert fragment in reason


def test_denies_name_not_matching_stem(tmp_path):
    d, reason = decision(run_hook(write_payload(tmp_path, fm(name="other"))))
    assert d == "deny" and "my-fact" in reason


@pytest.mark.parametrize("typ", ["error-prevention", "technique"])
def test_denies_missing_confidence(tmp_path, typ):
    d, reason = decision(run_hook(write_payload(tmp_path, fm(typ=typ))))
    assert d == "deny" and "confidence" in reason


def test_denies_adding_stale_fields(tmp_path):
    d, reason = decision(run_hook(write_payload(tmp_path, fm(meta=GOOD_EVIDENCE + "  stale: true\n"))))
    assert d == "deny" and "stale" in reason and "nelly_evidence.py refresh" in reason


def test_denies_changing_stale_fields_via_edit(tmp_path):
    cwd, path = target(tmp_path)
    os.makedirs(os.path.dirname(path))
    old = fm(meta=GOOD_EVIDENCE + "  stale: true\n  stale_since: 2026-11-01\n  stale_paths: [src/a.py]\n")
    with open(path, "w") as fh:
        fh.write(old)
    payload = {"tool_name": "Edit", "cwd": cwd, "tool_input": {
        "file_path": path, "old_string": "stale: true\n", "new_string": ""}}
    d, reason = decision(run_hook(payload))
    assert d == "deny" and "stale" in reason


def test_allows_valid_evidence_write(tmp_path):
    assert decision(run_hook(write_payload(tmp_path, fm(meta=GOOD_EVIDENCE))))[0] is None


def test_allows_rewrite_that_keeps_existing_stale_fields(tmp_path):
    cwd, path = target(tmp_path)
    os.makedirs(os.path.dirname(path))
    meta = GOOD_EVIDENCE + "  stale: true\n  stale_since: 2026-11-01\n  stale_paths: [src/a.py]\n"
    with open(path, "w") as fh:
        fh.write(fm(meta=meta))
    payload = {"tool_name": "Write", "cwd": cwd, "tool_input": {
        "file_path": path, "content": fm(meta=meta).replace("body", "new body")}}
    assert decision(run_hook(payload))[0] is None


def test_allows_legacy_entry_without_sources(tmp_path):
    assert decision(run_hook(write_payload(tmp_path, fm())))[0] is None


def test_edit_applied_to_existing_content_is_checked(tmp_path):
    cwd, path = target(tmp_path)
    os.makedirs(os.path.dirname(path))
    with open(path, "w") as fh:
        fh.write(fm(meta=GOOD_EVIDENCE))
    bad = {"tool_name": "Edit", "cwd": cwd, "tool_input": {
        "file_path": path, "old_string": "  basis: observed\n", "new_string": ""}}
    d, reason = decision(run_hook(bad))
    assert d == "deny" and "basis" in reason
    ok = {"tool_name": "Edit", "cwd": cwd, "tool_input": {
        "file_path": path, "old_string": "body", "new_string": "changed"}}
    assert decision(run_hook(ok))[0] is None


def test_multiedit_applied_sequentially(tmp_path):
    cwd, path = target(tmp_path)
    os.makedirs(os.path.dirname(path))
    with open(path, "w") as fh:
        fh.write(fm(meta=GOOD_EVIDENCE))
    payload = {"tool_name": "MultiEdit", "cwd": cwd, "tool_input": {"file_path": path, "edits": [
        {"old_string": "body", "new_string": "ok"},
        {"old_string": "verified: 2026-11-20", "new_string": "verified: soon"}]}}
    assert decision(run_hook(payload))[0] == "deny"


@pytest.mark.parametrize("kw", [
    {"name": "MEMORY"}, {"name": "GLOBAL-MEMORY"}, {"sub": "research-digest"},
])
def test_skips_files_owned_elsewhere(tmp_path, kw):
    content = fm(name="zzz", meta="  sources: [{path: /abs, hash: x}]\n")
    assert decision(run_hook(write_payload(tmp_path, content, **kw)))[0] is None


def test_skips_index_json(tmp_path):
    payload = write_payload(tmp_path, fm(name="zzz", meta="  sources: [{path: /abs, hash: x}]\n"))
    payload["tool_input"]["file_path"] = os.path.join(os.path.dirname(os.path.dirname(
        payload["tool_input"]["file_path"])), "nelly-index.json")
    assert decision(run_hook(payload))[0] is None


def test_skips_non_memory_path(tmp_path):
    content = fm(name="zzz", meta="  sources: [{path: /abs, hash: x}]\n")
    assert decision(run_hook(write_payload(tmp_path, content, inside=False)))[0] is None


def test_gate_off_and_bad_payloads_fail_open(tmp_path):
    bad = write_payload(tmp_path, fm(name="other"))
    assert decision(run_hook(bad, env={"NELLY_GATE": "off"}))[0] is None
    junk = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True)
    assert decision(junk)[0] is None
    assert decision(run_hook({"tool_name": "Write", "tool_input": {}}))[0] is None
    assert decision(run_hook(write_payload(tmp_path, "no frontmatter here")))[0] is None
    assert decision(run_hook(write_payload(tmp_path, "---\nname: x\nno closing")))[0] is None


LEGACY_BAD = fm(name="my-fact", typ="technique", meta="  files: [/abs/old.py]\n")  # no confidence, abs path


def _existing(tmp_path, content):
    cwd, path = target(tmp_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(content)
    return cwd, path


def test_body_only_edit_of_legacy_nonconforming_entry_is_allowed(tmp_path):
    cwd, path = _existing(tmp_path, LEGACY_BAD)
    payload = {"tool_name": "Edit", "cwd": cwd, "tool_input": {
        "file_path": path, "old_string": "body", "new_string": "better body"}}
    assert decision(run_hook(payload))[0] is None


def test_edit_adding_new_violation_to_legacy_entry_is_denied(tmp_path):
    cwd, path = _existing(tmp_path, LEGACY_BAD)
    payload = {"tool_name": "Edit", "cwd": cwd, "tool_input": {
        "file_path": path, "old_string": "  files: [/abs/old.py]\n",
        "new_string": "  files: [/abs/old.py, ~/new.py]\n"}}
    d, reason = decision(run_hook(payload))
    assert d == "deny" and "~/new.py" in reason


def test_edit_on_missing_target_is_a_write_of_new_string(tmp_path):
    cwd, path = target(tmp_path)
    bad = {"tool_name": "Edit", "cwd": cwd, "tool_input": {
        "file_path": path, "old_string": "", "new_string": fm(name="other")}}
    assert decision(run_hook(bad))[0] == "deny"
    ok = {"tool_name": "Edit", "cwd": cwd, "tool_input": {
        "file_path": path, "old_string": "", "new_string": fm()}}
    assert decision(run_hook(ok))[0] is None


def test_replace_all_turning_source_path_absolute_is_denied(tmp_path):
    cwd, path = _existing(tmp_path, fm(meta=GOOD_EVIDENCE))
    payload = {"tool_name": "Edit", "cwd": cwd, "tool_input": {
        "file_path": path, "old_string": "src/a.py", "new_string": "/etc/a.py", "replace_all": True}}
    d, reason = decision(run_hook(payload))
    assert d == "deny" and "/etc/a.py" in reason


def test_edit_with_missing_old_string_gives_no_decision(tmp_path):
    cwd, path = _existing(tmp_path, fm(meta=GOOD_EVIDENCE))
    payload = {"tool_name": "Edit", "cwd": cwd, "tool_input": {
        "file_path": path, "old_string": "not-in-file", "new_string": "/abs"}}
    assert decision(run_hook(payload))[0] is None
