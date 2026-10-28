# PRODUCT — r-mcp

Status: v0.1.0 built and locally verified (2026-10-25). Not published; G2/G3 owner-gated. See ADR-002 for the competitor reclassification.

## Problem

MCP servers expose tools to AI clients over stdio JSON-RPC. When a tool call fails (wrong schema, silent error, unexpected side-effect), there is no built-in way to see the traffic — clients swallow stdio, logs are sparse, and replaying a call manually is error-prone. Teams wiring MCP into production need: (1) full traffic capture for debugging, (2) a **confirm-gate** before dangerous calls execute, (3) replay/forge for repro, (4) per-tool token attribution for cost control.

Capture, replay and redaction are available from the active Go project `mcpsnoop` (see comparison below). The confirm-gate and labelled token estimates are the narrow gap this project targets.

## Target users (personas)

1. **MCP integration engineer (primary):** wiring MCP servers into an AI client in production. Job: debug a failing tool call without re-running the whole agent loop; gate destructive calls (file-write, shell) behind human confirm.
2. **Platform/cost engineer (secondary):** attributing token spend to specific MCP tools across a fleet. Job: per-tool usage report, labeled as estimates.
3. **MCP server author (tertiary):** testing their server's JSON-RPC contract. Job: capture + replay traffic as fixtures.

## Jobs-to-be-done

- "Show me every MCP request/response between client and server, redacted, offline."
- "Before the server executes `write_file`, ask me to confirm."
- "Replay this captured call to reproduce the bug."
- "Which MCP tool burned the most tokens this session?"

## Value proposition (one sentence)

Offline stdio MCP proxy with capture, confirm-gate, forge-replay, and per-tool token attribution — redacted by default, no auth persistence.

## Non-goals (explicit)

- Not an MCP server or client (transparent proxy only).
- Not HTTP/SSE transport (stdio-first; HTTP post-1.0).
- Not a token-precision meter (estimates labeled; provider-specific counting out of scope).
- Not a secrets manager (no auth persistence by design).
- Not a GUI (CLI + JSON output; TUI post-1.0 if demand).

## MVP scope (MoSCoW)

**Must (v0.1 walking skeleton):**
- Transparent stdio proxy: client ⇄ proxy ⇄ server; JSON-RPC framing preserved.
- Capture: full request/response streams to JSONL (redacted by default).
- Confirm-gate: rules like `tools/call name=write_file` → pause, prompt CLI, allow/deny.
- Forge/replay: `r-mcp replay capture.jsonl --id <n>` re-sends a captured request.
- Per-tool token attribution: estimate from payload sizes + model info if present; **labeled "estimate"** in output.
- Redaction engine: headers, `authorization`, `token`, `api_key`, long hex/base64 blobs → `[REDACTED]`.
- `doctor` self-check; `--dry-run` (log rules, no proxying).

**Should (v0.5):**
- Rule DSL (YAML): match tool name / method / arg pattern → action (allow | deny | confirm | redact-more).
- Capture diff mode (`r-mcp diff a.jsonl b.jsonl`).
- `--no-redact` with loud warning + audit log entry (not persisted token, just the fact it was disabled).
- MCP SDK integration (pin version; use official framing if available — verify at build time, don't assume).

**Could (v1.0):**
- HTTP/SSE transport; TUI live view; Prometheus metrics; signed captures for forensics.

**Won't (this run):** GUI; token-precision metering; auth persistence; non-stdio transports.

## Success criteria (measurable)

| Criterion | Measure | Status 2026-10-25 |
|---|---|---|
| L1 units | JSON-RPC framing, redaction engine, rule matcher unit tests green | PASS (71 total tests) |
| L2 integration | Mock MCP server over real stdio → proxy captures all frames; confirm-gate pauses; replay reproduces | PASS |
| L3 e2e | Local stdio server behind proxy → tool call gated, captured, replayed | PASS with the fixture server; no vendor client tested |
| L4 clean env | Fresh copy + new venv + install + README quickstart | PASS |
| L5 adversarial | Malformed frame, non-object, invalid UTF-8, deep nesting, oversize, timeout, spawn failure | PASS |
| Redaction default | Default capture has zero raw test secrets | PASS (security test) |
| No-auth-persist | No token or credential written except inside an explicit `--no-redact` capture | PASS by code review; no credential store exists |
| Honesty | Token numbers labelled "estimate" in human and JSON output | PASS |

## Honest comparison

- **mcpsnoop (Go, MIT, active, 364★):** transparent stdio/HTTP proxy, TUI, JSONL capture, replay, redaction, CI action, OpenTelemetry. No confirm-gate found in source; its docs measure context cost in **bytes, not tokens**. It is the better choice for capture/replay/HTTP and is more mature.
- **MCP SDK / client logs:** sparse, client-specific; no gate or per-tool report.
- **MCP Inspector:** connects as its own client, so it cannot see what your real client sends.
- **Generic HTTP proxies (mitmproxy etc.):** wrong layer — MCP stdio is not HTTP.
- **Manual `cat | jq`:** no framing, no confirm, no replay, no attribution.

## Naming & license

- Working name `r-mcp`; PyPI and the normalized `r_mcp` both returned 404 on 2026-10-25. Not published.
- `mcpsnoop` is a named competitor (ADR-002). If it adds a confirm-gate before G3, pivot or contribute upstream rather than publish a duplicate.
- License: MIT. Runtime dependency PyYAML 6.0.2 is MIT; no MCP SDK is used at runtime.

## Risk register (top)

| Risk | Sev | Mitigation |
|---|---|---|
| mcpsnoop owns capture/replay and may add a gate | High | ADR-002: verified 2026-10-25 that it has no gate and reports bytes, not tokens; re-check before G3 and pivot or contribute if that changes |
| MCP framing changes / SDK churn | Med | Thin framing layer; pin SDK; rules-as-data |
| Redaction false-negative leaks secret | High | Conservative patterns; `--no-redact` warns + audits; security tests |
| Token estimates misread as precision | Med | Label "estimate" everywhere; no false precision |
