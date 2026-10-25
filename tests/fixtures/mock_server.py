"""Minimal MCP-shaped stdio server used by integration tests.

It speaks newline-delimited JSON-RPC 2.0 and implements initialize, ping,
tools/list and tools/call for a few fixture tools.
"""

from __future__ import annotations

import json
import sys
from typing import Any

TOOLS = [
    {"name": "echo", "description": "Echo the text argument", "inputSchema": {"type": "object"}},
    {"name": "echo_args", "description": "Return arguments", "inputSchema": {"type": "object"}},
    {"name": "read_file", "description": "Read a file", "inputSchema": {"type": "object"}},
    {"name": "write_file", "description": "Write a file", "inputSchema": {"type": "object"}},
]


def respond(request_id: Any, result: Any) -> None:
    _write({"jsonrpc": "2.0", "id": request_id, "result": result})


def fail(request_id: Any, code: int, message: str) -> None:
    _write({"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}})


def _write(message: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def handle(message: dict[str, Any]) -> None:
    request_id = message.get("id")
    method = message.get("method")
    params = message.get("params") or {}
    if request_id is None:
        return
    if method == "initialize":
        respond(
            request_id,
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "mock-mcp", "version": "0.1.0"},
            },
        )
    elif method == "ping":
        respond(request_id, {})
    elif method == "tools/list":
        respond(request_id, {"tools": TOOLS})
    elif method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if name == "echo":
            text = arguments.get("text", "")
            respond(request_id, {"content": [{"type": "text", "text": text}]})
        elif name == "echo_args":
            respond(request_id, {"content": [{"type": "text", "text": json.dumps(arguments)}]})
        elif name == "read_file":
            respond(request_id, {"content": [{"type": "text", "text": "file contents"}]})
        elif name == "write_file":
            respond(request_id, {"content": [{"type": "text", "text": "written"}]})
        else:
            fail(request_id, -32602, f"unknown tool: {name}")
    elif method is None:
        return
    else:
        fail(request_id, -32601, f"method not found: {method}")


def main() -> int:
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    for line in sys.stdin:
        text = line.strip()
        if not text:
            continue
        try:
            message = json.loads(text)
        except json.JSONDecodeError:
            _write(
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "parse error"},
                }
            )
            continue
        if isinstance(message, dict):
            handle(message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
