"""Adversarial input tests: fail cleanly, never crash or hang."""

from __future__ import annotations

import json
from pathlib import Path

from conftest import (
    FIXTURES,
    initialize,
    parse_lines,
    run_cli,
    server_arg,
)


def test_malformed_frame_exits_three() -> None:
    result = run_cli(["proxy", "--server", server_arg()], b"{not json}\n")
    assert result.returncode == 3
    assert b"malformed JSON-RPC frame" in result.stderr


def test_non_object_frame_exits_three() -> None:
    result = run_cli(["proxy", "--server", server_arg()], b"[]\n")
    assert result.returncode == 3
    assert b"must be an object" in result.stderr


def test_incomplete_frame_at_eof_exits_three() -> None:
    result = run_cli(["proxy", "--server", server_arg()], b'{"jsonrpc":"2.0","id":1}')
    assert result.returncode == 3
    assert b"incomplete frame" in result.stderr


def test_oversized_frame_is_rejected_before_parsing() -> None:
    payload = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {"x": "y" * 400}}
    ).encode()
    result = run_cli(
        ["proxy", "--server", server_arg(), "--max-frame-bytes", "128"],
        payload + b"\n",
    )
    assert result.returncode == 3
    assert b"byte limit" in result.stderr


def test_deeply_nested_frame_is_rejected() -> None:
    nested: object = "x"
    for _ in range(150):
        nested = {"a": nested}
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping", "params": nested})
    result = run_cli(["proxy", "--server", server_arg()], payload.encode() + b"\n")
    assert result.returncode == 3
    assert b"nesting" in result.stderr


def test_invalid_utf8_is_rejected_cleanly() -> None:
    result = run_cli(["proxy", "--server", server_arg()], b"\xff\xfe\n")
    assert result.returncode == 3
    assert b"malformed JSON-RPC frame" in result.stderr


def test_server_spawn_failure_exits_four() -> None:
    result = run_cli(["proxy", "--server", "definitely-not-a-real-command-xyz"])
    assert result.returncode == 4
    assert b"cannot start server" in result.stderr


def test_malformed_server_frame_exits_three() -> None:
    result = run_cli(
        ["proxy", "--server", server_arg(FIXTURES / "bad_server.py")],
        initialize(),
    )
    assert result.returncode == 3
    assert b"server produced" in result.stderr


def test_tool_call_without_params_does_not_match(tmp_path: Path) -> None:
    config = tmp_path / "rules.yaml"
    config.write_text(
        "rules:\n  - name: gate\n    match: {tool_name: write_file}\n    action: deny\n",
        encoding="utf-8",
    )
    data = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call"}).encode() + b"\n"
    result = run_cli(
        ["proxy", "--server", server_arg(), "--config", str(config)],
        data,
    )
    assert result.returncode == 0
    assert parse_lines(result.stdout)
