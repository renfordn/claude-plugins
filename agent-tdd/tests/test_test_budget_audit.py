import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "skills" / "test-budget" / "scripts" / "audit_tests.py"
spec = importlib.util.spec_from_file_location("audit_tests", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class TestAudit(unittest.TestCase):
    def test_extracts_names_across_frameworks(self):
        py = "def test_a():\n    pass\nasync def test_b():\n    pass\n"
        js = "it('does x', () => {})\ntest(\"does y\", () => {})\n"
        self.assertEqual(audit.extract_test_names(py), ["test_a", "test_b"])
        self.assertEqual(audit.extract_test_names(js), ["does x", "does y"])

    def test_clusters_near_duplicates(self):
        names = ["test_total_with_tax", "test_total_with_discount", "test_total_with_both", "test_refund"]
        found = audit.clusters(names)
        self.assertEqual(len(found), 1)
        self.assertEqual(len(next(iter(found.values()))), 3)

    def test_cli_reports_candidates(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "test_orders.py"
            f.write_text("".join(f"def test_total_with_{i}():\n    pass\n" for i in "abc"))
            self.assertEqual(audit.main([str(f)]), 0)

    def test_missing_target_exits_2(self):
        self.assertEqual(audit.main(["/nonexistent/path"]), 2)


if __name__ == "__main__":
    unittest.main()
