"""Optional read-only stdio MCP adapter for Harness 2.0."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, TextIO

from . import __version__
from .codex_adapter import load_projection_bundle, runtime_state
from .contracts import blocker_codes
from .selection import analyze_workspace_impact


TOOLS = [
    {
        "name": "inspect",
        "description": "Read the current Harness runtime state.",
        "inputSchema": {
            "type": "object",
            "properties": {"repository": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "get_projection",
        "description": "Read the deterministic 16-cell projection.",
        "inputSchema": {
            "type": "object",
            "properties": {"repository": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "analyze_impact",
        "description": "Select T0-T3 from the current workspace changes.",
        "inputSchema": {
            "type": "object",
            "properties": {"repository": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "explain_blocker",
        "description": "Check whether a stable blocker code is canonical.",
        "inputSchema": {
            "type": "object",
            "required": ["blocker_code"],
            "properties": {"blocker_code": {"type": "string"}},
            "additionalProperties": False,
        },
    },
]


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
    if name == "inspect":
        result = runtime_state(repository)
        return _tool_result(result, is_error=result.get("status") != "active")
    if name == "get_projection":
        bundle = load_projection_bundle(repository)
        return _tool_result(
            bundle.get("projection") if bundle else {
                "blocker_codes": ["GOVERNANCE_SOURCE_MISSING"]
            },
            is_error=bundle is None,
        )
    if name == "analyze_impact":
        return _tool_result(analyze_workspace_impact(repository))
    if name == "explain_blocker":
        code = str(arguments["blocker_code"])
        canonical = code in blocker_codes()
        return _tool_result(
            {
                "blocker_code": code,
                "canonical": canonical,
                "summary": (
                    "Canonical Harness 2.0 blocker code."
                    if canonical
                    else "Unknown blocker code; do not infer its meaning."
                ),
            },
            is_error=not canonical,
        )
    return _tool_result({"error": f"unknown tool {name}"}, is_error=True)


def serve(stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> int:
    for line in stdin:
        request_id: Any = None
        try:
            message = json.loads(line)
            request_id = message.get("id")
            method = message.get("method")
            if method == "initialize":
                result = {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "harness", "version": __version__},
                    "instructions": (
                        "Read Harness state only. Execute governed work through "
                        "the sdd-harness command on PATH."
                    ),
                }
            elif method == "tools/list":
                result = {"tools": TOOLS}
            elif method == "tools/call":
                params = message.get("params", {})
                result = call_tool(
                    str(params.get("name", "")),
                    params.get("arguments", {}),
                )
            elif method in {"notifications/initialized", "ping"}:
                if request_id is None:
                    continue
                result = {}
            else:
                result = {"error": f"unsupported method {method}"}
            response = {"jsonrpc": "2.0", "id": request_id, "result": result}
        except (KeyError, TypeError, ValueError, OSError) as exc:
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32602, "message": str(exc)},
            }
        stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
        stdout.flush()
    return 0
