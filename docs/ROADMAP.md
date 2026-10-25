# ROADMAP — r-mcp

Status: v0.1.0 built and locally verified (2026-10-25). SemVer; Keep a Changelog. Competitor: `mcpsnoop` (ADR-002).

## v0.1 — Walking skeleton

- [x] Gate 0: verify MCP stdio framing against the official spec; frozen in [FRAMING.md](FRAMING.md) (2025-06-18 and 2026-07-28).
- [x] Transparent stdio proxy (original bytes forwarded; JSON parsed only for rules/capture).
- [x] Capture (JSONL, redacted by default) with security tests.
- [x] Rule engine (allow/deny/confirm), terminal prompt, `--confirm-command`, deny-default timeout.
- [x] Replay (`--id` / `--index`); per-tool token estimates, labelled.
- [x] `doctor`; `rules validate`; `report`; README quickstart; CI workflow added.
- [ ] CI matrix observed green (blocked: no remote).

**Riskiest assumption:** MCP stdio framing. Spiked and verified against two spec revisions; a real subprocess server is proxied in tests.

## v0.5 — Core value

- [ ] Rule DSL hardening: argument-pattern matching, per-rule redaction overrides.
- [ ] Capture diff mode (`r-mcp diff a.jsonl b.jsonl`).
- [ ] Interactive terminal prompt proven on a real console (Windows and POSIX).
- [ ] Vendor-client end-to-end test (Claude Desktop, Cursor or Codex config).
- [ ] mcpsnoop re-check; if it ships a confirm-gate, pivot or contribute upstream (ADR-002).

## v1.0 — Production-ready

- [ ] HTTP/SSE transport (opt-in; mcpsnoop already covers this, so justify the scope first).
- [ ] L4 in CI on Ubuntu and Windows; Python 3.10–3.13.
- [ ] SBOM; signed release; THIRD_PARTY_NOTICES.
- [ ] PyPI name reconfirmed and publish only at G3.

## Post-1.0 (parked)

- TUI live view; Prometheus metrics; signed captures for forensics; GUI.

## Maintenance cadence

- MCP spec revision → framing layer review and a framing test.
- Redaction patterns → data-only patch with a regression fixture.
- Dependency updates → PyYAML and dev tools, automated.
