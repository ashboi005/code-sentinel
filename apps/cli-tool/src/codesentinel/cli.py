from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import ConfigError, load_config
from .openharness import OpenHarnessError, run_openharness
from .report import write_report


class CliError(RuntimeError):
    pass


def resolve_scan_root(target: str) -> Path:
    if target.startswith(("http://", "https://")):
        raise CliError("Phase 1 supports local path targets only. Deployed URL scans are planned for a later phase.")

    path = Path(target).expanduser().resolve()
    if not path.exists():
        raise CliError(f"Scan target does not exist: {path}")

    if not path.is_dir():
        raise CliError(f"Phase 1 scan target must be a directory: {path}")

    return path


def scan(target: str) -> int:
    scan_root = resolve_scan_root(target)
    config = load_config()
    print(f"codesentinel: scanning {scan_root}", file=sys.stderr)
    result = run_openharness(scan_root, config)
    report_path = write_report(scan_root, result.report_markdown)
    print(f"CodeSentinel report written to {report_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="codesentinel", description="CodeSentinel Phase 1 CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Run a Phase 1 local scan")
    scan_parser.add_argument("target", help="Local directory to scan")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "scan":
            return scan(args.target)
    except (CliError, ConfigError, OpenHarnessError) as exc:
        print(f"codesentinel: {exc}", file=sys.stderr)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
