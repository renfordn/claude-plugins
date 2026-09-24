"""Tests for scripts/check_account_plugins.py (stdlib unittest, mirrors test_merge_plugin_data.py)."""
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

from check_account_plugins import account_copies, compare, main, repo_versions


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)


class CheckAccountPluginsTests(unittest.TestCase):
    def setUp(self):
        base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, base)
        self.repo = os.path.join(base, "repo")
        self.app = os.path.join(base, "app")
        self.rpm = os.path.join(self.app, "local-agent-mode-sessions", "acct", "org", "rpm")
        for name, version in (("agent-nelly", "0.4.16"), ("agent-isdd", "0.1.58"), ("agent-tdd", "0.2.16")):
            _write_json(os.path.join(self.repo, name, ".claude-plugin", "plugin.json"),
                        {"name": name, "version": version})

    def _account(self, plugins):
        entries = []
        for i, (name, version) in enumerate(plugins):
            pid = f"plugin_{i}"
            _write_json(os.path.join(self.rpm, pid, ".claude-plugin", "plugin.json"),
                        {"name": name, "version": version})
            entries.append({"id": pid, "name": name, "updatedAt": "2026-09-24T18:08:12Z",
                            "marketplaceName": "claude-plugins"})
        _write_json(os.path.join(self.rpm, "manifest.json"), {"plugins": entries})

    def _run(self, *extra):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(["--repo", self.repo, "--app-data", self.app, *extra])
        return code, out.getvalue(), err.getvalue()

    def test_reads_repo_and_account_versions(self):
        self._account([("agent-nelly", "0.4.14"), ("whatsapp-followup", "1.0.0")])
        self.assertEqual(repo_versions(self.repo)["agent-isdd"], "0.1.58")
        copies = account_copies(self.app)
        self.assertEqual(copies["agent-nelly"][0]["version"], "0.4.14")
        self.assertEqual(copies["agent-nelly"][0]["marketplace"], "claude-plugins")

    def test_statuses(self):
        self._account([("agent-nelly", "0.4.16"), ("agent-isdd", "0.1.55")])
        rows = {r["plugin"]: r["status"] for r in compare(repo_versions(self.repo), account_copies(self.app))}
        self.assertEqual(rows, {"agent-nelly": "current", "agent-isdd": "stale", "agent-tdd": "missing"})

    def test_exit_zero_when_selected_plugins_current(self):
        self._account([("agent-nelly", "0.4.16"), ("agent-isdd", "0.1.55")])
        code, out, _ = self._run("--plugins", "agent-nelly")
        self.assertEqual(code, 0)
        self.assertIn("All checked account copies match the repo.", out)

    def test_exit_one_and_guidance_when_stale(self):
        self._account([("agent-nelly", "0.4.16"), ("agent-isdd", "0.1.55")])
        code, out, _ = self._run("--plugins", "agent-nelly", "agent-isdd")
        self.assertEqual(code, 1)
        self.assertIn("agent-isdd", out)
        self.assertIn("Re-sync the account's plugin marketplace", out)

    def test_exit_two_when_no_account_copies(self):
        code, _, err = self._run()
        self.assertEqual(code, 2)
        self.assertIn("No account plugin copies found", err)

    def test_json_output(self):
        self._account([("agent-nelly", "0.4.16")])
        code, out, _ = self._run("--plugins", "agent-nelly", "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)[0]["status"], "current")


if __name__ == "__main__":
    unittest.main()
