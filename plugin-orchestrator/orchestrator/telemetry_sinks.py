"""Ready-made TelemetryPublisher hooks for production monitoring backends.

TelemetryPublisher.register_hook() accepts any Callable[[dict], None]; these
classes are that callable, pre-wired for two common production sinks so
integrating one is a constructor call rather than a protocol implementation.
Both fail closed: a hook that raises only loses that one delivery (caught and
logged by TelemetryPublisher.emit), never orchestration.
"""

import json
import logging
import socket
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Optional, Union

logger = logging.getLogger(__name__)

# Event fields promoted to dogstatsd/New Relic tags when present, chosen to
# cover the fields PluginRouter actually emits (see core.py's telemetry.emit
# calls) without hardcoding every possible custom field a caller might add.
_TAGGABLE_FIELDS = (
    "plugin", "source", "target", "success", "available",
    "current_plugin", "current_phase", "next_plugin",
)


class JSONLFileHook:
    """Append every event as one JSON line to a local file -- the zero-config
    default sink, for when no Datadog/New Relic backend is set up.

    Exists specifically to make skill/hook invocation observable without any
    external service: registering *no* hook on a TelemetryPublisher silently
    drops every event (by design, per TelemetryPublisher.emit's docstring),
    which is exactly how orchestration events went unnoticed before this
    sink existed -- the publisher and emit() call sites were already there,
    nothing was ever listening. Same fail-closed contract as the other
    hooks here: a write failure only loses that one line, logged and
    skipped, never raised back to the caller.

    Example:
        telemetry.register_hook(JSONLFileHook(workflow_state_dir / "hook_telemetry_log.jsonl"))
    """

    def __init__(self, path: Union[str, Path]):
        self.path = Path(path)
        self._dir_ready = False

    def __call__(self, event: Dict) -> None:
        record = dict(event)
        record.setdefault("logged_at", datetime.now(timezone.utc).isoformat())
        try:
            if not self._dir_ready:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self._dir_ready = True
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
        except (IOError, OSError) as e:
            logger.warning(f"JSONLFileHook failed to write {self.path}: {e!r}")


class DatadogStatsDHook:
    """Publish orchestrator events to Datadog via the DogStatsD (UDP) protocol.

    No datadog client library required - DogStatsD is a small plaintext
    protocol over UDP, sent fire-and-forget (no ack, no connection setup).

    Example:
        telemetry.register_hook(DatadogStatsDHook())
        # or, for a non-default agent address:
        telemetry.register_hook(DatadogStatsDHook(host="dd-agent", port=8125))
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8125,
        metric_prefix: str = "orchestrator",
    ):
        """
        Args:
            host: DogStatsD agent hostname.
            port: DogStatsD agent port (default 8125).
            metric_prefix: Prefix applied to every metric name.
        """
        self.host = host
        self.port = port
        self.metric_prefix = metric_prefix
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def __call__(self, event: Dict) -> None:
        """Emit a counter for the event plus a gauge if it carries duration_ms."""
        metric_name = f"{self.metric_prefix}.{event.get('event_type', 'unknown')}"
        tag_suffix = self._tag_suffix(event)

        self._send(f"{metric_name}:1|c{tag_suffix}")

        duration_ms = event.get("duration_ms")
        if duration_ms is not None:
            self._send(f"{metric_name}.duration_ms:{duration_ms}|g{tag_suffix}")

    def _tag_suffix(self, event: Dict) -> str:
        tags = [
            f"{field}:{event[field]}"
            for field in _TAGGABLE_FIELDS
            if event.get(field) is not None
        ]
        return f"|#{','.join(tags)}" if tags else ""

    def _send(self, message: str) -> None:
        self._socket.sendto(message.encode("utf-8"), (self.host, self.port))


class NewRelicEventHook:
    """Publish orchestrator events to New Relic via the Event API (HTTPS).

    Each call makes one synchronous POST. Since TelemetryPublisher.emit()
    is on the router's hot path, prefer a short timeout so a slow/unreachable
    endpoint degrades to a dropped telemetry event (logged, then skipped)
    rather than adding latency to handoff validation or routing.

    Example:
        telemetry.register_hook(
            NewRelicEventHook(account_id="1234567", api_key="NRAK-...")
        )
    """

    def __init__(
        self,
        account_id: str,
        api_key: str,
        event_type: str = "OrchestratorEvent",
        region_endpoint: str = "https://insights-collector.newrelic.com",
        timeout: float = 2.0,
    ):
        """
        Args:
            account_id: New Relic account ID.
            api_key: New Relic Insights insert key.
            event_type: New Relic eventType attribute for every event sent.
            region_endpoint: API base URL (US default; use the EU collector
                endpoint for EU-region accounts).
            timeout: Request timeout in seconds.
        """
        self.account_id = account_id
        self.api_key = api_key
        self.event_type = event_type
        self.url = f"{region_endpoint}/v1/accounts/{account_id}/events"
        self.timeout = timeout

    def __call__(self, event: Dict) -> None:
        """POST the event to New Relic's Event API."""
        payload = {"eventType": self.event_type, **self._flatten(event)}
        request = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Api-Key": self.api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            response.read()

    @staticmethod
    def _flatten(event: Dict) -> Dict:
        """Drop/stringify values the New Relic Event API can't accept.

        New Relic events are flat and only accept string/number/boolean
        attribute values, so a nested "metadata" dict (as emitted by
        PluginRouter.validate_handoff) is JSON-stringified rather than
        dropped or sent malformed.
        """
        flattened = {}
        for key, value in event.items():
            if isinstance(value, dict):
                flattened[key] = json.dumps(value)
            elif value is None:
                continue
            else:
                flattened[key] = value
        return flattened
