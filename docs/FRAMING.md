# FRAMING — MCP stdio transport

Verified 2026-10-25 against the official specification:

- 2025-06-18: <https://modelcontextprotocol.io/specification/2025-06-18/basic/transports>
- 2026-07-28: <https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio.md>

Both revisions state that stdio messages are **newline-delimited JSON-RPC 2.0**, encoded as UTF-8, and **MUST NOT contain embedded newlines**. stdout carries protocol messages only; stderr may carry logs.

This is not LSP-style `Content-Length` framing. r-mcp therefore does not implement `Content-Length` parsing.

## Implementation contract

| Case | Behaviour |
|---|---|
| Complete frame | Parse as UTF-8 JSON; require an object with `"jsonrpc": "2.0"`; forward the original bytes unchanged |
| `\r\n` line ending | Accepted; the delimiter is stripped for parsing, the original bytes are forwarded |
| Partial final line at EOF | Rejected with `E_FRAMING` (exit 3) rather than forwarded |
| Empty input | Clean EOF; server stdin closes and the proxy exits 0 unless a call was denied |
| Frame larger than the cap | Rejected before parsing (default 10 MiB, configurable with `--max-frame-bytes`) |
| Invalid UTF-8 | Rejected with a framing error; the proxy does not crash |
| Non-object JSON | Rejected with a framing error |
| JSON nesting deeper than 100 | Rejected with a framing error; protects the recursive redaction walk |
| Malformed frame from the server | Reported on stderr; proxy exits 3 |

Capture records the parsed object, the original byte length, and the estimated tokens. The live stream is never re-serialized in v0.1: allowed client frames are written to the server exactly as received, and server frames are written to the client exactly as received.

## Byte transparency

Tests assert that the client receives the server's result unchanged, including Unicode, and that a tool call's arguments reach the server unchanged while the capture file contains redacted copies. The proxy only rewrites a frame when it denies a call, in which case it emits a JSON-RPC error response to the client and does not forward the request.

## Known gaps

- A frame longer than the configured cap terminates the session; there is no truncation-and-resume mode.
- Notification methods are captured and forwarded but are not persisted to a separate stream.
- Protocol-version negotiation is not interpreted; r-mcp is framing-level only and works with both verified revisions.
