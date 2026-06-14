from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .config import ConfigError, load_config
from .openharness import OpenHarnessError, run_openharness
from .presenter import (
    print_artifact,
    print_banner,
    print_error,
    print_note,
    render_markdown_report,
    print_stage,
    print_success,
)
from .remediation import RemediationError, finalize_github_pr, run_remediation
from .report import write_fix_report, write_report
from .semgrep import SemgrepError, run_semgrep
from .trufflehog import TruffleHogError, run_trufflehog


DESCRIPTION = """\
       ___
      [___]    ██████╗ ██████╗ ██████╗ ███████╗    ███████╗███████╗███╗   ██╗████████╗██╗███╗   ██╗███████╗██╗     
      (o,o)   ██╔════╝██╔═══██╗██╔══██╗██╔════╝    ██╔════╝██╔════╝████╗  ██║╚══██╔══╝██║████╗  ██║██╔════╝██║     
      /)__(\   ██║     ██║   ██║██║  ██║█████╗      ███████╗█████╗  ██╔██╗ ██║   ██║   ██║██╔██╗ ██║█████╗  ██║     
      "    "  ██║     ██║   ██║██║  ██║██╔══╝      ╚════██║██╔══╝  ██║╚██╗██║   ██║   ██║██║╚██╗██║██╔══╝  ██║     
               ╚██████╗╚██████╔╝██████╔╝███████╗    ███████║███████╗██║ ╚████║   ██║   ██║██║ ╚████║███████╗███████╗
                ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝    ╚══════╝╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚═╝╚═╝  ╚═══╝╚══════╝╚══════╝

CodeSentinel is an autonomous, context-aware AI agent that acts 
as your personal security engineer.

Equipped with industry-standard SAST and DAST capabilities, 
CodeSentinel has its own browser, terminal, and Docker access 
to dynamically acquire packages, hunt down complex vulnerabilities,
and even automatically fix them and open a PR on GitHub.
"""

EPILOG = """\
examples:
  # Scan a local codebase (static + AI analysis)
  codesentinel scan ./my-project

  # Scan a deployed website (dynamic analysis)
  codesentinel scan --url https://example.com

  # Use your own API key instead of the built-in proxy
  codesentinel scan ./my-project --api-key sk-... --base-url https://api.openai.com/v1 --model gpt-4o

  # Use a local Ollama model
  codesentinel scan ./my-project --local-ollama --model llama3

  # Launch the interactive setup wizard
  codesentinel interactive
"""


class CliError(RuntimeError):
    pass


def _render_scan_report_excerpt(markdown: str) -> None:
    lines = [line.strip() for line in markdown.splitlines() if line.strip()]
    summary_lines: list[str] = []
    in_summary = False
    for line in lines:
        if line.startswith("## Summary"):
            in_summary = True
            continue
        if in_summary and line.startswith("## "):
            break
        if in_summary:
            summary_lines.append(line.lstrip("- "))
        if len(summary_lines) == 3:
            break
    if summary_lines:
        print_note("Agent snapshot:")
        for entry in summary_lines:
            print_note(entry)


def _provider_label(provider: str) -> str:
    return {
        "proxy": "Guided Cloud",
        "byok": "Custom Provider",
        "ollama": "Local Model",
    }.get(provider, provider)


def resolve_scan_root(target: str) -> Path:
    path = Path(target).expanduser().resolve()
    if not path.exists():
        raise CliError(f"Scan target does not exist: {path}")

    if not path.is_dir():
        raise CliError(f"Scan target must be a directory: {path}")

    return path


def require_github_token_for_pr() -> None:
    if not os.environ.get("CODESENTINEL_GITHUB_TOKEN", "").strip():
        raise CliError(
            "Missing required environment variable for GitHub PR mode: CODESENTINEL_GITHUB_TOKEN"
        )


def scan(
    target: str | None = None,
    url: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    remediation_mode: str | None = None,
) -> int:
    config = load_config(api_key=api_key, base_url=base_url, model=model)
    if remediation_mode == "github-pr":
        require_github_token_for_pr()

    if url:
        print_banner("CodeSentinel", "Autonomous security agent online")
        print_stage("Target Lock", f"Inspecting deployed surface at {url}", icon="@")
        result = run_openharness(scan_root=None, config=config, target_url=url)
        report_dir = Path.cwd()
        report_path = report_dir / "codesentinel-report.md"
        report_path.write_text(result.report_markdown, encoding="utf-8")
        print_artifact("Scan report", report_path)
        _render_scan_report_excerpt(result.report_markdown)
        render_markdown_report("Scan Report", result.report_markdown)
        print_success("Scan completed")
    else:
        assert target is not None
        scan_root = resolve_scan_root(target)
        print_banner("CodeSentinel", "Autonomous security agent online")
        print_stage("Workspace Intake", f"Mapping repository at {scan_root}", icon="#")
        trufflehog_summary = run_trufflehog(scan_root)
        semgrep_summary = run_semgrep(scan_root)
        print_stage(
            "Reasoning Pass",
            "Correlating evidence across code, config, and history",
            icon=">",
        )
        result = run_openharness(
            scan_root=scan_root,
            config=config,
            trufflehog_summary=trufflehog_summary,
            semgrep_summary=semgrep_summary,
        )
        report_path = write_report(scan_root, result.report_markdown)
        print_artifact("Scan report", report_path)
        _render_scan_report_excerpt(result.report_markdown)
        render_markdown_report("Scan Report", result.report_markdown)
        if remediation_mode:
            print_stage(
                "Repair Pass",
                "Applying focused fixes from the verified findings",
                icon="*",
            )
            remediation_result = run_remediation(
                scan_root, config, result.report_markdown, remediation_mode
            )
            fix_report_path = write_fix_report(scan_root, remediation_result)
            print_artifact("Fix report", fix_report_path)
            if remediation_mode == "github-pr":
                print_stage(
                    "Handoff", "Packaging the remediation branch for review", icon="^"
                )
                pr_url = finalize_github_pr(
                    scan_root, os.environ["CODESENTINEL_GITHUB_TOKEN"]
                )
                print_success(f"Pull request created: {pr_url}")
            render_markdown_report("Fix Report", remediation_result)
        print_success("Agent workflow completed")

    return 0


def interactive_mode() -> int:
    """Launch the interactive TUI wizard."""
    try:
        import time
        from rich.console import Console
        from rich.panel import Panel
        from rich.prompt import Prompt, Confirm
        from rich.text import Text
        from rich.rule import Rule
        from rich.status import Status
        from rich.live import Live
        from rich.align import Align
    except ImportError:
        print(
            "codesentinel: 'rich' is required for interactive mode. "
            "Install it with: pip install rich",
            file=sys.stderr,
        )
        return 1

    console = Console()

    # Fancy boot sequence
    console.clear()

    boot_messages = [
        "Waking your security engineer...",
        "Preparing the agent workspace...",
        "Tuning analysis lenses...",
        "Sharpening claws...",
    ]

    with Live(console=console, refresh_per_second=20) as live:
        for msg in boot_messages:
            for i in range(1, 4):
                loading_text = Text(f"{msg}{'.' * i}", style="bold green")
                live.update(Align.center(loading_text, vertical="middle"))
                time.sleep(0.45)

        # Flashy transition
        for _ in range(3):
            live.update(
                Align.center(
                    Text(">>> SYSTEM READY <<<", style="bold red reverse"),
                    vertical="middle",
                )
            )
            time.sleep(0.1)
            live.update(
                Align.center(
                    Text(">>> SYSTEM READY <<<", style="bold white"), vertical="middle"
                )
            )
            time.sleep(0.1)

        live.update(
            Align.center(
                Text(
                    "CodeSentinel - your personal security engineer.",
                    style="bold cyan",
                ),
                vertical="middle",
            )
        )
        time.sleep(0.8)
    console.clear()

    # Step 1: Welcome
    console.print(
        Text(
            """\
       ___
      [___]    ██████╗ ██████╗ ██████╗ ███████╗    ███████╗███████╗███╗   ██╗████████╗██╗███╗   ██╗███████╗██╗     
      (o,o)   ██╔════╝██╔═══██╗██╔══██╗██╔════╝    ██╔════╝██╔════╝████╗  ██║╚══██╔══╝██║████╗  ██║██╔════╝██║     
      /)__(\   ██║     ██║   ██║██║  ██║█████╗      ███████╗█████╗  ██╔██╗ ██║   ██║   ██║██╔██╗ ██║█████╗  ██║     
      "    "  ██║     ██║   ██║██║  ██║██╔══╝      ╚════██║██╔══╝  ██║╚██╗██║   ██║   ██║██║╚██╗██║██╔══╝  ██║     
               ╚██████╗╚██████╔╝██████╔╝███████╗    ███████║███████╗██║ ╚████║   ██║   ██║██║ ╚████║███████╗███████╗
                ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝    ╚══════╝╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚═╝╚═╝  ╚═══╝╚══════╝╚══════╝
""",
            style="bold cyan",
        )
    )

    welcome = Text()
    welcome.append(" — AI-Powered Security Scanner & Defense Agent\n\n", style="dim")
    welcome.append(
        "CodeSentinel is an autonomous, context-aware AI agent equipped with industry-standard\n"
        "SAST and DAST capabilities. It has its own browser, terminal, and Docker access to\n"
        "dynamically acquire packages, hunt down complex vulnerabilities, and even automatically\n"
        "fix them and package the work for review.\n\n"
        "Choose how you want to power the agent:\n"
    )
    welcome.append("  1. ", style="bold")
    welcome.append("Guided Cloud", style="bold green")
    welcome.append(" — Fastest setup. Uses the managed CodeSentinel experience.\n")
    welcome.append("  2. ", style="bold")
    welcome.append("Custom Provider", style="bold yellow")
    welcome.append(" — Use your own API key and model endpoint.\n")
    welcome.append("  3. ", style="bold")
    welcome.append("Local Model", style="bold magenta")
    welcome.append(" — Connect to a model running on your own machine.\n")

    console.print(
        Panel(
            welcome,
            title="[bold white]Welcome[/bold white]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    # Step 2: Choose provider
    console.print(Rule("[bold]Agent Power[/bold]"))
    provider = Prompt.ask(
        "Choose how to power the agent",
        choices=["proxy", "byok", "ollama"],
        default="proxy",
    )

    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None

    if provider == "byok":
        console.print("\n[yellow]Custom Provider[/yellow]")
        console.print("Use any OpenAI-compatible endpoint and your preferred model.")
        api_key = Prompt.ask("API Key")
        base_url = Prompt.ask("Base URL", default="https://api.openai.com/v1")
        model = Prompt.ask("Model ID", default="gpt-4o")
    elif provider == "ollama":
        console.print("\n[magenta]Local Model[/magenta]")
        console.print("Make sure your local model server is running before launch.")
        base_url = "http://localhost:11434/v1"
        api_key = "ollama"  # Ollama doesn't require a real key but the SDK needs one
        model = Prompt.ask("Local model name", default="llama3")
        console.print(f"Using local endpoint [cyan]{base_url}[/cyan]")
    else:
        console.print("\n[green]Guided Cloud selected[/green]")

    # Step 3: Choose scan type
    console.print()
    console.print(Rule("[bold]Mission Profile[/bold]"))
    console.print("\n[bold]Scan Types:[/bold]")
    console.print(
        "  [cyan]repo[/cyan]  — Inspect a local codebase with deep static review"
    )
    console.print(
        "          The agent can correlate code, secrets, and architecture evidence."
    )
    console.print(
        "  [cyan]url[/cyan]   — Inspect a deployed website and its live attack surface\n"
    )

    scan_type = Prompt.ask("Scan type", choices=["repo", "url"], default="repo")

    target: str | None = None
    url: str | None = None
    remediation_mode: str | None = None

    if scan_type == "repo":
        is_docker = Path("/scan").is_dir()
        default_target = "/scan" if is_docker else "."
        if is_docker:
            console.print(
                "[dim]Docker workspace detected. Your mounted repository is available at [bold]/scan[/bold].[/dim]"
            )
        target = Prompt.ask("Repository path", default=default_target)

        console.print()
        console.print(Rule("[bold]After Analysis[/bold]"))
        do_fix = Confirm.ask(
            "Should the agent also repair the issues it confirms?",
            default=False,
        )
        do_pr = False
        if do_fix:
            do_pr = Confirm.ask(
                "Should the agent also package the repair into a GitHub pull request?",
                default=False,
            )
            if do_pr:
                github_token = Prompt.ask("GitHub access token", password=True)
                os.environ["CODESENTINEL_GITHUB_TOKEN"] = github_token
        remediation_mode = "github-pr" if do_pr else "apply-local" if do_fix else None
    else:
        url = Prompt.ask("Deployed URL", default="https://example.com")

    # Step 4: Confirm and launch
    console.print()
    console.print(Rule("[bold]Launch Review[/bold]"))
    summary_parts = []
    summary_parts.append(f"Agent power: [bold]{_provider_label(provider)}[/bold]")
    if model:
        summary_parts.append(f"Model: [bold]{model}[/bold]")
    if target:
        summary_parts.append(f"Repository: [bold]{target}[/bold]")
    if url:
        summary_parts.append(f"URL: [bold]{url}[/bold]")
    if remediation_mode:
        mode_label = (
            "Repair locally"
            if remediation_mode == "apply-local"
            else "Repair + pull request"
        )
        summary_parts.append(f"Follow-up: [bold]{mode_label}[/bold]")
    console.print(
        Panel("\n".join(summary_parts), title="Mission Summary", border_style="green")
    )

    if not Confirm.ask("Proceed with scan?", default=True):
        console.print("[dim]Launch cancelled.[/dim]")
        return 0

    console.print()

    # Fancy launch spinner
    with console.status(
        "[bold cyan]Handing the mission to your security agent...", spinner="dots12"
    ):
        import time

        time.sleep(1.5)

    return scan(
        target=target,
        url=url,
        api_key=api_key,
        base_url=base_url,
        model=model,
        remediation_mode=remediation_mode,
    )


def remediate(target: str, apply_local: bool = False, github_pr: bool = False) -> int:
    if apply_local == github_pr:
        raise CliError(
            "Specify exactly one remediation mode: --apply-local or --github-pr"
        )

    scan_root = resolve_scan_root(target)
    report_path = scan_root / "codesentinel-report.md"
    if not report_path.exists():
        raise CliError(f"CodeSentinel report not found: {report_path}")

    config = load_config()
    if github_pr:
        require_github_token_for_pr()

    mode = "github-pr" if github_pr else "apply-local"
    report_markdown = report_path.read_text(encoding="utf-8")
    print_banner("CodeSentinel", "Autonomous security agent online")
    print_stage(
        "Repair Pass", f"Continuing from existing report in {scan_root}", icon="*"
    )
    result = run_remediation(scan_root, config, report_markdown, mode)
    fix_report_path = write_fix_report(scan_root, result)
    print_artifact("Fix report", fix_report_path)
    if github_pr:
        print_stage("Handoff", "Packaging the remediation branch for review", icon="^")
        pr_url = finalize_github_pr(scan_root, os.environ["CODESENTINEL_GITHUB_TOKEN"])
        print_success(f"Pull request created: {pr_url}")
    render_markdown_report("Fix Report", result)
    print_success("Agent workflow completed")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codesentinel",
        description=DESCRIPTION,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command")

    # scan subcommand
    scan_parser = subparsers.add_parser(
        "scan",
        help="Run a security scan on a local codebase or deployed URL",
        description=(
            "Scan a local repository for vulnerabilities using static analysis "
            "(TruffleHog + Semgrep) combined with AI-powered code review. "
            "For deployed URLs, the agent performs dynamic analysis including "
            "JS bundle inspection, HTTP probing, and browser-based testing."
        ),
    )
    scan_parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="Local directory to scan (uses static analysis first; the agent may use browser tools if needed)",
    )
    scan_parser.add_argument(
        "--url",
        dest="url",
        default=None,
        help="Deployed website URL to scan dynamically (e.g. https://example.com)",
    )
    scan_parser.add_argument(
        "--fix",
        action="store_true",
        help="Apply local fixes after writing the scan report",
    )
    scan_parser.add_argument(
        "--fix-pr",
        action="store_true",
        help="Apply fixes after writing the scan report and create a GitHub pull request",
    )

    # Provider flags
    provider_group = scan_parser.add_argument_group("provider configuration")
    provider_group.add_argument(
        "--api-key",
        dest="api_key",
        default=None,
        help="Your own API key (OpenAI, Groq, Anthropic, etc.)",
    )
    provider_group.add_argument(
        "--base-url",
        dest="base_url",
        default=None,
        help="Custom API base URL (e.g. https://api.openai.com/v1)",
    )
    provider_group.add_argument(
        "--model",
        dest="model",
        default=None,
        help="Model ID to use (e.g. gpt-4o, llama3, gemini-pro)",
    )
    provider_group.add_argument(
        "--local-ollama",
        dest="local_ollama",
        action="store_true",
        default=False,
        help="Use a locally running Ollama instance (auto-configures base URL)",
    )

    # interactive subcommand
    subparsers.add_parser(
        "interactive",
        help="Launch the interactive setup wizard",
    )

    # remediate subcommand
    remediate_parser = subparsers.add_parser(
        "remediate", help="Apply fixes from a CodeSentinel report"
    )
    remediate_parser.add_argument(
        "target", help="Local directory containing codesentinel-report.md"
    )
    remediate_parser.add_argument(
        "--apply-local",
        action="store_true",
        help="Apply fixes on a local remediation branch",
    )
    remediate_parser.add_argument(
        "--github-pr",
        action="store_true",
        help="Apply fixes and create a GitHub pull request",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    try:
        if args.command == "interactive":
            return interactive_mode()

        if args.command == "scan":
            if args.fix and args.fix_pr:
                print(
                    "codesentinel: cannot specify both --fix and --fix-pr",
                    file=sys.stderr,
                )
                return 1
            if args.url and (args.fix or args.fix_pr):
                print(
                    "codesentinel: --fix and --fix-pr require a local scan target",
                    file=sys.stderr,
                )
                return 1
            if args.url and args.target:
                print(
                    "codesentinel: cannot specify both a local directory and --url",
                    file=sys.stderr,
                )
                return 1
            if not args.url and not args.target:
                print(
                    "codesentinel: must specify either a local directory or --url",
                    file=sys.stderr,
                )
                return 1
            base_url = args.base_url
            api_key = args.api_key
            model = args.model
            if args.local_ollama:
                base_url = "http://localhost:11434/v1"
                api_key = "ollama"
                if model is None:
                    model = "llama3"
            remediation_mode = (
                "github-pr" if args.fix_pr else "apply-local" if args.fix else None
            )
            return scan(
                target=args.target,
                url=args.url,
                api_key=api_key,
                base_url=base_url,
                model=model,
                remediation_mode=remediation_mode,
            )

        if args.command == "remediate":
            return remediate(
                target=args.target,
                apply_local=args.apply_local,
                github_pr=args.github_pr,
            )

    except (
        CliError,
        ConfigError,
        TruffleHogError,
        SemgrepError,
        OpenHarnessError,
        RemediationError,
    ) as exc:
        print_error(str(exc))
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
