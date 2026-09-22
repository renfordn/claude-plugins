"""Pre-Commit Drift Validator Hook: Detect INTEROP.md vs. code schema divergence.

This module implements a PreToolUse hook that intercepts git commits and validates that
any changes to INTEROP.md files are reflected in corresponding validation code (interop_parser.py).
"""

import json
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from orchestrator.schema_extractor import SchemaExtractor

logger = logging.getLogger(__name__)


class InteropDriftValidator:
    """Validates INTEROP.md changes against validation code."""

    def __init__(self, repo_root: Optional[Path] = None):
        """Initialize the validator.

        Args:
            repo_root: Root directory of the git repository (default: current directory).
        """
        self.repo_root = repo_root or Path.cwd()
        self.schema_extractor = SchemaExtractor(base_dir=self.repo_root)

    def get_staged_files(self) -> List[str]:
        """Get list of staged files.

        Returns:
            List of file paths that are staged for commit.
        """
        try:
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip().split('\n') if result.stdout.strip() else []
            return []
        except Exception as e:
            logger.warning(f"Failed to get staged files: {e}")
            return []

    def get_file_content_before(self, file_path: str) -> Optional[str]:
        """Get file content from HEAD (before staged changes).

        Args:
            file_path: Path to file (relative to repo root).

        Returns:
            File content as string, or None if not found.
        """
        try:
            result = subprocess.run(
                ["git", "show", f"HEAD:{file_path}"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout
            return None
        except Exception as e:
            logger.debug(f"Cannot get content of HEAD:{file_path}: {e}")
            return None

    def get_file_content_staged(self, file_path: str) -> Optional[str]:
        """Get file content from index (staged changes).

        Args:
            file_path: Path to file (relative to repo root).

        Returns:
            File content as string, or None if not found.
        """
        try:
            result = subprocess.run(
                ["git", "show", f":{file_path}"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout
            return None
        except Exception as e:
            logger.debug(f"Cannot get staged content of {file_path}: {e}")
            return None

    def extract_schema_from_text(self, plugin_name: str, capability_id: str, text: str) -> Dict[str, str]:
        """Extract schema from INTEROP.md text.

        Args:
            plugin_name: Name of the plugin.
            capability_id: Name of the capability.
            text: File content.

        Returns:
            Dict mapping field names to types.
        """
        schema = self.schema_extractor.extract_schema_from_content(
            plugin_name, capability_id, text
        )
        if schema:
            return {f.name: f.type_name for f in schema.fields.values()}
        return {}

    def compare_schemas(
        self,
        before_schema: Dict[str, str],
        after_schema: Dict[str, str]
    ) -> Tuple[List[str], List[str], List[Tuple[str, str, str]]]:
        """Compare two schemas and identify drift.

        Args:
            before_schema: Schema before changes.
            after_schema: Schema after changes.

        Returns:
            Tuple of (added_fields, removed_fields, type_mismatches)
        """
        added = []
        removed = []
        mismatches = []

        # Check for added fields
        for field_name in after_schema:
            if field_name not in before_schema:
                added.append(field_name)

        # Check for removed fields
        for field_name in before_schema:
            if field_name not in after_schema:
                removed.append(field_name)

        # Check for type mismatches
        for field_name in before_schema:
            if field_name in after_schema:
                if before_schema[field_name] != after_schema[field_name]:
                    mismatches.append((
                        field_name,
                        before_schema[field_name],
                        after_schema[field_name]
                    ))

        return added, removed, mismatches

    def validate_drift(self) -> Tuple[bool, List[str]]:
        """Validate that staged INTEROP.md changes match validation code.

        Returns:
            Tuple of (is_valid, error_messages)
            - is_valid: True if no drift detected (commit allowed)
            - error_messages: List of drift error descriptions
        """
        # Check for SDD_GATE environment variable (escape hatch)
        if os.environ.get("SDD_GATE") == "off":
            logger.info("SDD_GATE=off: drift validation skipped")
            return True, []

        errors = []
        staged_files = self.get_staged_files()

        # Filter to INTEROP.md files only
        interop_files = [f for f in staged_files if "INTEROP.md" in f or "STRUCTURE.md" in f]

        if not interop_files:
            # No INTEROP files changed, validation passes
            return True, []

        # For each changed INTEROP.md, validate schema consistency
        for interop_file in interop_files:
            # Extract plugin name from file path
            parts = interop_file.split('/')
            if not parts or len(parts) < 2:
                continue

            plugin_name = parts[0]

            # Get before and after content
            before_content = self.get_file_content_before(interop_file)
            after_content = self.get_file_content_staged(interop_file)

            if not after_content:
                # File was deleted or not accessible
                continue

            # Try to detect capability name from content
            # For now, hardcode expected capabilities per plugin
            expected_capabilities = {
                "agent-isdd": "design_spec_handoff",
                "agent-tdd": "design_spec_slicing",
                "code-reviewer": "code_review",
                "agent-nelly": "memory_brief",
                "agent-cache-plugin": "agent_output_cache",
                "agent-ux": "render_event"
            }

            capability_id = expected_capabilities.get(plugin_name)
            if not capability_id:
                continue

            # Extract schemas before and after
            before_schema = {}
            if before_content:
                before_schema = self.extract_schema_from_text(
                    plugin_name, capability_id, before_content
                )

            after_schema = self.extract_schema_from_text(
                plugin_name, capability_id, after_content
            )

            # If no schema extracted after, skip validation
            if not after_schema:
                continue

            # Compare schemas
            added, removed, mismatches = self.compare_schemas(before_schema, after_schema)

            if added or removed or mismatches:
                # Drift detected - check if code is also updated
                error_msg = f"\nSchema Drift Detected: {interop_file}\n"

                if added:
                    error_msg += f"  Added fields: {', '.join(added)}\n"
                if removed:
                    error_msg += f"  Removed fields: {', '.join(removed)}\n"
                if mismatches:
                    error_msg += "  Type mismatches:\n"
                    for field_name, old_type, new_type in mismatches:
                        error_msg += f"    - {field_name}: {old_type} → {new_type}\n"

                # Check if interop_parser.py is also being updated. Staged paths are
                # repo-relative (plugin-harness/orchestrator/interop_parser.py), so match on
                # basename rather than exact list membership.
                if not any(os.path.basename(f) == "interop_parser.py" for f in staged_files):
                    error_msg += (
                        f"\n  ACTION: Validation code (interop_parser.py) not staged.\n"
                        f"  Update interop_parser.py to reflect these schema changes.\n"
                    )
                    errors.append(error_msg)

        return len(errors) == 0, errors

    def format_error_message(self, errors: List[str]) -> str:
        """Format error messages for display with detailed drift report.

        Args:
            errors: List of error messages.

        Returns:
            Formatted error message string with side-by-side diffs and suggestions.
        """
        if not errors:
            return ""

        message = "\n" + "=" * 75 + "\n"
        message += " INTEROP DRIFT VALIDATION FAILED\n"
        message += "=" * 75 + "\n"

        for error in errors:
            message += error
            message += "\n"

        message += "-" * 75 + "\n"
        message += " ACTION REQUIRED\n"
        message += "-" * 75 + "\n"
        message += " • Update plugin-harness/orchestrator/interop_parser.py\n"
        message += "   - Find fallback_schemas dict\n"
        message += "   - Update 'consumes' field to match INTEROP.md schema\n"
        message += "\n"
        message += " • Options:\n"
        message += "   1. Fix the code and re-stage it with INTEROP.md changes\n"
        message += "   2. Use 'git reset HEAD <file>' to unstage changes\n"
        message += "   3. Use 'SDD_GATE=off git commit' to skip validation (use carefully)\n"
        message += "\n"
        message += "=" * 75 + "\n"

        return message


class PreCommitHook:
    """PreToolUse hook for git commit interception."""

    def __init__(self, repo_root: Optional[Path] = None):
        """Initialize the hook.

        Args:
            repo_root: Root directory of the git repository.
        """
        self.validator = InteropDriftValidator(repo_root=repo_root)

    def should_intercept(self, command: str) -> bool:
        """Determine if command should be intercepted.

        Args:
            command: The command being executed.

        Returns:
            True if this is a git commit command.
        """
        # Match 'git commit' at the beginning of the command
        return bool(re.match(r'git\s+commit\b', command))

    def validate_commit(self) -> Tuple[bool, Optional[str]]:
        """Validate the pending commit.

        Returns:
            Tuple of (allowed, error_message)
            - allowed: True if commit should be allowed
            - error_message: Error message to display, or None
        """
        is_valid, errors = self.validator.validate_drift()

        if is_valid:
            return True, None
        else:
            error_msg = self.validator.format_error_message(errors)
            return False, error_msg


# Export public interface
__all__ = [
    "InteropDriftValidator",
    "PreCommitHook"
]
