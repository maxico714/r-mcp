# TECHNICAL — r-mcp

Status: v0.1.0 built and verified. Date: 2026-10-25. Stack: Python 3.10+ standard library plus PyYAML 6.0.2; no MCP SDK at runtime.

## Architecture

```
[MCP client] ⇄ stdin/stdout ⇄ [r-mcp proxy]
                                  │
                     client pump thread ──► frame parser (newline JSON-RPC)
                                  │              │
                                  │        rule engine (allow/deny/confirm)
                                  │              │
                                  │        capture writer (redacted JSONL)
                                  │              │
                                  └──────────► server stdin
                                                 │
                     server pump thread ◄──── server stdout
                                  │
                                  └──────────► client stdout + capture
```

Two blocking threads, one per direction. The client pump parses each client frame, evaluates rules, optionally asks for confirmation, writes the capture entry, then forwards the original bytes. The server pump parses each server frame, captures it, and forwards the original bytes to the client.

The live stream is never re-serialized. The only frame the proxy authors is a JSON-RPC error response for a denied call (`-32001`), which goes to the client and is never sent to the server.

## Modules

| Module | Responsibility |
|---|---|
| `framing.py` | Newline-delimited framing, UTF-8 decode, size cap, nesting cap, compact encoder |
| `redact.py` | Recursive redaction of keys, prefixes, hex/base64 blobs |
| `rules.py` | YAML load/validate, regex tool matching, first-match decision |
| `confirmer.py` | Terminal prompt, `--confirm-command`, timeout, safe deny |
| `capture.py` | Thread-safe JSONL writer and reader |
| `attrib.py` | chars/4 estimate rounded to 10; per-tool aggregation |
| `proxy.py` | The two-thread proxy and exit-code handling |
| `replay.py` | Select one captured request, spawn the server, read one response with timeout |
| `cli.py` | Argument parsing and command dispatch |

## Framing

Verified against MCP 2025-06-18 and 2026-07-28: newline-delimited JSON-RPC 2.0, UTF-8, no embedded newlines. Details and edge cases in [FRAMING.md](FRAMING.md).

- Default frame cap: 10 MiB (`--max-frame-bytes`).
- Default nesting cap: 100.
- Partial line at EOF, invalid UTF-8, non-object JSON, missing `jsonrpc: 2.0`, oversize and over-nested frames all produce `E_FRAMING` (exit 3).

## Rules

```yaml
rules:
  - name: gate-file-writes
    match:
      method: tools/call
      tool_name: write_file
    action: confirm
    prompt: "Allow write_file? (y/N) "
default: allow
```

- Top-level keys: `rules`, `default` only.
- Rule keys: `name`, `match`, `action`, `prompt` only.
- `match` keys: `method`, `tool_name` only. `tool_name` is a regex used with `fullmatch`.
- Actions: `allow`, `deny`, `confirm`. First match wins.
- Invalid YAML, unknown keys, duplicate names, invalid regex, invalid action or default → `E_CONFIG` (exit 2).

## Confirmation

Order of precedence: `--auto-allow` → `--confirm-command` → terminal.

- Terminal: opens `CONIN$` on Windows and `/dev/tty` elsewhere, so the protocol stream on stdin is untouched. No terminal, timeout, or a non-affirmative answer → **deny**.
- `--confirm-command`: receives the compact JSON request on stdin; exit 0 allows, anything else denies. A timeout denies. This is the automation path used by tests.
- Denied calls never reach the server. The client receives `{"code": -32001, "message": "blocked by r-mcp rule <name>"}` when the request has an id.

## Capture format

One JSON object per line. Fields: `ts`, `direction` (`c2s`/`s2c`), `method`, `id`, `tool_name` (when present), `action`, `rule`, `redacted`, `redactions`, `raw_len`, `est_tokens`, `payload`.

A `--no-redact` run starts with `{"event":"redaction_disabled","ts":...}`. No credentials are written outside this opt-in file.

## Redaction

- Key-based: exact normalized names such as `authorization`, `token`, `api_key`, `password`, `secret`, cookies and sessions.
- Value-based: `Bearer`/`Basic` values, 32+ hex characters, 40+ base64-like characters with digits and letters.
- Free-text scan: common API-key prefixes and embedded hex/base64 runs.
- Applies to the capture only; the live stream is unchanged.
- The engine is heuristic. It can miss unusual encodings; captures should be reviewed before sharing.

## Token estimates

`len(json.dumps(payload, separators=(",", ":"))) / 4`, rounded to the nearest 10, summed per tool over both directions. Every human and JSON output carries the note `estimate - provider-specific counting is out of scope`.

## Interfaces

```
r-mcp proxy --server CMD [--config FILE] [--capture FILE] [--no-redact]
            [--confirm-command CMD] [--confirm-timeout SEC] [--auto-allow]
            [--max-frame-bytes N] [--dry-run]
r-mcp replay CAPTURE (--id ID | --index N) --server CMD [--timeout SEC]
r-mcp report CAPTURE [--json FILE]
r-mcp rules validate --config FILE
r-mcp doctor [--config FILE]
```

Exit codes: `0` ok; `1` at least one denied call; `2` config or capture I/O error; `3` framing error or replay timeout; `4` server spawn failure or server stdin closed.

## Threat model (STRIDE-lite)

- **Untrusted traffic:** size cap, nesting cap, UTF-8 validation, clean errors, no tracebacks.
- **Secrets in traffic:** redaction on by default; `--no-redact` warns and audits; security tests include a fake secret that must not appear in the capture.
- **No auth persistence:** no credential file, no token store, no network calls.
- **Gate bypass:** rules are evaluated inside the proxy; `--confirm-command` and TTY are the only allow paths; no TTY and timeout deny.
- **Supply chain:** one runtime dependency (PyYAML, MIT, pinned); stdlib everywhere else.
- **Local write scope:** the only write is the user-specified capture file.

## Error model

`E_CONFIG` (exit 2), `E_FRAMING` (exit 3), `E_SERVER` (exit 4), `E_DENIED` (exit 1 at session end). Errors are printed to stderr; stdout carries only protocol frames.

## Performance

No benchmark was run in v0.1. Per-frame work is one JSON parse for rules/capture, one redaction walk, and one buffered write; the live path forwards bytes. Frame memory is capped at 10 MiB and aggregate memory is independent of session length. Measure before claiming a throughput number.

## Testing strategy (actual)

| Level | Coverage |
|---|---|
| L0 | ruff (E/F/I/UP/B/SIM/RUF), format check, strict mypy |
| L1 | 4 unit modules: framing, redaction, rules, attribution |
| L2 | Real subprocess mock server through the proxy; capture, confirm allow/deny, replay, report |
| L3 | Same fixture server as an end-to-end stdio process; no vendor client |
| L4 | Fresh copy + new venv + install + 68 tests + README quickstart |
| L5 | Malformed, non-object, invalid UTF-8, incomplete, oversize, deep nesting, spawn failure, timeout, redaction audit |

## Packaging

`pyproject.toml` (setuptools), wheel and sdist, MIT, Python 3.10+. PyPI name free (404 on 2026-10-25); publish is G3-gated. CI workflow is present but has never run (no remote).
