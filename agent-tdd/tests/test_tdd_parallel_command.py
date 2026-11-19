import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CMD = ROOT / "commands" / "tdd-parallel.md"
REF = ROOT / "references" / "parallel-delivery.md"
NEEDLES = ["isolation", "worktree.baseRef", "verify-branch", "Review scope", "Review cwd",
           "integration", "git revert -m 1", "merge --abort", "SLICE-ID", 'parallel_plan.py" check',
           "AskUserQuestion", "pre_wave_sha", "--slice-id", "--base", "merge-base --is-ancestor",
           "agent-tdd:agent-TDD", "all_slices_complete", "worktreePath"]


class TddParallelCommandTests(unittest.TestCase):
    def test_command_frontmatter_and_pointer(self):
        text = CMD.read_text()
        fm = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        self.assertIsNotNone(fm)
        fields = dict(l.split(":", 1) for l in fm.group(1).splitlines() if ":" in l)
        desc = fields["description"].strip()
        self.assertTrue(0 < len(desc) <= 110, len(desc))
        self.assertTrue(fields.get("argument-hint", "").strip())
        self.assertIn("references/parallel-delivery.md", text)

    def test_review_findings_needles(self):
        text = REF.read_text()
        for n in ["git -C <worktreePath> diff --stat <base>", "git -C <worktreePath> status --porcelain",
                  "uncommitted", "git diff <base>", "untracked",
                  "Validation slice", "no Red/Green", "Test Files", "Shared Files",
                  "every merge of the wave", "do not re-queue"]:
            self.assertIn(n, text, n)
        self.assertNotIn("--base <base>)", text)

    def test_scripts_use_plugin_root(self):
        text = REF.read_text()
        self.assertIn('python3 "${CLAUDE_PLUGIN_ROOT}/scripts/parallel_plan.py"', text)
        self.assertIn('python3 "${CLAUDE_PLUGIN_ROOT}/scripts/tdd_check.py"', text)
        self.assertNotRegex(text, r"(?<!/)scripts/(parallel_plan|tdd_check)\.py")
        self.assertNotRegex(text, r"python3 (scripts/|parallel_plan|tdd_check)")

    def test_reference_has_protocol_needles(self):
        text = REF.read_text()
        for n in NEEDLES:
            self.assertIn(n, text, n)


if __name__ == "__main__":
    unittest.main()
