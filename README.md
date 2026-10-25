# r-mcp

**Offline MCP stdio proxy: redacted capture, confirm-gate, replay, and per-tool token estimates.**

> Status: **v0.1.0 built and verified (2026-10-25).** Source published on GitHub; registry publish (G3) remains owner-gated and has not happened. The PyPI name `r-mcp` returned 404 on 2026-10-25.

MCP servers talk newline-delimited JSON-RPC over stdio. Clients swallow that traffic, so a wrong argument, a silent failure, or a surprising cost is hard to see. `r-mcp` sits between a client and a server as a transparent proxy: it records both directions with secrets redacted, can pause and ask before a dangerous tool call runs, replays a captured request, and reports rough per-tool token estimates. Everything is local; there is no account, no telemetry, and no auth persistence.

## Install (from source)

```bash
git clone https://github.com/maxico714/r-mcp.git
cd r-mcp
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

Requires Python 3.10+ and `git` is not needed at runtime. Runtime dependency: PyYAML 6.0.2.

## Quickstart

```bash
python -m r_mcp proxy --server "python tests/fixtures/mock_server.py" --capture demo.jsonl < examples/initialize.jsonl
python -m r_mcp report demo.jsonl
python -m r_mcp doctor
```

Expected: three JSON-RPC responses on stdout, a capture summary on stderr, and a report line such as `echo	1	~30`. `doctor` prints the Python version, config state, and whether a terminal is available for confirmation prompts.

Use it in front of a real server by making the proxy the command your client launches:

```json
{
  "mcpServers": {
    "my-server": {
      "command": "r-mcp",
      "args": ["proxy", "--server", "node build/index.js", "--config", "rules.yaml", "--capture", "mcp.jsonl"]
    }
  }
}
```

## Commands

| Command | Purpose |
|---|---|
| `r-mcp proxy --server CMD [--config rules.yaml] [--capture out.jsonl]` | Run the transparent proxy |
| `r-mcp proxy ... --confirm-command CMD` | Non-interactive confirmation: exit 0 allows, anything else denies |
| `r-mcp proxy ... --confirm-timeout 30` | Deny a confirmation that takes too long (default 30s) |
| `r-mcp proxy ... --no-redact` | Disable capture redaction (warns on stderr and writes an audit entry) |
| `r-mcp proxy ... --max-frame-bytes N` | Per-frame memory cap (default 10 MiB) |
| `r-mcp proxy ... --dry-run` | Print the resolved rules and exit without starting the server |
| `r-mcp replay capture.jsonl --id ID --server CMD` | Re-send one captured request and print the response |
| `r-mcp replay capture.jsonl --index N --server CMD` | Same, selecting the Nth client request (1-based) |
| `r-mcp report capture.jsonl [--json out.json]` | Per-tool call count and estimated tokens |
| `r-mcp rules validate --config rules.yaml` | Validate a rules file |
| `r-mcp doctor [--config rules.yaml]` | Self-check |

Exit codes: `0` ok, `1` at least one call was denied, `2` config or capture-file error, `3` framing error or replay timeout, `4` server could not start or its stdin closed.

## Rules and the confirm-gate

```yaml
rules:
  - name: gate-file-writes
    match:
      method: tools/call
      tool_name: write_file
    action: confirm
    prompt: "Allow write_file? (y/N) "
  - name: deny-shell
    match:
      method: tools/call
      tool_name: "shell|exec|run"
    action: deny
default: allow
```

Rules are evaluated in order and the first match wins. `tool_name` is a Python regex matched with `fullmatch`, so `write_file` matches exactly and `shell|exec|run` matches any of the three. `method` is optional. Actions are `allow`, `deny` and `confirm`.

A `confirm` rule asks on the controlling terminal. If no terminal is available, or the confirmation times out, the call is **denied** (safe default). `--confirm-command` receives the JSON-RPC request on stdin and allows only on exit code 0. `--auto-allow` bypasses the gate and prints a warning. A denied call never reaches the server; the client receives JSON-RPC error `-32001` and the proxy exits `1` when the session ends.

## Capture format

One JSON object per line:

```json
{"ts":"2026-10-25T11:12:13.456+00:00","direction":"c2s","method":"tools/call","id":3,"redacted":true,"redactions":2,"raw_len":142,"est_tokens":40,"payload":{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"echo","arguments":{"api_key":"[REDACTED]"}}},"tool_name":"echo","action":"allow"}
```

`est_tokens` is a rough estimate: JSON characters divided by four, rounded to the nearest ten. It is always labelled as an estimate. Provider-specific token counting is out of scope.

## Redaction and safety

Redaction runs on the **capture only**. The live stream stays byte-transparent, so a tool that legitimately handles a token keeps working while the capture stays clean.

- Sensitive keys (`authorization`, `token`, `api_key`, `password`, `secret`, cookies, sessions, and related names) are replaced with `[REDACTED]`.
- Common API-key prefixes (`sk-…`, `ghp_…`, `github_pat_…`, `xox…-…`, `AKIA…`, `AIza…`) are redacted even inside free text.
- Long hex or base64 blobs are redacted.
- `--no-redact` is explicit, prints a warning, and writes a `{"event":"redaction_disabled"}` audit entry into the capture.

Redaction is conservative heuristics, not a guarantee. A secret that appears in an unusual format, or split across fields, can still be captured. Review captures before sharing them. The proxy never writes credentials anywhere by design.

## Honest comparison (checked 2026-10-25)

| Tool | Capture | Replay | Redaction | Confirm-gate | Token estimates |
|---|---|---|---|---|---|
| **r-mcp** | JSONL, stdio | yes | on by default | yes | chars/4, labelled |
| [mcpsnoop](https://github.com/kerlenton/mcpsnoop) 364★, MIT, Go, active | JSONL + TUI, stdio and HTTP | yes | yes | no | no (bytes in context) |
| MCP Inspector | own client only | no | no | no | no |
| mitmproxy | HTTP, wrong layer | yes | yes | no | no |

`mcpsnoop` is the mature alternative for capture, replay, redaction, HTTP and CI integration; use it if you need those. Its own documentation says it measures **bytes, not tokens**, and the source has no confirm-gate. The reason `r-mcp` exists is the gate plus labelled token estimates in a small Python package that can be embedded in a local test harness.

## Verification (2026-10-25)

| Check | Result |
|---|---|
| `pytest -q` | 68 passed on Python 3.12.10 and 3.14.5 |
| `ruff check .`, `ruff format --check .` | clean |
| `mypy src` (strict) | clean |
| Mutation check | disabling the entropy heuristic made the redaction security test fail; restored and green |
| L4 clean environment | fresh copy + new venv + `pip install`, 68 tests passed; README quickstart exited 0 and wrote a 7-line capture |
| Packaging | wheel and sdist build; `twine check` passes |
| Secrets scan | `detect-secrets`: 0 findings on the project files (two fake test fixtures are inline-allowlisted) |
| PyPI name | `r-mcp` and `r_mcp` both returned 404 |
| Read-only behaviour | the proxy only reads client stdin and writes the capture file; no repository or system state is modified |

Not verified: a real vendor client (Claude Desktop, Cursor, Codex) end to end, the interactive terminal prompt on a real TTY (the test environment has none, so the safe deny path is what is exercised), macOS/Linux runtime, sustained throughput and memory on very large sessions, and HTTP/SSE (out of scope for v0.1).

## Limitations

- stdio transport only. HTTP/SSE is post-1.0.
- Token numbers are estimates, not billing truth.
- Captures store the redacted payload. Replaying a request that contained a redacted value sends `[REDACTED]`; the command warns when this happens. Use `--no-redact` deliberately if you need byte-faithful replay.
- Redaction is heuristic; see above.
- No GUI, no auth persistence, no remote collection.

## Documents

- [docs/PRODUCT.md](docs/PRODUCT.md) — problem, scope, success criteria
- [docs/TECHNICAL.md](docs/TECHNICAL.md) — architecture, interfaces, threat model
- [docs/FRAMING.md](docs/FRAMING.md) — verified MCP stdio framing
- [docs/ROADMAP.md](docs/ROADMAP.md) — v0.1 → v1.0
- [docs/EVIDENCE.md](docs/EVIDENCE.md) — research and competitor evidence
- [docs/DECISIONS.md](docs/DECISIONS.md) — ADR-001 framing, ADR-002 competitor
- [BUILD_CHECKLIST.md](BUILD_CHECKLIST.md) — gates and evidence

## License

MIT. See [LICENSE](LICENSE).
