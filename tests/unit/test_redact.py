"""Unit tests for the redaction engine."""

from __future__ import annotations

from r_mcp.redact import REDACTED, is_sensitive_key, looks_secret, redact


def test_sensitive_key_names() -> None:
    assert is_sensitive_key("Authorization")
    assert is_sensitive_key("x-api-key")
    assert is_sensitive_key("access_token")
    assert not is_sensitive_key("max_tokens")
    assert not is_sensitive_key("token_count")


def test_nested_fields_are_redacted() -> None:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "params": {
            "name": "echo",
            "arguments": {
                "text": "hello",
                "api_key": "sk-live-123",  # pragma: allowlist secret (fake fixture)
                "headers": {"Authorization": "Bearer abc", "Accept": "text/plain"},
            },
        },
    }
    cleaned, count = redact(payload)
    assert cleaned["params"]["arguments"]["api_key"] == REDACTED
    assert cleaned["params"]["arguments"]["headers"]["Authorization"] == REDACTED
    assert cleaned["params"]["arguments"]["headers"]["Accept"] == "text/plain"
    assert cleaned["params"]["arguments"]["text"] == "hello"
    assert cleaned["params"]["name"] == "echo"
    assert cleaned["id"] == 1
    assert count == 2


def test_input_is_not_mutated() -> None:
    payload = {"token": "secret"}
    redact(payload)
    assert payload["token"] == "secret"


def test_entropy_heuristics() -> None:
    assert looks_secret("a" * 40)
    assert looks_secret("A1b2C3d4" * 8)
    assert looks_secret("Bearer abc.def.ghi")
    assert not looks_secret("hello world")
    assert not looks_secret("some/long/path/to/a/file.txt")


def test_long_token_strings_are_redacted_anywhere() -> None:
    cleaned, count = redact({"text": "A1b2C3d4" * 8})
    assert cleaned["text"] == REDACTED
    assert count == 1


def test_secrets_embedded_in_text_are_redacted() -> None:
    text = "request used key sk-live-abcdefgh1234 and blob " + "A1b2C3d4" * 8
    cleaned, count = redact({"text": text})
    assert "sk-live-abcdefgh1234" not in cleaned["text"]
    assert "A1b2C3d4" * 8 not in cleaned["text"]
    assert count == 2


def test_empty_sensitive_values_are_not_counted() -> None:
    cleaned, count = redact({"token": None, "password": "", "secret": []})
    assert cleaned == {"token": None, "password": "", "secret": []}
    assert count == 0


def test_token_counts_are_preserved() -> None:
    payload = {"max_tokens": 1024, "token_count": 12}
    cleaned, count = redact(payload)
    assert cleaned == payload
    assert count == 0
