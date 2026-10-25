"""Command-line interface for r-mcp."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from . import __version__
from .attrib import NOTE, summarize
from .capture import CaptureWriter, read_capture
from .confirmer import Confirmer, split_command, tty_available
from .framing import MAX_FRAME_BYTES
from .proxy import Proxy
from .replay import replay
from .rules import RulesError, RuleSet


def _configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(errors="backslashreplace")


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as err:
        raise argparse.ArgumentTypeError(f"expected an integer, got {value!r}") from err
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def _positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as err:
        raise argparse.ArgumentTypeError(f"expected a number, got {value!r}") from err
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def _load_rules(path: Path | None) -> RuleSet:
    return RuleSet.load(path)


def _print_rules(ruleset: RuleSet, out: TextIO) -> None:
    print(f"rules: {len(ruleset.rules)} (default: {ruleset.default})", file=out)
    for rule in ruleset.rules:
        method = rule.method or "*"
        tool = rule.tool_name.pattern if rule.tool_name is not None else "*"
        print(f"  {rule.name:24} {rule.action:8} method={method} tool={tool}", file=out)


def _summary_lines(capture_path: Path) -> list[str]:
    try:
        entries = read_capture(capture_path)
    except ValueError:
        return []
    tools = summarize(entries)
    if not tools:
        return []
    lines = ["per-tool attribution (estimate):"]
    for item in tools:
        lines.append(f"  {item['tool']}: {item['calls']} calls, ~{item['est_tokens']} tokens")
    return lines


def _cmd_proxy(args: argparse.Namespace) -> int:
    try:
        server_cmd = split_command(args.server)
    except ValueError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    config_path: Path | None = args.config
    try:
        ruleset = _load_rules(config_path)
    except RulesError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2

    if args.dry_run:
        _print_rules(ruleset, sys.stdout)
        return 0

    try:
        capture = CaptureWriter(args.capture, redact_enabled=not args.no_redact)
    except OSError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2

    if args.auto_allow:
        print("warning: --auto-allow bypasses the confirm-gate", file=sys.stderr)
    confirmer = Confirmer(
        command=args.confirm_command,
        timeout=args.confirm_timeout,
        auto_allow=args.auto_allow,
    )
    proxy = Proxy(
        server_cmd,
        ruleset=ruleset,
        capture=capture,
        confirmer=confirmer,
        max_frame_bytes=args.max_frame_bytes,
    )
    try:
        code = proxy.run()
    finally:
        capture.close()

    if args.capture is not None:
        for line in _summary_lines(args.capture):
            print(f"r-mcp: {line}", file=sys.stderr)
    return code


def _cmd_replay(args: argparse.Namespace) -> int:
    try:
        server_cmd = split_command(args.server)
    except ValueError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    return replay(
        args.capture,
        server_cmd=server_cmd,
        request_id=args.request_id,
        index=args.index,
        timeout=args.timeout,
    )


def _cmd_report(args: argparse.Namespace) -> int:
    try:
        entries = read_capture(args.capture)
    except ValueError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    tools = summarize(entries)
    if not tools:
        print("no tool calls in capture", file=sys.stderr)
    for item in tools:
        print(f"{item['tool']}\t{item['calls']}\t~{item['est_tokens']}")
    print(f"note: {NOTE}", file=sys.stderr)
    if args.json is not None:
        try:
            args.json.write_text(
                json.dumps({"tools": tools, "note": NOTE}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as err:
            print(f"error: cannot write {args.json}: {err}", file=sys.stderr)
            return 2
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    print(f"r-mcp {__version__}")
    print(f"python: {sys.version.split()[0]}")
    print(f"platform: {sys.platform}")
    try:
        import yaml as _yaml

        print(f"pyyaml: {_yaml.__version__}")
    except ImportError:
        print("pyyaml: missing", file=sys.stderr)
        return 4
    print(f"terminal: {'available' if tty_available() else 'unavailable (confirm-gate denies)'}")
    try:
        ruleset = _load_rules(args.config)
    except RulesError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    print(f"config: {args.config if args.config is not None else 'none (default allow)'}")
    _print_rules(ruleset, sys.stdout)
    print("doctor: ready")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="r-mcp",
        description=(
            "Offline MCP stdio proxy: redacted capture, confirm-gate, replay "
            "and estimated per-tool token attribution"
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    proxy = sub.add_parser("proxy", help="Run the proxy in front of an MCP stdio server")
    proxy.add_argument("--server", required=True, help="Server command line to run")
    proxy.add_argument("--config", type=Path, default=None, help="YAML rules file")
    proxy.add_argument("--capture", type=Path, default=None, help="Write redacted JSONL capture")
    proxy.add_argument(
        "--no-redact", action="store_true", help="Disable redaction (warns + audits)"
    )
    proxy.add_argument(
        "--confirm-command",
        default=None,
        help="Command that receives the request on stdin and allows on exit 0",
    )
    proxy.add_argument(
        "--confirm-timeout", type=_positive_float, default=30.0, help="Seconds before denying"
    )
    proxy.add_argument("--auto-allow", action="store_true", help="Bypass the confirm-gate")
    proxy.add_argument(
        "--max-frame-bytes",
        type=_positive_int,
        default=MAX_FRAME_BYTES,
        help="Per-frame memory cap",
    )
    proxy.add_argument("--dry-run", action="store_true", help="Print rules and exit")
    proxy.set_defaults(func=_cmd_proxy)

    replay_cmd = sub.add_parser("replay", help="Replay one captured request")
    replay_cmd.add_argument("capture", type=Path, help="Capture JSONL file")
    replay_cmd.add_argument("--id", dest="request_id", default=None, help="JSON-RPC request id")
    replay_cmd.add_argument("--index", type=int, default=None, help="1-based request index")
    replay_cmd.add_argument("--server", required=True, help="Server command line to run")
    replay_cmd.add_argument(
        "--timeout", type=_positive_float, default=10.0, help="Response timeout"
    )
    replay_cmd.set_defaults(func=_cmd_replay)

    report = sub.add_parser("report", help="Summarize estimated tokens per tool")
    report.add_argument("capture", type=Path, help="Capture JSONL file")
    report.add_argument("--json", type=Path, default=None, help="Write JSON report")
    report.set_defaults(func=_cmd_report)

    rules_cmd = sub.add_parser("rules", help="Inspect rules")
    rules_sub = rules_cmd.add_subparsers(dest="rules_command", required=True)
    validate = rules_sub.add_parser("validate", help="Validate a YAML rules file")
    validate.add_argument("--config", type=Path, required=True, help="YAML rules file")
    validate.set_defaults(func=_cmd_rules_validate)

    doctor = sub.add_parser("doctor", help="Self-check environment, config and terminal")
    doctor.add_argument("--config", type=Path, default=None, help="YAML rules file")
    doctor.set_defaults(func=_cmd_doctor)

    return parser


def _cmd_rules_validate(args: argparse.Namespace) -> int:
    try:
        ruleset = _load_rules(args.config)
    except RulesError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    _print_rules(ruleset, sys.stdout)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    _configure_console()
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
