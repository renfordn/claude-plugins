"""ErrorLogger: Dual-tier logging for session and persistent error storage.

Also includes ErrorRegistry: JSON lines format with auto-rotation at 10MB.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any
from orchestrator.error import OrchestrationError, HookError


class ErrorLogger:
    """Logs orchestration errors to both session (memory) and persistent (file) storage.

    Session-scoped errors are immediately accessible within the workflow.
    Persistent errors enable cross-session pattern detection.
    """

    def __init__(self):
        """Initialize ErrorLogger with empty session error list."""
        self._session_errors: List[OrchestrationError] = []

    def log_error(self, error: OrchestrationError) -> None:
        """Log error to session-scoped storage (in-memory).

        Args:
            error: OrchestrationError to log
        """
        self._session_errors.append(error)

    def persist_error(self, error: OrchestrationError, base_path: str, project_slug: str) -> None:
        """Persist error to project-wide error registry (file).

        Creates error-registry.json in ~/.claude/sdd-memory/<project_slug>/ if it doesn't exist.
        Appends error to errors[] array.

        Non-blocking; errors logged to session even if file persistence fails.

        Args:
            error: OrchestrationError to persist
            base_path: Base directory path (e.g., ~/.claude/sdd-memory)
            project_slug: Project identifier
        """
        # Always log to session first (non-blocking)
        self.log_error(error)

        try:
            registry_dir = Path(base_path) / project_slug
            registry_dir.mkdir(parents=True, exist_ok=True)

            registry_path = registry_dir / "error-registry.json"

            # Load existing registry or create new
            if registry_path.exists():
                with open(registry_path) as f:
                    registry = json.load(f)
            else:
                registry = {"errors": [], "patterns": []}

            # Append error
            registry["errors"].append(error.to_dict())

            # Write back
            with open(registry_path, "w") as f:
                json.dump(registry, f, indent=2)

        except Exception:
            # Non-blocking: error already logged to session even if persistence fails
            pass

    def get_session_errors(self) -> List[OrchestrationError]:
        """Return all session-scoped errors logged so far.

        Returns:
            List of OrchestrationError objects
        """
        return self._session_errors.copy()

    def clear_session_errors(self) -> None:
        """Clear all session-scoped errors from memory."""
        self._session_errors = []


def persist_best_effort(
    error: OrchestrationError,
    base_path: str,
    project_slug: str,
    log: logging.Logger
) -> None:
    """Persist an error via a fresh ErrorLogger, swallowing and logging any failure.

    Shared by every orchestration call site that persists an error opportunistically
    (plugin_unavailable, interop_parse_failure, handoff_validation): persistence is
    always best-effort and must never raise or affect the caller's own control flow.

    Args:
        error: OrchestrationError to persist
        base_path: Base directory for error-registry.json
        project_slug: Project identifier under base_path
        log: Caller's module logger, used to report a persistence failure
    """
    try:
        ErrorLogger().persist_error(error, base_path, project_slug)
    except Exception as e:
        log.error(
            f"Failed to persist orchestration error: {e.__class__.__name__}: {e}. "
            "Continuing without persistence."
        )


class ErrorRegistry:
    """Structured error logging in JSON lines format with auto-rotation at 10MB.

    Each error is logged as one JSON line: timestamp, hook, agent_type, error_type,
    severity, message, recovery_action.

    Auto-rotates when file exceeds 10MB: error_registry.json → error_registry.<timestamp>.json
    """

    MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10MB

    def __init__(self, registry_path: Path):
        """Initialize ErrorRegistry.

        Args:
            registry_path: Path to error_registry.json file
        """
        self.registry_path = Path(registry_path)

    def log_error(
        self,
        error: HookError,
        hook: str,
        agent_type: str
    ) -> None:
        """Log error to error_registry.json in JSON lines format.

        Args:
            error: HookError to log
            hook: Hook name (e.g., "before_continue", "subagent_stop")
            agent_type: Agent type (e.g., "agent-isdd", "agent-tdd")
        """
        try:
            # Ensure directory exists
            self.registry_path.parent.mkdir(parents=True, exist_ok=True)

            # Build error entry
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "hook": hook,
                "agent_type": agent_type,
                "error_type": error.error_type.value,
                "severity": error.severity,
                "message": error.message,
                "recovery_action": error.recovery_action,
            }

            # Check if rotation needed before writing
            if self.registry_path.exists():
                if self.registry_path.stat().st_size >= self.MAX_SIZE_BYTES:
                    self.rotate_on_size()

            # Append entry as JSON line
            with open(self.registry_path, "a") as f:
                f.write(json.dumps(entry) + "\n")

        except Exception:
            # Graceful degradation: don't block on logging failure
            pass

    def rotate_on_size(self) -> None:
        """Rotate error_registry.json when it exceeds MAX_SIZE_BYTES.

        Renames current file to error_registry.<timestamp>.json.
        """
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            rotated_name = self.registry_path.parent / f"error_registry.{timestamp}.json"
            self.registry_path.rename(rotated_name)
        except Exception:
            # Graceful degradation: rotation failure doesn't block logging
            pass

    def read_errors(self) -> List[Dict[str, Any]]:
        """Read all errors from error_registry.json.

        Returns:
            List of error entries (dicts), one per JSON line
        """
        try:
            if not self.registry_path.exists():
                return []

            errors = []
            with open(self.registry_path) as f:
                for line in f:
                    if line.strip():
                        try:
                            errors.append(json.loads(line))
                        except json.JSONDecodeError:
                            # Skip malformed lines
                            pass
            return errors
        except Exception:
            # Graceful degradation: return empty list on read failure
            return []
