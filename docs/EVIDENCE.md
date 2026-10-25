# EVIDENCE — r-mcp

Research from round-2 M2 / ADR-002 (2026-10-10), re-verified and extended on 2026-10-25.

## Gap classification: F (partial overlap, one nameable gap)

The original premise — "no mature open-source tool does capture + confirm-gate + replay + attribution" — is **no longer true**. The mandatory pre-publish check found an active competitor:

| Field | Verified value (2026-10-25) |
|---|---|
| Repository | <https://github.com/kerlenton/mcpsnoop> |
| Language / license | Go / MIT |
| Stars / forks | 364 / 36 |
| Last push | 2026-10-17 (commit `b737bec`) |
| Documented scope | Transparent stdio and Streamable HTTP proxy, TUI, JSONL capture, replay, redaction, CI action, OpenTelemetry, stats |
| Confirm-gate | **Not found.** A shallow clone at `b737bec` was searched for confirm/approve/deny/blocked logic in Go and Markdown; all hits were client-matrix test fixtures, not a proxy gate |
| Token attribution | **Not tokens.** Its usage documentation says context cost is measured in bytes, not tokens |

Related projects checked in the same pass: MCP Observatory (its own client, security/regression testing), mcprec (record and replay as a test fixture). Neither is an on-the-wire confirm-gate.

**Measurable differentiator:** r-mcp pauses a matching `tools/call` before it reaches the server and denies by default on timeout or when no terminal exists, and reports per-tool token estimates labelled as estimates. mcpsnoop has no gate and deliberately reports bytes instead of tokens.

**Honest caveat:** mcpsnoop is more mature in every other dimension (binary delivery, TUI, HTTP, OTel, CI, redaction docs, adoption). The r-mcp niche is narrow and may close.

## Demand hook

MCP production wiring pain is documented across MCP issues and discussions; token/cost control is a live concern. The hook sentence: "MCP servers talk stdio JSON-RPC with no built-in capture, gate or per-tool estimate — here is the offline redacted proxy for those."

Demand rating remains 4/5 from the original research; no new quantitative evidence was gathered in this pass.

## Host feasibility: VERIFIED

- Python 3.12.10 and 3.14.5 on this host; no Docker, no network, no credentials needed for tests.
- Local stdio fixture server; 68 tests pass.
- Runtime dependency PyYAML 6.0.2 (MIT), verified in a clean venv.
- The official MCP Python SDK is not installed; tests use the documented framing directly, not SDK types.

## Correction ledger

| Claim | Verified fact |
|---|---|
| "No MCP tooling exists" | FALSE — MCP SDKs and clients exist; the niche was always narrower |
| "No tool does capture + gate + replay + attribution" (2026-10-10) | FALSE as of 2026-10-25 — mcpsnoop does capture, replay and redaction; it lacks a gate and token estimates |
| "Token counting is exact" | FALSE — estimates only; provider-specific counting is out of scope |
| "Redaction guarantees no secret leaves" | FALSE — heuristics only; free-form or unusual encodings can be missed |

## Skeptic failure scenarios → mitigations

1. mcpsnoop adds a gate → ADR-002: pivot or contribute upstream; do not publish a duplicate.
2. MCP framing changes → thin framing layer; re-verify the spec each release; both 2025-06-18 and 2026-07-28 verified.
3. Redaction false negative → conservative patterns, security tests, `--no-redact` audit, documented limits.
4. Token estimates misread as precision → rounded to 10, labelled in every output, note in JSON reports.
5. Interactive gate blocked in non-TTY environments → safe deny plus `--confirm-command`.

## Pre-mortem (2027-04)

Most likely failure: mcpsnoop ships a confirm-gate and wins on distribution before r-mcp reaches G3. Mitigation: do not publish without a new differentiator; prefer contributing the gate concept upstream. Second: a redaction miss damages trust. Mitigation: documented heuristics, fake-secret tests, explicit warning to review captures.

## v0.1 implementation evidence

- 68 tests pass (unit, integration, security, adversarial) on Python 3.12.10 and 3.14.5.
- `ruff check`, `ruff format --check`, strict `mypy` clean.
- Mutation check: disabling the entropy heuristic fails the redaction security test; restoring makes it pass.
- L4: fresh copy, clean venv, `pip install`, 68 tests, README quickstart exit 0 with a 7-line capture.
- Wheel and sdist build; `twine check` passes; `detect-secrets` reports 0 findings; PyPI returns 404 for `r-mcp`.
- No push, release, account, spend or external communication occurred.
