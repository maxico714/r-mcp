"""Unit tests for the MCP stdio framing layer."""

from __future__ import annotations

import io
import json

import pytest

from r_mcp.framing import FramingError, encode_frame, parse_frame, read_frame


def test_parse_valid_frame() -> None:
    obj = parse_frame(b'{"jsonrpc":"2.0","id":1,"method":"ping"}\n')
    assert obj["method"] == "ping"


def test_parse_accepts_crlf() -> None:
    obj = parse_frame(b'{"jsonrpc":"2.0","id":1}\r\n')
    assert obj["id"] == 1


@pytest.mark.parametrize(
    "raw",
    [
        b"not json\n",
        b"[1,2,3]\n",
        b'{"id":1}\n',
        b'{"jsonrpc":"1.0","id":1}\n',
        b'{"jsonrpc":"2.0"',
    ],
)
def test_parse_rejects_invalid(raw: bytes) -> None:
    with pytest.raises(FramingError):
        parse_frame(raw)


def test_read_frame_returns_none_at_eof() -> None:
    assert read_frame(io.BytesIO(b"")) is None


def test_read_frame_complete() -> None:
    frame = read_frame(io.BytesIO(b'{"jsonrpc":"2.0","id":7}\n'))
    assert frame is not None
    assert frame.complete
    assert frame.obj["id"] == 7


def test_read_frame_partial_at_eof() -> None:
    frame = read_frame(io.BytesIO(b'{"jsonrpc":"2.0","id":7}'))
    assert frame is not None
    assert not frame.complete


def test_read_frame_enforces_memory_cap() -> None:
    oversized = b'{"jsonrpc":"2.0","id":1,"method":"' + b"x" * 200 + b'"}\n'
    with pytest.raises(FramingError):
        read_frame(io.BytesIO(oversized), max_bytes=64)


def test_encode_frame_is_compact_and_newline_terminated() -> None:
    raw = encode_frame({"jsonrpc": "2.0", "id": 1})
    assert raw.endswith(b"\n")
    assert b" " not in raw
    assert json.loads(raw) == {"jsonrpc": "2.0", "id": 1}
