"""Tests for scripts/merge_plugin_data.py (stdlib unittest, mirrors test_first_class_check.py)."""
import os
import shutil
import tempfile
import time
import unittest

from merge_plugin_data import main, merge


def _write(root, rel, text, mtime=None):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def _read(root, rel):
    with open(os.path.join(root, rel)) as f:
        return f.read()


class MergeTests(unittest.TestCase):
    def setUp(self):
        base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, base)
        self.src = os.path.join(base, "agent-nelly-inline")
        self.dst = os.path.join(base, "agent-nelly-renfordn-plugins")
        os.makedirs(self.src)
        os.makedirs(self.dst)

    def test_copies_missing_files(self):
        _write(self.src, "mem/proj/entries/a.md", "A")
        merge(self.src, self.dst)
        self.assertEqual(_read(self.dst, "mem/proj/entries/a.md"), "A")

    def test_skips_test_leftovers_and_ds_store(self):
        _write(self.src, "mem/var-folders-xyz-tmpabc/state.json", "{}")
        _write(self.src, "mem/tmp-some-test-project/x.md", "x")
        _write(self.src, ".DS_Store", "junk")
        merge(self.src, self.dst)
        self.assertEqual(os.listdir(self.dst), [])

    def test_memory_index_is_line_union(self):
        _write(self.dst, "mem/proj/MEMORY.md", "# Index\n\n- [A](a.md) — a\n")
        _write(self.src, "mem/proj/MEMORY.md", "# Index\n\n- [B](b.md) — b\n- [A](a.md) — a\n")
        merge(self.src, self.dst)
        self.assertEqual(_read(self.dst, "mem/proj/MEMORY.md"),
                         "# Index\n\n- [A](a.md) — a\n- [B](b.md) — b\n")

    def test_global_memory_is_block_union(self):
        header = "# Global\n"
        _write(self.dst, "mem/global/GLOBAL-MEMORY.md", header + "\n---\nname: one\n")
        _write(self.src, "mem/global/GLOBAL-MEMORY.md", header + "\n---\nname: two\n\n---\nname: one\n")
        merge(self.src, self.dst)
        text = _read(self.dst, "mem/global/GLOBAL-MEMORY.md")
        self.assertEqual(text.count("name: one"), 1)
        self.assertIn("name: two", text)

    def test_history_appends_missing_lines(self):
        _write(self.dst, "sdd/p/DOC-AUDIT-HISTORY.md", "- run 1\n")
        _write(self.src, "sdd/p/DOC-AUDIT-HISTORY.md", "- run 1\n- run 2\n")
        merge(self.src, self.dst)
        self.assertEqual(_read(self.dst, "sdd/p/DOC-AUDIT-HISTORY.md"), "- run 1\n- run 2\n")

    def test_newer_source_wins_and_older_is_kept(self):
        now = time.time()
        _write(self.dst, "sdd/p/state.json", "old", mtime=now - 100)
        _write(self.src, "sdd/p/state.json", "new", mtime=now)
        merge(self.src, self.dst)
        self.assertEqual(_read(self.dst, "sdd/p/state.json"), "new")
        self.assertEqual(_read(self.dst, "sdd/p/state.json.conflict-agent-nelly-renfordn-plugins"), "old")

    def test_newer_destination_is_kept_and_source_saved_beside_it(self):
        now = time.time()
        _write(self.dst, "sdd/p/state.json", "new", mtime=now)
        _write(self.src, "sdd/p/state.json", "old", mtime=now - 100)
        merge(self.src, self.dst)
        self.assertEqual(_read(self.dst, "sdd/p/state.json"), "new")
        self.assertEqual(_read(self.dst, "sdd/p/state.json.conflict-agent-nelly-inline"), "old")

    def test_dry_run_writes_nothing(self):
        _write(self.src, "mem/proj/entries/a.md", "A")
        report = merge(self.src, self.dst, dry_run=True)
        self.assertEqual(report, [("copy", os.path.join("mem", "proj", "entries", "a.md"), "")])
        self.assertEqual(os.listdir(self.dst), [])

    def test_source_is_never_modified(self):
        _write(self.src, "mem/proj/MEMORY.md", "- [B](b.md)\n")
        _write(self.dst, "mem/proj/MEMORY.md", "- [A](a.md)\n")
        merge(self.src, self.dst)
        self.assertEqual(_read(self.src, "mem/proj/MEMORY.md"), "- [B](b.md)\n")

    def test_delete_source_refused_when_conflicts(self):
        now = time.time()
        _write(self.dst, "x.json", "a", mtime=now)
        _write(self.src, "x.json", "b", mtime=now - 100)
        self.assertEqual(main([self.src, self.dst, "--delete-source"]), 1)
        self.assertTrue(os.path.isdir(self.src))

    def test_delete_source_after_clean_merge(self):
        _write(self.src, "mem/proj/entries/a.md", "A")
        self.assertEqual(main([self.src, self.dst, "--delete-source"]), 0)
        self.assertFalse(os.path.exists(self.src))

    def test_same_dir_rejected(self):
        self.assertEqual(main([self.dst, self.dst]), 2)


if __name__ == "__main__":
    unittest.main()
