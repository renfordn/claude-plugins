"""monday-sync skill docs: procedure, ordering and board reference stay aligned with the code."""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "hooks"))

import planner  # noqa: E402

SKILL = os.path.join(ROOT, "skills", "monday-sync", "SKILL.md")
BOARD = os.path.join(ROOT, "skills", "monday-sync", "references", "board.md")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def test_skill_frontmatter_names_the_triggers():
    text = read(SKILL)
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, "frontmatter"
    front = m.group(1)
    assert re.search(r"^name: monday-sync$", front, re.M)
    desc = front.lower()
    for trigger in ("sync monday board", "update monday.com board", "phase", "monday: "):
        assert trigger in desc, trigger


def test_skill_covers_cli_git_probe_mcp_and_failure_rules():
    text = read(SKILL)
    for needle in ('CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}"', "${CLAUDE_PLUGIN_ROOT}/hooks/cli.py",
                   "pending list", "pending clear", "--expect-hash", "--item-missing", "record",
                   "candidates --items", "candidates --dismiss",
                   "${CLAUDE_PLUGIN_ROOT}/hooks/git_probe.sh", "device_bash", "<<'PROBE'", "~",
                   "get_board_items_page", "get_updates", "update_items", "create_item",
                   "AskUserQuestion", "Edit tool", "recap.md", "/isdd", "Backlog",
                   "references/board.md", "sync-begin", "--accept-board-status", "--unlink",
                   "--forget-item", "relink", "change_item_column_values",
                   "--item-id <new id> --snapshot plan.json", "--accept-board-status X --git git.json"):
        assert needle in text, needle


def test_skill_orders_plan_writes_isdd_replan_record_clear():
    text = read(SKILL)
    steps = ["**Begin.**", "**Plan.**", "**Write the board.**", "**Apply isdd_updates.**", "**Re-plan.**",
             "**Record.**", "**Clear the flag.**"]
    positions = [text.index(s) for s in steps]
    assert positions == sorted(positions)


def test_board_reference_lists_columns_labels_and_value_formats():
    text = read(BOARD)
    for col in (planner.STATUS_COL, planner.TYPE_COL, planner.PROJECT_COL, planner.LINK_COL,
                planner.NOTES_COL):
        assert col in text, col
    for label in ("To do", "In progress", "Review", "Done", "Stuck", "Backlog", "5105170755"):
        assert label in text, label
    assert '{"label":' in text and '{"text":' in text and '{"labels": ["' in text


def test_skill_description_has_no_angle_brackets():
    """Cowork plugin validation rejects XML-like tags in a SKILL.md description."""
    front = re.match(r"^---\n(.*?)\n---\n", read(SKILL), re.S).group(1)
    desc = re.search(r"^description:(.*)$", front, re.M).group(1)
    assert "<" not in desc and ">" not in desc


KICKOFF = os.path.join(ROOT, "skills", "monday-kickoff", "SKILL.md")


def test_kickoff_skill_frontmatter_names_the_poll_trigger_without_angle_brackets():
    front = re.match(r"^---\n(.*?)\n---\n", read(KICKOFF), re.S).group(1)
    assert re.search(r"^name: monday-kickoff$", front, re.M)
    desc = re.search(r"^description:(.*)$", front, re.M).group(1)
    assert "<" not in desc and ">" not in desc
    for trigger in ("scheduled", "poll", "gather requirements", "kickoff"):
        assert trigger in desc.lower(), trigger


def test_kickoff_skill_covers_cli_markers_spec_files_and_guardrails():
    text = read(KICKOFF)
    for needle in ("${CLAUDE_PLUGIN_ROOT}/hooks/cli.py", "kickoff-candidates --items", "--now",
                   "references/projects.json", "device_bash", "test -d", "get_board_items_page",
                   "get_updates", "create_update", "update_items", "PushNotification",
                   "Gather Requirements", "Implementation Ready", "Stuck", "needs_project", "stuck",
                   "🤖 isdd kickoff started (attempt N)", "🤖 isdd kickoff done",
                   "🤖 isdd kickoff needs-project", "requirements/requirements.md",
                   "design/design.md", "tasks/tasks.md", "recap/recap.md", "workflow-state.md",
                   "open-questions.md", "Awaiting Implementation Request",
                   "Implementation Requested: No", "never overwrite", "AskUserQuestion",
                   "commit", "agent-TDD", "../monday-sync/references/board.md"):
        assert needle in text, needle


def test_kickoff_skill_steps_follow_the_design_order():
    text = read(KICKOFF)
    steps = ["**Preflight.**", "**Candidates.**", "**Report blockers.**", "**Start.**", "**Draft.**",
             "**Open questions.**", "**Finish on the board.**", "**Never.**"]
    positions = [text.index(s) for s in steps]
    assert positions == sorted(positions)


def test_board_reference_documents_kickoff_labels_mapping_and_markers():
    text = read(BOARD)
    for needle in ("Gather Requirements", "Implementation Ready", "create_update",
                   "🤖 isdd kickoff started", "🤖 isdd kickoff done", "🤖 isdd kickoff needs-project",
                   "Awaiting Implementation Request"):
        assert needle in text, needle
    assert "| To do (git ignored" not in text            # pre-impl phases no longer map to To do


def test_sync_skill_mentions_the_new_status_mapping():
    text = read(SKILL)
    assert "Gather Requirements" in text and "Implementation Ready" in text
    assert "monday-kickoff" in text


def test_kickoff_skill_review_fixes_are_documented():
    text = read(KICKOFF)
    for needle in ("--spec-index", "- Monday Item:", "- Title:", "isdd kickoff retry", "created_at",
                   "set -C", "test -e", "Spec: <YYYY-MM-DD-slug>", "Source Inputs", "append"):
        assert needle in text, needle
    assert "Spec: <slug>" not in text                    # full folder name, like planner.notes_text
    assert text.index("**Spec index.**") < text.index("**Candidates.**")


def test_board_reference_documents_spec_index_retry_and_created_at():
    text = read(BOARD)
    for needle in ("--spec-index", "Monday Item", "isdd kickoff retry", "created_at"):
        assert needle in text, needle


def test_kickoff_skill_reads_memories_folder_read_only_before_drafting():
    text = read(KICKOFF)
    for needle in ("**Memory.**", "agent-nelly-memory", "sdd-memory", "GLOBAL-MEMORY.md",
                   "MEMORY.md", "Intent:", "read-only", "never write", "## Memory Context"):
        assert needle in text, needle
    assert text.index("**Start.**") < text.index("**Memory.**") < text.index("**Draft.**")
