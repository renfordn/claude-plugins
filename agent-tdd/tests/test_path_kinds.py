"""path_kinds: classify repo-relative POSIX paths as test / doc / prod; path-identity helpers."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks"))
import path_kinds  # noqa: E402

CASES = [
    # tests
    ("tests/test_a.py", "test"), ("pkg/tests/helper.py", "test"), ("a/b/tests/x.py", "test"),
    ("test/foo.js", "test"), ("a/b/test/foo.js", "test"),
    ("test_x.py", "test"), ("pkg/test_x.py", "test"), ("x_test.py", "test"), ("pkg/x_test.go", "test"),
    ("src/app.test.ts", "test"), ("src/app.spec.tsx", "test"),
    ("src/test/java/com/Foo.java", "test"), ("FooTest.java", "test"), ("src/main/FooTests.java", "test"),
    ("spec/models/user_spec.rb", "test"), ("packages/core/spec/helper.rb", "test"), ("lib/user_spec.rb", "test"),
    ("conftest.py", "test"), ("pkg/conftest.py", "test"),
    ("e2e/login.ts", "test"), ("apps/web/cypress/support/x.js", "test"), ("cypress/support/x.js", "test"), ("playwright/a.ts", "test"),
    ("src/__tests__/a.js", "test"), ("src/__snapshots__/a.snap", "test"),
    ("tests/testdata/x.json", "test"), ("pkg/testdata/x.json", "test"), ("tests/fixtures/a.json", "test"),
    # docs
    ("README.md", "doc"), ("a/b/notes.rst", "doc"), ("docs/guide.mdx", "doc"), ("pkg/docs/x.txt", "doc"), ("docs/a/b.adoc", "doc"), ("CHANGELOG.md", "doc"),
    # F6 languages / case
    ("Tests/FooTests/FooTests.swift", "test"), ("Sources/FooTests.swift", "test"), ("Test/a.cs", "test"),
    ("src/FooTest.kt", "test"), ("src/FooTests.kt", "test"), ("src/FooTest.cs", "test"),
    ("src/FooTests.cs", "test"), ("src/FooSpec.kt", "test"), ("src/FooSpec.scala", "test"),
    # prod (manifests, CI, config, lookalikes)
    ("src/app.py", "prod"), ("package.json", "prod"), ("pyproject.toml", "prod"),
    (".github/workflows/ci.yml", "prod"), ("config/settings.yaml", "prod"),
    ("src/spec_loader.py", "prod"), ("src/contest.py", "prod"), ("src/latest.py", "prod"),
    ("Dockerfile", "prod"), ("src/Attest.java", "prod"), ("fixtures/a.json", "prod"),
    ("src/testing/util.py", "prod"), ("", "prod"),
    # negatives for broad rules
    ("docs/conf.py", "prod"), ("docs/app.js", "prod"), ("docs/Button.tsx", "prod"),
    ("src/spec/app.py", "prod"), ("lib/e2e/runner.py", "prod"), ("web/cypress/support/x.js", "prod"),
    ("src/playwright/driver.py", "prod"), ("a/b/spec/helper.rb", "prod"),
    ("src/contest/a.py", "prod"), ("requirements.txt", "prod"), ("src/Foo.swift", "prod"),
    ("src/Foo.kt", "prod"), ("src/FooTestable.java", "prod"),
    # path normalization
    ("tests/../src/app.py", "prod"), ("../tests/x.py", "prod"), ("./tests/x.py", "test"),
    ("src/../README.md", "doc"),
    # plugin product markdown is prod
    ("skills/x/SKILL.md", "prod"), ("SKILL.md", "prod"), ("CLAUDE.md", "prod"),
    ("pkg/AGENTS.md", "prod"), ("agent-tdd/agents/a.md", "prod"), ("p/commands/run.md", "prod"),
    ("p/skills/x/references/r.md", "prod"), ("output-styles/s.md", "prod"),
    ("docs/agents/x.md", "prod"), ("agents/tests/x.md", "test"), ("p/README.md", "doc"),
]


@pytest.mark.parametrize("rel,expected", CASES)
def test_kind(rel, expected):
    assert path_kinds.kind(rel) == expected


def test_is_inside(tmp_path):
    root = tmp_path / "repo"
    (root / "a").mkdir(parents=True)
    f = root / "a" / "f.txt"
    f.write_text("x")
    assert path_kinds.is_inside(str(f), str(root))
    assert path_kinds.is_inside(str(root), str(root))
    assert not path_kinds.is_inside(str(tmp_path / "other" / "f"), str(root))
    assert not path_kinds.is_inside(str(tmp_path), str(root))
    assert path_kinds.relative_to(str(f), str(root)) == ["a", "f.txt"]
    assert path_kinds.relative_to(str(tmp_path), str(root)) is None


def test_relative_to_symlink(tmp_path):
    root = tmp_path / "repo"
    (root / "a").mkdir(parents=True)
    (root / "a" / "f.txt").write_text("x")
    link = tmp_path / "link"
    link.symlink_to(root)
    assert path_kinds.relative_to(str(link / "a" / "f.txt"), str(root)) == ["a", "f.txt"]
    outside = tmp_path / "out"
    outside.mkdir()
    (root / "esc").symlink_to(outside)
    assert not path_kinds.is_inside(str(root / "esc" / "g"), str(root))


def test_relative_to_case_variant(tmp_path):
    root = tmp_path / "Repo"
    (root / "a").mkdir(parents=True)
    (root / "a" / "f.txt").write_text("x")
    variant = tmp_path / "repo" / "a" / "f.txt"
    if not variant.exists():
        pytest.skip("case-sensitive filesystem")
    assert path_kinds.relative_to(str(variant), str(root)) == ["a", "f.txt"]
