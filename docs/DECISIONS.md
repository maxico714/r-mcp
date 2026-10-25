# DECISIONS — r-mcp

## ADR-001: newline-delimited framing, threads instead of asyncio

**Date:** 2026-10-25
**Status:** accepted

**Context.** The scaffold assumed an asyncio proxy and left the framing unverified. The official MCP stdio specification (2025-06-18 and 2026-07-28) says messages are newline-delimited JSON-RPC with no embedded newlines and UTF-8 encoding.

**Decision.**
1. Implement newline-delimited framing exactly; no `Content-Length` support.
2. Use blocking reads on two threads (client pump and server pump) instead of asyncio. Client and server stdio are blocking pipes on Windows; a thread per direction is portable, keeps frame order trivial, and avoids event-loop integration problems when the proxy is launched as a child process by another program.
3. Bound every read with `readline(max_bytes + 1)` and reject oversized frames before parsing.
4. Forward original bytes; parse only for rules, capture and redaction.

**Consequences.** The proxy is simple and testable with subprocess pipes. Throughput is bounded by one thread per direction, which is ample for stdio MCP traffic. Memory is bounded by the frame cap, not by session length. A future HTTP/SSE transport would need a different I/O layer, as expected.

## ADR-002: competitor check — keep r-mcp but narrow the claim

**Date:** 2026-10-25
**Status:** accepted; publication remains G3-gated

**Context.** The research premise was "no mature open-source tool does capture + confirm-gate + replay + per-tool attribution". The mandatory pre-publish check found [`kerlenton/mcpsnoop`](https://github.com/kerlenton/mcpsnoop): Go, MIT, 364 stars, 36 forks, last push 2026-10-17, release line v0.28.0. Its README documents capture (stdio and Streamable HTTP, TUI, OpenTelemetry, CI action), replay, redaction, and stats. A shallow clone at commit `b737bec` was searched for confirm/approval/deny logic; the only hits were test fixtures (`clientmatrix`), not a proxy gate. Its usage documentation states that context cost is measured in **bytes, not tokens**.

**Decision.**
1. Reclassify the gap from **A (nothing found)** to **F (exists but incomplete in a nameable way)**.
2. Keep the confirmed differentiators: an explicit **confirm-gate** with deny-by-default timeout and no TTY, and **labelled token estimates** per tool.
3. Do not claim that no tool covers capture, replay and redaction; mcpsnoop does, and is more mature (binary distribution, TUI, HTTP, OTel, CI).
4. Do not publish. G2 (public push) and G3 (registry publish) remain owner-gated. If mcpsnoop adds a confirm-gate before G3, pivot or contribute upstream instead of publishing a duplicate.

**Consequences.** README and PRODUCT carry the honest comparison. The v0.1 code remains useful as a small, embeddable Python reference and test harness. The competitive window is narrow and is recorded as a risk, not hidden.
