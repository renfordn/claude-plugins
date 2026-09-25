#!/usr/bin/env python3
"""Find (and with --delete, remove) non-account copies of this repo's plugins under ~/.claude.

This repo's plugins should only run as the account copies the Claude app syncs (`<plugin>@inline`
in the app, `~/.claude/plugins/synced/` for the terminal `claude`), so every machine runs the same
version. Anything else is a leftover that can shadow or duplicate them:

    marketplace-cache    ~/.claude/plugins/cache/<marketplace>/<plugin>/
    marketplace-data     ~/.claude/plugins/data/<plugin>-<marketplace>/   (not -inline / -synced)
    retired-data         ~/.claude/plugins/data/<plugin>-{inline,synced}/ for a plugin named in
                         --plugins that is no longer in the repo
    repo-clone           any git clone of this repo under ~/.claude/plugins/ (old harness bootstraps)
    user-skill           ~/.claude/skills/<name>/ byte-identical to a repo plugin's skills/<name>/
    user-agent           ~/.claude/agents/<name>.md byte-identical to a repo plugin's agents/<name>.md
    marketplace-install  <plugin>@<marketplace> in installed_plugins.json -- reported with the
                         `claude plugin uninstall` command, never edited here

Account copies (the synced/ tree, -inline/-synced data of plugins still in the repo) and anything
that differs from the repo (a locally edited skill) are never touched.

Usage:
    python3 scripts/clean_local_plugin_copies.py [--plugins agent-nelly agent-ux] [--delete]
        [--home DIR]   # default: ~/.claude

Dry run by default. Exit status: 0 nothing (left) to clean, 1 copies found and not deleted.

Stdlib only.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_HOME = os.path.expanduser("~/.claude")
ACCOUNT_SUFFIXES = ("inline", "synced")
IGNORED_NAMES = {"__pycache__", ".DS_Store", ".pytest_cache"}


def repo_plugins(repo):
    """Names of plugin directories in the repo (a directory with .claude-plugin/plugin.json)."""
    return sorted(n for n in os.listdir(repo)
                  if os.path.isfile(os.path.join(repo, n, ".claude-plugin", "plugin.json")))


def _norm_remote(url):
    url = (url or "").strip().rstrip("/").lower()
    return url[:-4] if url.endswith(".git") else url


def _origin(path):
    try:
        out = subprocess.run(["git", "-C", path, "remote", "get-url", "origin"],
                             capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def _tree_digest(path):
    """Content hash of a file or directory tree, ignoring caches."""
    h = hashlib.sha256()
    if os.path.isfile(path):
        with open(path, "rb") as f:
            h.update(f.read())
        return h.hexdigest()
    for root, dirs, files in os.walk(path):
        dirs[:] = sorted(d for d in dirs if d not in IGNORED_NAMES)
        for name in sorted(f for f in files if f not in IGNORED_NAMES):
            full = os.path.join(root, name)
            h.update(os.path.relpath(full, path).encode() + b"\0")
            with open(full, "rb") as f:
                h.update(f.read())
    return h.hexdigest()


def _repo_clones(plugins_dir, remote, max_depth=3):
    found = []
    base_depth = plugins_dir.rstrip(os.sep).count(os.sep)
    for root, dirs, _ in os.walk(plugins_dir):
        if root == plugins_dir:
            dirs[:] = [d for d in dirs if d != "synced"]
        if ".git" in dirs:
            if _norm_remote(_origin(root)) == remote:
                found.append(root)
            dirs[:] = []
            continue
        if root.count(os.sep) - base_depth >= max_depth:
            dirs[:] = []
    return found


def find_copies(repo, home, plugins=None, remote=None):
    """[{"kind", "path", "plugin", "hint"?}] for every non-account copy found."""
    in_repo = set(repo_plugins(repo))
    scope = list(plugins) if plugins else sorted(in_repo)
    remote = _norm_remote(remote if remote is not None else _origin(repo))
    plugins_dir = os.path.join(home, "plugins")
    copies = []

    cache = os.path.join(plugins_dir, "cache")
    if os.path.isdir(cache):
        for mkt in sorted(os.listdir(cache)):
            for p in scope:
                path = os.path.join(cache, mkt, p)
                if os.path.isdir(path):
                    copies.append({"kind": "marketplace-cache", "path": path, "plugin": p})

    data = os.path.join(plugins_dir, "data")
    if os.path.isdir(data):
        for name in sorted(os.listdir(data)):
            for p in scope:
                if not name.startswith(p + "-"):
                    continue
                suffix = name[len(p) + 1:]
                if suffix not in ACCOUNT_SUFFIXES:
                    copies.append({"kind": "marketplace-data", "path": os.path.join(data, name), "plugin": p})
                elif p not in in_repo:
                    copies.append({"kind": "retired-data", "path": os.path.join(data, name), "plugin": p})

    if remote and os.path.isdir(plugins_dir):
        for path in _repo_clones(plugins_dir, remote):
            copies.append({"kind": "repo-clone", "path": path, "plugin": "*"})

    for p in scope:
        if p not in in_repo:
            continue
        for kind, sub, home_sub in (("user-skill", "skills", "skills"), ("user-agent", "agents", "agents")):
            src_dir = os.path.join(repo, p, sub)
            if not os.path.isdir(src_dir):
                continue
            for name in sorted(os.listdir(src_dir)):
                src, dst = os.path.join(src_dir, name), os.path.join(home, home_sub, name)
                if name in IGNORED_NAMES or not os.path.exists(dst):
                    continue
                if os.path.isdir(src) != os.path.isdir(dst) or _tree_digest(src) != _tree_digest(dst):
                    continue
                copies.append({"kind": kind, "path": dst, "plugin": p})

    installed_path = os.path.join(plugins_dir, "installed_plugins.json")
    try:
        with open(installed_path) as f:
            installed = json.load(f)
    except (OSError, ValueError):
        installed = {}
    for key in sorted((installed.get("plugins") or {}) if isinstance(installed, dict) else {}):
        name = key.split("@", 1)[0]
        if name in scope:
            copies.append({"kind": "marketplace-install", "path": installed_path, "plugin": name,
                           "hint": f"claude plugin uninstall {key}"})
    return copies


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--plugins", nargs="+",
                        help="Only these plugins (default: all in the repo). Retired names allowed.")
    parser.add_argument("--home", default=DEFAULT_HOME, help="Claude config dir (default ~/.claude).")
    parser.add_argument("--delete", action="store_true", help="Remove what's found (default: dry run).")
    parser.add_argument("--repo", default=REPO_ROOT, help=argparse.SUPPRESS)
    parser.add_argument("--remote", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    copies = find_copies(args.repo, args.home, args.plugins, args.remote)
    if not copies:
        print("No non-account plugin copies found.")
        return 0
    left = 0
    for c in copies:
        if c["kind"] == "marketplace-install":
            print(f"  {c['kind']:<19} {c['plugin']}: run `{c['hint']}`")
            left += 1
        elif args.delete:
            if not os.path.lexists(c["path"]):  # already gone with an enclosing copy
                continue
            (shutil.rmtree if os.path.isdir(c["path"]) else os.remove)(c["path"])
            print(f"  deleted {c['kind']:<19} {c['path']}")
        else:
            print(f"  {c['kind']:<19} {c['path']}")
            left += 1
    if left and not args.delete:
        print("\nDry run -- re-run with --delete to remove these.")
    return 1 if left else 0


if __name__ == "__main__":
    sys.exit(main())
