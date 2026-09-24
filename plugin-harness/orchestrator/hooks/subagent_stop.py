"""SubagentStop hook: Capture agent completion, validate output, and log handoff.

Implements the subagent_stop hook that intercepts agent completion and:
1. Parses phase markers from agent report (e.g., RED_GREEN_REFACTOR_COMPLETE)
2. Detects escalation markers (<!--AGENT-TDD-PLAN-FLAG:...-->, <!--AGENT-*-FAILED:...-->)
3. Validates output against capability contract (from INTEROP.md "produces" field)
4. Logs handoff to workflow-state["orchestration"]["handoff_history"]
5. Triggers error handler on contract violations (for rollback/degrade/pause)
6. Handles soft dependency unavailability gracefully

Error Handling:
- Regex errors in marker parsing: log warning, continue with None marker
- Contract validation failures: log to handoff_history, trigger error handler
- Escalation markers: set rollback_pending for orchestrator to handle
"""

import logging
import re
from datetime import datetime, timezone
from typing import Optional, Dict, Tuple, List, Union
from orchestrator.error_handler import ErrorHandler
from orchestrator.checkpoint import CheckpointManager
from orchestrator.interop_parser import CapabilityMap
from orchestrator.error import OrchestrationError, HookError, HookErrorType
from orchestrator.error_logger import persist_best_effort, ErrorRegistry
from orchestrator.core import PluginRouter, HARD_DEPENDENCY_PLUGINS

logger = logging.getLogger(__name__)

# Soft dependencies that degrade gracefully
SOFT_DEPENDENCY_PLUGINS = ["agent-nelly", "agent-ux"]


def validate_in_order(
    agent_type: str,
    output: str,
    workflow_state: dict,
    capability_map: Optional[CapabilityMap] = None
) -> Tuple[bool, Optional[HookErrorType], str]:
    """Validate output in strict order: hard deps → soft deps → payload.

    Args:
        agent_type: Agent that produced output
        output: Agent output to validate
        workflow_state: Workflow state
        capability_map: Optional CapabilityMap for contract validation

    Returns:
        Tuple of (is_valid, error_type, error_message)
    """
    # 1. Check hard dependencies
    for dep in HARD_DEPENDENCY_PLUGINS:
        if dep not in workflow_state.get("orchestration", {}).get("available_plugins", []):
            return False, HookErrorType.INFRASTRUCTURE_ERROR, f"Hard dependency unavailable: {dep}"

    # 2. Check soft dependencies (log but don't block)
    for dep in SOFT_DEPENDENCY_PLUGINS:
        if dep not in workflow_state.get("orchestration", {}).get("available_plugins", []):
            logger.warning(f"Soft dependency unavailable: {dep}. Continuing with degraded state.")

    # 3. Validate payload against capability contract
    if capability_map:
        is_valid, errors = capability_map.validate_output(agent_type, output)
        if not is_valid:
            return False, HookErrorType.CONTRACT_VIOLATION, f"Contract validation failed: {errors}"

    return True, None, ""


def extract_error_lesson(
    agent_type: str,
    error: HookError,
    root_cause: Optional[str] = None
) -> Dict[str, str]:
    """Extract error lesson from HookError for cross-phase sharing.

    Args:
        agent_type: Agent that failed (e.g., "agent-isdd")
        error: The HookError that occurred
        root_cause: Optional root cause description

    Returns:
        Error lesson dict with agent_type, error_type, root_cause, recommendation
    """
    recommendations = {
        "CONTRACT_VIOLATION": "Re-run with updated spec containing all required fields",
        "DEPENDENCY_UNAVAILABLE": "Continue with degraded state; available features remain operational",
        "INFRASTRUCTURE_ERROR": "Check logs and system state; may require manual intervention",
    }
    return {
        "agent_type": agent_type,
        "error_type": error.error_type.name,
        "root_cause": root_cause or error.message,
        "recommendation": recommendations.get(error.error_type.name, error.recovery_action),
    }


def share_error_lessons_to_next_phase(workflow_state: dict, error_lesson: Dict[str, str]) -> None:
    """Add error lesson to workflow_state for next phase to consume.

    Args:
        workflow_state: Workflow state dict (modified in-place)
        error_lesson: Error lesson dict from extract_error_lesson()
    """
    if "orchestration" not in workflow_state:
        workflow_state["orchestration"] = {}

    lessons = workflow_state["orchestration"].setdefault("error_lessons", [])
    lessons.append(error_lesson)

    # Keep only last 20 for memory efficiency
    workflow_state["orchestration"]["error_lessons"] = lessons[-20:]


def build_system_message(
    error: Optional[HookError] = None,
    errors: Optional[List[HookError]] = None,
    registry_path: Optional[str] = None,
    min_severity: str = "warn",
    error_lessons: Optional[List[Dict]] = None,
) -> str:
    """Build systemMessage to surface errors and prior lessons to user.

    Args:
        error: Single HookError to include
        errors: List of HookErrors to include (last 3)
        registry_path: Path to error_registry.json for reference
        min_severity: Minimum severity to include (default "warn")
        error_lessons: Prior error lessons from earlier phases

    Returns:
        Formatted systemMessage string for user
    """
    severity_order = {"info": 0, "warn": 1, "critical": 2}
    min_sev_level = severity_order.get(min_severity, 1)

    lines = []
    error_list = []

    if error:
        error_list = [error]
    elif errors:
        error_list = errors[-3:]  # Last 3 errors

    if error_list:
        lines.append("## Error Report")
        lines.append("")
        for err in error_list:
            if severity_order.get(err.severity, 0) >= min_sev_level:
                lines.append(f"**{err.error_type.name}** ({err.severity})")
                lines.append(f"- Issue: {err.message}")
                lines.append(f"- Recovery: {err.recovery_action}")
                lines.append("")

    if error_lessons:
        lines.append("## Prior Error Lessons")
        lines.append("")
        for lesson in error_lessons[-3:]:  # Last 3 lessons
            lines.append(f"- **{lesson['agent_type']}**: {lesson['error_type']}")
            lines.append(f"  Avoid: {lesson['recommendation']}")
        lines.append("")

    if registry_path:
        lines.append(f"For full error history, see: {registry_path}")

    return "\n".join(lines) if lines else ""


def handle_agent_completion(
    agent_type: str,
    report: str,
    workflow_state: dict,
    error_registry_base_path: Optional[str] = None,
    project_slug: Optional[str] = None
) -> Dict:
    """
    Capture agent completion, validate output, and log handoff.

    Parses agent report for phase markers, validates against capability contract,
    logs handoff to workflow-state, and triggers error handler if contract violated.

    Args:
        agent_type: Name of completed agent (e.g., "agent-tdd")
        report: Agent output report
        workflow_state: Current workflow state dict (modified in-place)
        error_registry_base_path: Optional base directory for the persistent,
            cross-session error-registry.json (e.g. ${CLAUDE_PLUGIN_DATA}/sdd-memory). When
            given together with project_slug, a contract violation is persisted
            there (via ErrorLogger.persist_error) in addition to being logged to
            workflow_state's handoff_history. Omit to keep session-only logging
            (e.g. existing callers/tests that don't care about persistence).
        project_slug: Optional project identifier under error_registry_base_path.
            Required alongside error_registry_base_path for persistence to occur.

    Returns:
        Summary dict the calling hook entrypoint can use to surface a
        systemMessage to the user:
        {
            "success": bool,
            "validation_result": "contract_valid" | "contract_invalid",
            "error_details": {...},
            "escalation_marker": str | None,
            "recovery_action": str | None  # set only when contract_invalid
        }
    """
    # Ensure orchestration structure exists
    _ensure_orchestration_structure(workflow_state)

    # Extract phase marker from report
    phase_marker = _extract_phase_marker(report)

    # Check for escalation markers
    escalation_marker = _detect_escalation_marker(report)
    if escalation_marker:
        _set_rollback_pending(workflow_state, escalation_marker)

    # Validate output against capability contract
    capability_map = workflow_state.get("orchestration", {}).get("capability_map", {})
    validation_result, error_details = _validate_output_contract(
        agent_type, report, capability_map
    )

    # Determine success based on validation
    success = validation_result == "contract_valid"

    # Log handoff to history
    _log_handoff(
        workflow_state,
        agent_type,
        phase_marker,
        validation_result,
        error_details,
        success
    )

    # Trigger error handler on contract mismatch
    recovery_action = None
    if validation_result == "contract_invalid":
        recovery_action = _trigger_error_handler(
            workflow_state,
            agent_type,
            error_details,
            error_registry_base_path=error_registry_base_path,
            project_slug=project_slug
        )

    return {
        "success": success,
        "validation_result": validation_result,
        "error_details": error_details,
        "escalation_marker": escalation_marker,
        "recovery_action": recovery_action,
    }


def _ensure_orchestration_structure(workflow_state: dict) -> None:
    """Ensure workflow_state has required orchestration structure.

    Creates orchestration and handoff_history if missing.

    Args:
        workflow_state: Workflow state dict (modified in-place)
    """
    if "orchestration" not in workflow_state:
        workflow_state["orchestration"] = {}

    if "handoff_history" not in workflow_state["orchestration"]:
        workflow_state["orchestration"]["handoff_history"] = []


def _extract_phase_marker(report: str) -> Optional[str]:
    """Extract phase marker from agent report.

    Searches for phase markers in two formats:
    1. Markdown heading: "### Phase Marker: RED_GREEN_REFACTOR_COMPLETE"
    2. HTML comment: "<!--AGENT-TDD-PHASE:RED_GREEN_REFACTOR_COMPLETE-->"

    Handles regex errors gracefully (logs warning, returns None).

    Args:
        report: Agent report text

    Returns:
        Phase marker string (e.g., "RED_GREEN_REFACTOR_COMPLETE") or None if not found
    """
    try:
        # Pattern 1: Markdown heading "### Phase Marker: <MARKER>"
        match = re.search(r"###\s+Phase Marker:\s+([A-Z_]+)", report, re.IGNORECASE)
        if match:
            marker = match.group(1)
            logger.debug(f"Extracted phase marker (markdown): {marker}")
            return marker

        # Pattern 2: HTML comment "<!--..PHASE..-->"
        match = re.search(r"<!--.*?PHASE[:\-_]+(\w+).*?-->", report, re.IGNORECASE)
        if match:
            marker = match.group(1)
            logger.debug(f"Extracted phase marker (HTML comment): {marker}")
            return marker

        logger.debug("No phase marker found in report")
        return None
    except re.error as e:
        logger.warning(f"Regex error parsing phase marker: {e}. Continuing without marker.")
        return None


def _detect_escalation_marker(report: str) -> Optional[str]:
    """Detect escalation markers in agent report.

    Escalation markers signal that an agent encountered a condition requiring
    orchestrator intervention (research gap, design conflict, etc.). Supported formats:
    - <!--AGENT-TDD-PLAN-FLAG:reason-->
    - <!--AGENT-*-FAILED:reason--> (generic; no live emitter as of 2026-09-16 -- see note below)

    Note on the FAILED pattern (2026-09-16): agent-tdd's retired modular design-spec pipeline
    named four escalation markers in its own docs, most prominently
    <!--AGENT-TDD-RESEARCH-VALIDATION-FAILED:...-->, and this docstring used to cite that one
    as this pattern's real-world example. It never actually was: the regex requires exactly
    two dash-separated segments between "AGENT-" and "-FAILED" (`AGENT-[A-Z]+-[A-Z]+-FAILED`),
    and "TDD-RESEARCH-VALIDATION" is three, so that marker -- and all four of the retired
    pipeline's markers -- never matched this pattern (verified directly against the regex, not
    assumed). This pattern has therefore never had a real emitter; the pipeline it was
    documented as supporting is now retired regardless (see agent-tdd/INTEROP.md's "Design
    Spec Mode" section). Kept as generic infrastructure -- any future agent can raise a hard
    escalation this way without this hook needing a per-agent marker vocabulary;
    test_e2e_isdd_to_tdd.py's
    test_e2e_error_recovery_escalation_marker_research_validation_failed exercises this
    generic path directly with its own two-segment example marker (it does not require the
    specific classification below, only that the marker is detected at all).

    Handles regex errors gracefully (logs warning, returns None).

    Args:
        report: Agent report text

    Returns:
        Full escalation marker string (e.g., '<!--AGENT-TDD-PLAN-FLAG:reason="..."-->') or
        None if no escalation detected
    """
    try:
        # Pattern 1: FAILED markers (highest priority)
        match = re.search(r"(<!--AGENT-[A-Z]+-[A-Z]+-FAILED:[^>]*-->)", report)
        if match:
            marker = match.group(1)
            logger.info(f"Detected escalation marker (FAILED): {marker}")
            return marker

        # Pattern 2: PLAN-FLAG markers (design/validity conflicts)
        match = re.search(r"(<!--AGENT-[A-Z]+-PLAN-FLAG:[^>]*-->)", report)
        if match:
            marker = match.group(1)
            logger.info(f"Detected escalation marker (PLAN-FLAG): {marker}")
            return marker

        logger.debug("No escalation markers found in report")
        return None
    except re.error as e:
        logger.warning(f"Regex error parsing escalation markers: {e}. Continuing without marker.")
        return None


def _validate_output_contract(
    agent_type: str,
    report: str,
    capability_map: Dict
) -> Tuple[str, Dict]:
    """Validate agent output against capability contract.

    Checks that all required output fields (from agent's INTEROP.md "produces" contract)
    are present in the agent report. Validation uses case-insensitive text search.

    Contract structure (from INTEROP.md):
        produces: {
            "field_name": "required" | "optional"
        }

    Args:
        agent_type: Name of agent (e.g., "agent-tdd")
        report: Agent output report text
        capability_map: Capability map dict (from workflow_state["orchestration"]["capability_map"])

    Returns:
        Tuple of (validation_result, error_details):
        - validation_result: "contract_valid" | "contract_invalid"
        - error_details: {} if valid, or dict with:
            - reason: "contract_mismatch"
            - missing_fields: [list of missing required fields]
            - expected_contract: {full produces dict from contract}
    """
    # Look up contract for this agent in capability map
    agent_contract = capability_map.get(agent_type, {})
    produces_contract = agent_contract.get("produces", {})

    # No contract defined for this agent; treat as valid (lenient)
    if not produces_contract:
        logger.debug(f"No contract defined for {agent_type}; validation lenient")
        return "contract_valid", {}

    # Check each required field in the contract
    missing_required_fields = []
    for field_name, requirement_level in produces_contract.items():
        # Only validate "required" fields; "optional" fields are not enforced
        if requirement_level == "required":
            # Use case-insensitive text search (field names in reports are often lowercased)
            if field_name.lower() not in report.lower():
                missing_required_fields.append(field_name)
                logger.debug(f"Missing required field: {field_name}")

    # If any required fields are missing, validation fails
    if missing_required_fields:
        error_details = {
            "reason": "contract_mismatch",
            "missing_fields": missing_required_fields,
            "expected_contract": produces_contract
        }
        logger.warning(
            f"Contract validation failed for {agent_type}: missing {missing_required_fields}"
        )
        return "contract_invalid", error_details

    logger.debug(f"Contract validation passed for {agent_type}")
    return "contract_valid", {}


def _set_rollback_pending(workflow_state: dict, escalation_marker: str) -> None:
    """Set rollback_pending marker when escalation detected.

    Stores rollback_pending marker in workflow_state to signal orchestrator that
    agent encountered a condition requiring intervention (research gap, design conflict, etc.).

    Rollback marker structure:
    {
        "source": "escalation_marker_detected",
        "escalation_type": "plan_validity_conflict" | "unknown_escalation",
        "marker_found": "full HTML comment marker",
        "timestamp": "ISO 8601 timestamp",
        "action_required": "Guidance for orchestrator"
    }

    Args:
        workflow_state: Workflow state dict (modified in-place)
        escalation_marker: Full escalation marker string (e.g., '<!--AGENT-TDD-PLAN-FLAG:reason="..."-->')
    """
    # Classify escalation type based on marker content
    escalation_type = _classify_escalation_type(escalation_marker)

    rollback_marker = {
        "source": "escalation_marker_detected",
        "escalation_type": escalation_type,
        "marker_found": escalation_marker,
        "timestamp": _get_iso_timestamp(),
        "action_required": "Review escalation trigger and retry or rollback"
    }

    workflow_state["rollback_pending"] = rollback_marker
    logger.info(f"Rollback pending: escalation_type={escalation_type}, marker={escalation_marker}")


def _classify_escalation_type(escalation_marker: str) -> str:
    """Classify escalation type from marker content.

    Maps marker keywords to canonical escalation type strings.

    Args:
        escalation_marker: Full escalation marker string

    Returns:
        Escalation type: "plan_validity_conflict" | "unknown_escalation"
    """
    if "PLAN-FLAG" in escalation_marker:
        return "plan_validity_conflict"
    else:
        return "unknown_escalation"


def _log_handoff(
    workflow_state: dict,
    agent_type: str,
    phase_marker: Optional[str],
    validation_result: str,
    error_details: Dict,
    success: bool
) -> None:
    """Log handoff to workflow-state handoff_history.

    Appends entry to handoff_history with audit trail information:
    timestamp, source agent, phase marker, validation result, success status, error details.

    Handoff entry structure:
    {
        "timestamp": "ISO 8601 timestamp",
        "source": "agent-tdd" (or other agent type),
        "success": true | false,
        "validation_result": "contract_valid" | "contract_invalid",
        "phase_marker": "RED_GREEN_REFACTOR_COMPLETE" (if present),
        "error_details": {...} (if validation failed)
    }

    Args:
        workflow_state: Workflow state dict (modified in-place)
        agent_type: Name of completing agent (e.g., "agent-tdd")
        phase_marker: Extracted phase marker from report, or None if not found
        validation_result: "contract_valid" or "contract_invalid"
        error_details: Dict with error details (empty if validation passed)
        success: Boolean indicating overall success (True if contract valid)
    """
    # Build base handoff entry (always include these fields)
    handoff_entry = {
        "timestamp": _get_iso_timestamp(),
        "source": agent_type,
        "success": success,
        "validation_result": validation_result
    }

    # Add optional fields only if present
    if phase_marker:
        handoff_entry["phase_marker"] = phase_marker

    if error_details:
        handoff_entry["error_details"] = error_details

    # Append to handoff history for audit trail
    workflow_state["orchestration"]["handoff_history"].append(handoff_entry)

    logger.info(
        f"Handoff logged: {agent_type} → validation={validation_result}, "
        f"success={success}, phase={phase_marker}"
    )


def _trigger_error_handler(
    workflow_state: dict,
    agent_type: str,
    error_details: Dict,
    error_registry_base_path: Optional[str] = None,
    project_slug: Optional[str] = None
) -> Optional[str]:
    """Trigger error handler on contract violation.

    Instantiates ErrorHandler to classify and handle the contract mismatch error.
    Recovery paths: rollback (restore checkpoint), skip (soft deps), degrade (stale cache),
    workaround (nelly memory), or pause (surface to user).

    Errors during error handling are caught and logged (non-fatal).

    Args:
        workflow_state: Workflow state dict (may be modified by error handler)
        agent_type: Agent that violated contract
        error_details: Dict with validation failure details (reason, missing_fields, etc.)
        error_registry_base_path: Optional base directory for the persistent
            error-registry.json. See handle_agent_completion's docstring.
        project_slug: Optional project identifier paired with error_registry_base_path.

    Returns:
        The recovery action taken (e.g. "rollback", "pause"), or None if the
        error handler itself failed.
    """
    try:
        # Instantiate error handler with dependencies
        capability_map = CapabilityMap()
        checkpoint_manager = CheckpointManager()
        error_handler = ErrorHandler(capability_map, checkpoint_manager)

        # Determine recovery strategy and handle the error
        error_type = error_details.get("reason", "contract_mismatch")
        recovery_action, updated_state = error_handler.determine_recovery(
            error_type=error_type,
            source_plugin=agent_type,
            target_plugin="orchestrator",
            error_details=error_details,
            workflow_state=workflow_state
        )

        logger.warning(
            f"Contract violation from {agent_type}: "
            f"error_type={error_type}, recovery_action={recovery_action}"
        )

        _persist_orchestration_error(
            agent_type, error_type, error_details, recovery_action,
            error_registry_base_path, project_slug
        )

        return recovery_action

    except (IOError, OSError) as e:
        # File I/O error (e.g., checkpoint file not accessible)
        logger.error(
            f"Error handler file I/O error: {e.__class__.__name__}: {e}. "
            "Proceeding without recovery."
        )
        return None
    except Exception as e:
        # Any other error in error handler (parsing, instantiation, etc.)
        logger.error(
            f"Error handler failed: {e.__class__.__name__}: {e}. "
            "Proceeding without error recovery."
        )
        return None


# Recovery actions that exhausted automated recovery and warrant surfacing this
# error in future agent-spawn context (via before_continue's error-pattern read
# side), vs. ones handled gracefully enough that persisting them would just add
# noise to the registry.
_NOTEWORTHY_RECOVERY_ACTIONS = {"rollback", "pause", None}


def _persist_orchestration_error(
    agent_type: str,
    error_type: str,
    error_details: Dict,
    recovery_action: Optional[str],
    error_registry_base_path: Optional[str],
    project_slug: Optional[str]
) -> None:
    """Persist a contract-violation error to the project-wide error-registry.json.

    No-op when error_registry_base_path or project_slug is missing (callers that
    don't care about cross-session persistence, e.g. existing tests), or when the
    recovery action doesn't warrant persisting (see _NOTEWORTHY_RECOVERY_ACTIONS).
    Never raises -- persistence is best-effort and must never affect recovery.

    Args:
        agent_type: Agent whose output failed contract validation (source_plugin)
        error_type: Raw error type from error_details (e.g. "contract_mismatch")
        error_details: Dict with validation failure details
        recovery_action: Recovery action ErrorHandler took, or None if it failed
        error_registry_base_path: Base directory for error-registry.json
        project_slug: Project identifier under error_registry_base_path
    """
    if not error_registry_base_path or not project_slug:
        return
    if recovery_action not in _NOTEWORTHY_RECOVERY_ACTIONS:
        return

    try:
        missing = error_details.get("missing_fields")
        root_cause = error_details.get("reason", error_type) or "contract_mismatch"
        if missing:
            root_cause = f"{root_cause}: missing fields {missing}"

        error = OrchestrationError(
            timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            error_type="handoff_validation",
            source_plugin=agent_type,
            target_plugin="orchestrator",
            root_cause=root_cause,
            severity="high" if recovery_action in ("rollback", "pause", None) else "medium",
            suggested_fix=(
                f"Review {agent_type}'s output against its INTEROP.md produces contract "
                f"(recovery action taken: {recovery_action or 'none'})"
            ),
            context=dict(error_details)
        )
        persist_best_effort(error, error_registry_base_path, project_slug, logger)
    except Exception as e:
        logger.error(
            f"Failed to persist orchestration error: {e.__class__.__name__}: {e}. "
            "Continuing without persistence."
        )


def _get_iso_timestamp() -> str:
    """Generate ISO 8601 UTC timestamp with Z suffix.

    Returns:
        ISO timestamp string (e.g., "2026-08-25T10:35:00Z")
    """
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def check_plugin_availability(
    plugin_name: str,
    error_registry_base_path: Optional[str] = None,
    project_slug: Optional[str] = None
) -> bool:
    """Check if a plugin is available/installed.

    Real detection against the shared hard-dependency set (see
    orchestrator.core.HARD_DEPENDENCY_PLUGINS). No plugin-discovery mechanism exists
    yet, so every plugin currently reports unavailable; a hard-dependency
    unavailability persists a plugin_unavailable error via ErrorLogger, mirroring
    _persist_orchestration_error's best-effort, non-blocking, no-op-when-missing
    pattern. A soft-dependency unavailability never persists.

    Args:
        plugin_name: Name of plugin to check
        error_registry_base_path: Optional base directory for the persistent
            error registry. No-op persistence unless given together with
            project_slug.
        project_slug: Optional project identifier under
            error_registry_base_path. Required alongside
            error_registry_base_path for persistence to occur.

    Returns:
        True if plugin available, False otherwise. Never raises -- persistence
        failure never affects the returned value.
    """
    normalized_name = PluginRouter._normalize_plugin_name(plugin_name)
    available = False  # No real plugin-discovery mechanism exists yet.

    if normalized_name in HARD_DEPENDENCY_PLUGINS and error_registry_base_path and project_slug:
        error = OrchestrationError(
            timestamp=_get_iso_timestamp(),
            error_type="plugin_unavailable",
            source_plugin=normalized_name,
            root_cause="plugin_not_found",
            severity="high",
            suggested_fix=(
                f"ensure {normalized_name} is installed and enabled for this session"
            ),
            context={"hard_dependency": True}
        )
        persist_best_effort(error, error_registry_base_path, project_slug, logger)

    return available
