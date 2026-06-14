from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import ConfigError, load_config
from .openharness import OpenHarnessError, run_openharness
from .report import write_report
from .semgrep import SemgrepError, run_semgrep
from .trufflehog import TruffleHogError, run_trufflehog


DESCRIPTION = """\
       ___
      [___]    ██████╗ ██████╗ ██████╗ ███████╗    ███████╗███████╗███╗   ██╗████████╗██╗███╗   ██╗███████╗██╗     
      (o,o)   ██╔════╝██╔═══██╗██╔══██╗██╔════╝    ██╔════╝██╔════╝████╗  ██║╚══██╔══╝██║████╗  ██║██╔════╝██║     
      /)__(\\   ██║     ██║   ██║██║  ██║█████╗      ███████╗█████╗  ██╔██╗ ██║   ██║   ██║██╔██╗ ██║█████╗  ██║     
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


def resolve_scan_root(target: str) -> Path:
    path = Path(target).expanduser().resolve()
    if not path.exists():
        raise CliError(f"Scan target does not exist: {path}")

    if not path.is_dir():
        raise CliError(f"Scan target must be a directory: {path}")

    return path


def scan(
    target: str | None = None,
    url: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> int:
    config = load_config(api_key=api_key, base_url=base_url, model=model)

    if url:
        print(f"codesentinel: scanning deployed URL {url}", file=sys.stderr)
        result = run_openharness(scan_root=None, config=config, target_url=url)
        report_dir = Path.cwd()
        report_path = report_dir / "codesentinel-report.md"
        report_path.write_text(result.report_markdown, encoding="utf-8")
        print(f"CodeSentinel report written to {report_path}")
    else:
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
    
    # Fancy High-Tech Boot Sequence
    console.clear()
    
    boot_messages = [
        "Initializing your security engineer...",
        "Loading LLM configuration options...",
        "HACKPRIX SEASON 3 LESSSGOOOO...",
        "Cracked Nerds present to you...",
    ]
    
    with Live(console=console, refresh_per_second=20) as live:
        for msg in boot_messages:
            for i in range(1, 4):
                loading_text = Text(f"{msg}{'.' * i}", style="bold green")
                live.update(Align.center(loading_text, vertical="middle"))
                time.sleep(0.45)
        
        # Flashy transition
        for _ in range(3):
            live.update(Align.center(Text(">>> SYSTEM READY <<<", style="bold red reverse"), vertical="middle"))
            time.sleep(0.1)
            live.update(Align.center(Text(">>> SYSTEM READY <<<", style="bold white"), vertical="middle"))
            time.sleep(0.1)

        live.update(Align.center(Text("Code Sentinel - your personal security engineer.", style="bold cyan"), vertical="middle"))
        time.sleep(0.8)
    console.clear()

    # Step 1: Welcome
    console.print(Text("""\
       ___
      [___]    ██████╗ ██████╗ ██████╗ ███████╗    ███████╗███████╗███╗   ██╗████████╗██╗███╗   ██╗███████╗██╗     
      (o,o)   ██╔════╝██╔═══██╗██╔══██╗██╔════╝    ██╔════╝██╔════╝████╗  ██║╚══██╔══╝██║████╗  ██║██╔════╝██║     
      /)__(\\   ██║     ██║   ██║██║  ██║█████╗      ███████╗█████╗  ██╔██╗ ██║   ██║   ██║██╔██╗ ██║█████╗  ██║     
      "    "  ██║     ██║   ██║██║  ██║██╔══╝      ╚════██║██╔══╝  ██║╚██╗██║   ██║   ██║██║╚██╗██║██╔══╝  ██║     
               ╚██████╗╚██████╔╝██████╔╝███████╗    ███████║███████╗██║ ╚████║   ██║   ██║██║ ╚████║███████╗███████╗
                ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝    ╚══════╝╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚═╝╚═╝  ╚═══╝╚══════╝╚══════╝
""", style="bold cyan"))
    
    welcome = Text()
    welcome.append(" — AI-Powered Security Scanner & Defense Agent\n\n", style="dim")
    welcome.append(
        "CodeSentinel is an autonomous, context-aware AI agent equipped with industry-standard\n"
        "SAST and DAST capabilities. It has its own browser, terminal, and Docker access to\n"
        "dynamically acquire packages, hunt down complex vulnerabilities, and even automatically\n"
        "fix them and open a PR on GitHub.\n\n"
        "It supports three provider configurations:\n"
    )
    welcome.append("  1. ", style="bold")
    welcome.append("Built-in Proxy", style="bold green")
    welcome.append(" — Use the CodeSentinel cloud proxy (default)\n")
    welcome.append("  2. ", style="bold")
    welcome.append("Bring Your Own Key", style="bold yellow")
    welcome.append(" — Use your own API key (OpenAI, Groq, Anthropic, etc.)\n")
    welcome.append("  3. ", style="bold")
    welcome.append("Local Ollama", style="bold magenta")
    welcome.append(" — Connect to a locally running Ollama instance\n")

    console.print(Panel(welcome, title="[bold white]Welcome[/bold white]", border_style="cyan", padding=(1, 2)))

    # Step 2: Choose provider
    console.print(Rule("[bold]Provider Configuration[/bold]"))
    provider = Prompt.ask(
        "Choose your provider",
        choices=["proxy", "byok", "ollama"],
        default="proxy",
    )

    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None

    if provider == "byok":
        console.print("\n[yellow]Bring Your Own Key[/yellow]")
        console.print("Supported providers: OpenAI, Groq, Anthropic, OpenRouter, any OpenAI-compatible API")
        api_key = Prompt.ask("API Key")
        base_url = Prompt.ask("Base URL", default="https://api.openai.com/v1")
        model = Prompt.ask("Model ID", default="gpt-4o")
    elif provider == "ollama":
        console.print("\n[magenta]Local Ollama[/magenta]")
        console.print("Make sure Ollama is running locally (ollama serve)")
        base_url = "http://localhost:11434/v1"
        api_key = "ollama"  # Ollama doesn't require a real key but the SDK needs one
        model = Prompt.ask("Ollama model name", default="llama3")
        console.print(f"Using Ollama at [cyan]{base_url}[/cyan]")
    else:
        console.print("\n[green]Using the built-in CodeSentinel proxy[/green]")

    # Step 3: Choose scan type
    console.print()
    console.print(Rule("[bold]Scan Configuration[/bold]"))
    console.print("\n[bold]Scan Types:[/bold]")
    console.print("  [cyan]repo[/cyan]  — Scan a local codebase (static analysis + AI review)")
    console.print("          The agent may also use browser tools if it deems necessary.")
    console.print("  [cyan]url[/cyan]   — Scan a deployed website (dynamic analysis of live endpoints)\n")

    scan_type = Prompt.ask("Scan type", choices=["repo", "url"], default="repo")

    target: str | None = None
    url: str | None = None

    if scan_type == "repo":
        target = Prompt.ask("Path to repository", default=".")
    else:
        url = Prompt.ask("Deployed URL (e.g. https://example.com)")

    # Step 4: Confirm and launch
    console.print()
    console.print(Rule("[bold]Launching Scan[/bold]"))
    summary_parts = []
    summary_parts.append(f"Provider: [bold]{provider}[/bold]")
    if model:
        summary_parts.append(f"Model: [bold]{model}[/bold]")
    if target:
        summary_parts.append(f"Target: [bold]{target}[/bold]")
    if url:
        summary_parts.append(f"URL: [bold]{url}[/bold]")
    console.print(Panel("\n".join(summary_parts), title="Scan Summary", border_style="green"))

    if not Confirm.ask("Proceed with scan?", default=True):
        console.print("[dim]Scan cancelled.[/dim]")
        return 0

    console.print()
    
    # Fancy launch spinner
    with console.status("[bold cyan]Establishing secure connection to AI provider...", spinner="dots12"):
        import time
        time.sleep(1.5)
        
    return scan(target=target, url=url, api_key=api_key, base_url=base_url, model=model)


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
        "target", nargs="?", default=None,
        help="Local directory to scan (uses static analysis first; the agent may use browser tools if needed)",
    )
    scan_parser.add_argument(
        "--url", dest="url", default=None,
        help="Deployed website URL to scan dynamically (e.g. https://example.com)",
    )

    # Provider flags
    provider_group = scan_parser.add_argument_group("provider configuration")
    provider_group.add_argument(
        "--api-key", dest="api_key", default=None,
        help="Your own API key (OpenAI, Groq, Anthropic, etc.)",
    )
    provider_group.add_argument(
        "--base-url", dest="base_url", default=None,
        help="Custom API base URL (e.g. https://api.openai.com/v1)",
    )
    provider_group.add_argument(
        "--model", dest="model", default=None,
        help="Model ID to use (e.g. gpt-4o, llama3, gemini-pro)",
    )
    provider_group.add_argument(
        "--local-ollama", dest="local_ollama", action="store_true", default=False,
        help="Use a locally running Ollama instance (auto-configures base URL)",
    )

    # interactive subcommand
    subparsers.add_parser(
        "interactive",
        help="Launch the interactive setup wizard",
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
            if args.url and args.target:
                print("codesentinel: cannot specify both a local directory and --url", file=sys.stderr)
                return 1
            if not args.url and not args.target:
                print("codesentinel: must specify either a local directory or --url", file=sys.stderr)
                return 1
            base_url = args.base_url
            api_key = args.api_key
            model = args.model
            if args.local_ollama:
                base_url = "http://localhost:11434/v1"
                api_key = "ollama"
                if model is None:
                    model = "llama3"
            return scan(
                target=args.target,
                url=args.url,
                api_key=api_key,
                base_url=base_url,
                model=model,
            )
    except (CliError, ConfigError, TruffleHogError, SemgrepError, OpenHarnessError) as exc:
        print(f"codesentinel: {exc}", file=sys.stderr)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
