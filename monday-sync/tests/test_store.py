"""store.py: monday.json sidecar and plugin store.json I/O."""
import json
import os
import sys

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
sys.path.insert(0, HOOKS)

import store  # noqa: E402


def test_sidecar_missing_returns_schema_1_default(tmp_path):
    sc = store.load_sidecar(str(tmp_path))
    assert sc["schema"] == 1
    assert sc["item_id"] is None and sc["last_pushed"] is None and sc["recreated_from"] is None


def test_sidecar_corrupt_json_returns_default(tmp_path):
    (tmp_path / "monday.json").write_text("{not json", encoding="utf-8")
    assert store.load_sidecar(str(tmp_path))["item_id"] is None


def test_sidecar_save_round_trips_atomically(tmp_path):
    sc = store.load_sidecar(str(tmp_path))
    sc["item_id"] = "3251077128"
    assert store.save_sidecar(str(tmp_path), sc) is True
    assert json.loads((tmp_path / "monday.json").read_text())["item_id"] == "3251077128"
    assert store.load_sidecar(str(tmp_path))["item_id"] == "3251077128"
    assert not any(p.name.endswith(".tmp") for p in tmp_path.iterdir())


def test_sidecar_partial_merges_over_defaults(tmp_path):
    (tmp_path / "monday.json").write_text('{"item_id": "1"}', encoding="utf-8")
    sc = store.load_sidecar(str(tmp_path))
    assert sc["item_id"] == "1" and sc["schema"] == 1 and sc["board_id"] == store.BOARD_ID


def test_sidecar_non_object_json_returns_default(tmp_path):
    (tmp_path / "monday.json").write_text("[1]", encoding="utf-8")
    assert store.load_sidecar(str(tmp_path)) == store.default_sidecar()


def test_sidecar_unserializable_value_fails_cleanly(tmp_path):
    assert store.save_sidecar(str(tmp_path), {"x": object()}) is False
    assert list(tmp_path.iterdir()) == []


def test_sidecar_replace_failure_fails_cleanly(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise OSError("replace failed")
    monkeypatch.setattr(store.os, "replace", boom)
    assert store.save_sidecar(str(tmp_path), {"item_id": "1"}) is False
    assert list(tmp_path.iterdir()) == []


# -- plugin store.json ---------------------------------------------------------------------------

def _store_json(data_dir):
    return json.loads((data_dir / "store.json").read_text())


def test_store_path_follows_claude_plugin_data(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path / "data"))
    assert store.store_path() == str(tmp_path / "data" / "store.json")
    monkeypatch.delenv("CLAUDE_PLUGIN_DATA")
    assert store.store_path() is None


def test_store_add_pending_dedupes_by_realpath(tmp_path, monkeypatch):
    data = tmp_path / "data"
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(data))
    feat = tmp_path / "spec" / "f1"
    feat.mkdir(parents=True)
    link = tmp_path / "alias"
    link.symlink_to(tmp_path / "spec")
    assert store.add_pending(str(feat)) is True
    assert store.add_pending(str(link / "f1")) is True
    assert _store_json(data)["pending"] == [os.path.realpath(str(feat))]


def test_store_list_pending_prunes_missing_dirs_and_remove(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path / "data"))
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    store.add_pending(str(a)); store.add_pending(str(b))
    b.rmdir()
    assert store.list_pending() == [os.path.realpath(str(a))]
    assert store.load_store()["pending"] == [os.path.realpath(str(a))]
    store.remove_pending(str(a))
    assert store.list_pending() == []


def test_store_linked_and_dismissed(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path / "data"))
    feat = tmp_path / "f"; feat.mkdir()
    store.set_linked(str(feat), "123")
    store.dismiss("999"); store.dismiss("999")
    s = store.load_store()
    assert s["linked"] == {os.path.realpath(str(feat)): "123"}
    assert s["dismissed_candidates"] == ["999"]


def test_store_without_plugin_data_is_a_safe_no_op(monkeypatch, tmp_path):
    monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)
    assert store.add_pending(str(tmp_path)) is False
    assert store.list_pending() == []


def test_store_set_linked_with_falsy_id_removes_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path / "data"))
    feat = tmp_path / "f"; feat.mkdir()
    store.set_linked(str(feat), "123")
    store.set_linked(str(feat), None)
    assert store.load_store()["linked"] == {}
