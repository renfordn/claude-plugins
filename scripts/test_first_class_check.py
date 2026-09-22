#!/usr/bin/env python3
"""Tests for scripts/first_class_check.py (stdlib unittest, mirrors
shared/test_*.py style — no new dependency).
"""
import io
import json
import os
import shutil
import tempfile
import unittest

from first_class_check import (
    evaluate_collection,
    evaluate_plugin,
    is_declared_absent,
    main,
    plugins_missing_from_ci_matrix,
)


class DeclaredAbsentTests(unittest.TestCase):
    def test_declared_absent_recognized_value_suppresses(self):
        plugin_json = {"first_class": {"declared_absent": ["hooks"]}}
        self.assertTrue(is_declared_absent(plugin_json, "hooks"))

    def test_declared_absent_missing_field_defaults_to_empty_list(self):
        plugin_json = {"name": "agent-tdd"}
        self.assertFalse(is_declared_absent(plugin_json, "hooks"))
        self.assertFalse(is_declared_absent(plugin_json, "commands"))

    def test_declared_absent_unrecognized_value_does_not_suppress_anything(self):
        plugin_json = {"first_class": {"declared_absent": ["typo-component"]}}
        self.assertFalse(is_declared_absent(plugin_json, "hooks"))
        self.assertFalse(is_declared_absent(plugin_json, "commands"))
        self.assertFalse(is_declared_absent(plugin_json, "skills"))
        self.assertFalse(is_declared_absent(plugin_json, "agents"))
        self.assertFalse(is_declared_absent(plugin_json, "INTEROP.md"))

    def test_declared_absent_tests_is_never_suppressible_even_if_declared(self):
        plugin_json = {"first_class": {"declared_absent": ["tests"]}}
        self.assertFalse(is_declared_absent(plugin_json, "tests"))


MARKETPLACE_FIXTURE = {
    "name": "renfordn-plugins",
    "plugins": [
        {"name": "agent-cache-plugin", "source": "./agent-cache-plugin"},
        {"name": "agent-isdd", "source": "./agent-isdd"},
        {"name": "agent-tdd", "source": "./agent-tdd"},
    ],
}

WORKFLOW_FIXTURE_MISSING_ONE = """\
name: Tests
jobs:
  python-tests:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        plugin: [agent-isdd, agent-tdd, shared]
    steps:
      - uses: actions/checkout@v4
"""

WORKFLOW_FIXTURE_ALL_PRESENT = """\
name: Tests
jobs:
  python-tests:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        plugin: [agent-isdd, agent-tdd, agent-cache-plugin, shared]
    steps:
      - uses: actions/checkout@v4
"""


class CiMatrixDiffTests(unittest.TestCase):
    def _write_fixtures(self, tmp, workflow_text):
        marketplace_path = os.path.join(tmp, "marketplace.json")
        workflow_path = os.path.join(tmp, "tests.yml")
        with open(marketplace_path, "w") as f:
            json.dump(MARKETPLACE_FIXTURE, f)
        with open(workflow_path, "w") as f:
            f.write(workflow_text)
        return marketplace_path, workflow_path

    def test_matrix_diff_detects_known_missing_plugin(self):
        with tempfile.TemporaryDirectory() as tmp:
            marketplace_path, workflow_path = self._write_fixtures(
                tmp, WORKFLOW_FIXTURE_MISSING_ONE
            )
            missing = plugins_missing_from_ci_matrix(marketplace_path, workflow_path)
            self.assertEqual(missing, ["agent-cache-plugin"])

    def test_matrix_diff_empty_when_all_plugins_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            marketplace_path, workflow_path = self._write_fixtures(
                tmp, WORKFLOW_FIXTURE_ALL_PRESENT
            )
            missing = plugins_missing_from_ci_matrix(marketplace_path, workflow_path)
            self.assertEqual(missing, [])


class EvaluatePluginTests(unittest.TestCase):
    """Red tests for evaluate_plugin(plugin_dir, plugin_json) -> list[ItemResult].

    ItemResult is whatever small structure Green defines (namedtuple/dataclass);
    these tests assert on its fields by name (`.item_id`, `.status`, `.evidence`),
    not positional unpacking, so Green has freedom in the exact type.

    Design choice for CI-02 (the only Mechanical=Y rubric item whose pass
    condition depends on the external `deployment-ops-plugin:plugin-validate`
    tool being available): evaluate_plugin() accepts an optional keyword
    parameter `plugin_validate_available: bool = True`. Green must define
    evaluate_plugin(plugin_dir, plugin_json, plugin_validate_available=True)
    and use that flag -- rather than probing the real environment -- to decide
    CI-02's status: False -> "SKIPPED", never "PASS", never omitted from the
    results list.
    """

    VALID_PLUGIN_JSON = {
        "name": "fixture-plugin",
        "version": "1.2.3",
        "description": "A fixture plugin for tests.",
        "author": "renfordn",
        "homepage": "https://example.com",
        "keywords": ["fixture"],
        "license": "MIT",
    }

    LICENSE_TEXT = "MIT License fixture text\n"

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_complete_plugin_dir(self):
        plugin_dir = os.path.join(self.tmp, "fixture-plugin")
        os.makedirs(os.path.join(plugin_dir, ".claude-plugin"))
        os.makedirs(os.path.join(plugin_dir, "hooks"))
        os.makedirs(os.path.join(plugin_dir, "commands"))
        os.makedirs(os.path.join(plugin_dir, "skills"))
        os.makedirs(os.path.join(plugin_dir, "agents"))
        os.makedirs(os.path.join(plugin_dir, "tests"))
        with open(os.path.join(plugin_dir, "INTEROP.md"), "w") as f:
            f.write("# Interop\n")
        with open(os.path.join(plugin_dir, "CHANGELOG.md"), "w") as f:
            f.write("# Changelog\n\n## 1.2.3\n\nInitial release.\n")
        with open(os.path.join(plugin_dir, "LICENSE"), "w") as f:
            f.write(self.LICENSE_TEXT)
        with open(os.path.join(plugin_dir, "tests", "test_fixture.py"), "w") as f:
            f.write("def test_ok():\n    assert True\n")
        with open(os.path.join(plugin_dir, ".claude-plugin", "plugin.json"), "w") as f:
            json.dump(self.VALID_PLUGIN_JSON, f)
        return plugin_dir

    def _find(self, results, item_id):
        matches = [r for r in results if r.item_id == item_id]
        self.assertEqual(
            len(matches), 1,
            f"expected exactly one result for {item_id}, got {len(matches)}: {results}",
        )
        return matches[0]

    def test_all_present_fixture_scores_every_item_pass(self):
        plugin_dir = self._make_complete_plugin_dir()
        results = evaluate_plugin(plugin_dir, self.VALID_PLUGIN_JSON)
        self.assertTrue(results, "evaluate_plugin returned no results")
        for result in results:
            self.assertEqual(
                result.status, "PASS", f"{result.item_id} expected PASS, got {result.status}"
            )

    def test_missing_interop_without_declared_absent_fails(self):
        plugin_dir = self._make_complete_plugin_dir()
        os.remove(os.path.join(plugin_dir, "INTEROP.md"))
        plugin_json = dict(self.VALID_PLUGIN_JSON)  # no "first_class" key at all
        results = evaluate_plugin(plugin_dir, plugin_json)
        interop_result = self._find(results, "CONS-01")
        self.assertEqual(interop_result.status, "FAIL")

    def test_missing_interop_with_declared_absent_is_na(self):
        plugin_dir = self._make_complete_plugin_dir()
        os.remove(os.path.join(plugin_dir, "INTEROP.md"))
        plugin_json = dict(self.VALID_PLUGIN_JSON)
        plugin_json["first_class"] = {"declared_absent": ["INTEROP.md"]}
        results = evaluate_plugin(plugin_dir, plugin_json)
        interop_result = self._find(results, "CONS-01")
        self.assertEqual(interop_result.status, "N/A")

    def test_malformed_plugin_json_fails_manifest_item_but_does_not_crash(self):
        plugin_dir = self._make_complete_plugin_dir()
        # A naive `plugin_json["name"]`-style access would raise on None --
        # evaluate_plugin must not let that propagate.
        results = evaluate_plugin(plugin_dir, None)
        self.assertTrue(
            results, "evaluate_plugin returned no results despite malformed plugin_json"
        )
        manifest_result = self._find(results, "CONS-07")
        self.assertEqual(manifest_result.status, "FAIL")
        self.assertTrue(
            any(r.status == "FAIL" for r in results),
            "expected at least one FAIL result among the items evaluate_plugin could score",
        )

    def test_ci02_skipped_when_plugin_validate_unavailable(self):
        plugin_dir = self._make_complete_plugin_dir()
        results = evaluate_plugin(
            plugin_dir, self.VALID_PLUGIN_JSON, plugin_validate_available=False
        )
        ci02_result = self._find(results, "CI-02")
        self.assertEqual(ci02_result.status, "SKIPPED")


class CollectionEvaluationTests(unittest.TestCase):
    """Red tests for evaluate_collection(repo_root) -> list[ItemResult].

    Covers ONBOARD-01/02, COLL-01/02/03, CI-01 (per-plugin, exploded from the
    same matrix diff as COLL-02), and CONS-08's real collection-wide
    byte-identical-LICENSE check (the item evaluate_plugin's per-plugin
    "present and non-empty" proxy explicitly defers).
    """

    DEFAULT_PLUGINS = ["agent-isdd", "agent-tdd", "agent-cache-plugin"]
    DEFAULT_LICENSE_TEXT = "MIT License fixture text\n"

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _build_repo(
        self,
        plugin_names=None,
        marketplace_names=None,
        matrix_names=None,
        readme_names=None,
        readme_has_install_link=True,
        install_doc_names=None,
        license_contents=None,
    ):
        plugin_names = plugin_names if plugin_names is not None else self.DEFAULT_PLUGINS
        marketplace_names = marketplace_names if marketplace_names is not None else plugin_names
        matrix_names = matrix_names if matrix_names is not None else plugin_names
        readme_names = readme_names if readme_names is not None else plugin_names
        install_doc_names = install_doc_names if install_doc_names is not None else plugin_names
        license_contents = license_contents or {}

        os.makedirs(os.path.join(self.tmp, ".claude-plugin"))
        with open(os.path.join(self.tmp, ".claude-plugin", "marketplace.json"), "w") as f:
            json.dump(
                {
                    "name": "renfordn-plugins",
                    "plugins": [{"name": n, "source": f"./{n}"} for n in marketplace_names],
                },
                f,
            )

        for name in plugin_names:
            plugin_dir = os.path.join(self.tmp, name)
            os.makedirs(os.path.join(plugin_dir, ".claude-plugin"))
            with open(os.path.join(plugin_dir, ".claude-plugin", "plugin.json"), "w") as f:
                json.dump({"name": name, "version": "1.0.0"}, f)
            with open(os.path.join(plugin_dir, "LICENSE"), "w") as f:
                f.write(license_contents.get(name, self.DEFAULT_LICENSE_TEXT))

        os.makedirs(os.path.join(self.tmp, ".github", "workflows"))
        matrix_list = ", ".join(matrix_names)
        with open(os.path.join(self.tmp, ".github", "workflows", "tests.yml"), "w") as f:
            f.write(
                "jobs:\n  python-tests:\n    strategy:\n      matrix:\n"
                f"        plugin: [{matrix_list}]\n"
            )

        readme_lines = ["# claude-plugins\n\n"]
        if readme_has_install_link:
            readme_lines.append(
                "See [docs/install-and-verify.md](./docs/install-and-verify.md).\n\n"
            )
        for name in readme_names:
            readme_lines.append(f"- `{name}/` — a plugin\n")
        with open(os.path.join(self.tmp, "README.md"), "w") as f:
            f.write("".join(readme_lines))

        os.makedirs(os.path.join(self.tmp, "docs"))
        install_doc_lines = ["# Install and Verify\n\n"]
        for name in install_doc_names:
            install_doc_lines.append(f"claude plugin install {name}@renfordn-plugins\n")
        with open(os.path.join(self.tmp, "docs", "install-and-verify.md"), "w") as f:
            f.write("".join(install_doc_lines))

        return self.tmp

    def _find(self, results, item_id, plugin=None):
        matches = [r for r in results if r.item_id == item_id and (plugin is None or r.plugin == plugin)]
        self.assertEqual(
            len(matches), 1,
            f"expected exactly one result for {item_id}/{plugin}, got {len(matches)}: {results}",
        )
        return matches[0]

    def test_coll01_passes_when_marketplace_and_directories_agree(self):
        repo_root = self._build_repo()
        results = evaluate_collection(repo_root)
        self.assertEqual(self._find(results, "COLL-01").status, "PASS")

    def test_coll01_fails_when_marketplace_lists_a_missing_directory(self):
        repo_root = self._build_repo(
            plugin_names=["agent-isdd", "agent-tdd"],
            marketplace_names=["agent-isdd", "agent-tdd", "ghost-plugin"],
            matrix_names=["agent-isdd", "agent-tdd", "ghost-plugin"],
            readme_names=["agent-isdd", "agent-tdd", "ghost-plugin"],
            install_doc_names=["agent-isdd", "agent-tdd", "ghost-plugin"],
        )
        results = evaluate_collection(repo_root)
        self.assertEqual(self._find(results, "COLL-01").status, "FAIL")

    def test_coll02_fails_when_a_plugin_is_missing_from_ci_matrix(self):
        repo_root = self._build_repo(matrix_names=["agent-isdd", "agent-tdd"])
        results = evaluate_collection(repo_root)
        coll02 = self._find(results, "COLL-02")
        self.assertEqual(coll02.status, "FAIL")
        self.assertIn("agent-cache-plugin", coll02.evidence)

    def test_ci01_is_exploded_per_plugin_from_the_same_matrix_diff(self):
        repo_root = self._build_repo(matrix_names=["agent-isdd", "agent-tdd"])
        results = evaluate_collection(repo_root)
        self.assertEqual(self._find(results, "CI-01", plugin="agent-cache-plugin").status, "FAIL")
        self.assertEqual(self._find(results, "CI-01", plugin="agent-isdd").status, "PASS")
        self.assertEqual(self._find(results, "CI-01", plugin="agent-tdd").status, "PASS")

    def test_coll03_fails_when_readme_omits_a_marketplace_plugin(self):
        repo_root = self._build_repo(readme_names=["agent-isdd", "agent-tdd"])
        results = evaluate_collection(repo_root)
        self.assertEqual(self._find(results, "COLL-03").status, "FAIL")

    def test_coll03_passes_when_readme_lists_every_marketplace_plugin(self):
        repo_root = self._build_repo()
        results = evaluate_collection(repo_root)
        self.assertEqual(self._find(results, "COLL-03").status, "PASS")

    def test_onboard01_fails_when_readme_has_no_install_link(self):
        repo_root = self._build_repo(readme_has_install_link=False)
        results = evaluate_collection(repo_root)
        self.assertEqual(self._find(results, "ONBOARD-01").status, "FAIL")

    def test_onboard01_passes_when_readme_links_install_doc(self):
        repo_root = self._build_repo(readme_has_install_link=True)
        results = evaluate_collection(repo_root)
        self.assertEqual(self._find(results, "ONBOARD-01").status, "PASS")

    def test_onboard02_fails_when_install_doc_missing_a_plugin_command(self):
        repo_root = self._build_repo(install_doc_names=["agent-isdd", "agent-tdd"])
        results = evaluate_collection(repo_root)
        onboard02 = self._find(results, "ONBOARD-02")
        self.assertEqual(onboard02.status, "FAIL")
        self.assertIn("agent-cache-plugin", onboard02.evidence)

    def test_cons08_collection_passes_when_all_licenses_byte_identical(self):
        repo_root = self._build_repo()
        results = evaluate_collection(repo_root)
        self.assertEqual(self._find(results, "CONS-08").status, "PASS")

    def test_cons08_collection_fails_when_a_license_diverges(self):
        repo_root = self._build_repo(
            license_contents={"agent-cache-plugin": "Apache License fixture text\n"}
        )
        results = evaluate_collection(repo_root)
        cons08 = self._find(results, "CONS-08")
        self.assertEqual(cons08.status, "FAIL")


class CliMainTests(unittest.TestCase):
    """Red tests for main(argv, stream) -> int (exit code)."""

    PLUGIN_NAMES = ["plugin-a", "plugin-b"]
    LICENSE_TEXT = "MIT License fixture text\n"

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_complete_plugin(self, name, version="1.0.0"):
        plugin_dir = os.path.join(self.tmp, name)
        os.makedirs(os.path.join(plugin_dir, ".claude-plugin"))
        for d in ("hooks", "commands", "skills", "agents", "tests"):
            os.makedirs(os.path.join(plugin_dir, d))
        with open(os.path.join(plugin_dir, "INTEROP.md"), "w") as f:
            f.write("# Interop\n")
        with open(os.path.join(plugin_dir, "CHANGELOG.md"), "w") as f:
            f.write(f"# Changelog\n\n## {version}\n\nInitial release.\n")
        with open(os.path.join(plugin_dir, "LICENSE"), "w") as f:
            f.write(self.LICENSE_TEXT)
        with open(os.path.join(plugin_dir, "tests", "test_fixture.py"), "w") as f:
            f.write("def test_ok():\n    assert True\n")
        plugin_json = {
            "name": name,
            "version": version,
            "description": "fixture",
            "author": "renfordn",
            "homepage": "https://example.com",
            "keywords": ["fixture"],
            "license": "MIT",
        }
        with open(os.path.join(plugin_dir, ".claude-plugin", "plugin.json"), "w") as f:
            json.dump(plugin_json, f)
        return plugin_dir

    def _build_passing_repo(self):
        for name in self.PLUGIN_NAMES:
            self._write_complete_plugin(name)

        os.makedirs(os.path.join(self.tmp, ".claude-plugin"))
        marketplace_path = os.path.join(self.tmp, ".claude-plugin", "marketplace.json")
        with open(marketplace_path, "w") as f:
            json.dump(
                {
                    "name": "fixture-marketplace",
                    "plugins": [{"name": n, "source": f"./{n}"} for n in self.PLUGIN_NAMES],
                },
                f,
            )

        os.makedirs(os.path.join(self.tmp, ".github", "workflows"))
        with open(os.path.join(self.tmp, ".github", "workflows", "tests.yml"), "w") as f:
            f.write(
                "jobs:\n  python-tests:\n    strategy:\n      matrix:\n"
                f"        plugin: [{', '.join(self.PLUGIN_NAMES)}]\n"
            )

        with open(os.path.join(self.tmp, "README.md"), "w") as f:
            f.write(
                "See [install](./docs/install-and-verify.md).\n\n"
                + "".join(f"- `{n}/` — a plugin\n" for n in self.PLUGIN_NAMES)
            )

        os.makedirs(os.path.join(self.tmp, "docs"))
        with open(os.path.join(self.tmp, "docs", "install-and-verify.md"), "w") as f:
            f.write("".join(f"claude plugin install {n}@renfordn-plugins\n" for n in self.PLUGIN_NAMES))

        return marketplace_path

    def test_main_exits_zero_on_all_passing_fixture(self):
        marketplace_path = self._build_passing_repo()
        stream = io.StringIO()
        exit_code = main(["--marketplace", marketplace_path], stream=stream)
        self.assertEqual(exit_code, 0, stream.getvalue())

    def test_main_exits_one_when_a_mechanical_item_fails(self):
        marketplace_path = self._build_passing_repo()
        os.remove(os.path.join(self.tmp, self.PLUGIN_NAMES[0], "INTEROP.md"))
        stream = io.StringIO()
        exit_code = main(["--marketplace", marketplace_path], stream=stream)
        self.assertEqual(exit_code, 1)

    def test_main_json_output_is_valid_json(self):
        marketplace_path = self._build_passing_repo()
        stream = io.StringIO()
        main(["--marketplace", marketplace_path, "--json"], stream=stream)
        payload = json.loads(stream.getvalue())
        self.assertIsInstance(payload, list)
        self.assertTrue(all({"plugin", "item_id", "status", "evidence"} <= set(row) for row in payload))

    def test_main_ci02_always_skipped_never_fake_pass(self):
        marketplace_path = self._build_passing_repo()
        stream = io.StringIO()
        main(["--marketplace", marketplace_path, "--json"], stream=stream)
        payload = json.loads(stream.getvalue())
        ci02_rows = [row for row in payload if row["item_id"] == "CI-02"]
        self.assertTrue(ci02_rows)
        self.assertTrue(all(row["status"] == "SKIPPED" for row in ci02_rows))


if __name__ == "__main__":
    unittest.main()
