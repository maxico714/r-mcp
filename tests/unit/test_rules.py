"""Unit tests for the rule engine."""

from __future__ import annotations

from pathlib import Path

import pytest

from r_mcp.rules import RulesError, RuleSet


def call(name: str, request_id: int = 1) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": {}},
    }


def write_rules(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "rules.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def test_default_allow_without_config() -> None:
    ruleset = RuleSet.load(None)
    assert ruleset.decide(call("write_file")).action == "allow"


def test_exact_tool_match(tmp_path: Path) -> None:
    ruleset = RuleSet.load(
        write_rules(
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
    )
    assert ruleset.decide(call("write_file")).action == "confirm"
    assert ruleset.decide(call("write_file_backup")).action == "allow"


def test_regex_tool_match(tmp_path: Path) -> None:
    ruleset = RuleSet.load(
        write_rules(
            tmp_path,
            """
rules:
  - name: gate-shell
    match:
      tool_name: "shell|exec|run"
    action: deny
""",
        )
    )
    assert ruleset.decide(call("shell")).action == "deny"
    assert ruleset.decide(call("exec")).action == "deny"


def test_first_matching_rule_wins(tmp_path: Path) -> None:
    ruleset = RuleSet.load(
        write_rules(
            tmp_path,
            """
rules:
  - name: deny-all-tools
    match:
      method: tools/call
    action: deny
  - name: allow-reads
    match:
      tool_name: read_file
    action: allow
""",
        )
    )
    assert ruleset.decide(call("read_file")).rule == "deny-all-tools"


def test_default_deny(tmp_path: Path) -> None:
    ruleset = RuleSet.load(write_rules(tmp_path, "default: deny\n"))
    assert ruleset.decide(call("anything")).action == "deny"


def test_rules_ignore_methods_without_matching_name(tmp_path: Path) -> None:
    ruleset = RuleSet.load(
        write_rules(
            tmp_path,
            """
rules:
  - name: gate-writes
    match:
      tool_name: write_file
    action: deny
""",
        )
    )
    assert ruleset.decide({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).action == "allow"


def test_prompt_for_named_rule(tmp_path: Path) -> None:
    ruleset = RuleSet.load(
        write_rules(
            tmp_path,
            """
rules:
  - name: gate-writes
    match:
      tool_name: write_file
    action: confirm
    prompt: "Write? "
""",
        )
    )
    assert ruleset.prompt_for("gate-writes") == "Write? "


@pytest.mark.parametrize(
    "content",
    [
        "default: maybe\n",
        "rules: {}\n",
        "rules:\n  - name: x\n    action: maybe\n",
        "rules:\n  - name: x\n    match: {bogus: 1}\n    action: allow\n",
        "rules:\n  - name: x\n    match: {tool_name: '['}\n    action: allow\n",
        "rules:\n  - name: x\n    action: allow\n  - name: x\n    action: deny\n",
        "extra: true\n",
        "- not-a-mapping\n",
    ],
)
def test_invalid_rules_raise(tmp_path: Path, content: str) -> None:
    with pytest.raises(RulesError):
        RuleSet.load(write_rules(tmp_path, content))


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(RulesError):
        RuleSet.load(tmp_path / "missing.yaml")
