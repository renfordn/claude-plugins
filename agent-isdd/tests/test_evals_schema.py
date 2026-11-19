"""Schema + topic checks for agent-isdd/evals/evals.json (skill-creator format)."""
import json
from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent.parent / "evals"

TOPICS = {
    "low-risk-compact": ["risk: low", "track: fast", "slice spec", "review"],
    "tiny-auth-high-risk": ["risk: high", "every slice", "reviewed"],
    "user-led-coaching": ["isdd-coach", "user", "production code"],
    "tier1-sonnet-vs-opus": ["sonnet", "opus", "tier1"],
}


def load():
    return json.loads((EVALS_DIR / "evals.json").read_text())


KEY_ASSERTIONS = {
    "low-risk-compact": ["Risk: low", "Risk Reason"],
    "tiny-auth-high-risk": ["Risk: high"],
    "user-led-coaching": ["AskUserQuestion", "isdd-coach"],
    "tier1-sonnet-vs-opus": ["sonnet", "opus"],
}


def test_skill_name_is_existing_skill():
    skills = EVALS_DIR.parent / "skills"
    assert (skills / load()["skill_name"]).is_dir()


def test_ids_are_ints():
    assert all(type(e["id"]) is int for e in load()["evals"])


def test_key_discriminating_assertions_pinned():
    by_name = {e["name"]: e for e in load()["evals"]}
    for name, needles in KEY_ASSERTIONS.items():
        for n in needles:
            assert any(n in a for a in by_name[name]["assertions"]), (name, n)


def test_tier1_eval_has_enough_planted_claims():
    ev = next(e for e in load()["evals"] if e["name"] == "tier1-sonnet-vs-opus")
    assert ev["prompt"].count("[PLANTED-") >= 8


def test_top_level_shape():
    data = load()
    assert data["skill_name"]
    assert isinstance(data["evals"], list)


def test_each_eval_has_required_fields():
    for ev in load()["evals"]:
        for key in ("id", "name", "prompt", "expected_output", "files", "assertions"):
            assert key in ev, (ev.get("id"), key)
        assert ev["prompt"].strip() and ev["expected_output"].strip()
        assert isinstance(ev["files"], list)
        assert isinstance(ev["assertions"], list) and ev["assertions"]
        assert all(isinstance(a, str) and a.strip() for a in ev["assertions"])


def test_ids_unique_and_four_evals():
    ids = [e["id"] for e in load()["evals"]]
    assert len(ids) == len(set(ids)) == 4


def test_four_topics_present():
    by_name = {e["name"]: e for e in load()["evals"]}
    assert set(by_name) == set(TOPICS)
    for name, needles in TOPICS.items():
        blob = json.dumps(by_name[name]).lower()
        for n in needles:
            assert n in blob, (name, n)


def test_fixture_files_exist():
    for ev in load()["evals"]:
        for f in ev["files"]:
            assert (EVALS_DIR / f).is_file(), f


def test_readme_documents_baseline():
    text = (EVALS_DIR / "README.md").read_text()
    assert "6949c4b" in text and "without" in text.lower()
    assert "--plugin-dir" in text and "git worktree add" in text
    assert "model" in text and "plan-reviewer-tier1" in text
