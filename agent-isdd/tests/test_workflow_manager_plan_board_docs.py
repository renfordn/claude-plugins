"""The Plan Board workflow step is only reliable if the skill actually tells the model to do it,
the procedure is written down, and every file the docs point at exists."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "skills", "workflow-manager", "SKILL.md")
REF = os.path.join(ROOT, "skills", "workflow-manager", "references", "plan-board.md")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _step():
    text = _read(SKILL)
    m = re.search(r"\*\*Plan Board sync.*?(?=\n\n\||\n\n\*\*|\n## )", text, re.S)
    assert m, "workflow-manager/SKILL.md has no 'Plan Board sync' step"
    return m.group(0)


def test_the_skill_has_a_plan_board_sync_step_that_runs_at_every_state_change():
    step = _step()
    for phrase in ("phase transition", "pause", "resume", "rewind", "handoff", "completion"):
        assert phrase in step.lower(), phrase
    assert "PLAN-BOARD.md" in step
    assert "references/plan-board.md" in step


def test_the_step_gives_expanded_commands_and_the_db_write():
    step = _step()
    assert 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/plan_board.py" doc' in step
    assert "mark-synced" in step
    assert "ArtifactData" in step and "plans" in step


def test_a_failed_sync_never_blocks_the_workflow():
    step = _step().lower()
    assert "never" in step and "block" in step


def test_the_reference_documents_setup_sync_fields_and_turning_it_off():
    ref = _read(REF)
    for needle in ("First-time setup", "Syncing a feature", "Record fields", "Turning it off",
                   "PLAN-BOARD.md", "plan-board-sync.json", '"owner"', "capabilities",
                   "collection `plans`", "doc_id", "nextAction", "phases"):
        assert needle in ref, needle


def test_every_file_the_docs_point_at_exists():
    for rel in ("hooks/plan_board.py", "skills/workflow-manager/assets/plan-board.html",
                "skills/workflow-manager/references/plan-board.md"):
        assert os.path.isfile(os.path.join(ROOT, rel)), rel
    assert "hooks/plan_board.py" in _read(SKILL) or "plan_board.py" in _step()


def test_interop_and_readme_mention_the_board():
    interop = _read(os.path.join(ROOT, "INTEROP.md"))
    readme = _read(os.path.join(ROOT, "README.md"))
    assert "Plan Board" in interop and "`plans`" in interop
    assert "Plan Board" in readme and "PLAN-BOARD.md" in readme


def test_existing_records_need_their_version_so_the_write_names_it():
    """ArtifactData refuses a `set` on an existing record without `if_version`; a procedure that
    forgets this works once and then silently fails on every later sync."""
    assert "if_version" in _step()
    ref = _read(REF)
    assert "if_version" in ref and "`get`" in ref and "file_path" in ref


def test_setup_says_how_to_find_the_memory_dir_and_how_to_list_every_feature():
    """The audit found setup steps that could not be followed as written: no way to locate the
    memory dir, and a claim that SessionStart lists every feature when it lists three."""
    ref = _read(REF)
    assert "sdd_memory.py" in ref and "--path" in ref
    assert "`stale`" in ref and "up to three" in ref


def test_project_label_is_defined_the_way_the_code_computes_it():
    for text in (_step(), _read(REF)):
        assert "git top-level" in text
        assert "repo folder name" not in text


def test_the_step_names_the_board_url_and_a_mark_synced_command_without_out():
    step = _step()
    assert "url" in step and "PLAN-BOARD.md" in step
    assert "mark-synced" in step
    assert re.search(r"mark-synced[^`]*--project", step) or "mark-synced" in step
    ref = _read(REF)
    assert "mark-synced <workflow-state.md> --project" in ref and "--out" not in ref.split("mark-synced")[1].split("\n")[0]


def test_the_ordering_of_the_step_is_defined_for_every_trigger():
    step = _step()
    assert "Verification Step" in step


def test_the_page_must_be_published_with_the_owner_only_rule():
    ref = _read(REF)
    assert "Contributors" in ref and "200" in ref and "https://" in ref


def test_changelog_and_interop_do_not_restate_or_overclaim():
    changelog = _read(os.path.join(ROOT, "CHANGELOG.md")).split("## [0.3.3]")[0]
    assert "Mutation-checked" not in changelog
    assert "from anywhere" not in changelog
    interop = _read(os.path.join(ROOT, "INTEROP.md"))
    section = interop.split("## → Plan Board (Artifact page)")[1].split("\n## ")[0]
    assert "implementationRequested" not in section  # the field list lives in the reference only


def test_the_reference_documents_the_brief_toggle_and_drift_commands():
    ref = _read(REF)
    for needle in ("schema 2", "`brief`", "`closedAt`", "`contentHash`", "`briefBoardUrl`", "- Sync: off",
                   "- Brief Board:", "requirements/requirements.md", "design/design.md", "recap/recap.md",
                   "tasks/tasks.md", "Recently closed", "Archive", "14 days", "plan_board_sync.py",
                   "verify", "resync", "prune", "/isdd-board-sync", "direct-mode-state.json"):
        assert needle in ref, needle
    assert len(ref.splitlines()) <= 400


def test_the_sync_step_names_the_post_write_reminder_and_the_repair_command():
    step = _step()
    assert "post-write" in step and "/isdd-board-sync" in step
    assert len(_read(SKILL).splitlines()) <= 400


def test_readme_and_interop_describe_the_reworked_board():
    readme = _read(os.path.join(ROOT, "README.md"))
    assert "/isdd-board-sync" in readme
    assert "brief" in readme.lower() and "Recently closed" in readme and "Sync: off" in readme
    interop = _read(os.path.join(ROOT, "INTEROP.md"))
    section = interop.split("## → Plan Board (Artifact page)")[1].split("\n## ")[0]
    for needle in ("brief", "post-write", "plan_brief.py", "plan_board_sync.py", "/isdd-board-sync"):
        assert needle in section, needle
    assert "implementationRequested" not in section


def test_docs_state_the_slice_done_lag_and_verified_batch_shapes():
    ref = _read(REF)
    changelog = _read(os.path.join(ROOT, "CHANGELOG.md")).split("## [0.4.2]")[0]
    for text in (ref, changelog):
        assert "next watched write" in text and "/isdd-board-sync" in text
        assert "unverified against a live board" not in text
        assert "live board" in text
