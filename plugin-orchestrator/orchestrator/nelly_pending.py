"""PendingNellyRequestQueue: async hand-off for agent-nelly calls hooks can't make.

Both before_continue.py (PreToolUse) and subagent_stop.py (SubagentStop) run as
blocking hook subprocesses with no Agent-tool access, so neither can invoke the
agent-nelly:agent-nelly subagent directly (see agent-nelly's INTEROP.md).
This module lets a hook enqueue a request and, on a later invocation, pick up a
result that the main session (which *does* have Agent-tool access) resolved out
of band -- via hooks/resolve_nelly_request.py, after noticing the pending entry
in a hook's systemMessage/injected context.

Queue Schema:
    workflow_state["orchestration"]["pending_nelly_requests"] = [
        {
            "id": "<uuid4>",
            "kind": "workaround_lookup" | "brief_fetch",
            "requested_at": "<ISO 8601 UTC>",
            "status": "pending" | "resolved" | "expired",
            "query": { ... kind-specific ... },
            "result": None | { ... kind-specific ... },
            "resolved_at": "<ISO 8601 UTC>" | None
        }
    ]

TTL mirrors NellyBriefManager's existing 1-hour brief-cache TTL: a pending (or
resolved) entry older than that is treated as expired rather than matched
against, so a stale answer is never applied to a since-changed situation.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from uuid import uuid4

# Matches NellyBriefManager.NELLY_BRIEF_CACHE_TTL (orchestrator/nelly.py)
PENDING_REQUEST_TTL_SECONDS = 3600

VALID_KINDS = {"workaround_lookup", "brief_fetch"}


class PendingNellyRequestQueue:
    """Enqueue, look up, and expire pending agent-nelly requests in workflow_state."""

    def _requests(self, workflow_state: dict) -> List[Dict[str, Any]]:
        """Return (creating if needed) the pending_nelly_requests list, in-place."""
        orchestration = workflow_state.setdefault("orchestration", {})
        return orchestration.setdefault("pending_nelly_requests", [])

    def find_resolved(
        self,
        workflow_state: dict,
        kind: str,
        query: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Return the result dict of a resolved, non-expired entry matching (kind, query).

        Args:
            workflow_state: Workflow state dict (read-only for this call, but
                expire_stale is run first so expired entries are never matched).
            kind: "workaround_lookup" | "brief_fetch"
            query: Exact-match query dict (see module docstring for shape per kind)

        Returns:
            The matching entry's "result" dict, or None if no resolved match exists.
        """
        self.expire_stale(workflow_state)
        for entry in self._requests(workflow_state):
            if (
                entry["status"] == "resolved"
                and entry["kind"] == kind
                and entry["query"] == query
            ):
                return entry["result"]
        return None

    def enqueue(
        self,
        workflow_state: dict,
        kind: str,
        query: Dict[str, Any]
    ) -> str:
        """Add a pending request, or return the id of an equivalent one already pending.

        Args:
            workflow_state: Workflow state dict (modified in-place)
            kind: "workaround_lookup" | "brief_fetch"
            query: Exact-match query dict for this request

        Returns:
            The request's id (new or pre-existing pending match).

        Raises:
            ValueError: If kind is not a recognized request kind.
        """
        if kind not in VALID_KINDS:
            raise ValueError(f"invalid kind: {kind}")

        self.expire_stale(workflow_state)
        requests = self._requests(workflow_state)

        for entry in requests:
            if entry["status"] == "pending" and entry["kind"] == kind and entry["query"] == query:
                return entry["id"]

        entry = {
            "id": str(uuid4()),
            "kind": kind,
            "requested_at": self._now(),
            "status": "pending",
            "query": query,
            "result": None,
            "resolved_at": None,
        }
        requests.append(entry)
        return entry["id"]

    def expire_stale(self, workflow_state: dict) -> None:
        """Mark any pending/resolved entry older than the TTL as "expired", in-place."""
        now = datetime.now(timezone.utc)
        for entry in self._requests(workflow_state):
            if entry["status"] == "expired":
                continue
            age = (now - self._parse(entry["requested_at"])).total_seconds()
            if age > PENDING_REQUEST_TTL_SECONDS:
                entry["status"] = "expired"

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _parse(iso_ts: str) -> datetime:
        return datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
