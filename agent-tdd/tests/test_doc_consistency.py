"""Tests that agents/agent-TDD.md and agents/test-author.md stay documented
consistently with the Slice Spec contract defined in INTEROP.md, catching
future drift (a field silently removed from one file but not the others).
"""

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INTEROP_PATH = REPO_ROOT / "INTEROP.md"
AGENT_TDD_PATH = REPO_ROOT / "agents" / "agent-TDD.md"
TEST_AUTHOR_PATH = REPO_ROOT / "agents" / "test-author.md"

# The six Slice Spec fields defined by INTEROP.md's contract. Where a field is
# expressed in the wild as one of several acceptable substrings (e.g. combined
# "Acceptance criteria / Test Intent" phrasing), the entry is a tuple of
# alternatives — a match on any one of them counts as present.
ALL_FIELDS = [
    "Task description",
    ("Acceptance criteria", "Test Intent"),
    "Risk Tier",
    "Data Contracts And Interfaces",
    "Pre-Slice Brief",
    "Review handoff mode",
]

# Concepts that agent-TDD.md must discuss (beyond the raw field names) to
# confirm it documents the full contract, not just the field list.
ALL_CONCEPTS = [
    "high-risk",
    ("review pause", ["mandatory", "review"]),
    "Handoff Facts",
]

# test-author.md only receives a subset of the six fields.
TEST_AUTHOR_FIELDS = [
    "Task description",
    ("Acceptance criteria", "Test Intent"),
    "Data Contracts And Interfaces",
]

# test-author.md must describe the two-part invocation concept: it is spawned
# separately from, and before, agent-TDD.
TEST_AUTHOR_CONCEPTS = [
    (["test-author", "agent-TDD"], ("two-part", "two part")),
]


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _contains(haystack_lower, needle):
    """Return True if `needle` is present in `haystack_lower` (already
    lower-cased). `needle` may be:
      - a plain string: checked as a single case-insensitive substring.
      - a tuple: OR of its items — True if ANY item matches.
      - a list: AND (co-occurrence) group of its items — True if ALL items
        match.
    Items themselves may recursively be strings, tuples, or lists.
    """
    if isinstance(needle, str):
        return needle.lower() in haystack_lower
    if isinstance(needle, tuple):
        return any(_contains(haystack_lower, item) for item in needle)
    if isinstance(needle, list):
        return all(_contains(haystack_lower, item) for item in needle)
    raise TypeError(f"Unsupported needle type: {type(needle)!r}")


def _describe(needle):
    if isinstance(needle, str):
        return repr(needle)
    if isinstance(needle, tuple):
        return "(" + " OR ".join(_describe(item) for item in needle) + ")"
    if isinstance(needle, list):
        return "(" + " AND ".join(_describe(item) for item in needle) + ")"
    raise TypeError(f"Unsupported needle type: {type(needle)!r}")


def _missing(haystack_lower, entries):
    return [
        _describe(entry) for entry in entries if not _contains(haystack_lower, entry)
    ]


class TestInteropDocumentsAllFields(unittest.TestCase):
    def test_interop_documents_all_fields(self):
        text = _read(INTEROP_PATH).lower()
        missing = _missing(text, ALL_FIELDS)
        self.assertEqual(
            missing,
            [],
            f"INTEROP.md is missing Slice Spec field(s): {missing}",
        )


class TestAgentTddDocumentsFullContract(unittest.TestCase):
    def test_agent_tdd_documents_full_contract(self):
        text = _read(AGENT_TDD_PATH).lower()
        missing_fields = _missing(text, ALL_FIELDS)
        missing_concepts = _missing(text, ALL_CONCEPTS)
        self.assertEqual(
            missing_fields,
            [],
            f"agents/agent-TDD.md is missing Slice Spec field(s): {missing_fields}",
        )
        self.assertEqual(
            missing_concepts,
            [],
            f"agents/agent-TDD.md is missing contract concept(s): {missing_concepts}",
        )


class TestTestAuthorDocumentsItsSubset(unittest.TestCase):
    def test_test_author_documents_its_subset(self):
        text = _read(TEST_AUTHOR_PATH).lower()
        missing_fields = _missing(text, TEST_AUTHOR_FIELDS)
        missing_concepts = _missing(text, TEST_AUTHOR_CONCEPTS)
        self.assertEqual(
            missing_fields,
            [],
            f"agents/test-author.md is missing Slice Spec field(s): {missing_fields}",
        )
        self.assertEqual(
            missing_concepts,
            [],
            f"agents/test-author.md is missing contract concept(s): {missing_concepts}",
        )


if __name__ == "__main__":
    unittest.main()
