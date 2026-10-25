"""End-to-end tests: proxy, capture, confirm-gate, replay and report."""

from __future__ import annotations

import json
from pathlib import Path

from conftest import (
    ALLOW_CONFIRM,
    DENY_CONFIRM,
    MOCK_SERVER,
    SLOW_CONFIRM,
    by_id,
    confirm_arg,
    initialize,
    initialized,
    parse_lines,
    read_capture,
    rules_file,
    run_cli,
    server_arg,
    tool_call,
)


def test_proxy_forwards_and_captures(tmp_path: Path) -> None:
    capture = tmp_path / "capture.jsonl"
    data = initialize() + initialized() + tool_call("echo", 2, {"text": "hello"})
    result = run_cli(
        ["proxy", "--server", server_arg(), "--capture", str(capture)],
        data,
    )
    assert result.returncode == 0, result.stderr.decode()
    messages = parse_lines(result.stdout)
    assert by_id(messages, 1)["result"]["serverInfo"]["name"] == "mock-mcp"
    assert by_id(messages, 2)["result"]["content"][0]["text"] == "hello"

    entries = read_capture(capture)
    assert any(
        entry["direction"] == "c2s" and entry.get("tool_name") == "echo" for entry in entries
    )
    assert any(entry["direction"] == "s2c" for entry in entries)
    tool_entries = [entry for entry in entries if entry.get("tool_name") == "echo"]
    assert all(entry["est_tokens"] >= 0 for entry in tool_entries)
    assert "estimate" in result.stderr.decode()


def test_confirm_gate_denies_and_reports_exit_one(tmp_path: Path) -> None:
    config = rules_file(
        tmp_path,
        """
rules:
  - name: gate-writes
    match:
      method: tools/call
      tool_name: write_file
    action: confirm
""",
    )
    capture = tmp_path / "capture.jsonl"
    data = initialize() + tool_call("write_file", 2, {"path": "a.txt"}) + tool_call("echo", 3)
    result = run_cli(
        [
            "proxy",
            "--server",
            server_arg(),
            "--config",
            str(config),
            "--capture",
            str(capture),
            "--confirm-command",
            confirm_arg(DENY_CONFIRM),
        ],
        data,
    )
    assert result.returncode == 1, result.stderr.decode()
    messages = parse_lines(result.stdout)
    blocked = by_id(messages, 2)
    assert blocked["error"]["code"] == -32001
    assert "gate-writes" in blocked["error"]["message"]
    assert by_id(messages, 3)["result"]["content"][0]["text"] == ""

    entries = read_capture(capture)
    write_entry = next(entry for entry in entries if entry.get("tool_name") == "write_file")
    assert write_entry["action"] == "deny"
    assert write_entry["rule"] == "gate-writes"


def test_confirm_gate_allows_when_command_exits_zero(tmp_path: Path) -> None:
    config = rules_file(
        tmp_path,
        """
rules:
  - name: gate-writes
    match:
      tool_name: write_file
    action: confirm
""",
    )
    data = initialize() + tool_call("write_file", 2, {"path": "a.txt"})
    result = run_cli(
        [
            "proxy",
            "--server",
            server_arg(),
            "--config",
            str(config),
            "--confirm-command",
            confirm_arg(ALLOW_CONFIRM),
        ],
        data,
    )
    assert result.returncode == 0, result.stderr.decode()
    assert by_id(parse_lines(result.stdout), 2)["result"]["content"][0]["text"] == "written"


def test_confirm_timeout_denies(tmp_path: Path) -> None:
    config = rules_file(
        tmp_path,
        """
rules:
  - name: gate-writes
    match:
      tool_name: write_file
    action: confirm
""",
    )
    data = initialize() + tool_call("write_file", 2, {"path": "a.txt"})
    result = run_cli(
        [
            "proxy",
            "--server",
            server_arg(),
            "--config",
            str(config),
            "--confirm-command",
            confirm_arg(SLOW_CONFIRM),
            "--confirm-timeout",
            "0.3",
        ],
        data,
        timeout=20,
    )
    assert result.returncode == 1, result.stderr.decode()
    assert "timed out" in result.stderr.decode()
    assert "error" in by_id(parse_lines(result.stdout), 2)


def test_explicit_deny_rule_never_reaches_server(tmp_path: Path) -> None:
    config = rules_file(
        tmp_path,
        """
rules:
  - name: deny-reads
    match:
      tool_name: read_file
    action: deny
""",
    )
    data = initialize() + tool_call("read_file", 2, {"path": ".env"})
    result = run_cli(
        ["proxy", "--server", server_arg(), "--config", str(config)],
        data,
    )
    assert result.returncode == 1
    assert "deny-reads" in by_id(parse_lines(result.stdout), 2)["error"]["message"]


def test_replay_resends_captured_request(tmp_path: Path) -> None:
    capture = tmp_path / "capture.jsonl"
    first = run_cli(
        ["proxy", "--server", server_arg(), "--capture", str(capture)],
        initialize() + tool_call("echo", 2, {"text": "replayed"}),
    )
    assert first.returncode == 0, first.stderr.decode()

    replay = run_cli(
        ["replay", str(capture), "--id", "2", "--server", server_arg()],
    )
    assert replay.returncode == 0, replay.stderr.decode()
    response = json.loads(replay.stdout)
    assert response["id"] == 2
    assert response["result"]["content"][0]["text"] == "replayed"
    assert "redacted" not in replay.stderr.decode()


def test_replay_rejects_missing_selection(tmp_path: Path) -> None:
    capture = tmp_path / "capture.jsonl"
    run_cli(["proxy", "--server", server_arg(), "--capture", str(capture)], initialize())
    result = run_cli(["replay", str(capture), "--server", server_arg()])
    assert result.returncode == 2
    assert "--id or --index" in result.stderr.decode()


def test_report_labels_estimates(tmp_path: Path) -> None:
    capture = tmp_path / "capture.jsonl"
    run_cli(
        ["proxy", "--server", server_arg(), "--capture", str(capture)],
        initialize() + tool_call("echo", 2, {"text": "hello"}),
    )
    report_json = tmp_path / "report.json"
    result = run_cli(["report", str(capture), "--json", str(report_json)])
    assert result.returncode == 0, result.stderr.decode()
    assert result.stdout.decode().startswith("echo\t1\t~")
    payload = json.loads(report_json.read_text(encoding="utf-8"))
    assert payload["tools"][0]["tool"] == "echo"
    assert "estimate" in payload["note"]


def test_dry_run_prints_rules_without_running_server(tmp_path: Path) -> None:
    config = rules_file(
        tmp_path,
        """
rules:
  - name: gate-writes
    match:
      tool_name: write_file
    action: confirm
""",
    )
    result = run_cli(
        [
            "proxy",
            "--server",
            "definitely-not-a-real-command-xyz",
            "--config",
            str(config),
            "--dry-run",
        ],
    )
    assert result.returncode == 0
    assert b"gate-writes" in result.stdout


def test_invalid_config_exits_two(tmp_path: Path) -> None:
    config = rules_file(tmp_path, "rules:\n  - name: x\n    action: nope\n")
    result = run_cli(["proxy", "--server", server_arg(), "--config", str(config)])
    assert result.returncode == 2
    assert b"action must be one of" in result.stderr


def test_rules_validate(tmp_path: Path) -> None:
    valid = rules_file(tmp_path, "default: deny\n")
    assert run_cli(["rules", "validate", "--config", str(valid)]).returncode == 0
    invalid = rules_file(tmp_path, "rules:\n  - name: x\n    action: nope\n")
    assert run_cli(["rules", "validate", "--config", str(invalid)]).returncode == 2


def test_doctor_reports_ready() -> None:
    result = run_cli(["doctor"])
    assert result.returncode == 0, result.stderr.decode()
    assert b"doctor: ready" in result.stdout


def test_capture_write_failure_exits_two(tmp_path: Path) -> None:
    missing_dir = tmp_path / "missing" / "capture.jsonl"
    result = run_cli(["proxy", "--server", server_arg(), "--capture", str(missing_dir)])
    assert result.returncode == 2
    assert b"cannot write capture file" in result.stderr


def test_unicode_tool_arguments_round_trip(tmp_path: Path) -> None:
    capture = tmp_path / "capture.jsonl"
    text = "नमस्ते \u2014 файл"
    result = run_cli(
        ["proxy", "--server", server_arg(), "--capture", str(capture)],
        initialize() + tool_call("echo", 2, {"text": text}),
    )
    assert result.returncode == 0, result.stderr.decode()
    assert by_id(parse_lines(result.stdout), 2)["result"]["content"][0]["text"] == text
    entries = read_capture(capture)
    assert any(text in json.dumps(entry, ensure_ascii=False) for entry in entries)


def test_mock_server_fixture_exists() -> None:
    assert MOCK_SERVER.exists()
