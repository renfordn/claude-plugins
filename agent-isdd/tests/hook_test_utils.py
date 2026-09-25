"""Shared test helpers for hooks/*.py's black-box test suite.

Every hook runs as a real subprocess in production (invoked via hooks.json), so tests spawn the
same subprocess rather than importing and monkeypatching each module -- this exercises the exact
code path production uses and needs no per-module mock/reset bookkeeping between tests.

Assumed baseline: Python 3.11 (see .github/workflows/tests.yml -- nothing in this repo pinned a
version before this test suite existed).

Isolation: hooks resolve ${CLAUDE_PLUGIN_DATA}/sdd-memory/ (see hooks/sdd_memory.py's BASE) and
refuse to run without CLAUDE_PLUGIN_DATA. When a test passes env_extra={"HOME": <temp_home()>},
_hook_env() sets CLAUDE_PLUGIN_DATA to <HOME>/.claude/plugins/data/agent-isdd -- the same layout
Claude Code uses -- so fixtures built with feature_spec_dir(home, ...) line up with what the hook
resolves. Without a HOME override the hook inherits conftest.py's throwaway temp dir, never the
real ~/.claude/plugins/data/ tree.
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
    at the same location a real hook run would resolve to under a given HOME (git toplevel of
    path, or path itself outside a repo)."""
    absp = os.path.abspath(path)
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_WORK_TREE")}
    proc = subprocess.run(["git", "-C", absp, "rev-parse", "--show-toplevel"],
                          capture_output=True, text=True, env=env)
    top = proc.stdout.strip()
    if proc.returncode == 0 and top:
        d = absp
        while os.path.realpath(d) != os.path.realpath(top) and os.path.dirname(d) != d:
            d = os.path.dirname(d)
        absp = d if os.path.realpath(d) == os.path.realpath(top) else top
    slug = re.sub(r"[^A-Za-z0-9]+", "-", absp).strip("-").lower()
    return slug or "root"


def make_git_repo(root):
    """git init <root> with one empty commit (so worktrees can be added); returns root."""
    os.makedirs(root, exist_ok=True)
    git = ["git", "-C", root, "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(git[:3] + ["init", "-q"], check=True)
    subprocess.run(git + ["commit", "-q", "--allow-empty", "-m", "init"], check=True)
    return root


def add_git_worktree(repo, path):
    """Add a linked worktree of <repo> at <path>; returns path."""
    subprocess.run(["git", "-C", repo, "worktree", "add", "-q", "--detach", path], check=True)
    return path


def feature_spec_dir(home, cwd, feature_slug="2020-01-01-test-feature"):
    """Create and return <home>/.claude/plugins/data/agent-isdd/sdd-memory/<project_slug(cwd)>/
    spec/<feature_slug>/, the same location active_state_file()/find_state_files() would look
    under given HOME=home (mirrors hooks/sdd_memory.py's BASE with CLAUDE_PLUGIN_DATA set by
    _hook_env() from that HOME)."""
    slug = project_slug_for(cwd)
    d = os.path.join(home, ".claude", "plugins", "data", "agent-isdd", "sdd-memory",
                      slug, "spec", feature_slug)
    os.makedirs(d, exist_ok=True)
    return d


def plugin_data_for(home):
    """The CLAUDE_PLUGIN_DATA a real install would get under HOME=home."""
    return os.path.join(home, ".claude", "plugins", "data", "agent-isdd")


def _hook_env(env_extra):
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
        if "HOME" in env_extra and "CLAUDE_PLUGIN_DATA" not in env_extra:
            env["CLAUDE_PLUGIN_DATA"] = plugin_data_for(env_extra["HOME"])
    return env


def run_hook(name, payload, cwd=None, env_extra=None, timeout=10):
    """Run hooks/<name> as a subprocess, feeding payload (a dict) as JSON on stdin.

    Returns (decision_or_None, returncode). decision_or_None is the parsed
    hookSpecificOutput dict when stdout is non-empty JSON, else None -- matching every
    hook's own allow()/deny()-vs-no_decision() convention.
    """
    script = os.path.join(HOOKS_DIR, name)
    env = _hook_env(env_extra)

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
    env = _hook_env(env_extra)

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
    env = _hook_env(env_extra)

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
    """A throwaway directory standing in for HOME, isolating ${CLAUDE_PLUGIN_DATA}/sdd-memory/ resolution."""
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
