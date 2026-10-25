"""Shared fixtures and subprocess helpers."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
MOCK_SERVER = FIXTURES / "mock_server.py"
ALLOW_CONFIRM = FIXTURES / "allow_confirm.py"
DENY_CONFIRM = FIXTURES / "deny_confirm.py"
SLOW_CONFIRM = FIXTURES / "slow_confirm.py"

SHIM = str(SRC)

if SHIM not in sys.path:
    sys.path.insert(0, SHIM)


@pytest.fixture(autouse=True)
def _src_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    existing = os.environ.get("PYTHONPATH")
    prefix = SHIM if not existing else SHIM + os.pathsep + existing
    monkeypatch.setenv("PYTHONPATH", prefix)


def cli_env() -> dict[str, str]:
    env = dict(os.environ)
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = SHIM if not existing else SHIM + os.pathsep + existing
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def server_arg(script: Path = MOCK_SERVER) -> str:
    return f'"{sys.executable}" "{script}"'


def confirm_arg(script: Path = DENY_CONFIRM) -> str:
    return f'"{sys.executable}" "{script}"'


def run_cli(
    args: Sequence[str],
    data: bytes = b"",
    *,
    timeout: float = 30.0,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-m", "r_mcp", *args],
        input=data,
        capture_output=True,
        env=cli_env(),
        timeout=timeout,
        check=False,
    )


def frame(obj: dict[str, Any]) -> bytes:
    return json.dumps(obj, separators=(",", ":")).encode("utf-8") + b"\n"


def initialize(request_id: int = 1) -> bytes:
    return frame(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "r-mcp-tests", "version": "0.1.0"},
            },
        }
    )


def initialized() -> bytes:
    return frame({"jsonrpc": "2.0", "method": "notifications/initialized"})


def tool_call(name: str, request_id: int, arguments: dict[str, Any] | None = None) -> bytes:
    return frame(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        }
    )


def parse_lines(data: bytes) -> list[dict[str, Any]]:
    messages = []
    for line in data.splitlines():
        if line.strip():
            messages.append(json.loads(line))
    return messages


def by_id(messages: list[dict[str, Any]], request_id: int) -> dict[str, Any]:
    for message in messages:
        if message.get("id") == request_id:
            return message
    raise AssertionError(f"no response with id {request_id}: {messages!r}")


def rules_file(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "rules.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def read_capture(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
