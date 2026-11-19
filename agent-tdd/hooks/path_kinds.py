"""path_kinds: classify a repo-relative POSIX path as "test", "doc" or "prod", plus path-identity
helpers. Derived from agent-isdd user_led_guard (copied, not imported, so the plugin stays
self-contained); the rules intentionally differ from it (more languages, nested test dirs).

Rules, in order: tests win, then plugin product files, then docs, else prod. Manifests, CI and
config are prod.
- Test: `tests/`, `test/` (any case), `__tests__/`, `__snapshots__/`, `testdata/` at any depth;
  `spec/`, `e2e/`, `cypress/`, `playwright/` only at the top level or directly under a monorepo
  package root (`packages/<pkg>/`, `apps/<app>/`, ...); conftest.py; and test-named files
  (test_*, *_test.*, *.test.*, *.spec.*, *_spec.rb, *Test(s).java/.kt/.cs, *Tests.swift,
  *Spec.kt/.scala).
- Plugin product files are prod even though they are markdown: SKILL.md, CLAUDE.md, AGENTS.md and
  any .md under agents/, skills/, commands/ or output-styles/. In these files the markdown is
  shipped behavior, not documentation.
- Doc: .md/.mdx/.rst/.adoc anywhere; .txt only under `docs/`. Other files under `docs/`
  (conf.py, app.js) are prod.
- The path is normalized first; one escaping the repo (leading `..`) is prod.
"""
import os
import posixpath
import re

_ANY_DEPTH_TEST_DIRS = frozenset(("tests", "test", "__tests__", "__snapshots__", "testdata"))
_SHALLOW_TEST_DIRS = frozenset(("spec", "e2e", "cypress", "playwright"))
_MONOREPO_ROOTS = frozenset(("packages", "apps", "libs", "modules", "services"))
_DOC_EXTS = (".md", ".mdx", ".rst", ".adoc")
_DOCS_DIR_EXTS = _DOC_EXTS + (".txt",)
_PRODUCT_MD_NAMES = frozenset(("SKILL.md", "CLAUDE.md", "AGENTS.md"))
_PRODUCT_MD_DIRS = frozenset(("agents", "skills", "commands", "output-styles"))
_TEST_NAME = re.compile(
    r"(^test_|_test\.[^.]+$|_spec\.rb$|Tests?\.(java|kt|cs)$|Tests\.swift$|Spec\.(kt|scala)$"
    r"|\.(test|spec)\.)")


def _parts(rel_path):
    """Normalized components; None when the path escapes the repo (leading `..`)."""
    norm = posixpath.normpath(str(rel_path).replace("\\", "/"))
    parts = [p for p in norm.split("/") if p and p != "."]
    if parts and parts[0] == "..":
        return None
    return parts


def _is_test(parts):
    dirs, name = parts[:-1], parts[-1]
    if any(d.lower() in _ANY_DEPTH_TEST_DIRS for d in dirs):
        return True
    if parts[0] in _SHALLOW_TEST_DIRS and len(parts) > 1:
        return True
    if len(parts) > 3 and parts[0] in _MONOREPO_ROOTS and parts[2] in _SHALLOW_TEST_DIRS:
        return True
    if name == "conftest.py":
        return True
    return bool(_TEST_NAME.search(name))


def _is_product_md(parts):
    name = parts[-1]
    if name in _PRODUCT_MD_NAMES:
        return True
    return name.lower().endswith(".md") and any(d in _PRODUCT_MD_DIRS for d in parts[:-1])


def kind(rel_path):
    """Return "test", "doc" or "prod" for a repo-relative POSIX path."""
    parts = _parts(rel_path)
    if not parts:
        return "prod"
    if _is_test(parts):
        return "test"
    if _is_product_md(parts):
        return "prod"
    name = parts[-1].lower()
    if name.endswith(_DOC_EXTS):
        return "doc"
    if "docs" in parts[:-1] and name.endswith(_DOCS_DIR_EXTS):
        return "doc"
    return "prod"


def _same(a, b):
    try:
        return os.path.samestat(os.stat(a), os.stat(b))
    except OSError:
        return os.path.normcase(a) == os.path.normcase(b)


def relative_to(path, root):
    """Components of `path` below `root`, matched by file identity (so case-variant spellings on
    case-insensitive filesystems still match); None if path is not inside root."""
    parts = []
    cur = os.path.realpath(path)
    root = os.path.realpath(root)
    while True:
        if _same(cur, root):
            return list(reversed(parts))
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        parts.append(os.path.basename(cur))
        cur = parent


def is_inside(path, root):
    """True when `path` is `root` or below it (realpath/samefile based, not string prefix)."""
    return relative_to(path, root) is not None
