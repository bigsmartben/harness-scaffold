"""Minimal stdio MCP server exposing only read/request-preparation tools."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, TextIO

from .codex_adapter import load_projection_bundle, runtime_state
from .gates import create_action_request


TOOLS = [
    {
        "name": "get_projection",
        "description": "Read the current Harness projection summary.",
        "inputSchema": {
            "type": "object",
            "properties": {"repository": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "resolve_action",
        "description": "Resolve one action_id without executing it.",
        "inputSchema": {
            "type": "object",
            "required": ["action_id"],
            "properties": {
                "repository": {"type": "string"},
                "action_id": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "explain_blocker",
        "description": "Explain one stable Harness blocker code.",
        "inputSchema": {
            "type": "object",
            "required": ["blocker_code"],
            "properties": {"blocker_code": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "prepare_action_request",
        "description": "Prepare a typed Action Request; never executes it.",
        "inputSchema": {
            "type": "object",
            "required": ["action_id", "grant"],
            "properties": {
                "repository": {"type": "string"},
                "action_id": {"type": "string"},
                "grant": {"type": "object"},
                "audience": {"type": "string"},
                "scope": {"type": "array", "items": {"type": "string"}},
                "parameters": {"type": "object"},
            },
            "additionalProperties": False,
        },
    },
]

_BLOCKER_EXPLANATIONS = {
    "GOVERNANCE_PROJECTION_STALE": "Repository governance inputs no longer match projection_id.",
    "INVOCATION_BYPASS_ATTEMPT": "A governed Action was invoked outside the Harness dispatcher.",
    "GOVERNANCE_EVIDENCE_INCOMPLETE": "Required postconditions or digest-bound Evidence are missing.",
    "TOOL_BINDING_AMBIGUOUS": "The Action does not resolve to exactly one invocation.",
    "HANDOFF_REQUIRED": "User or platform authority is required before continuing.",
}


def _repository(arguments: dict[str, Any]) -> Path:
    return Path(arguments.get("repository") or ".").resolve()


def _tool_result(value: Any, *, is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(value, ensure_ascii=False, sort_keys=True),
            }
        ],
        "isError": is_error,
    }


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    repository = _repository(arguments)
    if name == "get_projection":
        return _tool_result(runtime_state(repository))
    if name == "resolve_action":
        bundle = load_projection_bundle(repository)
        action = (
            next(
                (
                    item
                    for item in bundle["action_graph"]["actions"]
                    if item["action_id"] == arguments["action_id"]
                ),
                None,
            )
            if bundle
            else None
        )
        return _tool_result(
            action or {"blocker_codes": ["TOOL_ACTION_UNCLASSIFIED", "HANDOFF_REQUIRED"]},
            is_error=action is None,
        )
    if name == "explain_blocker":
        code = arguments["blocker_code"]
        return _tool_result(
            {
                "blocker_code": code,
                "explanation": _BLOCKER_EXPLANATIONS.get(
                    code, "See the canonical blocker enum and governance Evidence."
                ),
            }
        )
    if name == "prepare_action_request":
        bundle = load_projection_bundle(repository)
        if not bundle:
            return _tool_result(
                {"blocker_codes": ["GOVERNANCE_SOURCE_MISSING", "HANDOFF_REQUIRED"]},
                is_error=True,
            )
        request = create_action_request(
            bundle["projection_lock"]["projection_id"],
            arguments["grant"],
            arguments["action_id"],
            audience=arguments.get("audience", "maintainer"),
            scope=arguments.get("scope"),
            parameters=arguments.get("parameters"),
        )
        return _tool_result(request)
    return _tool_result({"error": f"unknown tool {name}"}, is_error=True)


def serve(stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> int:
    for line in stdin:
        try:
            message = json.loads(line)
            method = message.get("method")
            request_id = message.get("id")
            if method == "initialize":
                result = {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "harness", "version": "1.0.0"},
                    "instructions": "Read governance state and prepare typed requests. Never execute commands.",
                }
            elif method == "tools/list":
                result = {"tools": TOOLS}
            elif method == "tools/call":
                params = message.get("params", {})
                result = call_tool(params.get("name", ""), params.get("arguments", {}))
            elif method in {"notifications/initialized", "ping"}:
                if request_id is None:
                    continue
                result = {}
            else:
                result = {"error": f"unsupported method {method}"}
            response = {"jsonrpc": "2.0", "id": request_id, "result": result}
        except Exception as exc:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": str(exc)},
            }
        stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
        stdout.flush()
    return 0
