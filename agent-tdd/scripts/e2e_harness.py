#!/usr/bin/env python3
"""UI-path classification and e2e harness detection (stdlib only).

CLI:
  e2e_harness.py ui <paths...>      print JSON list of the paths that are UI paths
  e2e_harness.py harness [root]     print JSON {"harness": {name, evidence} | null}

Exit codes: 0 when a UI path matched (ui) or a harness was found (harness);
1 otherwise; 2 for usage errors or a missing/unreadable harness root.

Harness search order (first hit wins, fully deterministic): the root, then
tests/e2e, test/e2e, then the root's first-level subdirs (sorted; skipping
node_modules, .git, vendor, dist, build), then packages/* and apps/* (sorted).
Within a directory: config files, package.json, Python files, Gemfile.
A puppeteer-only hit is a fallback: returned (with a "library, not a test
runner" evidence note) only when no real harness is found anywhere.
"""
import json
import os
import re
import sys
from pathlib import PurePosixPath

UI_EXT = {".tsx", ".jsx", ".vue", ".svelte", ".html", ".css", ".scss", ".less", ".sass",
          ".styl", ".astro"}
TEMPLATE_EXT = {".erb", ".hbs", ".jinja", ".jinja2", ".njk", ".haml", ".slim", ".razor",
                ".cshtml", ".ejs", ".pug", ".twig", ".liquid", ".storyboard", ".xib"}
DOC_EXT = {".md", ".mdx", ".rst", ".adoc"}
PLAIN_SCRIPT_EXT = {".ts", ".js", ".mjs"}
TEST_DIRS = {"tests", "test", "__tests__", "spec", "specs", "__mocks__"}
DOC_DIRS = {"docs", "doc"}
BACKEND_DIRS = {"api", "models", "controllers", "services", "server", "routes"}
NON_UI_DIRS = {"fixtures", "__fixtures__", "testdata", "coverage", "htmlcov", "dist",
               "build", "out", ".next", "mailers", "emails", "mail"}
TEST_NAME = re.compile(r"(\.test\.|\.spec\.|_test\.|_spec\.|^test_|Tests?\.[a-z]+$)")


def is_ui_path(rel):
    p = PurePosixPath(str(rel).replace("\\", "/"))
    name, ext = p.name, p.suffix.lower()
    parts = p.parts[:-1]
    dirs = set(parts)
    if (dirs & (TEST_DIRS | DOC_DIRS | BACKEND_DIRS | NON_UI_DIRS) or ext in DOC_EXT
            or any(d.endswith("_mailer") for d in dirs) or TEST_NAME.search(name)
            or name in ("route.ts", "route.js") or name.startswith("middleware.")):
        return False
    if ext in UI_EXT or ext in TEMPLATE_EXT:
        return True
    if "components" in dirs and ext in PLAIN_SCRIPT_EXT:
        return True
    if name.endswith("View.swift") or name.endswith("Screen.kt"):
        return True
    if ext == ".dart":
        return "lib" in dirs and bool(dirs & {"widgets", "screens", "pages"})
    if ext == ".xml":
        return any(a == "res" and b.startswith("layout") for a, b in zip(parts, parts[1:]))
    return False


CONFIGS = [  # (filename regex, harness name)
    (re.compile(r"^playwright\.config\."), "playwright"),
    (re.compile(r"^cypress\.config\.|^cypress\.json$"), "cypress"),
    (re.compile(r"^wdio\.conf\."), "webdriverio"),
    (re.compile(r"^nightwatch\.conf\."), "nightwatch"),
    (re.compile(r"^\.testcaferc"), "testcafe"),
    (re.compile(r"^\.detoxrc|^detox\.config\."), "detox"),
]
NPM_DEPS = [("@playwright/test", "playwright"), ("playwright", "playwright"),
            ("cypress", "cypress"), ("webdriverio", "webdriverio"),
            ("nightwatch", "nightwatch"), ("testcafe", "testcafe"), ("detox", "detox")]
PUPPETEER_NOTE = "puppeteer; library, not a test runner"
PY_ALWAYS = [(re.compile(r"pytest-playwright", re.I), "playwright"),
             (re.compile(r"(?<![\w-])selenium(?![\w-])", re.I), "selenium")]
PY_BARE = [(re.compile(r"(?<![\w-])playwright(?![\w-])", re.I), "playwright")]
BARE_FILES = ("setup.py", "Pipfile")
RUBY = [(re.compile(r"capybara"), "capybara"), (re.compile(r"selenium-webdriver"), "selenium")]
SKIP_SUBDIRS = {"node_modules", ".git", "vendor", "dist", "build"}


def _read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return "".join(l for l in f if not l.lstrip().startswith("#"))
    except OSError:
        return ""


def _detect_dir(d, prefix):
    """Return a harness dict; a puppeteer-only hit comes back with name 'puppeteer'."""
    try:
        entries = sorted(os.scandir(d), key=lambda e: e.name)
    except OSError:
        return None
    names = {e.name for e in entries}
    for e in entries:
        if e.name == ".maestro" and e.is_dir():
            return {"name": "maestro", "evidence": prefix + ".maestro/"}
        if e.is_file():
            for rx, name in CONFIGS:
                if rx.search(e.name):
                    return {"name": name, "evidence": prefix + e.name}
    puppeteer = None
    if "package.json" in names:
        try:
            with open(os.path.join(d, "package.json"), encoding="utf-8") as f:
                pkg = json.load(f)
        except (OSError, ValueError):
            pkg = None
        if isinstance(pkg, dict):
            deps = {}
            for key in ("dependencies", "devDependencies", "optionalDependencies"):
                if isinstance(pkg.get(key), dict):
                    deps.update(pkg[key])
            for dep, name in NPM_DEPS:
                if dep in deps:
                    return {"name": name, "evidence": f"{prefix}package.json ({dep})"}
            if "puppeteer" in deps:
                puppeteer = {"name": "puppeteer",
                             "evidence": f"{prefix}package.json ({PUPPETEER_NOTE})"}
    for n in sorted(names):
        is_req = n.startswith("requirements") and n.endswith(".txt")
        if n in ("pyproject.toml", "setup.cfg") or n in BARE_FILES or is_req:
            text = _read(os.path.join(d, n))
            pats = PY_ALWAYS + (PY_BARE if (n in BARE_FILES or is_req) else [])
            for rx, name in pats:
                if rx.search(text):
                    return {"name": name, "evidence": f"{prefix}{n}"}
    if "Gemfile" in names:
        text = _read(os.path.join(d, "Gemfile"))
        for rx, name in RUBY:
            if rx.search(text):
                return {"name": name, "evidence": prefix + "Gemfile"}
    return puppeteer


def _subdirs(path):
    try:
        return sorted(e.name for e in os.scandir(path) if e.is_dir())
    except OSError:
        return []


def detect_harness(root):
    root = str(root)
    candidates = [(root, ""), (os.path.join(root, "tests", "e2e"), "tests/e2e/"),
                  (os.path.join(root, "test", "e2e"), "test/e2e/")]
    candidates += [(os.path.join(root, n), n + "/") for n in _subdirs(root)
                   if n not in SKIP_SUBDIRS]
    for group in ("packages", "apps"):
        candidates += [(os.path.join(root, group, n), f"{group}/{n}/")
                       for n in _subdirs(os.path.join(root, group)) if n != "node_modules"]
    fallback = None
    for d, prefix in candidates:
        found = _detect_dir(d, prefix)
        if found and found["name"] != "puppeteer":
            return found
        fallback = fallback or found
    return fallback


def main(argv):
    if len(argv) >= 2 and argv[1] == "ui":
        hits = [p for p in argv[2:] if is_ui_path(p)]
        print(json.dumps(hits))
        return 0 if hits else 1
    if len(argv) >= 2 and argv[1] == "harness":
        root = argv[2] if len(argv) > 2 else "."
        if not os.path.isdir(root) or not os.access(root, os.R_OK | os.X_OK):
            print(f"e2e_harness: root is missing or unreadable: {root}", file=sys.stderr)
            return 2
        h = detect_harness(root)
        print(json.dumps({"harness": h}))
        return 0 if h else 1
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
