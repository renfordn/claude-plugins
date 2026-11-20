"""Slice 2E (R5 coherence) for scripts/nelly_evidence.py and the weekly archive. Uses the conftest temp
CLAUDE_PLUGIN_DATA; never a real memory root."""
import json
import os
import shlex
import subprocess
import sys
import tempfile

import pytest

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
HOOKS = os.path.join(SCRIPTS, "..", "hooks")
SCRIPT = os.path.join(SCRIPTS, "nelly_evidence.py")
sys.path.insert(0, HOOKS)
sys.path.insert(0, SCRIPTS)

import build_index  # noqa: E402
import nelly_evidence  # noqa: E402
import nelly_freshness  # noqa: E402
import nelly_memory  # noqa: E402
import nelly_pending  # noqa: E402
import nelly_weekly_consolidate as consolidate  # noqa: E402


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                          text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = (tmp_path / "repo").resolve()
    (r / "src").mkdir(parents=True)
    (r / "src" / "a.py").write_text("print('a')\n")
    (r / "src" / "b.py").write_text("print('b')\n")
    git(r, "init", "-q", "-b", "main")
    git(r, "config", "user.email", "t@example.com")
    git(r, "config", "user.name", "t")
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "init")
    return r


def cli(*args, env=None):
    return subprocess.run([sys.executable, SCRIPT, *map(str, args)], capture_output=True, text=True, env=env)


def record(repo, slug="a-fact", type_="reference", description="A fact: it works", paths=("src/a.py",),
           body="Body one.", extra=()):
    return cli("record", "--cwd", repo, "--slug", slug, "--type", type_, "--description", description,
               "--body", body, "--paths", *paths, "--basis", "observed", *extra)


def entry(repo, slug="a-fact"):
    return nelly_memory.entry_path(str(repo), slug)


def refresh(repo, *extra, slug="a-fact", paths=("src/a.py",)):
    return cli("refresh", "--cwd", repo, "--slug", slug, "--paths", *paths, *extra)


def go_stale(repo, rel="src/a.py"):
    (repo / rel).write_text("print('changed')\n")
    git(repo, "commit", "-qam", "change " + rel)
    nelly_freshness.scan(str(repo))


# --- Eval A: description round-trips through YAML ---

@pytest.mark.parametrize("desc", ["A fact: it works", "uses # comment-ish text", 'says "hi" and \\ slash',
                                  "- starts with dash", "[brackets] and {braces}", "true", "plain words"])
def test_record_description_is_valid_yaml_and_round_trips(repo, desc):
    yaml = pytest.importorskip("yaml")
    assert record(repo, description=desc).returncode == 0
    text = open(entry(repo)).read()
    fm = yaml.safe_load(text.split("---\n")[1])
    assert fm["description"] == desc and fm["name"] == "a-fact"
    assert build_index.build_project_index(str(repo)) is not None
    with open(os.path.join(nelly_memory.memory_dir(str(repo)), "nelly-index.json")) as fh:
        assert {r["slug"]: r for r in json.load(fh)}["a-fact"]["description"] == desc


def test_record_numeric_slug_name_stays_a_string_in_yaml(repo):
    yaml = pytest.importorskip("yaml")
    assert record(repo, slug="123").returncode == 0
    fm = yaml.safe_load(open(entry(repo, "123")).read().split("---\n")[1])
    assert fm["name"] == "123"


# --- F6: summary/digest types have their own writers ---

@pytest.mark.parametrize("t", ["file-summary", "folder-summary", "research-digest"])
def test_record_rejects_types_with_their_own_writer(repo, t):
    p = record(repo, type_=t)
    assert p.returncode == 2 and "own writer" in p.stderr
    assert not os.path.exists(entry(repo))


# --- F9: missing plugin data dir -> one-line error, exit 5 ---

def test_missing_plugin_data_exits_5_without_traceback(tmp_path):
    env = {k: v for k, v in os.environ.items()
           if k not in ("CLAUDE_PLUGIN_DATA", "CLAUDE_PLUGIN_OPTION_SHARED_MEMORY_ROOT")}
    env["HOME"] = str(tmp_path / "home")
    env["CLAUDE_CONFIG_DIR"] = str(tmp_path / "cfg")
    p = cli("stale", "--cwd", tmp_path, env=env)
    assert p.returncode == 5, (p.stdout, p.stderr)
    assert "Traceback" not in p.stderr and len(p.stderr.strip().splitlines()) == 1


# --- F3: lexical roots ---

def test_base_keeps_the_lexical_spelling_of_a_symlinked_repo(tmp_path, repo):
    link = tmp_path / "link"
    os.symlink(str(repo), str(link))
    assert nelly_evidence._base(str(link)) == str(link)
    assert record(link).returncode == 0
    assert os.path.isfile(nelly_memory.entry_path(str(link), "a-fact"))
    sub = link / "src"
    assert refresh(sub, paths=("a.py",)).returncode == 0  # resolves through the subdirectory


# --- Eval B: refresh must not silently bless a changed fact ---

def test_refresh_of_stale_entry_requires_confirm_unchanged(repo):
    assert record(repo).returncode == 0
    go_stale(repo)
    p = refresh(repo)
    assert p.returncode == 2 and "--confirm-unchanged" in p.stderr and "rewrite" in p.stderr
    assert "stale: true" in open(entry(repo)).read()
    ok = refresh(repo, "--confirm-unchanged")
    assert ok.returncode == 0, ok.stderr
    text = open(entry(repo)).read()
    assert "stale" not in text and "stale_digest" not in text


@pytest.mark.parametrize("old,new", [("Body one.", "Body two, rewritten."),
                                     ("description: \"A fact: it works\"", "description: \"A different fact\"")])
def test_refresh_without_confirm_allowed_after_entry_was_rewritten(repo, old, new):
    assert record(repo).returncode == 0
    go_stale(repo)
    p = entry(repo)
    text = open(p).read()
    assert old in text
    with open(p, "w") as fh:
        fh.write(text.replace(old, new))
    ok = refresh(repo)
    assert ok.returncode == 0, ok.stderr
    assert "stale:" not in open(p).read()


def test_refresh_requires_confirm_for_legacy_stale_mark_without_digest(repo):
    assert record(repo).returncode == 0
    go_stale(repo)
    p = entry(repo)
    lines = [ln for ln in open(p).read().splitlines(True) if "stale_digest" not in ln]
    open(p, "w").write("".join(lines))
    p2 = refresh(repo)
    assert p2.returncode == 2 and "marked stale before rewrite tracking" in p2.stderr
    assert "--confirm-unchanged" in p2.stderr and "has not been rewritten" not in p2.stderr
    assert refresh(repo, "--confirm-unchanged").returncode == 0


def test_refresh_of_fresh_entry_needs_no_confirm(repo):
    assert record(repo).returncode == 0
    assert refresh(repo).returncode == 0


# --- F2: stale subcommand ---

def test_stale_subcommand_lists_stale_entries_with_commands_oldest_first(repo):
    assert record(repo, slug="one").returncode == 0
    assert record(repo, slug="two").returncode == 0
    go_stale(repo)
    p = cli("stale", "--cwd", repo)
    assert p.returncode == 0, p.stderr
    out = json.loads(p.stdout)
    assert [e["slug"] for e in out] == ["one", "two"]
    for e in out:
        assert e["stale_paths"] == ["src/a.py"] and e["stale_since"]
        assert f"--slug {e['slug']}" in e["command"] and "nelly_evidence.py" in e["command"]


# --- cleanups ---

def test_uncommitted_refusal_prints_a_runnable_pending_add(repo):
    (repo / "src" / "a.py").write_text("changed\n")
    p = record(repo)
    assert p.returncode == 2
    line = [ln for ln in p.stderr.splitlines() if "nelly_pending.py" in ln][0]
    tokens = shlex.split(line[line.index("CLAUDE_PLUGIN_DATA="):].split("`")[0])
    assert tokens[0].startswith("CLAUDE_PLUGIN_DATA=")
    ns = nelly_pending._parser().parse_args(tokens[tokens.index("add"):])
    assert ns.cwd == str(repo) and ns.paths == ["src/a.py"]


def test_drop_paths_removes_the_path_from_files_and_memory_md_under_one_lock(repo):
    assert record(repo, slug="fr", type_="file-relevance", paths=("src/a.py", "src/b.py")).returncode == 0
    mem = os.path.join(nelly_memory.memory_dir(str(repo)), "MEMORY.md")
    assert "paths:src/a.py;src/b.py" in open(mem).read()
    git(repo, "rm", "-q", "src/b.py")
    git(repo, "commit", "-qm", "rm b")
    p = cli("refresh", "--cwd", repo, "--slug", "fr", "--drop-paths", "src/b.py")
    assert p.returncode == 0, p.stderr
    text = open(entry(repo, "fr")).read()
    assert "src/b.py" not in text and "files: [src/a.py]" in text
    md = open(mem).read()
    assert "src/b.py" not in md and "paths:src/a.py]" in md
    with open(os.path.join(nelly_memory.memory_dir(str(repo)), "nelly-index.json")) as fh:
        assert "src/b.py" not in json.dumps(json.load(fh))


def test_weekly_archive_never_overwrites_an_existing_archive_file(tmp_path):
    proj = tmp_path / "proj"
    (proj / "entries").mkdir(parents=True)
    (proj / "archive").mkdir()
    (proj / "archive" / "x.md").write_text("OLD ARCHIVED")
    (proj / "entries" / "x.md").write_text("NEW ENTRY")
    dest = consolidate._archive_entry(str(proj), {"path": str(proj / "entries" / "x.md")})
    assert open(proj / "archive" / "x.md").read() == "OLD ARCHIVED"
    assert dest != str(proj / "archive" / "x.md") and open(dest).read() == "NEW ENTRY"
    assert not (proj / "entries" / "x.md").exists()


def test_record_slug_yes_indexes_as_yes(repo):
    assert record(repo, slug="yes").returncode == 0
    with open(os.path.join(nelly_memory.memory_dir(str(repo)), "nelly-index.json")) as fh:
        assert [r["slug"] for r in json.load(fh)] == ["yes"]
