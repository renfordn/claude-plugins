import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))

import isdd_markers as markers


class MarkersTests(unittest.TestCase):
    def test_marker_beats_prose_and_title(self):
        text = "Slice 3: other\n<!--SLICE-ID: 2f2-->\nreusing Slice 1's helper"
        self.assertEqual(markers.parse_slice_id_strict(text), "2F2")

    def test_title_on_first_line_only(self):
        self.assertEqual(markers.parse_slice_id_strict("Slice 4: x"), "4")
        self.assertIsNone(markers.parse_slice_id_strict("intro\nSlice 4: x"))

    def test_prose_mention_never_yields_id(self):
        self.assertIsNone(markers.parse_slice_id_strict("reusing Slice 1's helper"))

    def test_id_regex_shape(self):
        self.assertEqual(markers.parse_review_scope("<!--REVIEW-SCOPE: slice=12ab-->"), "12ab")
        self.assertIsNone(markers.parse_review_scope("<!--REVIEW-SCOPE: slice=abc-->"))
        self.assertEqual(markers.scope_marker(2), "<!--REVIEW-SCOPE: slice=2-->")


if __name__ == "__main__":
    unittest.main()
