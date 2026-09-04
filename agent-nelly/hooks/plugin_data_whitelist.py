"""Shared plugin_data permission validators and audit logging.

Provides centralized validators for:
- File-type restrictions (blocklist: .exe)
- Directory scoping (per-agent namespace enforcement)
- Audit trail logging
- Environment-variable gates for backward compatibility
"""

import os
import time
from typing import Callable, Dict, Any, Optional


# File types to block
BLOCKED_FILE_TYPES = {".exe"}


def create_whitelist_validator(check_namespace: bool = True) -> Callable[[str, str, str], Dict[str, Any]]:
    """Create a validator function for plugin_data writes.

    Args:
        check_namespace: If True, enforce plugin-data/<plugin_name>/ namespace.
                        If False, only check file types (for memory-dir use).

    Returns:
        A callable that takes (file_path, operation, plugin_name) and returns
        a dict with 'allowed' (bool) and 'reason' (str).
    """

    def validate(
        file_path: str,
        operation: str,
        plugin_name: str,
    ) -> Dict[str, Any]:
        """Validate a write operation against whitelist rules.

        Args:
            file_path: Full path to the file being written
            operation: "read", "write", or "delete"
            plugin_name: Name of the agent/plugin making the write

        Returns:
            {"allowed": bool, "reason": str}
        """
        # Check file-type blocklist
        _, ext = os.path.splitext(file_path)
        if ext.lower() in BLOCKED_FILE_TYPES:
            return {
                "allowed": False,
                "reason": f"Executable files blocked: {ext}",
            }

        if check_namespace:
            # Check directory scope: file must be under ~/.claude/plugin-data/<plugin_name>/
            # Extract the agent from the path and verify it matches the plugin_name
            normalized_path = os.path.normpath(file_path)

            # Check if path contains the plugin-data/<plugin_name>/ pattern
            plugin_namespace = f"plugin-data{os.sep}{plugin_name}{os.sep}"
            if plugin_namespace not in normalized_path:
                return {
                    "allowed": False,
                    "reason": f"Cross-namespace access denied: {plugin_name} cannot write outside its namespace",
                }

        return {
            "allowed": True,
            "reason": "File type allowed" + (" and namespace valid" if check_namespace else ""),
        }

    return validate


def create_audit_logger() -> Callable[[str, str, str, bool, str], Dict[str, Any]]:
    """Create an audit logger function.

    Returns:
        A callable that takes (operation, file_path, plugin_name, allowed, reason)
        and returns an audit entry dict with timestamp and metadata.
    """

    def log_entry(
        operation: str,
        file_path: str,
        plugin_name: str,
        allowed: bool,
        reason: str,
    ) -> Dict[str, Any]:
        """Create an audit trail entry.

        Args:
            operation: "read", "write", or "delete"
            file_path: Path to the file
            plugin_name: Name of the agent/plugin
            allowed: Whether the operation was allowed
            reason: Explanation for the decision

        Returns:
            Audit entry dict with timestamp, plugin_name, operation, allowed, reason
        """
        return {
            "timestamp": time.time(),
            "plugin_name": plugin_name,
            "operation": operation,
            "file_path": file_path,
            "allowed": allowed,
            "reason": reason,
        }

    return log_entry


def should_use_env_gate(gate_var: str) -> bool:
    """Check if an environment-variable gate is set.

    Args:
        gate_var: Name of the environment variable (e.g., "NELLY_GATE", "SDD_GATE")

    Returns:
        True if the gate variable is set (regardless of value), False otherwise.
    """
    return gate_var in os.environ
