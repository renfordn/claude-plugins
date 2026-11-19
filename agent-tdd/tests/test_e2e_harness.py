import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "e2e_harness.py"
spec = importlib.util.spec_from_file_location("e2e_harness", SCRIPT)
eh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eh)


def touch(root, rel, text=""):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


class IsUiPath(unittest.TestCase):
    def test_ui_paths(self):
        for rel in [
            "src/Button.tsx", "a/b.jsx", "x.vue", "x.svelte", "index.html", "s.css",
            "s.scss", "s.less", "m.erb", "m.hbs", "m.jinja", "m.jinja2", "m.njk",
            "templates/base.html", "app/templates/x.erb",
            "src/components/Foo.ts", "src/components/Foo.js", "src/pages/index.tsx",
            "views/a.vue", "app/page.tsx",
            "Sources/HomeView.swift", "ui/HomeScreen.kt",
        ]:
            self.assertTrue(eh.is_ui_path(rel), rel)

    def test_new_formats(self):
        for rel in [
            "v/a.haml", "v/a.slim", "v/a.razor", "v/a.cshtml", "v/a.astro", "v/a.ejs",
            "v/a.pug", "v/a.twig", "v/a.liquid", "v/a.sass", "v/a.styl",
            "ios/Main.storyboard", "ios/Cell.xib",
            "app/src/main/res/layout/activity_main.xml",
            "lib/widgets/button.dart", "lib/screens/home.dart", "lib/pages/x.dart",
        ]:
            self.assertTrue(eh.is_ui_path(rel), rel)

    def test_non_ui_paths(self):
        for rel in [
            "src/util.ts", "app/models/user.rb", "app/server.py", "components/data.json",
            "Sources/Model.swift", "ui/Home.kt", "README.md", "docs/guide.html",
            "src/Button.test.tsx", "src/Button.spec.tsx", "tests/test_x.py",
            "components/__tests__/Foo.ts", "docs/components/Foo.tsx", "templates/README.md",
            "app/__tests__/page.tsx", "HomeViewTests.swift", "HomeView.test.swift",
            "templates/base.txt",
        ]:
            self.assertFalse(eh.is_ui_path(rel), rel)

    def test_backend_negatives(self):
        for rel in [
            "app/layout.js", "app/actions.ts", "app/lib/db.ts", "app/api/users.ts",
            "src/pages/index.js", "pages/api/hello.ts", "views/a.ts", "views/helper.js",
            "components/api/client.ts", "src/models/user.tsx", "src/controllers/a.ts",
            "src/services/a.ts", "server/render.tsx", "src/routes/a.tsx",
            "app/users/route.ts", "app/users/route.js", "middleware.ts", "src/middleware.js",
            "lib/util.dart", "lib/widgets_helper/a.dart", "widgets/a.dart",
            "app/src/main/res/values/strings.xml", "config/layout/a.xml",
        ]:
            self.assertFalse(eh.is_ui_path(rel), rel)

    def test_fixture_build_mail_negatives(self):
        for rel in [
            "fixtures/page.html", "src/__fixtures__/a.html", "testdata/x.css",
            "coverage/index.html", "htmlcov/index.html", "dist/app.css", "build/x.html",
            "out/index.html", ".next/server/page.html", "app/mailers/welcome.erb",
            "emails/welcome.html", "mail/a.hbs", "user_mailer/welcome.erb",
            "app/views/user_mailer/welcome.html.erb",
        ]:
            self.assertFalse(eh.is_ui_path(rel), rel)


class DetectHarness(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)

    def tearDown(self):
        self.td.cleanup()

    def test_none(self):
        touch(self.root, "package.json", json.dumps({"dependencies": {"react": "1"}}))
        self.assertIsNone(eh.detect_harness(self.root))

    def test_config_files(self):
        for rel, name in [
            ("playwright.config.ts", "playwright"), ("cypress.config.js", "cypress"),
            ("cypress.json", "cypress"), ("wdio.conf.ts", "webdriverio"),
            ("nightwatch.conf.js", "nightwatch"), (".testcaferc.json", "testcafe"),
            (".detoxrc.js", "detox"), (".maestro/flow.yaml", "maestro"),
        ]:
            with tempfile.TemporaryDirectory() as d:
                touch(d, rel)
                r = eh.detect_harness(d)
                self.assertEqual(r["name"], name, rel)
                self.assertIn(rel.split("/")[0], r["evidence"])

    def test_package_json_deps(self):
        for dep, name in [("@playwright/test", "playwright"), ("playwright", "playwright"),
                          ("cypress", "cypress"), ("webdriverio", "webdriverio"),
                          ("puppeteer", "puppeteer"), ("nightwatch", "nightwatch"),
                          ("testcafe", "testcafe"), ("detox", "detox")]:
            for key in ("dependencies", "devDependencies"):
                with tempfile.TemporaryDirectory() as d:
                    touch(d, "package.json", json.dumps({key: {dep: "1"}}))
                    r = eh.detect_harness(d)
                    self.assertEqual(r["name"], name, dep)
                    self.assertIn("package.json", r["evidence"])

    def test_python_and_ruby(self):
        touch(self.root, "requirements-dev.txt", "pytest-playwright==0.4\n")
        self.assertEqual(eh.detect_harness(self.root)["name"], "playwright")
        with tempfile.TemporaryDirectory() as d:
            touch(d, "pyproject.toml", '[project]\ndependencies=["selenium>=4"]\n')
            self.assertEqual(eh.detect_harness(d)["name"], "selenium")
        with tempfile.TemporaryDirectory() as d:
            touch(d, "setup.cfg", "[options]\ntests_require = selenium\n")
            self.assertEqual(eh.detect_harness(d)["name"], "selenium")
        with tempfile.TemporaryDirectory() as d:
            touch(d, "Gemfile", "gem 'capybara'\n")
            self.assertEqual(eh.detect_harness(d)["name"], "capybara")

    def test_workspace_one_level(self):
        touch(self.root, "packages/web/playwright.config.ts")
        r = eh.detect_harness(self.root)
        self.assertEqual(r["name"], "playwright")
        self.assertIn("packages/web", r["evidence"])
        with tempfile.TemporaryDirectory() as d:
            touch(d, "apps/site/package.json", json.dumps({"devDependencies": {"cypress": "1"}}))
            self.assertEqual(eh.detect_harness(d)["name"], "cypress")

    def test_ignores_node_modules_and_deep(self):
        touch(self.root, "node_modules/foo/playwright.config.ts")
        touch(self.root, "packages/a/b/cypress.config.js")
        touch(self.root, "packages/node_modules/x/package.json",
              json.dumps({"dependencies": {"cypress": "1"}}))
        self.assertIsNone(eh.detect_harness(self.root))

    def test_bad_package_json(self):
        touch(self.root, "package.json", "{not json")
        self.assertIsNone(eh.detect_harness(self.root))

    def test_first_level_subdirs_and_e2e_dirs(self):
        touch(self.root, "web/playwright.config.ts")
        r = eh.detect_harness(self.root)
        self.assertEqual((r["name"], r["evidence"]), ("playwright", "web/playwright.config.ts"))
        with tempfile.TemporaryDirectory() as d:
            touch(d, "tests/e2e/cypress.config.js")
            self.assertEqual(eh.detect_harness(d)["evidence"], "tests/e2e/cypress.config.js")
        with tempfile.TemporaryDirectory() as d:
            touch(d, "test/e2e/wdio.conf.ts")
            self.assertEqual(eh.detect_harness(d)["name"], "webdriverio")
        for skip in ("node_modules", ".git", "vendor", "dist", "build"):
            with tempfile.TemporaryDirectory() as d:
                touch(d, f"{skip}/playwright.config.ts")
                self.assertIsNone(eh.detect_harness(d), skip)

    def test_new_signals(self):
        cases = [
            ("setup.py", "tests_require=['playwright']\n", "playwright"),
            ("setup.py", "install_requires=['selenium']\n", "selenium"),
            ("Pipfile", "[dev-packages]\nplaywright = '*'\n", "playwright"),
            ("Pipfile", "[dev-packages]\nselenium = '*'\n", "selenium"),
            ("requirements.txt", "playwright==1.4\n", "playwright"),
            ("requirements-test.txt", "selenium==4\n", "selenium"),
            ("Gemfile", "gem 'selenium-webdriver'\n", "selenium"),
            ("detox.config.js", "", "detox"),
        ]
        for rel, text, name in cases:
            with tempfile.TemporaryDirectory() as d:
                touch(d, rel, text)
                r = eh.detect_harness(d)
                self.assertEqual(r["name"], name, rel)
        with tempfile.TemporaryDirectory() as d:
            touch(d, "package.json", json.dumps({"optionalDependencies": {"cypress": "1"}}))
            self.assertEqual(eh.detect_harness(d)["name"], "cypress")

    def test_comment_lines_ignored(self):
        for rel, text in [
            ("requirements.txt", "# selenium\n  # playwright\nrequests\n"),
            ("Pipfile", "# selenium = '*'\n"),
            ("Gemfile", "# gem 'capybara'\n# gem 'selenium-webdriver'\n"),
        ]:
            with tempfile.TemporaryDirectory() as d:
                touch(d, rel, text)
                self.assertIsNone(eh.detect_harness(d), rel)

    def test_puppeteer_is_library_fallback(self):
        touch(self.root, "package.json", json.dumps({"dependencies": {"puppeteer": "1"}}))
        r = eh.detect_harness(self.root)
        self.assertEqual(r["name"], "puppeteer")
        self.assertIn("library, not a test runner", r["evidence"])
        # a real harness elsewhere wins over an earlier puppeteer hit
        touch(self.root, "web/playwright.config.ts")
        self.assertEqual(eh.detect_harness(self.root)["name"], "playwright")
        # and within one package.json
        with tempfile.TemporaryDirectory() as d:
            touch(d, "package.json", json.dumps({"dependencies": {"puppeteer": "1", "cypress": "1"}}))
            self.assertEqual(eh.detect_harness(d)["name"], "cypress")

    def test_deterministic_order(self):
        touch(self.root, "zeta/cypress.config.js")
        touch(self.root, "alpha/playwright.config.ts")
        for _ in range(3):
            self.assertEqual(eh.detect_harness(self.root)["name"], "playwright")
        # root beats tests/e2e beats first-level subdirs
        touch(self.root, "tests/e2e/wdio.conf.ts")
        self.assertEqual(eh.detect_harness(self.root)["name"], "webdriverio")
        touch(self.root, "nightwatch.conf.js")
        self.assertEqual(eh.detect_harness(self.root)["name"], "nightwatch")


class Cli(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)

    def test_ui(self):
        r = self.run_cli("ui", "a.tsx", "b.py", "c.css")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(json.loads(r.stdout), ["a.tsx", "c.css"])
        r = self.run_cli("ui", "b.py")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(json.loads(r.stdout), [])

    def test_harness(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.run_cli("harness", d)
            self.assertEqual(r.returncode, 1)
            self.assertEqual(json.loads(r.stdout), {"harness": None})
            touch(d, "playwright.config.ts")
            r = self.run_cli("harness", d)
            self.assertEqual(r.returncode, 0)
            self.assertEqual(json.loads(r.stdout)["harness"]["name"], "playwright")

    def test_bad_root(self):
        r = self.run_cli("harness", "/nonexistent/definitely/not/here")
        self.assertEqual(r.returncode, 2)
        self.assertTrue(r.stderr.strip())
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "afile"
            f.write_text("x")
            self.assertEqual(self.run_cli("harness", str(f)).returncode, 2)


if __name__ == "__main__":
    unittest.main()
