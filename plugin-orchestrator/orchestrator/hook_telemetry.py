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
`PLUGIN_ORCHESTRATOR_TELEMETRY=off` (same convention as this ecosystem's
`SDD_GATE=off`) to disable emission entirely, e.g. for tests that don't want
log-file side effects.
"""

import os
from pathlib import Path
from typing import Optional

from orchestrator.telemetry import TelemetryPublisher
from orchestrator.telemetry_sinks import JSONLFileHook


def _telemetry_disabled() -> bool:
    return os.environ.get("PLUGIN_ORCHESTRATOR_TELEMETRY", "").lower() in (
        "off", "0", "false", "disabled",
    )


class HookTelemetryLogger:
    """Thin wrapper around a `TelemetryPublisher`, scoped to one workflow
    state directory, following `HookErrorLogger`'s shape so the two can be
    constructed and read side by side at any hook entrypoint.
    """

    def __init__(self, workflow_state_dir: Optional[Path] = None):
        self.workflow_state_dir = workflow_state_dir
        self.publisher = TelemetryPublisher()
        if workflow_state_dir and not _telemetry_disabled():
            log_path = Path(workflow_state_dir) / "hook_telemetry_log.jsonl"
            self.publisher.register_hook(JSONLFileHook(log_path))
        # No workflow_state_dir, or disabled: publisher has zero hooks
        # registered, so emit() is a cheap no-op (see TelemetryPublisher.emit).

    def emit(self, event_type: str, **fields) -> None:
        """Emit a hook-lifecycle event. Never raises -- see
        TelemetryPublisher.emit's own fail-closed guarantee."""
        self.publisher.emit(event_type, **fields)


def get_hook_telemetry_logger(workflow_state_dir: Optional[Path] = None) -> HookTelemetryLogger:
    """Get or create a hook telemetry logger.

    Args:
        workflow_state_dir: Path to workflow state directory (same value
            passed to `get_hook_error_logger`). If None, telemetry is
            emitted to no sink (degraded/no-op mode).

    Returns:
        HookTelemetryLogger instance.
    """
    return HookTelemetryLogger(workflow_state_dir)
