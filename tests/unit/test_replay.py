"""Unit tests for replay request selection."""

from __future__ import annotations

import pytest

from r_mcp.replay import select_request


def request(request_id: int, name: str = "echo") -> dict[str, object]:
    return {
        "direction": "c2s",
        "payload": {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": {}},
        },
    }


def response(request_id: int) -> dict[str, object]:
    return {
        "direction": "c2s",
        "payload": {"jsonrpc": "2.0", "id": request_id, "result": {}},
    }


def test_select_request_ignores_client_responses() -> None:
    entries = [response(99), request(2), response(100), request(3)]

    selected = select_request(entries, index=1)
    assert selected["payload"]["id"] == 2  # type: ignore[index]

    selected = select_request(entries, index=2)
    assert selected["payload"]["id"] == 3  # type: ignore[index]


def test_select_request_id_does_not_match_response() -> None:
    with pytest.raises(ValueError, match="no captured request with id"):
        select_request([response(99), request(2)], request_id="99")
