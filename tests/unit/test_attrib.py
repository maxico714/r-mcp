"""Unit tests for token estimates and per-tool summaries."""

from __future__ import annotations

from r_mcp.attrib import NOTE, estimate_tokens, summarize


def test_estimate_is_rounded_to_nearest_ten() -> None:
    assert estimate_tokens({"text": "x" * 400}) == 100
    assert estimate_tokens({"text": "xxxx"}) == 0


def test_estimate_scales_with_payload() -> None:
    small = estimate_tokens({"text": "a" * 40})
    large = estimate_tokens({"text": "a" * 4000})
    assert large > small


def test_summarize_counts_calls_and_tokens() -> None:
    entries = [
        {"event": "redaction_disabled"},
        {"direction": "c2s", "method": "tools/call", "tool_name": "echo", "est_tokens": 30},
        {"direction": "c2s", "method": "tools/call", "tool_name": "echo", "est_tokens": 20},
        {"direction": "c2s", "method": "tools/call", "tool_name": "write_file", "est_tokens": 10},
        {"direction": "s2c", "tool_name": "echo", "est_tokens": 5},
    ]
    summary = summarize(entries)
    assert summary[0] == {"tool": "echo", "calls": 2, "est_tokens": 55}
    assert summary[1] == {"tool": "write_file", "calls": 1, "est_tokens": 10}


def test_note_is_labelled_estimate() -> None:
    assert "estimate" in NOTE
