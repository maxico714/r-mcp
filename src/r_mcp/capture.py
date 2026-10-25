"""JSONL capture writer with redaction on by default."""

from __future__ import annotations

import json
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

from .attrib import estimate_tokens
from .redact import redact


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class CaptureWriter:
    """Append one JSON object per frame; safe to call from several threads."""

    def __init__(
        self,
        path: Path | None,
        *,
        redact_enabled: bool = True,
        err: TextIO = sys.stderr,
    ) -> None:
        self.path = path
        self.redact_enabled = redact_enabled
        self._lock = threading.Lock()
        self._handle: TextIO | None = None
        if path is not None:
            try:
                self._handle = path.open("w", encoding="utf-8", newline="\n")
            except OSError as err_obj:
                raise OSError(f"cannot write capture file {path}: {err_obj}") from err_obj
        if not redact_enabled:
            print("warning: redaction disabled; captures may contain secrets", file=err)
            self._write({"event": "redaction_disabled", "ts": _now()})

    def _write(self, entry: dict[str, Any]) -> None:
        if self._handle is None:
            return
        with self._lock:
            self._handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self._handle.flush()

    def write(
        self,
        direction: str,
        obj: dict[str, Any],
        *,
        raw_len: int,
        action: str | None = None,
        rule: str | None = None,
    ) -> None:
        if self._handle is None:
            return
        payload, redactions = redact(obj) if self.redact_enabled else (obj, 0)
        params = obj.get("params")
        tool_name = params.get("name") if isinstance(params, dict) else None
        entry: dict[str, Any] = {
            "ts": _now(),
            "direction": direction,
            "method": obj.get("method"),
            "id": obj.get("id"),
            "redacted": self.redact_enabled,
            "redactions": redactions,
            "raw_len": raw_len,
            "est_tokens": estimate_tokens(obj),
            "payload": payload,
        }
        if isinstance(tool_name, str):
            entry["tool_name"] = tool_name
        if action is not None:
            entry["action"] = action
        if rule is not None:
            entry["rule"] = rule
        self._write(entry)

    def close(self) -> None:
        if self._handle is not None:
            with self._lock:
                self._handle.close()
                self._handle = None


def read_capture(path: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                text = line.strip()
                if not text:
                    continue
                try:
                    entry = json.loads(text)
                except json.JSONDecodeError as err:
                    raise ValueError(f"{path}:{line_no}: invalid JSON: {err}") from err
                if not isinstance(entry, dict):
                    raise ValueError(f"{path}:{line_no}: capture entry must be an object")
                entries.append(entry)
    except OSError as err:
        raise ValueError(f"cannot read capture file {path}: {err}") from err
    return entries
