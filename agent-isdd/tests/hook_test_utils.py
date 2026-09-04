"""Shared test helpers for hooks/*.py's black-box test suite.

Every hook runs as a real subprocess in production (invoked via hooks.json), so tests spawn the
same subprocess rather than importing and monkeypatching each module -- this exercises the exact
code path production uses and needs no per-module mock/reset bookkeeping between tests.

Assumed baseline: Python 3.11 (see .github/workflows/tests.yml -- nothing in this repo pinned a
version before this test suite existed).

Isolation: hooks resolve ~/.claude/sdd-memory/ via os.path.expanduser("~"), which reads the HOME
environment variable on POSIX. Every test that could reach that resolution MUST pass
env_extra={"HOME": <temp_home() path>} to run_hook()/run_sdd_memory_cli() -- omitting it risks
silently touching the real ~/.claude/sdd-memory/ tree during a test run.
"""
import contextlib
import json
import os
import re
import subprocess
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS_DIR = os.path.join(REPO_ROOT, "hooks")


def project_slug_for(path):
    """Mirrors hooks/sdd_memory.py's project_slug() exactly, for building test fixtures
    at the same location a real hook run would resolve to under a given HOME."""
    absp = os.path.abspath(path)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", absp).strip("-").lower()
    return slug or "root"


def feature_spec_dir(home, cwd, feature_slug="2020-01-01-test-feature"):
    """Create and return <home>/.claude/sdd-memory/<project_slug(cwd)>/spec/<feature_slug>/,
    the same location active_state_file()/find_state_files() would look under given HOME=home."""
    slug = project_slug_for(cwd)
    d = os.path.join(home, ".claude", "sdd-memory", slug, "spec", feature_slug)
    os.makedirs(d, exist_ok=True)
    return d


def run_hook(name, payload, cwd=None, env_extra=None, timeout=10):
    """Run hooks/<name> as a subprocess, feeding payload (a dict) as JSON on stdin.

    Returns (decision_or_None, returncode). decision_or_None is the parsed
    hookSpecificOutput dict when stdout is non-empty JSON, else None -- matching every
    hook's own allow()/deny()-vs-no_decision() convention.
    """
    script = os.path.join(HOOKS_DIR, name)
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)

    result = subprocess.run(
        ["python3", script],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=cwd or REPO_ROOT,
        env=env,
        timeout=timeout,
    )

    stdout = result.stdout.strip()
    if not stdout:
        return None, result.returncode
    try:
        data = json.loads(stdout)
    except (json.JSONDecodeError, ValueError):
        return None, result.returncode
    return data.get("hookSpecificOutput"), result.returncode


def run_hook_message(name, payload, cwd=None, env_extra=None, timeout=10):
    """Like run_hook(), but for the hook family that emits {"systemMessage": ...} rather than
    {"hookSpecificOutput": {"permissionDecision": ...}} -- post_write_check.py, stop_check.py,
    precompact_snapshot.py, subagent_report.py. Two distinct response shapes exist in this
    codebase (permission-decision hooks vs. informational-reminder hooks); this plugin's own
    hooks already split cleanly along that line, so two narrow helpers stay clearer than one
    that tries to cover both shapes.

    Returns (systemMessage_str_or_None, returncode).
    """
    script = os.path.join(HOOKS_DIR, name)
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)

    result = subprocess.run(
        ["python3", script],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=cwd or REPO_ROOT,
        env=env,
        timeout=timeout,
    )

    stdout = result.stdout.strip()
    if not stdout:
        return None, result.returncode
    try:
        data = json.loads(stdout)
    except (json.JSONDecodeError, ValueError):
        return None, result.returncode
    return data.get("systemMessage"), result.returncode


def run_sdd_memory_cli(args, cwd=None, env_extra=None, timeout=10):
    """Run hooks/sdd_memory.py's CLI (argv-based, not stdin-based like every other hook).

    Returns (stdout_stripped, returncode).
    """
    script = os.path.join(HOOKS_DIR, "sdd_memory.py")
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)

    result = subprocess.run(
        ["python3", script] + list(args),
        capture_output=True,
        text=True,
        cwd=cwd or REPO_ROOT,
        env=env,
        timeout=timeout,
    )
    return result.stdout.strip(), result.returncode


@contextlib.contextmanager
def temp_home():
    """A throwaway directory standing in for HOME, isolating ~/.claude/sdd-memory/ resolution."""
    with tempfile.TemporaryDirectory() as d:
        yield d


@contextlib.contextmanager
def temp_git_repo(with_plugin_dirs=False):
    """A throwaway git repo with a configured identity (CI runners have none by default).

    with_plugin_dirs=True also creates empty skills/agents/commands/hooks/ subdirectories,
    for tests that need the repo to "look like" this plugin (see hooks/commit_audit_gate.py's
    _looks_like_this_plugin check).
    """
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["git", "init", "-q"], cwd=d, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=d, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=d, check=True)
        if with_plugin_dirs:
            for name in ("skills", "agents", "commands", "hooks"):
                os.makedirs(os.path.join(d, name), exist_ok=True)
        yield d


def seed_state_file(feature_dir, **fields):
    """Write a minimal workflow-state.md into feature_dir with the given `- Field: value` lines.

    Matches sdd_state.parse_state's `- Field: value` convention -- section headers are cosmetic
    only, parse_state regexes any such line regardless of which section it's under.
    """
    os.makedirs(feature_dir, exist_ok=True)
    lines = ["# Workflow State: Test Feature", "", "## Current State", ""]
    for key, value in fields.items():
        pretty_key = key.replace("_", " ").title()
        lines.append(f"- {pretty_key}: {value}")
    path = os.path.join(feature_dir, "workflow-state.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return path
