"""Tests for scripts/research_digest.py -- path-keyed research digests (write + lookup)."""
import hashlib
import json
import os
import subprocess
import sys
import time

import pytest

import build_index
import nelly_memory
import research_digest

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "research_digest.py")


# ---------------------------------------------------------------------------
# Pure helpers (Slice 7)
# ---------------------------------------------------------------------------

def test_blob_hash_matches_git_blob_hash():
    # `printf 'hello\n' | git hash-object --stdin`
    assert research_digest.blob_hash(b"hello\n") == "ce013625030ba8dba906f756967f9e9ca394464a"
    assert research_digest.blob_hash(b"") == "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"


def test_blob_hash_file_reads_bytes_and_returns_none_when_missing(tmp_path):
    (tmp_path / "a.bin").write_bytes(b"\x00\xffhello\n")
    expected = hashlib.sha1(b"blob 8\x00" + b"\x00\xffhello\n").hexdigest()
    assert research_digest.blob_hash_file(str(tmp_path / "a.bin")) == expected
    assert research_digest.blob_hash_file(str(tmp_path / "missing.py")) is None
    assert research_digest.blob_hash_file(str(tmp_path)) is None  # a directory is not a file


def test_digest_filename_shape_and_order_independence():
    name = research_digest.digest_filename("How the Index Rescan Works!", ["b.py", "a.py"])
    assert name == research_digest.digest_filename("How the Index Rescan Works!", ["a.py", "b.py"])
    stem, ext = os.path.splitext(name)
    assert ext == ".md"
    prefix, digest_hash = stem.rsplit("-", 1)
    assert prefix == "digest-how-the-index-rescan-works"
    assert len(digest_hash) == 12 and all(c in "0123456789abcdef" for c in digest_hash)


def test_digest_filename_differs_by_topic_and_path_set_and_caps_slug():
    base = research_digest.digest_filename("topic", ["a.py"])
    assert research_digest.digest_filename("topic", ["a.py", "b.py"]) != base
    assert research_digest.digest_filename("other", ["a.py"]) != base
    long_name = research_digest.digest_filename("x" * 100, ["a.py"])
    assert long_name == "digest-" + "x" * 40 + long_name[-16:]


def test_truncate_digest_leaves_short_text_unchanged():
    text = "line\n" * 10
    assert research_digest.truncate_digest(text) == text.strip()
    assert research_digest.truncate_digest("y" * 2000) == "y" * 2000


def test_truncate_digest_cuts_on_line_boundary_with_marker():
    text = "\n".join(f"- bullet {i:04d} " + "z" * 40 for i in range(60))  # ~3,300 chars
    out = research_digest.truncate_digest(text)
    assert len(out) <= 2000
    kept, marker = out.rsplit("\n", 1)
    assert text.startswith(kept + "\n")
    assert marker == f"…[truncated {len(text) - len(kept)} chars]"
    assert research_digest.truncate_digest(text) == out


def test_truncate_digest_hard_cuts_a_single_long_line():
    out = research_digest.truncate_digest("q" * 3000)
    assert len(out) <= 2000
    assert out.endswith(f"…[truncated {3000 - len(out.split(chr(10))[0])} chars]")


# ---------------------------------------------------------------------------
# write_digest (Slice 8)
# ---------------------------------------------------------------------------

@pytest.fixture
def store(tmp_path, monkeypatch):
    """Isolated memory store + a tmp repo holding a.py and pkg/b.py."""
    base = str(tmp_path / "agent-nelly-memory")
    monkeypatch.setattr(nelly_memory, "BASE", base)
    monkeypatch.setattr(build_index, "BASE", base)
    repo = tmp_path / "repo"
    (repo / "pkg").mkdir(parents=True)
    (repo / "a.py").write_text("print('a')\n", encoding="utf-8")
    (repo / "pkg" / "b.py").write_text("print('b')\n", encoding="utf-8")
    return {"cwd": str(repo), "repo": str(repo)}


def _digest_dir(cwd):
    return os.path.join(nelly_memory.memory_dir(cwd), "entries", nelly_memory.DIGEST_SUBDIR)


def _write(store, topic="Index rescan", summary="Findings.", paths=("a.py", "pkg/b.py"), **kw):
    paths = list(paths) if isinstance(paths, tuple) else paths
    return research_digest.write_digest(store["cwd"], store["repo"], topic, summary, paths, **kw)


def test_write_digest_creates_one_contract_shaped_file(store):
    result = _write(store, now="2026-09-25T15:40:00Z")

    files = os.listdir(_digest_dir(store["cwd"]))
    assert files == [research_digest.digest_filename("Index rescan", ["a.py", "pkg/b.py"])]
    text = open(os.path.join(_digest_dir(store["cwd"]), files[0]), encoding="utf-8").read()
    ha = research_digest.blob_hash(b"print('a')\n")
    hb = research_digest.blob_hash(b"print('b')\n")
    assert text == (
        "---\n"
        f"name: {files[0][:-3]}\n"
        "description: Index rescan\n"
        "type: research-digest\n"
        "topic: Index rescan\n"
        "sources:\n"
        f"  - path: a.py\n    hash: {ha}\n"
        f"  - path: pkg/b.py\n    hash: {hb}\n"
        "updated: 2026-09-25T15:40:00Z\n"
        "---\n"
        "Findings.\n"
    )
    assert result["file"] == os.path.join(_digest_dir(store["cwd"]), files[0])


def test_written_digest_round_trips_through_the_index(store):
    _write(store)
    records = [r for r in build_index.build_project_index(store["cwd"])
               if r["type"] == "research-digest"]
    assert len(records) == 1
    assert records[0]["topic"] == "Index rescan"
    assert records[0]["sources"] == [
        {"path": "a.py", "hash": research_digest.blob_hash(b"print('a')\n")},
        {"path": "pkg/b.py", "hash": research_digest.blob_hash(b"print('b')\n")},
    ]


def test_write_digest_upserts_the_index(store):
    _write(store)
    index = json.load(open(os.path.join(nelly_memory.memory_dir(store["cwd"]),
                                        build_index.INDEX_FILENAME)))
    assert [r["type"] for r in index] == ["research-digest"]


def test_same_topic_and_path_set_overwrites_in_place(store):
    _write(store, summary="First.")
    _write(store, summary="Second.", paths=("pkg/b.py", "./a.py"))

    files = os.listdir(_digest_dir(store["cwd"]))
    assert len(files) == 1
    assert open(os.path.join(_digest_dir(store["cwd"]), files[0])).read().endswith("Second.\n")


def test_long_summary_is_truncated_with_marker(store):
    summary = "\n".join(f"- finding {i:03d} " + "w" * 50 for i in range(50))  # ~3,100 chars
    result = _write(store, summary=summary)
    body = open(result["file"], encoding="utf-8").read().split("\n---\n", 1)[1]
    assert len(body.rstrip("\n")) <= 2000
    assert "…[truncated " in body
    assert result["truncated"] is True


@pytest.mark.parametrize("kwargs,needle", [
    ({"paths": ("/abs/a.py",)}, "absolute"),
    ({"paths": ("../outside.py",)}, ".."),
    ({"paths": tuple(f"f{i}.py" for i in range(31))}, "30"),
    ({"topic": "  "}, "topic"),
    ({"summary": ""}, "summary"),
    ({"paths": ()}, "path"),
    ({"paths": ("a.py", "gone.py")}, "gone.py"),
    ({"summary": 123}, "summary"),
    ({"topic": 5}, "topic"),
    ({"topic": ["a"]}, "topic"),
    ({"paths": "a.py"}, "list"),
    ({"paths": ("a.py", 1)}, "string"),
])
def test_invalid_requests_are_rejected_and_store_nothing(store, kwargs, needle):
    with pytest.raises(research_digest.DigestError) as exc:
        _write(store, **kwargs)
    assert needle in str(exc.value)
    assert not os.path.exists(_digest_dir(store["cwd"])) or not os.listdir(_digest_dir(store["cwd"]))


def test_cli_write_reads_json_from_stdin(store, monkeypatch, capsys):
    import io
    request = {"topic": "Index rescan", "summary": "Findings.", "paths": ["a.py"]}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(request)))

    research_digest.main(["write", "--json", "-", "--cwd", store["cwd"],
                          "--repo-root", store["repo"]])

    out = json.loads(capsys.readouterr().out)
    assert out["name"] == research_digest.digest_filename("Index rescan", ["a.py"])[:-3]
    assert os.path.isfile(out["file"])


def test_cli_write_ignores_repo_root_in_request_json(store, monkeypatch, capsys, tmp_path):
    import io
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "a.py").write_text("different content\n", encoding="utf-8")
    request = {"topic": "t", "summary": "s", "paths": ["a.py"], "repo_root": str(elsewhere)}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(request)))

    research_digest.main(["write", "--json", "-", "--cwd", store["cwd"],
                          "--repo-root", store["repo"]])

    out = json.loads(capsys.readouterr().out)
    assert out["sources"] == [{"path": "a.py", "hash": research_digest.blob_hash(b"print('a')\n")}]


def test_cli_write_non_string_summary_exits_2(store, monkeypatch, capsys):
    import io
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(
        {"topic": "t", "summary": 123, "paths": ["a.py"]})))
    with pytest.raises(SystemExit) as exc:
        research_digest.main(["write", "--json", "-", "--cwd", store["cwd"]])
    assert exc.value.code == 2
    assert "summary" in capsys.readouterr().err


def test_cli_write_invalid_request_exits_2_with_reason(store, monkeypatch, capsys):
    import io
    request = {"topic": "t", "summary": "s", "paths": ["/abs.py"]}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(request)))

    with pytest.raises(SystemExit) as exc:
        research_digest.main(["write", "--json", "-", "--cwd", store["cwd"]])

    assert exc.value.code == 2
    assert "absolute" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# lookup_digests (Slice 9)
# ---------------------------------------------------------------------------

def _lookup(store, path):
    return research_digest.lookup_digests(store["cwd"], store["repo"], path)


def _index_path(store):
    return os.path.join(nelly_memory.memory_dir(store["cwd"]), build_index.INDEX_FILENAME)


def test_lookup_fresh_digest_from_index(store):
    written = _write(store, summary="Findings about a and b.")

    result = _lookup(store, "a.py")

    assert result["path"] == "a.py"
    assert result["source"] == "index"
    assert result["digests"] == [{
        "name": written["name"], "topic": "Index rescan", "status": "fresh", "changed": [],
        "updated": written["updated"], "file": written["file"],
        "summary": "Findings about a and b.",
    }]


def test_lookup_reports_stale_with_changed_path_after_edit_and_delete(store):
    _write(store)
    (open(os.path.join(store["repo"], "pkg", "b.py"), "a")).write("# edit\n")

    edited = _lookup(store, "a.py")["digests"][0]
    assert (edited["status"], edited["changed"]) == ("stale", ["pkg/b.py"])

    os.remove(os.path.join(store["repo"], "pkg", "b.py"))
    deleted = _lookup(store, "a.py")["digests"][0]
    assert (deleted["status"], deleted["changed"]) == ("stale", ["pkg/b.py"])


def test_lookup_unrelated_path_returns_no_digests(store):
    _write(store, paths=("a.py",))
    assert _lookup(store, "pkg/b.py")["digests"] == []


@pytest.mark.parametrize("damage", ["delete", "corrupt"])
def test_missing_or_corrupt_index_falls_back_to_scan_with_identical_results(store, damage):
    _write(store)
    from_index = _lookup(store, "pkg/b.py")
    if damage == "delete":
        os.remove(_index_path(store))
    else:
        open(_index_path(store), "w").write("{not json")

    from_scan = _lookup(store, "pkg/b.py")

    assert from_index["source"] == "index"
    assert from_scan["source"] == "scan"
    assert from_scan["digests"] == from_index["digests"]


def test_index_missing_an_on_disk_digest_falls_back_to_scan(store):
    _write(store, topic="first", paths=("a.py",))
    with open(_index_path(store)) as fh:
        stale_index = fh.read()
    _write(store, topic="second", paths=("a.py",))
    open(_index_path(store), "w").write(stale_index)  # index no longer lists "second"

    result = _lookup(store, "a.py")

    assert result["source"] == "scan"
    assert sorted(d["topic"] for d in result["digests"]) == ["first", "second"]


def test_lookup_orders_fresh_first_then_newest(store):
    _write(store, topic="old fresh", paths=("a.py",), now="2026-01-01T00:00:00Z")
    _write(store, topic="new fresh", paths=("a.py",), now="2026-02-01T00:00:00Z")
    _write(store, topic="newest stale", now="2026-03-01T00:00:00Z")
    open(os.path.join(store["repo"], "pkg", "b.py"), "a").write("# edit\n")

    topics = [d["topic"] for d in _lookup(store, "a.py")["digests"]]

    assert topics == ["new fresh", "old fresh", "newest stale"]


def test_scan_ignores_conflict_copies(store):
    written = _write(store)
    copy = written["file"][:-3] + " 2.md"
    with open(written["file"]) as src, open(copy, "w") as dst:
        dst.write(src.read())
    os.remove(_index_path(store))

    result = _lookup(store, "a.py")

    assert result["source"] == "scan"
    assert [d["file"] for d in result["digests"]] == [written["file"]]


def test_lookup_rejects_absolute_path(store):
    with pytest.raises(research_digest.DigestError):
        _lookup(store, "/abs/a.py")


def test_scan_lookup_of_30_source_digest_is_fast(store):
    paths = []
    for i in range(30):
        rel = f"many/f{i:02d}.py"
        os.makedirs(os.path.join(store["repo"], "many"), exist_ok=True)
        open(os.path.join(store["repo"], rel), "w").write("x = 1\n" * 200)
        paths.append(rel)
    _write(store, paths=paths)
    os.remove(_index_path(store))

    start = time.perf_counter()
    result = _lookup(store, "many/f07.py")
    elapsed = time.perf_counter() - start

    assert result["digests"][0]["status"] == "fresh"
    assert elapsed < 0.5


def test_cli_lookup_prints_json(store, capsys):
    _write(store)
    research_digest.main(["lookup", "a.py", "--cwd", store["cwd"], "--repo-root", store["repo"]])
    out = json.loads(capsys.readouterr().out)
    assert out["path"] == "a.py"
    assert out["digests"][0]["status"] == "fresh"


def test_cli_runs_as_a_script(store, tmp_path):
    """Smoke test: the file's own sys.path setup lets it run standalone (not only under pytest)."""
    env = dict(os.environ, CLAUDE_PLUGIN_DATA=str(tmp_path / "plugin-data"))
    proc = subprocess.run([sys.executable, SCRIPT, "lookup", "a.py", "--cwd", store["cwd"]],
                          capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["digests"] == []
