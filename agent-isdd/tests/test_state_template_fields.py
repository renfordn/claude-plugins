import json
import os
import unittest

REFS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "references")


class StateTemplateFieldsTests(unittest.TestCase):
    def test_json_template_has_new_fields(self):
        with open(os.path.join(REFS, "workflow-state.template.json")) as fh:
            data = json.load(fh)
        for key in ("risk", "risk_reason", "implementation_mode", "approval_hash", "review_fallback"):
            self.assertIn(key, data)

    def test_markdown_template_lists_new_fields(self):
        with open(os.path.join(REFS, "artifact-templates.md")) as fh:
            text = fh.read()
        for field in ("Risk", "Risk Reason", "Implementation Mode", "Approval Hash", "Review Fallback"):
            self.assertIn("- %s: <" % field, text)


if __name__ == "__main__":
    unittest.main()
