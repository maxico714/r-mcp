"""Newline-delimited JSON-RPC framing for the MCP stdio transport.

MCP 2025-06-18, "stdio" transport: messages are delimited by newlines and MUST
NOT contain embedded newlines; encoding is UTF-8; stdout carries only MCP
messages and stderr may carry logs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import IO, Any

MAX_FRAME_BYTES = 10 * 1024 * 1024
MAX_NESTING_DEPTH = 100


class FramingError(ValueError):
    """Raised when a stdio frame cannot be read or parsed."""


@dataclass(frozen=True)
class Frame:
    raw: bytes
    obj: dict[str, Any]
    complete: bool


def _check_depth(obj: Any, max_depth: int = MAX_NESTING_DEPTH) -> None:
    stack: list[tuple[Any, int]] = [(obj, 1)]
    while stack:
        node, depth = stack.pop()
        if depth > max_depth:
            raise FramingError(f"frame nesting exceeds {max_depth} levels")
        if isinstance(node, dict):
            stack.extend((value, depth + 1) for value in node.values())
        elif isinstance(node, list):
            stack.extend((value, depth + 1) for value in node)


def parse_frame(raw: bytes) -> dict[str, Any]:
    """Parse one frame body (delimiter optional) into a JSON-RPC object."""
    body = raw.rstrip(b"\r\n")
    try:
        obj = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as err:
        raise FramingError(f"malformed JSON-RPC frame: {err}") from err
    except RecursionError as err:
        raise FramingError("frame nesting is too deep") from err
    if not isinstance(obj, dict):
        raise FramingError("JSON-RPC frame must be an object")
    if obj.get("jsonrpc") != "2.0":
        raise FramingError("JSON-RPC frame must declare jsonrpc 2.0")
    _check_depth(obj)
    return obj


def read_frame(stream: IO[bytes], max_bytes: int = MAX_FRAME_BYTES) -> Frame | None:
    """Read one newline-delimited frame, enforcing ``max_bytes`` as a memory cap."""
    raw = stream.readline(max_bytes + 1)
    if not raw:
        return None
    if len(raw) > max_bytes:
        raise FramingError(f"frame exceeds the {max_bytes} byte limit")
    return Frame(raw=raw, obj=parse_frame(raw), complete=raw.endswith(b"\n"))


def encode_frame(obj: dict[str, Any]) -> bytes:
    """Encode an object as one compact, newline-terminated frame."""
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n"
