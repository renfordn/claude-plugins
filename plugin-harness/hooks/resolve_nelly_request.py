#!/usr/bin/env python3
"""CLI for resolving a pending agent-nelly request enqueued by a hook.

before_continue.py and subagent_stop.py run as blocking hook subprocesses with
no Agent-tool access, so neither can call agent-nelly:agent-nelly
directly (see agent-nelly's INTEROP.md and orchestrator/nelly_pending.py).
Instead they enqueue a request in workflow_state["orchestration"]
["pending_nelly_requests"] and surface it via a hook's systemMessage or
injected context. The main session -- which does have Agent-tool access --
notices that, calls agent-nelly for a real answer, and runs this
script to write the result back atomically so the next hook invocation can
pick it up.

Usage:
    # See what's outstanding for a workflow-state.json
    python3 resolve_nelly_request.py --state <path> --list

    # Resolve one request (found a workaround / fetched a brief)
    python3 resolve_nelly_request.py --state <path> --id <request-id> \
        --result '{"workaround": {"action": "retry_with_flag"}}'

    # Resolve one request with "nothing found" (still a valid resolution --
    # stops the caller from re-enqueueing and re-pausing on the same query)
    python3 resolve_nelly_request.py --state <path> --id <request-id> \
        --result '{"workaround": null}'
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hook_state import load_workflow_state, save_workflow_state  # noqa: E402


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _pending_requests(workflow_state: dict) -> list:
    return workflow_state.setdefault("orchestration", {}).setdefault("pending_nelly_requests", [])


def list_requests(state_path: str) -> int:
    workflow_state = load_workflow_state(state_path)
    entries = _pending_requests(workflow_state)
    if not entries:
        print("No pending_nelly_requests entries.")
        return 0

    for entry in entries:
        print(
            f"[{entry['status']}] {entry['id']}  kind={entry['kind']}  "
            f"requested_at={entry['requested_at']}"
        )
        print(f"    query: {json.dumps(entry['query'])}")
    return 0


def resolve_request(state_path: str, request_id: str, result_json: str) -> int:
    try:
        result = json.loads(result_json)
    except json.JSONDecodeError as e:
        print(f"error: --result is not valid JSON: {e}", file=sys.stderr)
        return 1

    workflow_state = load_workflow_state(state_path)
    entries = _pending_requests(workflow_state)

    entry = next((e for e in entries if e["id"] == request_id), None)
    if entry is None:
        print(f"error: no pending_nelly_requests entry with id {request_id!r}", file=sys.stderr)
        return 1

    if entry["status"] == "expired":
        print(
            f"error: request {request_id!r} has expired (requested_at={entry['requested_at']}); "
            "the caller will enqueue a fresh one next time it hits this same situation.",
            file=sys.stderr
        )
        return 1

    if entry["status"] == "resolved":
        print(f"warning: request {request_id!r} was already resolved; overwriting.", file=sys.stderr)

    entry["status"] = "resolved"
    entry["result"] = result
    entry["resolved_at"] = _now()

    save_workflow_state(state_path, workflow_state)
    print(f"Resolved {entry['kind']} request {request_id!r}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--state", required=True, help="Path to workflow-state.json")
    parser.add_argument("--list", action="store_true", help="List pending_nelly_requests entries")
    parser.add_argument("--id", help="Request id to resolve (from --list)")
    parser.add_argument("--result", help="Result payload as a JSON string")
    args = parser.parse_args()

    if args.list:
        return list_requests(args.state)

    if not args.id or args.result is None:
        parser.error("--id and --result are required unless --list is given")

    return resolve_request(args.state, args.id, args.result)


if __name__ == "__main__":
    sys.exit(main())
