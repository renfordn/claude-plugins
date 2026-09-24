#!/usr/bin/env python3
"""Check that the Claude desktop app's account copies of this repo's plugins match the repo.

Plugins added to your Claude account (the Code tab loads them as `<plugin>@inline`) are not
managed by `claude plugin update`. The desktop app keeps its own copy of each one under

    <app data>/local-agent-mode-sessions/<account>/<org>/rpm/
        manifest.json                 # id, name, server updatedAt, marketplaceName per plugin
        plugin_<id>/.claude-plugin/plugin.json

This script compares every plugin in this repo (a directory with .claude-plugin/plugin.json)
against those copies and reports, per plugin, whether the account copy is current, stale, or
missing. How the account marketplace re-syncs from GitHub and when the app downloads a new
copy isn't documented, so this only verifies -- it never tries to force an update.

Usage:
    python3 scripts/check_account_plugins.py [--plugins agent-nelly agent-isdd] [--json]
        [--app-data DIR]   # default: $CLAUDE_APP_DATA, else ~/Library/Application Support/Claude

Exit status: 0 all checked plugins current, 1 something stale or missing, 2 no account copies
found at all (wrong --app-data, or not signed in on this machine).

Stdlib only.
"""
import argparse
import glob
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_APP_DATA = os.path.expanduser("~/Library/Application Support/Claude")


def _load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def repo_versions(repo_root=REPO_ROOT):
    """{plugin name: version} for every plugin directory in the repo."""
    out = {}
    for manifest in sorted(glob.glob(os.path.join(repo_root, "*", ".claude-plugin", "plugin.json"))):
        data = _load_json(manifest) or {}
        if data.get("name"):
            out[data["name"]] = data.get("version")
    return out


def account_copies(app_data):
    """{plugin name: [copy, ...]} from every rpm/manifest.json under the app data dir.

    A copy is {"version", "updated_at", "marketplace", "rpm_dir", "path"}. There can be more than
    one rpm dir (one per signed-in account/org), so each name maps to a list.
    """
    out = {}
    pattern = os.path.join(app_data, "local-agent-mode-sessions", "*", "*", "rpm", "manifest.json")
    for manifest_path in sorted(glob.glob(pattern)):
        rpm_dir = os.path.dirname(manifest_path)
        manifest = _load_json(manifest_path) or {}
        for entry in manifest.get("plugins", []):
            name, pid = entry.get("name"), entry.get("id")
            if not name or not pid:
                continue
            path = os.path.join(rpm_dir, pid)
            plugin_json = _load_json(os.path.join(path, ".claude-plugin", "plugin.json")) or {}
            out.setdefault(name, []).append({
                "version": plugin_json.get("version"),
                "updated_at": entry.get("updatedAt"),
                "marketplace": entry.get("marketplaceName"),
                "rpm_dir": rpm_dir,
                "path": path,
            })
    return out


def compare(repo, account, only=None):
    """One row per repo plugin: {"plugin", "repo", "account", "updated_at", "marketplace", "status"}.

    status: "current" (every account copy matches the repo version), "stale" (a copy differs),
    or "missing" (no account copy). Plugins in `only` that aren't in the repo are "not-in-repo".
    """
    names = list(only) if only else sorted(repo)
    rows = []
    for name in names:
        if name not in repo:
            rows.append({"plugin": name, "repo": None, "account": None, "updated_at": None,
                         "marketplace": None, "status": "not-in-repo"})
            continue
        copies = account.get(name, [])
        if not copies:
            rows.append({"plugin": name, "repo": repo[name], "account": None, "updated_at": None,
                         "marketplace": None, "status": "missing"})
            continue
        for copy in copies:
            rows.append({
                "plugin": name, "repo": repo[name], "account": copy["version"],
                "updated_at": copy["updated_at"], "marketplace": copy["marketplace"],
                "status": "current" if copy["version"] == repo[name] else "stale",
            })
    return rows


def render(rows):
    headers = ("plugin", "repo", "account", "status", "server updatedAt")
    table = [headers] + [
        (r["plugin"], r["repo"] or "-", r["account"] or "-", r["status"], r["updated_at"] or "-")
        for r in rows
    ]
    widths = [max(len(str(row[i])) for row in table) for i in range(len(headers))]
    lines = ["  ".join(str(c).ljust(w) for c, w in zip(row, widths)).rstrip() for row in table]
    lines.insert(1, "  ".join("-" * w for w in widths))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--plugins", nargs="+", help="Only check these plugins (default: all in the repo).")
    parser.add_argument("--app-data", default=os.environ.get("CLAUDE_APP_DATA", DEFAULT_APP_DATA),
                        help="Claude desktop app data dir.")
    parser.add_argument("--repo", default=REPO_ROOT, help=argparse.SUPPRESS)
    parser.add_argument("--json", action="store_true", help="Print rows as JSON.")
    args = parser.parse_args(argv)

    account = account_copies(args.app_data)
    if not account:
        print(f"No account plugin copies found under {args.app_data} "
              f"(looked for local-agent-mode-sessions/*/*/rpm/manifest.json).", file=sys.stderr)
        return 2
    rows = compare(repo_versions(args.repo), account, args.plugins)
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        print(render(rows))
        behind = [r for r in rows if r["status"] in ("stale", "missing")]
        if behind:
            print(f"\n{len(behind)} account cop{'y is' if len(behind) == 1 else 'ies are'} not on the "
                  f"repo version. Re-sync the account's plugin marketplace, restart the Claude app, "
                  f"then run this again.")
        else:
            print("\nAll checked account copies match the repo.")
    return 0 if all(r["status"] == "current" for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
