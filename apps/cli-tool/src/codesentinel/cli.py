from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .config import ConfigError, load_config
from .openharness import OpenHarnessError, run_openharness
from .remediation import RemediationError, run_remediation
from .report import write_fix_report, write_report
from .semgrep import SemgrepError, run_semgrep
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


def require_github_token_for_pr() -> None:
    if not os.environ.get("CODESENTINEL_GITHUB_TOKEN", "").strip():
        raise CliError("Missing required environment variable for GitHub PR mode: CODESENTINEL_GITHUB_TOKEN")


def scan(target: str | None = None, url: str | None = None, remediation_mode: str | None = None) -> int:
    config = load_config()
    if remediation_mode == "github-pr":
        require_github_token_for_pr()

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
        semgrep_summary = run_semgrep(scan_root)
        result = run_openharness(
            scan_root=scan_root,
            config=config,
            trufflehog_summary=trufflehog_summary,
            semgrep_summary=semgrep_summary,
        )
        report_path = write_report(scan_root, result.report_markdown)
        print(f"CodeSentinel report written to {report_path}")
        if remediation_mode:
            remediation_result = run_remediation(scan_root, config, result.report_markdown, remediation_mode)
            fix_report_path = write_fix_report(scan_root, remediation_result)
            print(f"CodeSentinel fix report written to {fix_report_path}")
            print(remediation_result)

    return 0


def remediate(target: str, apply_local: bool = False, github_pr: bool = False) -> int:
    if apply_local == github_pr:
        raise CliError("Specify exactly one remediation mode: --apply-local or --github-pr")

    scan_root = resolve_scan_root(target)
    report_path = scan_root / "codesentinel-report.md"
    if not report_path.exists():
        raise CliError(f"CodeSentinel report not found: {report_path}")

    config = load_config()
    if github_pr:
        require_github_token_for_pr()

    mode = "github-pr" if github_pr else "apply-local"
    report_markdown = report_path.read_text(encoding="utf-8")
    result = run_remediation(scan_root, config, report_markdown, mode)
    fix_report_path = write_fix_report(scan_root, result)
    print(f"CodeSentinel fix report written to {fix_report_path}")
    print(result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="codesentinel", description="CodeSentinel CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Run a security scan")
    scan_parser.add_argument("target", nargs="?", default=None, help="Local directory to scan")
    scan_parser.add_argument("--url", dest="url", default=None, help="Deployed website URL to scan (e.g. https://example.com)")
    scan_parser.add_argument("--fix", action="store_true", help="Apply local fixes after writing the scan report")
    scan_parser.add_argument("--fix-pr", action="store_true", help="Apply fixes after writing the scan report and create a GitHub pull request")

    remediate_parser = subparsers.add_parser("remediate", help="Apply fixes from a CodeSentinel report")
    remediate_parser.add_argument("target", help="Local directory containing codesentinel-report.md")
    remediate_parser.add_argument("--apply-local", action="store_true", help="Apply fixes on a local remediation branch")
    remediate_parser.add_argument("--github-pr", action="store_true", help="Apply fixes and create a GitHub pull request")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "scan":
            if args.fix and args.fix_pr:
                print("codesentinel: cannot specify both --fix and --fix-pr", file=sys.stderr)
                return 1
            if args.url and (args.fix or args.fix_pr):
                print("codesentinel: --fix and --fix-pr require a local scan target", file=sys.stderr)
                return 1
            if args.url and args.target:
                print("codesentinel: cannot specify both a local directory and --url", file=sys.stderr)
                return 1
            if not args.url and not args.target:
                print("codesentinel: must specify either a local directory or --url", file=sys.stderr)
                return 1
            remediation_mode = "github-pr" if args.fix_pr else "apply-local" if args.fix else None
            return scan(target=args.target, url=args.url, remediation_mode=remediation_mode)
        if args.command == "remediate":
            return remediate(target=args.target, apply_local=args.apply_local, github_pr=args.github_pr)
    except (CliError, ConfigError, TruffleHogError, SemgrepError, OpenHarnessError, RemediationError) as exc:
        print(f"codesentinel: {exc}", file=sys.stderr)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
