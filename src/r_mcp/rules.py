"""Rule engine for the confirm-gate: allow, deny or ask before forwarding."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ACTIONS = ("allow", "deny", "confirm")
_RULE_KEYS = {"name", "match", "action", "prompt"}
_MATCH_KEYS = {"method", "tool_name"}


class RulesError(ValueError):
    """Raised when a rules file is missing, unreadable or invalid."""


@dataclass(frozen=True)
class Rule:
    name: str
    action: str
    method: str | None
    tool_name: re.Pattern[str] | None
    prompt: str | None

    def matches(self, obj: dict[str, Any]) -> bool:
        method = obj.get("method")
        if self.method is not None and method != self.method:
            return False
        if self.tool_name is not None:
            params = obj.get("params")
            tool_name = params.get("name") if isinstance(params, dict) else None
            if not isinstance(tool_name, str):
                return False
            if self.tool_name.fullmatch(tool_name) is None:
                return False
        return True


@dataclass(frozen=True)
class Decision:
    action: str
    rule: str | None


class RuleSet:
    def __init__(self, rules: tuple[Rule, ...] = (), default: str = "allow") -> None:
        if default not in ACTIONS:
            raise RulesError(f"default must be one of {', '.join(ACTIONS)}")
        self.rules = rules
        self.default = default

    def decide(self, obj: dict[str, Any]) -> Decision:
        for rule in self.rules:
            if rule.matches(obj):
                return Decision(action=rule.action, rule=rule.name)
        return Decision(action=self.default, rule=None)

    def prompt_for(self, name: str | None) -> str:
        for rule in self.rules:
            if rule.name == name and rule.prompt:
                return rule.prompt
        return "Allow this tool call? (y/N) "

    @classmethod
    def load(cls, path: Path | None) -> RuleSet:
        if path is None:
            return cls()
        if not path.exists():
            raise RulesError(f"rules file not found: {path}")
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle) or {}
        except (OSError, yaml.YAMLError) as err:
            raise RulesError(f"cannot read rules file {path}: {err}") from err
        if not isinstance(data, dict):
            raise RulesError(f"rules file {path} must be a YAML mapping")
        unknown_top = set(data) - {"rules", "default"}
        if unknown_top:
            raise RulesError(f"unknown top-level keys: {', '.join(sorted(unknown_top))}")
        default = data.get("default", "allow")
        if not isinstance(default, str) or default not in ACTIONS:
            raise RulesError(f"default must be one of {', '.join(ACTIONS)}")

        raw_rules = data.get("rules", [])
        if not isinstance(raw_rules, list):
            raise RulesError("rules must be a list")
        rules: list[Rule] = []
        seen: set[str] = set()
        for index, raw in enumerate(raw_rules):
            rules.append(cls._parse_rule(index, raw))
            if rules[-1].name in seen:
                raise RulesError(f"duplicate rule name: {rules[-1].name}")
            seen.add(rules[-1].name)
        return cls(rules=tuple(rules), default=default)

    @staticmethod
    def _parse_rule(index: int, raw: Any) -> Rule:
        where = f"rules[{index}]"
        if not isinstance(raw, dict):
            raise RulesError(f"{where} must be a mapping")
        unknown = set(raw) - _RULE_KEYS
        if unknown:
            raise RulesError(f"{where} has unknown keys: {', '.join(sorted(unknown))}")
        name = raw.get("name")
        if not isinstance(name, str) or not name.strip():
            raise RulesError(f"{where}.name must be a non-empty string")
        action = raw.get("action")
        if not isinstance(action, str) or action not in ACTIONS:
            raise RulesError(f"{where}.action must be one of {', '.join(ACTIONS)}")
        prompt = raw.get("prompt")
        if prompt is not None and not isinstance(prompt, str):
            raise RulesError(f"{where}.prompt must be a string")

        match = raw.get("match", {})
        if not isinstance(match, dict):
            raise RulesError(f"{where}.match must be a mapping")
        unknown_match = set(match) - _MATCH_KEYS
        if unknown_match:
            raise RulesError(f"{where}.match has unknown keys: {', '.join(sorted(unknown_match))}")
        method = match.get("method")
        if method is not None and not isinstance(method, str):
            raise RulesError(f"{where}.match.method must be a string")
        tool_pattern = match.get("tool_name")
        if tool_pattern is not None and not isinstance(tool_pattern, str):
            raise RulesError(f"{where}.match.tool_name must be a string")
        compiled: re.Pattern[str] | None = None
        if tool_pattern is not None:
            try:
                compiled = re.compile(tool_pattern)
            except re.error as err:
                raise RulesError(f"{where}.match.tool_name is not a valid regex: {err}") from err
        return Rule(
            name=name,
            action=action,
            method=method,
            tool_name=compiled,
            prompt=prompt,
        )
