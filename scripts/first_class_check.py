#!/usr/bin/env python3
"""Repo-wide "first class" mechanical checker for the Claude-Plugins collection.

Read-only: never imports, executes, or modifies any plugin file. Stdlib-only
(no new pip/npm dependency), mirroring shared/'s existing no-dependency
convention. Enumerates plugins from .claude-plugin/marketplace.json so a new
plugin is picked up automatically, no code change required.

Rubric item ID -> implementing function (see docs/first-class-rubric.md for
the full pass conditions):

  CONS-01..CONS-07,09,10 -> evaluate_plugin()
  CONS-08 (per-plugin proxy) -> evaluate_plugin(); CONS-08 (real, collection-wide) -> evaluate_collection()
  ONBOARD-01/02       -> evaluate_collection()
  CI-01               -> evaluate_collection() (per-plugin, exploded from plugins_missing_from_ci_matrix())
  CI-02               -> evaluate_plugin()
  RUN-01              -> evaluate_plugin()
  COLL-01/02/03       -> evaluate_collection()

CONS-08 design note: LICENSE-content-identical-across-the-collection (the
rubric's full pass condition) cannot be scored from a single evaluate_plugin()
call -- it has no cross-plugin context. This function's CONS-08 check is
therefore a per-plugin proxy ("LICENSE file present and non-empty"); the full
byte-identical-across-all-plugins comparison is deferred to
evaluate_collection() (Phase 5), which has the whole-collection view needed to
do it properly.

CI-02 design note: deployment-ops-plugin:plugin-validate is a Claude Code
skill, not a subprocess-callable CLI (confirmed in design.md's Research
Basis) -- there is no real invocation this standalone script can perform.
evaluate_plugin() takes plugin_validate_available as a plain keyword flag
(testability seam; Phase 5's main() decides the real value). When True, this
currently records PASS as a placeholder rather than genuine tool output; when
False, it records SKIPPED, never PASS, never omitted.

This module is built up incrementally, phase by phase, per
tasks.md's 9-phase slice plan. Functions not yet implemented are not present
in this file until their phase lands.
"""

import argparse
import hashlib
import json
import os
import re
import sys
from collections import namedtuple

ItemResult = namedtuple("ItemResult", ["plugin", "item_id", "status", "evidence"])

# Fixed enum of structural/component names a plugin may declare intentionally
# absent via first_class.declared_absent in its own plugin.json. "tests" is
# deliberately excluded -- every plugin must have tests, no escape hatch.
DECLARED_ABSENT_ENUM = frozenset({"hooks", "commands", "skills", "agents", "INTEROP.md"})


def is_declared_absent(plugin_json: dict, component: str) -> bool:
    """Return True iff `component` is validly declared absent by this plugin.

    Fails closed: a component not in DECLARED_ABSENT_ENUM (e.g. "tests", or a
    typo) never suppresses a check, even if present in the plugin's own
    declared_absent array.
    """
    if component not in DECLARED_ABSENT_ENUM:
        return False
    first_class = plugin_json.get("first_class", {})
    if not isinstance(first_class, dict):
        return False
    declared = first_class.get("declared_absent", [])
    if not isinstance(declared, list):
        return False
    return component in declared


# Matches the `plugin: [a, b, c]` matrix line inside tests.yml's python-tests
# job. Deliberately stdlib regex, not PyYAML -- PyYAML is not a declared
# dependency anywhere in this repo (no requirements*.txt references it, CI's
# python-tests job only `pip install pytest`), so importing it here would be
# a new dependency this checker is not allowed to add.
_MATRIX_PLUGIN_RE = re.compile(r"plugin:\s*\[([^\]]*)\]")

# A plugin doesn't have to run through the python-tests matrix to have real CI
# coverage: a top-level job named exactly after the plugin (e.g.
# agent-cache-plugin's own Node/npm job) is equivalent coverage, just via a
# different job. Matches a job key at 2-space indent, the level every job in
# this repo's tests.yml is defined at.
_JOB_NAME_RE = re.compile(r"^  ([a-zA-Z0-9_-]+):\s*$", re.MULTILINE)


def plugins_missing_from_ci_matrix(marketplace_path: str, workflow_path: str) -> list:
    """Return marketplace.json plugin names with no CI coverage in
    workflow_path -- neither in the python-tests matrix.plugin list nor as
    their own equivalent top-level job (e.g. a Node plugin's own npm job) --
    in marketplace.json's own order."""
    with open(marketplace_path) as f:
        marketplace = json.load(f)
    plugin_names = [p["name"] for p in marketplace.get("plugins", [])]

    with open(workflow_path) as f:
        workflow_text = f.read()

    match = _MATRIX_PLUGIN_RE.search(workflow_text)
    matrix_names = set()
    if match:
        matrix_names = {name.strip() for name in match.group(1).split(",") if name.strip()}

    job_names = set(_JOB_NAME_RE.findall(workflow_text))

    return [name for name in plugin_names if name not in matrix_names and name not in job_names]


REQUIRED_MANIFEST_FIELDS = ["name", "version", "description", "author", "homepage", "keywords", "license"]
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")

# Patterns for CONS-09 "no stray root-level status/history docs" -- mirrors
# the concrete files confirmed in design.md's Research Basis (agent-cache-plugin's
# FOLLOW_UP_ITEMS.md / MARKETPLACE_SUBMISSION.md / SHIPPING_CHECKLIST.md /
# V1.3_RELEASE_NOTES.md / tasks.md; agent-nelly's CONTINUATION_GUIDE.md /
# SLICE_IMPLEMENTATION_STATUS.md / tasks.md).
#
# STRUCTURE.md is deliberately NOT in this list: for agent-cache-plugin it is
# load-bearing, not stray -- plugin-harness/orchestrator/schema_extractor.py
# and interop_parser.py both read it as this plugin's actual INTEROP.md
# equivalent (a real Capabilities/phase_state_cache contract lives in it),
# and agent-cache-plugin/tests/manifest-migration.test.js asserts its
# content directly. A generic "*_STRUCTURE.md is always stray" pattern was
# wrong -- confirmed by cross-reference search before removing it here.
_STRAY_DOC_PATTERNS = [
    re.compile(r".*_STATUS\.md$"),
    re.compile(r".*_CHECKLIST\.md$"),
    re.compile(r".*_NOTES\.md$"),
    re.compile(r".*_SUBMISSION\.md$"),
    re.compile(r".*_ITEMS\.md$"),
    re.compile(r"^CONTINUATION_GUIDE\.md$"),
    re.compile(r"^tasks\.md$"),
]


def _find_stray_docs(plugin_dir: str) -> list:
    try:
        entries = os.listdir(plugin_dir)
    except OSError:
        return []
    return sorted(
        name
        for name in entries
        if os.path.isfile(os.path.join(plugin_dir, name))
        and any(p.match(name) for p in _STRAY_DOC_PATTERNS)
    )


def _has_tests(plugin_dir: str) -> bool:
    if os.path.isdir(os.path.join(plugin_dir, "tests")):
        return True
    for root, dirs, files in os.walk(plugin_dir):
        dirs[:] = [d for d in dirs if d != "node_modules"]
        for name in files:
            if (name.startswith("test_") and name.endswith(".py")) or name.endswith(".test.js"):
                return True
    return False


def _check_component_presence(
    plugin_dir: str, plugin_name: str, safe_plugin_json: dict, component: str, item_id: str
) -> ItemResult:
    path = os.path.join(plugin_dir, component)
    exists = os.path.isfile(path) if component == "INTEROP.md" else os.path.isdir(path)
    if exists:
        return ItemResult(plugin_name, item_id, "PASS", path)
    if is_declared_absent(safe_plugin_json, component):
        return ItemResult(
            plugin_name, item_id, "N/A", f"declared absent via first_class.declared_absent: {component}"
        )
    return ItemResult(plugin_name, item_id, "FAIL", f"not found: {path}")


def _check_manifest_schema(plugin_name: str, plugin_json) -> ItemResult:
    if not isinstance(plugin_json, dict):
        return ItemResult(plugin_name, "CONS-07", "FAIL", "plugin.json missing or not a JSON object")
    missing = [f for f in REQUIRED_MANIFEST_FIELDS if f not in plugin_json]
    if missing:
        return ItemResult(plugin_name, "CONS-07", "FAIL", f"missing fields: {missing}")
    version = str(plugin_json.get("version", ""))
    if not _SEMVER_RE.match(version):
        return ItemResult(plugin_name, "CONS-07", "FAIL", f"version {version!r} is not semver")
    return ItemResult(plugin_name, "CONS-07", "PASS", "all required fields present, version is semver")


def _check_changelog_present(plugin_dir: str, plugin_name: str) -> ItemResult:
    path = os.path.join(plugin_dir, "CHANGELOG.md")
    status = "PASS" if os.path.isfile(path) else "FAIL"
    return ItemResult(plugin_name, "CONS-06", status, path)


def _check_license_present_nonempty(plugin_dir: str, plugin_name: str) -> ItemResult:
    path = os.path.join(plugin_dir, "LICENSE")
    if not os.path.isfile(path):
        return ItemResult(plugin_name, "CONS-08", "FAIL", f"{path} not found")
    if os.path.getsize(path) == 0:
        return ItemResult(plugin_name, "CONS-08", "FAIL", f"{path} is empty")
    return ItemResult(
        plugin_name, "CONS-08", "PASS",
        f"{path} present and non-empty (cross-plugin byte-diff deferred to evaluate_collection)",
    )


def _check_no_stray_docs(plugin_dir: str, plugin_name: str) -> ItemResult:
    stray = _find_stray_docs(plugin_dir)
    if stray:
        return ItemResult(plugin_name, "CONS-09", "FAIL", f"stray docs: {stray}")
    return ItemResult(plugin_name, "CONS-09", "PASS", "no stray root-level status/history docs")


def _check_tests_present(plugin_dir: str, plugin_name: str) -> ItemResult:
    if _has_tests(plugin_dir):
        return ItemResult(plugin_name, "CONS-10", "PASS", "test suite discovered")
    return ItemResult(
        plugin_name, "CONS-10", "FAIL",
        "no tests/ dir or test_*.py / *.test.js files found (never declarable absent)",
    )


def _check_changelog_matches_version(
    plugin_dir: str, plugin_name: str, safe_plugin_json: dict, manifest_ok: bool
) -> ItemResult:
    if not manifest_ok:
        return ItemResult(plugin_name, "RUN-01", "FAIL", "cannot determine version: plugin.json missing/malformed")
    version = str(safe_plugin_json.get("version", ""))
    if not version:
        return ItemResult(plugin_name, "RUN-01", "FAIL", "plugin.json has no version field")
    changelog_path = os.path.join(plugin_dir, "CHANGELOG.md")
    if not os.path.isfile(changelog_path):
        return ItemResult(plugin_name, "RUN-01", "FAIL", f"{changelog_path} not found")
    with open(changelog_path) as f:
        content = f.read()
    if version in content:
        return ItemResult(plugin_name, "RUN-01", "PASS", f"CHANGELOG.md references version {version}")
    return ItemResult(plugin_name, "RUN-01", "FAIL", f"CHANGELOG.md does not mention version {version}")


def _check_plugin_validate(plugin_name: str, plugin_validate_available: bool) -> ItemResult:
    if not plugin_validate_available:
        return ItemResult(
            plugin_name, "CI-02", "SKIPPED",
            "deployment-ops-plugin:plugin-validate not available in this environment",
        )
    # See module docstring's CI-02 design note: no real subprocess invocation
    # is possible for a Claude Code skill; this is a documented placeholder.
    return ItemResult(plugin_name, "CI-02", "PASS", "plugin_validate_available=True (placeholder score)")


def evaluate_plugin(plugin_dir: str, plugin_json, plugin_validate_available: bool = True) -> list:
    """Evaluate every CONS-* and RUN-01/CI-02 mechanical rubric item for one
    plugin. Never raises on a malformed/missing plugin_json -- scores CONS-07
    FAIL and continues evaluating every other item (per requirements' Unwanted-
    behavior EARS line)."""
    plugin_name = os.path.basename(os.path.normpath(plugin_dir))
    manifest_ok = isinstance(plugin_json, dict)
    safe_plugin_json = plugin_json if manifest_ok else {}

    results = [_check_manifest_schema(plugin_name, plugin_json)]

    for component, item_id in (
        ("INTEROP.md", "CONS-01"),
        ("hooks", "CONS-02"),
        ("commands", "CONS-03"),
        ("skills", "CONS-04"),
        ("agents", "CONS-05"),
    ):
        results.append(
            _check_component_presence(plugin_dir, plugin_name, safe_plugin_json, component, item_id)
        )

    results.append(_check_changelog_present(plugin_dir, plugin_name))
    results.append(_check_license_present_nonempty(plugin_dir, plugin_name))
    results.append(_check_no_stray_docs(plugin_dir, plugin_name))
    results.append(_check_tests_present(plugin_dir, plugin_name))
    results.append(_check_changelog_matches_version(plugin_dir, plugin_name, safe_plugin_json, manifest_ok))
    results.append(_check_plugin_validate(plugin_name, plugin_validate_available))

    return results


# Used as the `plugin` field on ItemResults that score a whole-collection item
# rather than a single plugin (COLL-*, ONBOARD-*, the real CONS-08 check).
COLLECTION_PLUGIN = "<collection>"


def _load_marketplace_plugin_names(marketplace_path: str) -> list:
    with open(marketplace_path) as f:
        marketplace = json.load(f)
    return [p["name"] for p in marketplace.get("plugins", [])]


def _plugin_dirs_with_manifest(repo_root: str) -> list:
    names = []
    for entry in sorted(os.listdir(repo_root)):
        full = os.path.join(repo_root, entry)
        if os.path.isdir(full) and os.path.isfile(os.path.join(full, ".claude-plugin", "plugin.json")):
            names.append(entry)
    return names


def _check_coll01(repo_root: str, marketplace_names: list) -> ItemResult:
    disk_names = set(_plugin_dirs_with_manifest(repo_root))
    marketplace_set = set(marketplace_names)
    if disk_names == marketplace_set:
        return ItemResult(
            COLLECTION_PLUGIN, "COLL-01", "PASS", "marketplace.json matches on-disk plugin directories 1:1"
        )
    only_marketplace = sorted(marketplace_set - disk_names)
    only_disk = sorted(disk_names - marketplace_set)
    return ItemResult(
        COLLECTION_PLUGIN, "COLL-01", "FAIL",
        f"marketplace-only: {only_marketplace}, disk-only: {only_disk}",
    )


def _check_coll02_and_ci01(marketplace_path: str, workflow_path: str, marketplace_names: list):
    missing = plugins_missing_from_ci_matrix(marketplace_path, workflow_path)
    coll02 = ItemResult(
        COLLECTION_PLUGIN, "COLL-02", "FAIL" if missing else "PASS",
        f"missing from CI matrix: {missing}" if missing else "every marketplace plugin is in the CI matrix",
    )
    ci01_results = [
        ItemResult(
            name, "CI-01", "FAIL" if name in missing else "PASS",
            "missing from tests.yml matrix.plugin" if name in missing
            else "present in tests.yml matrix.plugin",
        )
        for name in marketplace_names
    ]
    return coll02, ci01_results


def _check_coll03(readme_path: str, marketplace_names: list) -> ItemResult:
    try:
        with open(readme_path) as f:
            readme_text = f.read()
    except OSError:
        return ItemResult(COLLECTION_PLUGIN, "COLL-03", "FAIL", f"{readme_path} not found")
    missing = [name for name in marketplace_names if f"`{name}/`" not in readme_text]
    if missing:
        return ItemResult(COLLECTION_PLUGIN, "COLL-03", "FAIL", f"README.md does not list: {missing}")
    return ItemResult(COLLECTION_PLUGIN, "COLL-03", "PASS", "README.md lists every marketplace plugin")


def _check_onboard01(readme_path: str) -> ItemResult:
    try:
        with open(readme_path) as f:
            readme_text = f.read()
    except OSError:
        return ItemResult(COLLECTION_PLUGIN, "ONBOARD-01", "FAIL", f"{readme_path} not found")
    if "install-and-verify" in readme_text:
        return ItemResult(COLLECTION_PLUGIN, "ONBOARD-01", "PASS", f"{readme_path} links install-and-verify.md")
    return ItemResult(
        COLLECTION_PLUGIN, "ONBOARD-01", "FAIL", f"{readme_path} does not link docs/install-and-verify.md"
    )


def _check_onboard02(install_doc_path: str, marketplace_names: list) -> ItemResult:
    try:
        with open(install_doc_path) as f:
            doc_text = f.read()
    except OSError:
        return ItemResult(COLLECTION_PLUGIN, "ONBOARD-02", "FAIL", f"{install_doc_path} not found")
    missing = [
        name for name in marketplace_names
        if f"claude plugin install {name}@renfordn-plugins" not in doc_text
    ]
    if missing:
        return ItemResult(COLLECTION_PLUGIN, "ONBOARD-02", "FAIL", f"missing install command for: {missing}")
    return ItemResult(
        COLLECTION_PLUGIN, "ONBOARD-02", "PASS", "install command present for every marketplace plugin"
    )


def _check_cons08_collection(repo_root: str, marketplace_names: list) -> ItemResult:
    """The rubric's real CONS-08 pass condition: LICENSE content byte-identical
    across every plugin. evaluate_plugin()'s per-plugin CONS-08 is a weaker
    present+non-empty proxy (documented there) -- this is the authoritative
    score for the audit."""
    hashes = {}
    missing = []
    for name in marketplace_names:
        license_path = os.path.join(repo_root, name, "LICENSE")
        if not os.path.isfile(license_path):
            missing.append(name)
            continue
        with open(license_path, "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        hashes.setdefault(digest, []).append(name)
    if missing:
        return ItemResult(COLLECTION_PLUGIN, "CONS-08", "FAIL", f"LICENSE missing for: {missing}")
    if len(hashes) == 1:
        return ItemResult(
            COLLECTION_PLUGIN, "CONS-08", "PASS", "LICENSE content is byte-identical across all plugins"
        )
    groups = {digest[:8]: names for digest, names in hashes.items()}
    return ItemResult(
        COLLECTION_PLUGIN, "CONS-08", "FAIL",
        f"LICENSE content diverges across {len(hashes)} distinct contents: {groups}",
    )


def evaluate_collection(
    repo_root: str,
    marketplace_path: str = None,
    workflow_path: str = None,
    readme_path: str = None,
    install_doc_path: str = None,
) -> list:
    """Evaluate every collection-level mechanical rubric item (ONBOARD-01/02,
    COLL-01/02/03, CI-01 per-plugin exploded from the same matrix diff as
    COLL-02, and CONS-08's real byte-identical-across-all-plugins check)
    against the whole repo.

    Paths default to their conventional locations under repo_root so callers
    normally only need to pass repo_root; each is overridable for testing."""
    marketplace_path = marketplace_path or os.path.join(repo_root, ".claude-plugin", "marketplace.json")
    workflow_path = workflow_path or os.path.join(repo_root, ".github", "workflows", "tests.yml")
    readme_path = readme_path or os.path.join(repo_root, "README.md")
    install_doc_path = install_doc_path or os.path.join(repo_root, "docs", "install-and-verify.md")

    marketplace_names = _load_marketplace_plugin_names(marketplace_path)

    results = [_check_coll01(repo_root, marketplace_names)]
    coll02, ci01_results = _check_coll02_and_ci01(marketplace_path, workflow_path, marketplace_names)
    results.append(coll02)
    results.extend(ci01_results)
    results.append(_check_coll03(readme_path, marketplace_names))
    results.append(_check_onboard01(readme_path))
    results.append(_check_onboard02(install_doc_path, marketplace_names))
    results.append(_check_cons08_collection(repo_root, marketplace_names))

    return results


def _load_plugin_json_safe(plugin_dir: str):
    path = os.path.join(plugin_dir, ".claude-plugin", "plugin.json")
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _run_all_checks(marketplace_path: str) -> list:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(marketplace_path)))
    marketplace_names = _load_marketplace_plugin_names(marketplace_path)

    results = list(evaluate_collection(repo_root, marketplace_path=marketplace_path))
    for name in marketplace_names:
        plugin_dir = os.path.join(repo_root, name)
        plugin_json = _load_plugin_json_safe(plugin_dir)
        # plugin_validate_available is always False on the real CLI path --
        # deployment-ops-plugin:plugin-validate is a Claude Code skill, never
        # subprocess-callable from a standalone script (see module docstring's
        # CI-02 design note). True would make CI-02 score a fake PASS
        # placeholder on every real run, silently misinforming the audit.
        # The keyword itself stays a pure testability seam for unit tests.
        results.extend(evaluate_plugin(plugin_dir, plugin_json, plugin_validate_available=False))
    return results


def _print_human_table(results: list, stream) -> None:
    stream.write(f"{'plugin':<24} {'item_id':<10} {'status':<8} evidence\n")
    for r in results:
        stream.write(f"{r.plugin:<24} {r.item_id:<10} {r.status:<8} {r.evidence}\n")


def main(argv=None, stream=None) -> int:
    """CLI entry point. Exits (returns) 1 iff any mechanical item is FAIL, 0
    otherwise -- SKIPPED/N/A/PASS never fail the run."""
    stream = stream if stream is not None else sys.stdout
    parser = argparse.ArgumentParser(description="First-class plugin collection mechanical checker.")
    parser.add_argument(
        "--marketplace",
        default=os.path.join(".claude-plugin", "marketplace.json"),
        help="Path to marketplace.json (default: .claude-plugin/marketplace.json)",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of a table.")
    args = parser.parse_args(argv)

    results = _run_all_checks(args.marketplace)

    if args.json:
        stream.write(json.dumps([r._asdict() for r in results], indent=2))
        stream.write("\n")
    else:
        _print_human_table(results, stream)

    return 1 if any(r.status == "FAIL" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
