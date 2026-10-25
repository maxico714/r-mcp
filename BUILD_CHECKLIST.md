# BUILD CHECKLIST — r-mcp

Status: v0.1.0 built and locally verified on 2026-10-25. Not published. Each checked item has real command output recorded in this pass; publish items stay unchecked because G2/G3 are owner-gated.

## Gate 0 — Framing spike (riskiest assumption FIRST)

- [x] Read the official MCP spec for stdio framing (2025-06-18 and 2026-07-28): newline-delimited JSON-RPC 2.0, UTF-8, no embedded newlines.
- [x] Build a proxy: client ⇄ proxy ⇄ mock stdio server; byte-transparent passthrough plus capture round-trip verified.
- [x] Framing documented in `docs/FRAMING.md`; round-trip is byte-identical for allowed frames; edge cases recorded.
- [x] No ambiguity requiring an assumption: both revisions agree.

## Gate 1 — L0 static (every commit)

- [x] `ruff check .` clean.
- [x] `ruff format --check .` clean.
- [x] `mypy src/` strict clean.
- [x] `pytest --collect-only -q` collects 68 tests.

## Gate 2 — L1 units (framing, redaction, rules)

- [x] Frame parser: valid, CRLF, partial, malformed, non-object, invalid UTF-8, oversize, deep nesting.
- [x] Redaction: sensitive keys, nested headers, bearer values, hex/base64, free-text prefixes, empty values, no input mutation.
- [x] Rule matcher: exact, regex, method filter, first-match wins, default deny, prompt, invalid configs.
- [x] Mutation sanity: disabling the entropy heuristic fails `test_capture_redacts_secrets_but_traffic_is_intact`; restored and green.

## Gate 3 — L2 integration (mock MCP server)

- [x] Mock stdio server fixture → proxy captures requests and responses; JSONL is valid and redacted by default.
- [x] Confirm-gate: `write_file` call → deny blocks the server call (client receives `-32001`, exit 1); allow lets it through.
- [x] Replay: captured request re-sent; response parsed and printed; `--id` and `--index` selection.
- [x] Token attribution: per-tool summary printed on stderr and available from `report`, labelled estimate.

## Gate 4 — L3 e2e (local server process)

- [x] Local stdio server (fixture) behind the proxy: initialize, tools/list, gated call, captured and replayed.
- [x] Exit codes verified: 0 ok, 1 deny, 2 config/I/O, 3 framing/timeout, 4 spawn failure.
- [ ] Vendor MCP client (Claude Desktop / Cursor / Codex) end to end — not available in this environment; recorded as a v0.5 item.

## Gate 5 — L5 adversarial

- [x] Malformed JSON-RPC frame → clean error, exit 3, no traceback.
- [x] Non-object frame and invalid UTF-8 → exit 3.
- [x] Huge payload → rejected at the frame cap before parsing.
- [x] Deeply nested payload → rejected at the nesting cap.
- [x] Incomplete frame at EOF → exit 3.
- [x] Confirm timeout → deny (exit 1).
- [x] `--no-redact` → warning plus `redaction_disabled` audit entry.

## Gate 6 — Security & honesty audit (pre-M8)

- [x] Default capture contains no raw fake secret or blob; security test asserts this while the live response keeps the original bytes.
- [x] No auth persistence: no credential store, no network calls, only the user-specified capture file is written.
- [x] Token numbers labelled "estimate" in the capture summary, `report` text and `report --json`.
- [x] No TODO/FIXME in `src/`.
- [x] `detect-secrets` scan: 0 findings (two fake fixtures inline-allowlisted).

## Gate 7 — L4 clean env

- [x] Fresh copy + new venv + install → 68 tests pass.
- [x] README quickstart run verbatim → exit 0, 7-line capture, report exit 0.

## Gate 8 — Competitor & packaging (G3-gated)

- [x] Competitor check: `mcpsnoop` (Go, MIT, 364★, active) covers capture/replay/redaction/HTTP/CI; no confirm-gate found in source at `b737bec`; policy measures bytes, not tokens. Gap reclassified F; ADR-002 recorded.
- [x] `python -m build` → wheel and sdist; `twine check` passes.
- [x] PyPI name free: `r-mcp` and `r_mcp` returned 404 on 2026-10-25.
- [ ] Publish — **not done**; requires explicit owner approval at G3 and a re-check of mcpsnoop scope.

## Definition of done (v0.1)

Gates 0–7 green with evidence. Gate 8 is prepared; the competitor check is complete and the publish step remains owner-gated. The v0.1 definition is met locally; publication is not.
