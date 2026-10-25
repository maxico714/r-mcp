"""Security tests: redaction is on by default and never applied to traffic."""

from __future__ import annotations

import json
from pathlib import Path

from conftest import by_id, initialize, parse_lines, read_capture, run_cli, server_arg, tool_call

SECRET = "sk-live-super-secret-123"  # pragma: allowlist secret (fake fixture)
BLOB = "A1b2C3d4" * 8


def _run(tmp_path: Path, *extra: str) -> tuple[int, bytes, bytes, Path]:
    capture = tmp_path / "capture.jsonl"
    data = initialize() + tool_call(
        "echo_args", 2, {"api_key": SECRET, "blob": BLOB, "text": "visible"}
    )
    result = run_cli(
        ["proxy", "--server", server_arg(), "--capture", str(capture), *extra],
        data,
    )
    return result.returncode, result.stdout, result.stderr, capture


def test_capture_redacts_secrets_but_traffic_is_intact(tmp_path: Path) -> None:
    code, stdout, stderr, capture = _run(tmp_path)
    assert code == 0, stderr.decode()

    live = by_id(parse_lines(stdout), 2)["result"]["content"][0]["text"]
    assert SECRET in live
    assert BLOB in live

    raw_capture = capture.read_text(encoding="utf-8")
    assert SECRET not in raw_capture
    assert BLOB not in raw_capture
    assert "[REDACTED]" in raw_capture

    entries = read_capture(capture)
    client_entry = next(entry for entry in entries if entry.get("tool_name") == "echo_args")
    assert client_entry["redacted"] is True
    assert client_entry["redactions"] >= 2


def test_no_secret_in_stderr(tmp_path: Path) -> None:
    _, _, stderr, _ = _run(tmp_path)
    assert SECRET not in stderr.decode()


def test_no_redact_is_loud_and_audited(tmp_path: Path) -> None:
    code, _, stderr, capture = _run(tmp_path, "--no-redact")
    assert code == 0
    assert "redaction disabled" in stderr.decode()
    entries = read_capture(capture)
    assert entries[0]["event"] == "redaction_disabled"
    assert SECRET in capture.read_text(encoding="utf-8")


def test_capture_file_is_valid_jsonl(tmp_path: Path) -> None:
    _, _, _, capture = _run(tmp_path)
    for line in capture.read_text(encoding="utf-8").splitlines():
        assert isinstance(json.loads(line), dict)
