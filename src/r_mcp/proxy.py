"""Transparent stdio proxy with capture, rules and confirmation."""

from __future__ import annotations

import contextlib
import subprocess
import sys
import threading
from typing import IO, TextIO

from .capture import CaptureWriter
from .confirmer import Confirmer
from .framing import MAX_FRAME_BYTES, FramingError, encode_frame, read_frame
from .rules import RuleSet


class Proxy:
    def __init__(
        self,
        server_cmd: list[str],
        *,
        ruleset: RuleSet,
        capture: CaptureWriter,
        confirmer: Confirmer,
        client_in: IO[bytes] | None = None,
        client_out: IO[bytes] | None = None,
        err: TextIO = sys.stderr,
        max_frame_bytes: int = MAX_FRAME_BYTES,
    ) -> None:
        self.server_cmd = server_cmd
        self.ruleset = ruleset
        self.capture = capture
        self.confirmer = confirmer
        self.client_in: IO[bytes] = client_in if client_in is not None else sys.stdin.buffer
        self.client_out: IO[bytes] = client_out if client_out is not None else sys.stdout.buffer
        self.err = err
        self.max_frame_bytes = max_frame_bytes
        self._out_lock = threading.Lock()
        self._denied = False
        self._framing_error = False
        self._server_broken = False

    def run(self) -> int:
        try:
            proc = subprocess.Popen(
                self.server_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
            )
        except (OSError, ValueError) as err:
            print(f"error: cannot start server {self.server_cmd!r}: {err}", file=self.err)
            return 4
        assert proc.stdin is not None
        assert proc.stdout is not None
        reader = threading.Thread(target=self._pump_server, args=(proc.stdout,), daemon=True)
        reader.start()
        exit_code = 0
        try:
            exit_code = self._pump_client(proc.stdin)
        finally:
            with contextlib.suppress(OSError):
                proc.stdin.close()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
            reader.join(timeout=5)
        if self._framing_error:
            return 3
        if self._server_broken and exit_code == 0:
            return 4
        if self._denied and exit_code == 0:
            return 1
        return exit_code

    def _pump_client(self, server_in: IO[bytes]) -> int:
        while True:
            try:
                frame = read_frame(self.client_in, self.max_frame_bytes)
            except FramingError as err:
                print(f"error: {err}", file=self.err)
                self._framing_error = True
                return 3
            if frame is None:
                return 0
            if not frame.complete:
                print("error: incomplete frame at end of input", file=self.err)
                self._framing_error = True
                return 3

            decision = self.ruleset.decide(frame.obj)
            action = decision.action
            if action == "confirm":
                allowed = self.confirmer.ask(
                    decision.rule,
                    frame.obj,
                    prompt=self.ruleset.prompt_for(decision.rule),
                )
                action = "allow" if allowed else "deny"
            self.capture.write(
                "c2s",
                frame.obj,
                raw_len=len(frame.raw),
                action=action,
                rule=decision.rule,
            )
            if action == "deny":
                self._denied = True
                self._send_deny(frame.obj, decision.rule)
                continue
            try:
                server_in.write(frame.raw)
                server_in.flush()
            except (BrokenPipeError, OSError) as err:
                print(f"error: server stdin closed: {err}", file=self.err)
                self._server_broken = True
                return 4

    def _send_deny(self, obj: dict[str, object], rule: str | None) -> None:
        request_id = obj.get("id")
        if request_id is None:
            return
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32001,
                "message": f"blocked by r-mcp rule {rule or 'default'}",
            },
        }
        try:
            with self._out_lock:
                self.client_out.write(encode_frame(response))
                self.client_out.flush()
        except (BrokenPipeError, OSError):
            pass

    def _pump_server(self, server_out: IO[bytes]) -> None:
        while True:
            try:
                frame = read_frame(server_out, self.max_frame_bytes)
            except FramingError as err:
                print(f"error: server produced {err}", file=self.err)
                self._framing_error = True
                return
            if frame is None:
                return
            if not frame.complete:
                print("warning: server closed mid-frame; dropping partial frame", file=self.err)
                return
            self.capture.write("s2c", frame.obj, raw_len=len(frame.raw))
            try:
                with self._out_lock:
                    self.client_out.write(frame.raw)
                    self.client_out.flush()
            except (BrokenPipeError, OSError):
                return
