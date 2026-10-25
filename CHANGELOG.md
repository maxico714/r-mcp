# Changelog

All notable changes to this project are documented here. Format: Keep a Changelog; versioning: SemVer.

## [0.1.0] - 2026-10-25

### Added

- Transparent MCP stdio proxy using newline-delimited JSON-RPC framing.
- JSONL capture with redaction on by default; `--no-redact` warns and writes an audit entry.
- YAML rule engine with `allow`, `deny` and `confirm` actions, regex tool matching, first-match wins.
- Confirm-gate with a terminal prompt, `--confirm-command`, timeout deny, and deny when no terminal is available.
- Replay of one captured request by JSON-RPC id or 1-based request index.
- Per-tool call counts and labelled token estimates (`report`, capture summary).
- `rules validate`, `doctor`, `--dry-run`, and bounded frame size (`--max-frame-bytes`).
- 68 tests across unit, integration, security and adversarial tiers.
- CI workflow for Ubuntu and Windows, Python 3.10–3.13 (added; not yet executed because the repository has no remote).

### Security

- Redaction covers sensitive keys, common API-key prefixes, long hex and base64 blobs.
- Live traffic stays byte-transparent; redaction applies to captures only.
- Frame size and JSON nesting are bounded before parsing.
- Malformed input exits 3 without a traceback; server spawn failure exits 4.
