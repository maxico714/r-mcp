"""Conservative redaction for captured MCP traffic.

Redaction applies to the capture file only; the live stream is always
byte-transparent so tools keep working.
"""

from __future__ import annotations

import re
from typing import Any

REDACTED = "[REDACTED]"

_SENSITIVE_KEYS = {
    "authorization",
    "proxyauthorization",
    "xapikey",
    "apikey",
    "accesstoken",
    "refreshtoken",
    "idtoken",
    "token",
    "password",
    "passwd",
    "secret",
    "clientsecret",
    "privatekey",
    "cookie",
    "setcookie",
    "sessionid",
    "session",
    "credentials",
    "credential",
}

_HEX_RE = re.compile(r"^[0-9a-fA-F]{32,}$")
_BASE64_RE = re.compile(r"^[A-Za-z0-9+/=_-]{40,}$")
_AUTH_VALUE_RE = re.compile(r"^(bearer|basic|token)\s+\S+$", re.IGNORECASE)

_TOKEN_PREFIX_RE = re.compile(
    r"\b(?:"
    r"sk-[A-Za-z0-9_-]{8,}"
    r"|gh[pousr]_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|AKIA[0-9A-Z]{16}"
    r"|AIza[0-9A-Za-z_-]{35}"
    r")"
)
_EMBEDDED_HEX_RE = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{32,}(?![0-9a-fA-F])")
_EMBEDDED_B64_RE = re.compile(r"(?<![A-Za-z0-9+/=_-])[A-Za-z0-9+/=_-]{40,}(?![A-Za-z0-9+/=_-])")


def is_sensitive_key(key: str) -> bool:
    return re.sub(r"[-_]", "", key).lower() in _SENSITIVE_KEYS


def looks_secret(value: str) -> bool:
    if _AUTH_VALUE_RE.match(value):
        return True
    if _HEX_RE.match(value):
        return True
    if _BASE64_RE.match(value):
        return _base64_like(value)
    return False


def _base64_like(value: str) -> bool:
    has_digit = any(ch.isdigit() for ch in value)
    has_alpha = any(ch.isalpha() for ch in value)
    return has_digit and has_alpha


def _redact_string(value: str) -> tuple[str, int]:
    count = 0

    def replace(_match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return REDACTED

    def replace_base64(match: re.Match[str]) -> str:
        if _base64_like(match.group(0)):
            return replace(match)
        return match.group(0)

    result = _TOKEN_PREFIX_RE.sub(replace, value)
    result = _EMBEDDED_HEX_RE.sub(replace, result)
    result = _EMBEDDED_B64_RE.sub(replace_base64, result)
    if count == 0 and looks_secret(value):
        return REDACTED, 1
    return result, count


def redact(value: Any) -> tuple[Any, int]:
    """Return a redacted copy of ``value`` and the number of replacements."""
    count = 0

    def walk(node: Any) -> Any:
        nonlocal count
        if isinstance(node, dict):
            out: dict[str, Any] = {}
            for key, item in node.items():
                sensitive = isinstance(key, str) and is_sensitive_key(key)
                if sensitive and item not in (None, "", [], {}):
                    out[key] = REDACTED
                    count += 1
                else:
                    out[key] = walk(item)
            return out
        if isinstance(node, list):
            return [walk(item) for item in node]
        if isinstance(node, str):
            cleaned, replacements = _redact_string(node)
            count += replacements
            return cleaned
        return node

    return walk(value), count
