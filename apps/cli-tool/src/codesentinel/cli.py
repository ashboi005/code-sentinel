from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import ConfigError, load_config
from .openharness import OpenHarnessError, run_openharness
from .report import write_report
from .trufflehog import TruffleHogError, run_trufflehog


class CliError(RuntimeError):
    pass


def resolve_scan_root(target: str) -> Path:
    path = Path(target).expanduser().resolve()
    if not path.exists():
        raise CliError(f"Scan target does not exist: {path}")

    if not path.is_dir():
        raise CliError(f"Scan target must be a directory: {path}")

    return path


def scan(target: str | None = None, url: str | None = None) -> int:
    config = load_config()

    if url:
        print(f"codesentinel: scanning deployed URL {url}", file=sys.stderr)
        result = run_openharness(scan_root=None, config=config, target_url=url)
        report_dir = Path.cwd()
        report_path = report_dir / "codesentinel-report.md"
        report_path.write_text(result.report_markdown, encoding="utf-8")
        print(f"CodeSentinel report written to {report_path}")
    else:
        # Local codebase scan mode
        assert target is not None
        scan_root = resolve_scan_root(target)
        print(f"codesentinel: scanning {scan_root}", file=sys.stderr)
        trufflehog_summary = run_trufflehog(scan_root)
        result = run_openharness(scan_root=scan_root, config=config, trufflehog_summary=trufflehog_summary)
        report_path = write_report(scan_root, result.report_markdown)
        print(f"CodeSentinel report written to {report_path}")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="codesentinel", description="CodeSentinel CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Run a security scan")
    scan_parser.add_argument("target", nargs="?", default=None, help="Local directory to scan")
    scan_parser.add_argument("--url", dest="url", default=None, help="Deployed website URL to scan (e.g. https://example.com)")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "scan":
            if args.url and args.target:
                print("codesentinel: cannot specify both a local directory and --url", file=sys.stderr)
                return 1
            if not args.url and not args.target:
                print("codesentinel: must specify either a local directory or --url", file=sys.stderr)
                return 1
            return scan(target=args.target, url=args.url)
    except (CliError, ConfigError, TruffleHogError, OpenHarnessError) as exc:
        print(f"codesentinel: {exc}", file=sys.stderr)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
