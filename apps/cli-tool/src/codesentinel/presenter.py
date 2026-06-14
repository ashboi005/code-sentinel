from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from .semgrep import SemgrepSummary
    from .trufflehog import TruffleHogSummary


console = Console(stderr=True)


def print_banner(title: str, subtitle: str) -> None:
    text = Text()
    text.append("      /\\_/\\\n", style="bold cyan")
    text.append("   .-(' ' )-.\n", style="bold cyan")
    text.append("  ((  agent  ))\n", style="bold green")
    text.append("   `-.. ..-'\n\n", style="bold cyan")
    text.append(title, style="bold white")
    text.append("\n")
    text.append(subtitle, style="cyan")
    console.print(Panel(text, border_style="bright_blue", padding=(1, 2)))


def print_stage(title: str, detail: str, icon: str = ">") -> None:
    console.print(Rule(f"[bold cyan]{icon} {title}[/bold cyan]"))
    console.print(f"[white]{detail}[/white]")


def print_artifact(label: str, path: Path) -> None:
    console.print(
        f"[bold green]+[/bold green] [white]{label}[/white] [dim]{path}[/dim]"
    )


def print_note(message: str) -> None:
    console.print(f"[bold magenta]*[/bold magenta] [white]{message}[/white]")


def print_trufflehog_summary(summary: TruffleHogSummary) -> None:
    table = Table(show_header=True, header_style="bold yellow")
    table.add_column("Secret Sweep")
    table.add_column("Count", justify="right")
    table.add_row(
        "Filesystem findings",
        str(summary.finding_counts_by_source.get("filesystem", 0)),
    )
    table.add_row(
        "Git history findings", str(summary.finding_counts_by_source.get("git", 0))
    )
    table.add_row("Shown to agent", str(summary.included_findings))
    table.add_row("Total findings", str(summary.total_findings), style="bold")
    console.print(table)


def print_semgrep_summary(summary: SemgrepSummary) -> None:
    severity_counts = Counter(
        (finding.severity or "unknown").upper() for finding in summary.findings
    )
    table = Table(show_header=True, header_style="bold red")
    table.add_column("Code Review")
    table.add_column("Count", justify="right")
    table.add_row("ERROR", str(severity_counts.get("ERROR", 0)))
    table.add_row("WARNING", str(severity_counts.get("WARNING", 0)))
    table.add_row(
        "INFO/OTHER",
        str(
            sum(
                count
                for severity, count in severity_counts.items()
                if severity not in {"ERROR", "WARNING"}
            )
        ),
    )
    table.add_row("Shown to agent", str(summary.included_findings))
    table.add_row("Total findings", str(summary.total_findings), style="bold")
    console.print(table)


def print_success(message: str) -> None:
    console.print(f"[bold green]OK[/bold green] [white]{message}[/white]")


def print_error(message: str) -> None:
    console.print(f"[bold red]X[/bold red] [white]{message}[/white]")


def render_markdown_report(title: str, markdown: str) -> None:
    console.print(Rule(f"[bold green]{title}[/bold green]"))
    console.print(
        Panel(Markdown(markdown.strip()), border_style="green", padding=(1, 2))
    )
