"""Replay one captured request against a local MCP server."""

from __future__ import annotations

import contextlib
import json
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, TextIO

from .capture import read_capture
from .framing import MAX_FRAME_BYTES, FramingError, encode_frame, parse_frame
from .redact import REDACTED


def select_request(
    entries: list[dict[str, Any]],
    *,
    request_id: str | None = None,
    index: int | None = None,
) -> dict[str, Any]:
    requests = [
        entry
        for entry in entries
        if entry.get("direction") == "c2s"
        and isinstance(entry.get("payload"), dict)
        and isinstance(entry["payload"].get("method"), str)
    ]
    if not requests:
        raise ValueError("capture contains no client requests to replay")
    if request_id is not None:
        for entry in requests:
            if str(entry.get("id")) == request_id:
                return entry
        raise ValueError(f"no captured request with id {request_id!r}")
    if index is not None:
        if index < 1 or index > len(requests):
            raise ValueError(f"--index must be between 1 and {len(requests)}")
        return requests[index - 1]
    raise ValueError("select a request with --id or --index")


def frame_for(entry: dict[str, Any]) -> bytes:
    payload = entry.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("captured request has no payload")
    if REDACTED in json.dumps(payload):
        print("warning: captured request contains redacted values", file=sys.stderr)
    raw = entry.get("raw")
    if isinstance(raw, str) and raw:
        return raw.encode("utf-8") + (b"" if raw.endswith("\n") else b"\n")
    return encode_frame(payload)


def replay(
    capture_path: Path,
    *,
    server_cmd: list[str],
    request_id: str | None = None,
    index: int | None = None,
    timeout: float = 10.0,
    out: TextIO = sys.stdout,
    err: TextIO = sys.stderr,
) -> int:
    try:
        entries = read_capture(capture_path)
        entry = select_request(entries, request_id=request_id, index=index)
        request = frame_for(entry)
    except ValueError as err_obj:
        print(f"error: {err_obj}", file=err)
        return 2

    try:
        proc = subprocess.Popen(server_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    except (OSError, ValueError) as err_obj:
        print(f"error: cannot start server {server_cmd!r}: {err_obj}", file=err)
        return 4
    assert proc.stdin is not None
    assert proc.stdout is not None
    try:
        proc.stdin.write(request)
        proc.stdin.flush()
        response = _read_response(proc.stdout, entry.get("id"), timeout)
        print(json.dumps(response, ensure_ascii=False, indent=2), file=out)
        return 0
    except TimeoutError:
        print(f"error: no response within {timeout:g}s", file=err)
        return 3
    except (FramingError, EOFError) as err_obj:
        print(f"error: {err_obj}", file=err)
        return 3
    finally:
        with contextlib.suppress(OSError):
            proc.stdin.close()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()


def _read_response(stream: Any, request_id: Any, timeout: float) -> dict[str, Any]:
    lines: queue.Queue[bytes | None] = queue.Queue()

    def reader() -> None:
        while True:
            line = stream.readline(MAX_FRAME_BYTES + 1)
            if not line:
                lines.put(None)
                return
            lines.put(line)

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        try:
            line = lines.get(timeout=remaining)
        except queue.Empty:
            raise TimeoutError from None
        if line is None:
            raise EOFError("server closed stdout without a response")
        if len(line) > MAX_FRAME_BYTES:
            raise FramingError("server response exceeds the frame limit")
        obj = parse_frame(line)
        if "method" in obj:
            continue
        if request_id is None or str(obj.get("id")) == str(request_id):
            return obj
