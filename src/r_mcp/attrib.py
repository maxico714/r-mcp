"""Rough per-tool token attribution, always labelled as an estimate."""

from __future__ import annotations

import json
from typing import Any

NOTE = "estimate - provider-specific counting is out of scope"


def estimate_tokens(value: Any) -> int:
    """Round a chars/4 heuristic to the nearest 10 so it never looks exact."""
    chars = len(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
    return round(chars / 4 / 10.0) * 10


def summarize(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate calls and estimated tokens per tool from capture entries."""
    tools: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if entry.get("event"):
            continue
        tool = entry.get("tool_name")
        if not isinstance(tool, str) or not tool:
            continue
        bucket = tools.setdefault(tool, {"tool": tool, "calls": 0, "est_tokens": 0})
        bucket["est_tokens"] += int(entry.get("est_tokens", 0))
        if entry.get("direction") == "c2s" and entry.get("method") == "tools/call":
            bucket["calls"] += 1
    return sorted(tools.values(), key=lambda item: (-int(item["est_tokens"]), str(item["tool"])))
