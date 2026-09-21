"""Smoke test: skill invocation docs stay consistent across the repo.

Wraps scripts/check_skill_invocation_consistency.py so its two rules run as
part of the normal test suite instead of only via manual invocation.
"""
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "check_skill_invocation_consistency.py"


class TestSkillInvocationConsistency(unittest.TestCase):
    def test_no_invocation_model_violations(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode, 0,
            f"skill-invocation consistency check failed:\n{result.stdout}{result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
