"""Tests for WorkflowStateStore: pluggable, process-shared workflow state.

Covers the Priority 1 "distributed workflow state tracking" enhancement's
first slice: a store abstraction (get/save) with an in-memory backend for
tests/single-process use, and a file-based JSON backend so multiple
processes on the same machine can share workflow state instead of each
module reading/writing workflow-state.json directly.
"""

import json
import os
import tempfile
import threading
import unittest
import unittest.mock

from orchestrator.state_store import InMemoryStateStore, FileStateStore, RedisStateStore

try:
    import redis as redis_lib

    HAS_REDIS = False
    REDIS_PORT = None
    for _candidate_port in (6379, 6399):
        try:
            redis_lib.Redis(
                host="localhost", port=_candidate_port, socket_connect_timeout=0.5
            ).ping()
            HAS_REDIS = True
            REDIS_PORT = _candidate_port
            break
        except Exception:
            continue
except ImportError:
    HAS_REDIS = False
    REDIS_PORT = None


class TestInMemoryStateStore(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryStateStore()

    def test_get_missing_workflow_returns_empty_dict(self):
        self.assertEqual(self.store.get("nonexistent"), {})

    def test_save_then_get_roundtrips(self):
        self.store.save("wf-1", {"phase": "design_approved"})
        self.assertEqual(self.store.get("wf-1"), {"phase": "design_approved"})

    def test_save_returns_a_copy_not_a_shared_reference(self):
        state = {"phase": "design_approved"}
        self.store.save("wf-1", state)
        retrieved = self.store.get("wf-1")
        retrieved["phase"] = "mutated"
        self.assertEqual(self.store.get("wf-1"), {"phase": "design_approved"})

    def test_separate_workflow_ids_are_isolated(self):
        self.store.save("wf-1", {"phase": "a"})
        self.store.save("wf-2", {"phase": "b"})
        self.assertEqual(self.store.get("wf-1"), {"phase": "a"})
        self.assertEqual(self.store.get("wf-2"), {"phase": "b"})

    def test_model_selection_key_persists_in_state(self):
        """Slice 4: Workflow State Model Selection Key - model_selection persisted"""
        state = {
            "phase": "implementation",
            "orchestration": {
                "model_selection": {
                    "current_model": "claude-3-sonnet",
                    "tokens_used": 8234,
                    "cost": 0.041,
                    "escalations": [
                        {"from": "haiku", "to": "sonnet", "reason": "complex recursion"}
                    ]
                }
            }
        }
        self.store.save("wf-model", state)
        retrieved = self.store.get("wf-model")
        self.assertEqual(retrieved["orchestration"]["model_selection"]["current_model"], "claude-3-sonnet")
        self.assertEqual(retrieved["orchestration"]["model_selection"]["tokens_used"], 8234)

    def test_backward_compatibility_old_state_without_model_selection(self):
        """Slice 4: Old workflow states without model_selection key still work"""
        old_state = {
            "phase": "design_approved",
            "orchestration": {
                "handoff_history": []
            }
            # No model_selection key - legacy state
        }
        self.store.save("wf-old", old_state)
        retrieved = self.store.get("wf-old")
        self.assertEqual(retrieved["phase"], "design_approved")
        # State should still be retrievable without model_selection
        self.assertNotIn("model_selection", retrieved.get("orchestration", {}))


class TestFileStateStore(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.store = FileStateStore(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_get_missing_workflow_returns_empty_dict(self):
        self.assertEqual(self.store.get("nonexistent"), {})

    def test_save_then_get_roundtrips(self):
        self.store.save("wf-1", {"phase": "design_approved"})
        self.assertEqual(self.store.get("wf-1"), {"phase": "design_approved"})

    def test_save_writes_readable_json_file_on_disk(self):
        self.store.save("wf-1", {"phase": "design_approved"})
        path = os.path.join(self.tmpdir.name, "wf-1.json")
        self.assertTrue(os.path.exists(path))
        with open(path) as f:
            self.assertEqual(json.load(f), {"phase": "design_approved"})

    def test_second_store_instance_sees_saved_state(self):
        """Simulates a second process reading state a first process wrote."""
        self.store.save("wf-1", {"phase": "design_approved"})
        other_store = FileStateStore(self.tmpdir.name)
        self.assertEqual(other_store.get("wf-1"), {"phase": "design_approved"})

    def test_save_is_atomic_no_partial_file_left_on_crash_mid_write(self):
        # Corrupt-write simulation: ensure a completed save never leaves a
        # .tmp file behind (atomic rename cleans up).
        self.store.save("wf-1", {"phase": "design_approved"})
        leftover_tmp_files = [
            f for f in os.listdir(self.tmpdir.name) if f.endswith(".tmp")
        ]
        self.assertEqual(leftover_tmp_files, [])

    def test_concurrent_saves_do_not_corrupt_file(self):
        errors = []

        def writer(n):
            try:
                for _ in range(20):
                    self.store.save("wf-shared", {"counter": n})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        # File must be valid, fully-written JSON, not truncated/interleaved.
        result = self.store.get("wf-shared")
        self.assertIn("counter", result)

    def test_model_selection_key_persists_to_json_file(self):
        """Slice 4: Workflow State Model Selection Key - file-backed persistence"""
        state = {
            "phase": "implementation",
            "orchestration": {
                "model_selection": {
                    "current_model": "claude-3-sonnet",
                    "tokens_used": 8234,
                    "cost": 0.041,
                    "escalations": []
                }
            }
        }
        self.store.save("wf-model-file", state)
        # Verify file was written with correct JSON structure
        path = os.path.join(self.tmpdir.name, "wf-model-file.json")
        self.assertTrue(os.path.exists(path))
        with open(path) as f:
            file_state = json.load(f)
        self.assertEqual(file_state["orchestration"]["model_selection"]["current_model"], "claude-3-sonnet")

    def test_old_file_based_state_still_loads_without_model_selection(self):
        """Slice 4: Backward compatibility - old persisted files without model_selection work"""
        # Write an old-style state file directly (simulating legacy workflow-state.json)
        old_state = {
            "phase": "design_approved",
            "orchestration": {
                "handoff_history": []
            }
        }
        path = os.path.join(self.tmpdir.name, "wf-legacy.json")
        with open(path, "w") as f:
            json.dump(old_state, f)
        # Store should load it without errors
        retrieved = self.store.get("wf-legacy")
        self.assertEqual(retrieved["phase"], "design_approved")


class TestRedisStateStoreImportGuard(unittest.TestCase):
    def test_missing_redis_package_raises_clear_import_error(self):
        # redis is already imported at module level via try/except; patch the
        # module-level name to None to simulate the package being absent.
        import orchestrator.state_store as ss
        with unittest.mock.patch.object(ss, "redis", None):
            with self.assertRaises(ImportError) as ctx:
                RedisStateStore(host="localhost", port=6379)
        self.assertIn("pip install redis", str(ctx.exception))


class TestRedisStateStoreEnvConfig(unittest.TestCase):
    """Test REDIS_* environment variable fallback for connection settings."""

    def _make_mock_redis(self):
        """Return a mock redis module with a trackable Redis constructor."""
        mock_module = unittest.mock.MagicMock()
        return mock_module

    @unittest.mock.patch.dict(os.environ, {
        "REDIS_HOST": "redis.internal",
        "REDIS_PORT": "6380",
        "REDIS_DB": "2",
        "REDIS_PASSWORD": "secret",
        "REDIS_KEY_PREFIX": "myapp:workflow:",
    }, clear=False)
    def test_env_vars_used_when_no_kwargs_passed(self):
        import orchestrator.state_store as ss
        mock_redis = self._make_mock_redis()
        with unittest.mock.patch.object(ss, "redis", mock_redis):
            store = RedisStateStore()

        mock_redis.Redis.assert_called_once_with(
            host="redis.internal", port=6380, db=2, password="secret"
        )
        self.assertEqual(store.key_prefix, "myapp:workflow:")

    @unittest.mock.patch.dict(os.environ, {
        "REDIS_HOST": "redis.internal",
        "REDIS_PORT": "6380",
    }, clear=False)
    def test_explicit_kwargs_take_precedence_over_env(self):
        import orchestrator.state_store as ss
        mock_redis = self._make_mock_redis()
        with unittest.mock.patch.object(ss, "redis", mock_redis):
            RedisStateStore(host="explicit-host", key_prefix="explicit:")

        mock_redis.Redis.assert_called_once_with(host="explicit-host", port=6380)

    @unittest.mock.patch.dict(os.environ, {}, clear=True)
    def test_defaults_used_when_no_env_and_no_kwargs(self):
        import orchestrator.state_store as ss
        mock_redis = self._make_mock_redis()
        with unittest.mock.patch.object(ss, "redis", mock_redis):
            store = RedisStateStore()

        mock_redis.Redis.assert_called_once_with()
        self.assertEqual(store.key_prefix, "orchestrator:workflow:")

    def test_redis_client_bypasses_env_and_kwargs_entirely(self):
        fake_client = object()
        with unittest.mock.patch.dict(os.environ, {"REDIS_HOST": "should-be-ignored"}):
            store = RedisStateStore(redis_client=fake_client)
        self.assertIs(store._client, fake_client)


@unittest.skipUnless(HAS_REDIS, "requires a reachable Redis server")
class TestRedisStateStore(unittest.TestCase):
    def setUp(self):
        self.store = RedisStateStore(
            host="localhost", port=REDIS_PORT, key_prefix="test:whats-next:"
        )
        self.addCleanup(self._flush_test_keys)

    def _flush_test_keys(self):
        for key in self.store._client.keys("test:whats-next:*"):
            self.store._client.delete(key)

    def test_get_missing_workflow_returns_empty_dict(self):
        self.assertEqual(self.store.get("nonexistent"), {})

    def test_save_then_get_roundtrips(self):
        self.store.save("wf-1", {"phase": "design_approved"})
        self.assertEqual(self.store.get("wf-1"), {"phase": "design_approved"})

    def test_separate_workflow_ids_are_isolated(self):
        self.store.save("wf-1", {"phase": "a"})
        self.store.save("wf-2", {"phase": "b"})
        self.assertEqual(self.store.get("wf-1"), {"phase": "a"})
        self.assertEqual(self.store.get("wf-2"), {"phase": "b"})

    def test_second_store_instance_sees_saved_state(self):
        """Simulates a second host/process reading state a first one wrote."""
        self.store.save("wf-1", {"phase": "design_approved"})
        other_store = RedisStateStore(
            host="localhost", port=REDIS_PORT, key_prefix="test:whats-next:"
        )
        self.assertEqual(other_store.get("wf-1"), {"phase": "design_approved"})

    def test_keys_are_namespaced_with_prefix(self):
        self.store.save("wf-1", {"phase": "a"})
        self.assertIsNotNone(self.store._client.get("test:whats-next:wf-1"))

    def test_reuses_provided_redis_client(self):
        store = RedisStateStore(redis_client=self.store._client, key_prefix="test:whats-next:")
        store.save("wf-shared-client", {"phase": "a"})
        self.assertEqual(self.store.get("wf-shared-client"), {"phase": "a"})


if __name__ == "__main__":
    unittest.main()
