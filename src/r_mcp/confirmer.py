"""Confirmation strategies for gated tool calls.

The safe default is deny: if no terminal is available and no confirmation
command is configured, the call is blocked.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import threading
from typing import Any, TextIO


def split_command(command: str) -> list[str]:
    """Split a server/confirm command, keeping Windows backslashes intact."""
    parts = shlex.split(command, posix=False)
    cleaned = []
    for part in parts:
        if len(part) >= 2 and part[0] == part[-1] and part[0] in "\"'":
            part = part[1:-1]
        cleaned.append(part)
    if not cleaned:
        raise ValueError("command is empty")
    return cleaned


class Confirmer:
    def __init__(
        self,
        *,
        command: str | None = None,
        timeout: float = 30.0,
        auto_allow: bool = False,
        err: TextIO = sys.stderr,
    ) -> None:
        self.command = split_command(command) if command else None
        self.timeout = timeout
        self.auto_allow = auto_allow
        self.err = err

    def ask(self, rule: str | None, obj: dict[str, Any], *, prompt: str | None = None) -> bool:
        if self.auto_allow:
            return True
        if self.command is not None:
            return self._ask_command(self.command, rule, obj)
        return self._ask_tty(rule, obj, prompt)

    def _ask_command(self, command: list[str], rule: str | None, obj: dict[str, Any]) -> bool:
        payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        try:
            result = subprocess.run(
                command,
                input=payload,
                stdout=self.err,
                stderr=self.err,
                timeout=self.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            print("r-mcp: confirm command timed out; denying", file=self.err)
            return False
        except OSError as err:
            print(f"r-mcp: confirm command failed ({err}); denying", file=self.err)
            return False
        return result.returncode == 0

    def _ask_tty(self, rule: str | None, obj: dict[str, Any], prompt: str | None) -> bool:
        tty = _open_tty()
        if tty is None:
            print("r-mcp: no terminal available; denying", file=self.err)
            return False
        try:
            params = obj.get("params")
            tool = params.get("name") if isinstance(params, dict) else "unknown"
            text = prompt or f"r-mcp rule {rule or 'confirm'}: allow tool {tool!r}? (y/N) "
            tty.write(text)
            tty.flush()
            answer: list[str] = []

            def read_answer() -> None:
                try:
                    answer.append(tty.readline())
                except OSError:
                    answer.append("")

            reader = threading.Thread(target=read_answer, daemon=True)
            reader.start()
            reader.join(self.timeout)
            if reader.is_alive():
                print("r-mcp: confirmation timed out; denying", file=self.err)
                return False
            return answer[0].strip().lower() in {"y", "yes"}
        finally:
            tty.close()


def _open_tty() -> TextIO | None:
    name = "CONIN$" if os.name == "nt" else "/dev/tty"
    try:
        return open(name, "r+", encoding="utf-8", errors="replace")
    except OSError:
        return None


def tty_available() -> bool:
    handle = _open_tty()
    if handle is None:
        return False
    handle.close()
    return True
