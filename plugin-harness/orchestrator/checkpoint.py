"""CheckpointManager: Workflow state snapshots and rollback support.

This module provides checkpoint management for creating workflow-state snapshots
before major handoffs (e.g., before agent-tdd spawn) and restoring state on error
detection for rollback recovery.

Checkpoint Schema:
    workflow_state["orchestration"]["checkpoints"] = [
        {
            "checkpoint_id": "uuid",
            "label": "before_agent_tdd_spawn",
            "timestamp": "2026-08-25T10:35:00Z",
            "state_snapshot": { /* workflow_state copy, minus orchestration.checkpoints/handoff_history */ }
        }
    ]

Rollback Marker (in restored state):
    {
        "rollback_pending": {
            "source": "orchestrator_checkpoint_restore",
            "checkpoint_restored": "checkpoint_id",
            "timestamp": "2026-08-25T10:40:00Z",
            "target_phase": "Design",
            "action_required": "Address the error that triggered rollback, then continue"
        }
    }
"""

import copy
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

# Checkpoints retained in orchestration.checkpoints (oldest pruned first).
MAX_CHECKPOINTS = 10

# Entries retained in orchestration.handoff_history (oldest dropped first).
MAX_HANDOFF_HISTORY = 200

# orchestration.* keys that are never copied into a checkpoint's state_snapshot:
# "checkpoints" is self-referential (each snapshot would nest every prior
# checkpoint, doubling workflow-state.json per checkpoint -- this filled a
# 460 GB disk on 2026-09-24), and "handoff_history" is an append-only audit
# log that should survive a rollback rather than be rewound by it. Restoring
# a checkpoint carries both over from the *current* state instead.
SNAPSHOT_EXCLUDED_ORCHESTRATION_KEYS = ("checkpoints", "handoff_history")


def cap_handoff_history(workflow_state: dict, max_entries: int = MAX_HANDOFF_HISTORY) -> None:
    """Trim orchestration.handoff_history in-place to its most recent max_entries."""
    orch = workflow_state.get("orchestration")
    if not isinstance(orch, dict):
        return
    history = orch.get("handoff_history")
    if isinstance(history, list) and len(history) > max_entries:
        orch["handoff_history"] = history[-max_entries:]


def _strip_snapshot_excluded(state: dict) -> dict:
    """Shallow copy of state with SNAPSHOT_EXCLUDED_ORCHESTRATION_KEYS removed.

    Only state and its "orchestration" dict are copied, so the (otherwise
    recursive) excluded data is never deep-copied.
    """
    stripped = dict(state)
    orch = stripped.get("orchestration")
    if isinstance(orch, dict) and any(k in orch for k in SNAPSHOT_EXCLUDED_ORCHESTRATION_KEYS):
        stripped["orchestration"] = {
            k: v for k, v in orch.items() if k not in SNAPSHOT_EXCLUDED_ORCHESTRATION_KEYS
        }
    return stripped


class CheckpointManager:
    """
    Workflow state checkpoint manager: snapshot, restore, and audit.

    Manages creation of workflow-state snapshots before major handoffs (e.g.,
    before spawning agent-tdd) and supports deterministic state restoration
    for rollback recovery. Each checkpoint includes a full state snapshot and
    audit trail (timestamp, label).

    Example usage:
        manager = CheckpointManager()

        # Create checkpoint before major handoff
        checkpoint_id = manager.create_checkpoint(workflow_state, "before_agent_tdd_spawn")

        # On error detection, restore to prior state
        restored = manager.restore_checkpoint(workflow_state, checkpoint_id)

        # Check audit history
        history = manager.get_checkpoint_history(workflow_state)
    """

    def __init__(self):
        """Initialize CheckpointManager (stateless)."""
        pass

    def _get_iso_timestamp(self) -> str:
        """
        Generate ISO 8601 UTC timestamp with Z suffix.

        Returns:
            ISO timestamp string (e.g., "2026-08-25T10:35:00Z")
        """
        return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

    def _ensure_checkpoints_initialized(self, workflow_state: dict) -> None:
        """
        Ensure orchestration.checkpoints structure exists.

        Modifies workflow_state in-place to ensure nested dict structure for
        storing checkpoints. Safe to call multiple times.

        Args:
            workflow_state: Workflow state dict to initialize
        """
        if "orchestration" not in workflow_state:
            workflow_state["orchestration"] = {}
        if "checkpoints" not in workflow_state["orchestration"]:
            workflow_state["orchestration"]["checkpoints"] = []

    def _find_checkpoint(
        self,
        checkpoints: List[dict],
        checkpoint_id: Optional[str] = None
    ) -> Optional[dict]:
        """
        Find checkpoint by id or return most recent.

        Args:
            checkpoints: List of checkpoint dicts
            checkpoint_id: Specific checkpoint id to find. If None, returns most recent.

        Returns:
            Matching checkpoint dict, or None if not found
        """
        if not checkpoints:
            return None

        if checkpoint_id is None:
            return checkpoints[-1]

        for cp in checkpoints:
            if cp["checkpoint_id"] == checkpoint_id:
                return cp

        return None

    def _build_rollback_marker(self, checkpoint_id: str) -> dict:
        """
        Build rollback_pending marker for restored state.

        Args:
            checkpoint_id: ID of the checkpoint being restored from

        Returns:
            Rollback marker dict with source, checkpoint_restored, timestamp, target_phase, action_required
        """
        return {
            "source": "orchestrator_checkpoint_restore",
            "checkpoint_restored": checkpoint_id,
            "timestamp": self._get_iso_timestamp(),
            "target_phase": "Design",
            "action_required": "Address the error that triggered rollback, then continue"
        }

    def record_handoff(self, workflow_state: dict, entry: dict) -> None:
        """
        Append an entry to the workflow's handoff history log.

        Unlike checkpoints (full state snapshots taken before major handoffs),
        this is a lightweight, append-only audit log of routing decisions
        (including ones that don't produce a checkpoint, like an invalid
        handoff or reaching the end of the workflow). Stored alongside
        checkpoints in workflow_state["orchestration"]["handoff_history"].

        Args:
            workflow_state: Workflow state dict to append to (modified in-place)
            entry: Arbitrary dict describing the decision (e.g. current_plugin,
                current_phase, handoff_valid, next_plugin). A "timestamp" key
                is added automatically.

        Example:
            >>> manager.record_handoff(workflow_state, {
            ...     "current_plugin": "agent-isdd",
            ...     "current_phase": "design_approved",
            ...     "handoff_valid": True,
            ...     "next_plugin": "agent-tdd",
            ... })
        """
        if "orchestration" not in workflow_state:
            workflow_state["orchestration"] = {}
        workflow_state["orchestration"].setdefault("handoff_history", []).append({
            **entry,
            "timestamp": self._get_iso_timestamp(),
        })
        cap_handoff_history(workflow_state)

    def get_handoff_history(self, workflow_state: dict) -> List[dict]:
        """
        Retrieve the workflow's handoff history log for audit.

        Returns entries recorded via record_handoff(), most recent first.

        Args:
            workflow_state: Workflow state dict

        Returns:
            List of handoff history entries (most recent first). Empty list
            if none have been recorded.
        """
        if "orchestration" not in workflow_state or \
           "handoff_history" not in workflow_state["orchestration"]:
            return []

        return list(reversed(workflow_state["orchestration"]["handoff_history"]))

    def create_checkpoint(
        self,
        workflow_state: dict,
        checkpoint_label: str
    ) -> str:
        """
        Save snapshot of workflow state before major handoff.

        Creates a checkpoint with full state snapshot, label, and audit timestamp.
        Stored in workflow_state["orchestration"]["checkpoints"] array. Snapshots
        are deep copies, so modifications to original state after checkpoint
        creation do not affect the stored snapshot.

        The snapshot excludes `SNAPSHOT_EXCLUDED_ORCHESTRATION_KEYS`
        (`orchestration.checkpoints` and `orchestration.handoff_history`) --
        otherwise every checkpoint would carry a deep copy of every prior
        checkpoint's own snapshot, making workflow-state.json double in size
        with each handoff. `restore_checkpoint()` carries both over from the
        current state instead. Every other field of workflow_state is preserved.

        After appending, old checkpoints are pruned to the last
        `MAX_CHECKPOINTS` (see `prune_old_checkpoints`), which also strips any
        nested history out of snapshots written by older versions.

        Args:
            workflow_state: The workflow state dict to snapshot
            checkpoint_label: Label describing the checkpoint
                (e.g., "before_agent_tdd_spawn", "before_agent_isdd_spawn")

        Returns:
            checkpoint_id (string UUID) for later restoration or audit

        Example:
            >>> checkpoint_id = manager.create_checkpoint(
            ...     workflow_state, "before_agent_tdd_spawn"
            ... )
            >>> assert isinstance(checkpoint_id, str)  # Valid UUID
        """
        self._ensure_checkpoints_initialized(workflow_state)

        checkpoint_id = str(uuid4())
        timestamp = self._get_iso_timestamp()

        checkpoint = {
            "checkpoint_id": checkpoint_id,
            "label": checkpoint_label,
            "timestamp": timestamp,
            "state_snapshot": copy.deepcopy(_strip_snapshot_excluded(workflow_state))
        }

        workflow_state["orchestration"]["checkpoints"].append(checkpoint)
        self.prune_old_checkpoints(workflow_state)
        return checkpoint_id

    def restore_checkpoint(
        self,
        workflow_state: dict,
        checkpoint_id: Optional[str] = None
    ) -> dict:
        """
        Restore workflow state from checkpoint.

        Retrieves a checkpoint by id, or the most recent if id is None. Returns
        a deep copy of the checkpoint's state snapshot with rollback_pending
        marker added. `orchestration.checkpoints` and
        `orchestration.handoff_history` are carried over from the current
        workflow_state (snapshots never contain them), so saving the restored
        state keeps the checkpoint list and audit log intact. The marker includes source, checkpoint_restored id,
        timestamp, target_phase (default "Design"), and action_required message.

        Args:
            workflow_state: Current workflow state dict (used to find checkpoint)
            checkpoint_id: Specific checkpoint to restore. If None, restores most recent.

        Returns:
            restored_state dict (deep copy of snapshot) with rollback_pending marker

        Raises:
            ValueError: If checkpoint not found or no checkpoints available

        Example:
            >>> restored = manager.restore_checkpoint(workflow_state, checkpoint_id)
            >>> assert restored["rollback_pending"]["checkpoint_restored"] == checkpoint_id
        """
        if "orchestration" not in workflow_state or \
           "checkpoints" not in workflow_state["orchestration"]:
            raise ValueError("No checkpoints available in workflow state")

        checkpoints = workflow_state["orchestration"]["checkpoints"]
        checkpoint = self._find_checkpoint(checkpoints, checkpoint_id)

        if checkpoint is None:
            if checkpoint_id:
                raise ValueError(f"Checkpoint not found: {checkpoint_id}")
            else:
                raise ValueError("No checkpoints available in workflow state")

        # Deep copy the snapshot (stripped, in case it predates the exclusion)
        restored_state = copy.deepcopy(_strip_snapshot_excluded(checkpoint["state_snapshot"]))

        current_orch = workflow_state["orchestration"]
        restored_orch = restored_state.get("orchestration")
        if not isinstance(restored_orch, dict):
            restored_orch = restored_state["orchestration"] = {}
        for key in SNAPSHOT_EXCLUDED_ORCHESTRATION_KEYS:
            if key in current_orch:
                restored_orch[key] = copy.deepcopy(current_orch[key])

        # Add rollback_pending marker
        restored_state["rollback_pending"] = self._build_rollback_marker(
            checkpoint["checkpoint_id"]
        )

        return restored_state

    def get_checkpoint_history(self, workflow_state: dict) -> List[dict]:
        """
        Retrieve checkpoint history for audit trail.

        Returns full list of checkpoints in reverse order (most recent first).
        Useful for auditing checkpoint activity and validating rollback history.

        Args:
            workflow_state: Workflow state dict

        Returns:
            List of checkpoint dicts (most recent first). Empty list if no checkpoints.

        Example:
            >>> history = manager.get_checkpoint_history(workflow_state)
            >>> if history:
            ...     most_recent = history[0]  # Most recent checkpoint
        """
        if "orchestration" not in workflow_state or \
           "checkpoints" not in workflow_state["orchestration"]:
            return []

        checkpoints = workflow_state["orchestration"]["checkpoints"]
        return list(reversed(checkpoints))

    def is_valid_checkpoint(self, checkpoint: dict) -> bool:
        """
        Validate checkpoint has all required fields.

        Checks that checkpoint dict contains all required keys:
        checkpoint_id, label, timestamp, state_snapshot. Used for integrity
        checks when iterating checkpoints or before restore operations.

        Args:
            checkpoint: Checkpoint dict to validate

        Returns:
            True if checkpoint has all required fields, False otherwise

        Example:
            >>> cp = manager.get_checkpoint_history(workflow_state)[0]
            >>> assert manager.is_valid_checkpoint(cp)
        """
        required_fields = ["checkpoint_id", "label", "timestamp", "state_snapshot"]
        return all(field in checkpoint for field in required_fields)

    def prune_old_checkpoints(
        self,
        workflow_state: dict,
        max_checkpoints: int = MAX_CHECKPOINTS
    ) -> None:
        """
        Keep only N most recent checkpoints.

        Modifies workflow_state in-place, removing older checkpoints to prevent
        unbounded growth of the checkpoints array. Safe to call when checkpoints
        array is below max_checkpoints (operation is a no-op). Recommended to
        call periodically (e.g., after each major orchestration phase) to bound
        memory consumption.

        Args:
            workflow_state: Workflow state dict to prune (modified in-place)
            max_checkpoints: Maximum number of checkpoints to keep
                (default MAX_CHECKPOINTS)

        Retained snapshots are also stripped of any nested
        SNAPSHOT_EXCLUDED_ORCHESTRATION_KEYS left by older versions, so a
        workflow-state.json bloated before the fix shrinks on its next checkpoint.

        Example:
            >>> manager.prune_old_checkpoints(workflow_state, max_checkpoints=5)
            >>> assert len(workflow_state["orchestration"]["checkpoints"]) <= 5
        """
        if "orchestration" not in workflow_state or \
           "checkpoints" not in workflow_state["orchestration"]:
            return

        checkpoints = workflow_state["orchestration"]["checkpoints"]
        if len(checkpoints) > max_checkpoints:
            checkpoints = checkpoints[-max_checkpoints:]
            workflow_state["orchestration"]["checkpoints"] = checkpoints

        for cp in checkpoints:
            snapshot = cp.get("state_snapshot") if isinstance(cp, dict) else None
            if isinstance(snapshot, dict):
                cp["state_snapshot"] = _strip_snapshot_excluded(snapshot)
