"""Hook error logging — make all hook errors observable.

Maintains a hook_error_log.txt file in the workflow state directory so errors
are visible to users/developers, not silent or hidden in workflow-state.json.

Best practice: All hook failures are logged with timestamp, error type, message,
and recovery hint — never silent failures.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class HookErrorLogger:
    """Logger for hook errors with file and console output."""

    def __init__(self, workflow_state_dir: Optional[Path] = None):
        """Initialize hook error logger.

        Args:
            workflow_state_dir: Path to workflow state directory (e.g., ~/.claude/sdd-memory/project/spec/feature/)
                              If None, logs only to console (degraded mode).
        """
        self.workflow_state_dir = workflow_state_dir
        self.error_log_path = None
        if workflow_state_dir:
            self.error_log_path = workflow_state_dir / "hook_error_log.txt"

    def log_error(
        self,
        error_type: str,
        error_message: str,
        recovery_hint: str = "Continuing with graceful degradation",
        hook_name: str = "unknown"
    ) -> None:
        """Log a hook error to file and console.

        Args:
            error_type: Type of error (e.g., "FileNotFoundError", "JSON parse error", "Network error")
            error_message: Detailed error message
            recovery_hint: What the hook will do as recovery (e.g., "Continuing without context")
            hook_name: Name of hook (e.g., "before_continue", "subagent_stop")
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        log_entry = f"[{timestamp}] {hook_name} ERROR [{error_type}]: {error_message}. Recovery: {recovery_hint}"

        # Log to console
        logger.error(log_entry)

        # Log to file
        if self.error_log_path:
            try:
                self.error_log_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.error_log_path, "a", encoding="utf-8") as f:
                    f.write(log_entry + "\n")
            except (IOError, OSError) as e:
                # Even error logging failed — log to console only
                logger.error(f"Failed to write hook error log: {e}. Continuing without file logging.")

    def log_hook_status(
        self,
        hook_name: str,
        status: str,
        details: Optional[str] = None
    ) -> None:
        """Log hook status/checkpoint for observability.

        Args:
            hook_name: Name of hook
            status: Status message (e.g., "starting", "completed", "degraded")
            details: Additional details
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        details_str = f" ({details})" if details else ""
        log_entry = f"[{timestamp}] {hook_name} {status.upper()}{details_str}"

        logger.info(log_entry)

        if self.error_log_path:
            try:
                self.error_log_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.error_log_path, "a", encoding="utf-8") as f:
                    f.write(log_entry + "\n")
            except (IOError, OSError):
                pass  # Silent failure on log file I/O


def get_hook_error_logger(workflow_state_dir: Optional[Path] = None) -> HookErrorLogger:
    """Get or create a hook error logger.

    Args:
        workflow_state_dir: Path to workflow state directory

    Returns:
        HookErrorLogger instance
    """
    return HookErrorLogger(workflow_state_dir)
