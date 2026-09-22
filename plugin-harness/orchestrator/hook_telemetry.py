"""Hook telemetry — make real hook/skill invocations observable by default.

`orchestrator.telemetry.TelemetryPublisher` and `orchestrator.telemetry_sinks`
(Datadog, New Relic) have existed since this plugin's early design, but
nothing in the actual hook entrypoints (`hooks/before_continue.py`,
`hooks/subagent_stop.py` -- the two hooks Claude Code actually invokes every
session) ever constructed a publisher or emitted an event. `PluginRouter` in
`orchestrator/core.py` does call `self.telemetry.emit(...)`, but nothing in
production code ever instantiates a `PluginRouter` either (only tests and
API.md) -- so telemetry was a fully-built, fully-unused subsystem. This
module is the missing wire: a `HookTelemetryLogger` any real hook entrypoint
can call, mirroring `HookErrorLogger`'s exact construction convention
(workflow_state_dir in, degrade to no-op if unavailable) so both stay
consistent to read side by side.

Zero-config by default: a `JSONLFileHook` is registered pointing at
`hook_telemetry_log.jsonl` in the workflow state directory, so events are
visible on disk with no external service required. Set
`PLUGIN_HARNESS_TELEMETRY=off` (same convention as this ecosystem's
`SDD_GATE=off`) to disable emission entirely, e.g. for tests that don't want
log-file side effects. The prior old-name one-release compatibility
fallback (from this plugin's rename) has been removed -- see CHANGELOG.md.

Standalone calls (no `agent-isdd` SDD workflow active, so no
`workflow_state_dir`) are no longer silently dropped either: pass `cwd` and a
project-slug-keyed sink is constructed under this plugin's own data dir
instead (see design.md's "Standalone Telemetry" section).
"""

import os
import sys
from pathlib import Path
from typing import Optional

from orchestrator.telemetry import TelemetryPublisher
from orchestrator.telemetry_sinks import JSONLFileHook

_NEW_TELEMETRY_ENV_VAR = "PLUGIN_HARNESS_TELEMETRY"
_OFF_VALUES = ("off", "0", "false", "disabled")

# hook_state.py lives in the sibling hooks/ directory (a per-plugin copy, not
# a package -- see harness_context_cache.py for the same pattern). Only
# project_slug() is needed here, to scope a standalone sink to the calling
# project without requiring workflow-state.json to exist.
_hooks_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)
from hook_state import project_slug  # noqa: E402
from path_resolution import get_plugin_data_dir  # noqa: E402


def _telemetry_disabled() -> bool:
    new_value = os.environ.get(_NEW_TELEMETRY_ENV_VAR)
    if new_value is not None:
        return new_value.lower() in _OFF_VALUES

    return False


class HookTelemetryLogger:
    """Thin wrapper around a `TelemetryPublisher`, scoped to one workflow
    state directory (or, for standalone calls, one project), following
    `HookErrorLogger`'s shape so the two can be constructed and read side by
    side at any hook entrypoint.
    """

    def __init__(self, workflow_state_dir: Optional[Path] = None, cwd: Optional[str] = None):
        self.workflow_state_dir = workflow_state_dir
        self.publisher = TelemetryPublisher()
        if _telemetry_disabled():
            # Disabled: publisher has zero hooks registered, so emit() is a
            # cheap no-op (see TelemetryPublisher.emit).
            return

        if workflow_state_dir:
            log_path = Path(workflow_state_dir) / "hook_telemetry_log.jsonl"
            self.publisher.register_hook(JSONLFileHook(log_path))
        elif cwd:
            # Standalone: no active SDD workflow, so no workflow_state_dir --
            # scope the sink to this project via project_slug(cwd) instead of
            # silently no-op'ing (see design.md's "Standalone Telemetry").
            slug = project_slug(cwd)
            log_path = Path(get_plugin_data_dir("plugin-harness")) / slug / "telemetry.jsonl"
            self.publisher.register_hook(JSONLFileHook(log_path))
        # Neither workflow_state_dir nor cwd: publisher has zero hooks
        # registered, so emit() is a cheap no-op.

    def emit(self, event_type: str, **fields) -> None:
        """Emit a hook-lifecycle event. Never raises -- see
        TelemetryPublisher.emit's own fail-closed guarantee."""
        self.publisher.emit(event_type, **fields)


def get_hook_telemetry_logger(
    workflow_state_dir: Optional[Path] = None, cwd: Optional[str] = None
) -> HookTelemetryLogger:
    """Get or create a hook telemetry logger.

    Args:
        workflow_state_dir: Path to workflow state directory (same value
            passed to `get_hook_error_logger`). Takes precedence over cwd.
        cwd: Current working directory for a standalone (no active SDD
            workflow) call. Used to scope a project-slug-keyed sink when
            workflow_state_dir is None. If both are None, telemetry is
            emitted to no sink (degraded/no-op mode).

    Returns:
        HookTelemetryLogger instance.
    """
    return HookTelemetryLogger(workflow_state_dir, cwd=cwd)
