"""Slice 28: invocation control frontmatter."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def frontmatter(rel):
    text = (ROOT / rel).read_text(encoding="utf-8")
    assert text.startswith("---\n")
    block = text.split("---\n", 2)[1]
    fm, key = {}, None
    for line in block.splitlines():
        if line[:1] in (" ", "\t") or not line.strip():
            if key:
                fm[key] += " " + line.strip()
            continue
        key, _, val = line.partition(":")
        fm[key.strip()] = val.strip()
    return fm


@pytest.mark.parametrize("rel", ["commands/isdd-rewind.md", "commands/isdd-board-sync.md"])
def test_destructive_commands_disable_model_invocation(rel):
    fm = frontmatter(rel)
    assert fm.get("disable-model-invocation") == "true"
    assert fm.get("description")


def test_pickup_forks_into_explore_and_stays_model_invocable():
    fm = frontmatter("skills/isdd-pickup/SKILL.md")
    assert fm.get("context") == "fork"
    assert fm.get("agent") == "Explore"
    assert "disable-model-invocation" not in fm
    assert fm.get("description")


def _pickup_body():
    return (ROOT / "skills/isdd-pickup/SKILL.md").read_text(encoding="utf-8").split("---\n", 2)[2]


def test_pickup_body_has_no_write_instructions_for_the_fork():
    body = _pickup_body()
    for bad in (r"cat\s*>", r"\brm\s", r"<<\s*EOF", r"\bmkdir\b", r"\btee\s"):
        assert not re.search(bad, body), bad


def test_pickup_hands_lock_claim_and_release_to_main_session():
    body = _pickup_body()
    assert "Main-session actions" in body
    assert "AskUserQuestion" in body
    assert "session-lock.json" in body
    for field in ("session_id", "worktree", "feature", "claimed_at", "expires_at"):
        assert field in body
    low = body.lower()
    assert "main session" in low and "release" in low
    assert "never writes" in low


def _bash_blocks(body):
    return re.findall(r"```bash\n(.*?)```", body, re.S)


def test_pickup_fork_commands_cannot_write_or_create_dirs():
    body = _pickup_body()
    assert not re.search(r"\btouch\b", body)
    assert "--spec-path" not in body  # creates directories (sdd_memory.spec_dir makedirs)
    assert "--path" not in body
    blocks = _bash_blocks(body)
    assert blocks
    for block in blocks:
        assert ">" not in block, block  # no redirects in the fork's shell commands


def test_pickup_claim_rereads_lock_and_uses_show_toplevel():
    body = _pickup_body()
    assert "re-read" in body.lower()
    assert "expires_at is" in body and "do not overwrite" in body
    assert "git rev-parse --show-toplevel" in body
    assert "first path" not in body


def test_pickup_main_session_block_is_a_literal_template_with_release():
    body = _pickup_body()
    m = re.search(r"```text\nMain-session actions\n(.*?)```", body, re.S)
    assert m, "Main-session actions must be a fenced literal template"
    t = m.group(1)
    assert "AskUserQuestion" in t and "session-lock.json" in t and "Release" in t


def test_pickup_single_staleness_rule_and_intro_does_not_manage_locks():
    body = _pickup_body()
    assert "> 2 hours" not in body and "2 hours" not in body
    assert body.count("force-claim rule") == 1  # defined once, in Overlap prevention
    assert "does not manage locks itself" in body
