from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .config import CliConfig
from .openharness import OpenHarnessError, build_oh_command, build_oh_environment, extract_report, log


class RemediationError(RuntimeError):
    pass


def build_remediation_prompt(scan_root: Path, report_markdown: str, mode: str) -> str:
    if mode not in {"apply-local", "github-pr"}:
        raise RemediationError(f"Unsupported remediation mode: {mode}")

    mode_guidance = (
        "Apply fixes locally only. Do not create a pull request. Do not push any branch."
        if mode == "apply-local"
        else (
            "Apply fixes locally first, then use GitHub MCP for GitHub operations. "
            "Create a pull request from the remediation branch. Never merge the pull request."
        )
    )

    github_guidance = (
        """
## GitHub PR Mode
- Use GitHub MCP only for GitHub operations such as repository metadata, branch publishing, and pull request creation.
- Keep GitHub credentials out of the prompt and out of committed files.
- Never push to main, master, or any default branch.
- Create a pull request and stop. Never merge the pull request.
- Use native shell Docker commands if a container is needed to run the official GitHub MCP server.
"""
        if mode == "github-pr"
        else """
## Local Mode
- Apply changes directly in the target folder.
- Do not create a pull request.
- Never push to main, master, or any default branch.
- Use native shell Docker commands if containers are needed for local testing.
"""
    )

    return f"""You are CodeSentinel's remediation harness.

You are editing a LOCAL codebase at:
{scan_root}

The read-only scan harness already wrote this report to codesentinel-report.md. Consume it as the source of truth:

{report_markdown.strip()}

## Remediation Rules
- Fix only findings from the report.
- Keep changes small, focused, and maintainable.
- Prefer correctness and clarity over cleverness.
- Preserve unrelated user changes.
- Run the most relevant available tests after editing.
- Summarize changed files, tests run, and any remaining risks.
- Report every fix with the finding title or type, file path, original vulnerable line number if known, new fixed line number if changed, and the exact change made.
- If the report does not include a line number for a fix, write `Line: unknown`; do not invent line numbers.
- Never push to main, master, or any default branch.

## Mode
{mode_guidance}
{github_guidance}
When finished, return concise Markdown with:
# CodeSentinel Fix Report
## Summary
## Fixed Findings
For each fixed finding, include:
- Finding:
- File:
- Original line:
- Fixed line:
- Exact change:

## Changed Lines
List each changed file and line range. Use `Line: unknown` when a reliable line number is unavailable.

## Tests Run
## Remaining Risks
"""


def create_remediation_branch(scan_root: Path) -> str:
    branch_name = datetime.now(timezone.utc).strftime("codesentinel/fix-%Y%m%d-%H%M%S")
    result = subprocess.run(
        ["git", "switch", "-c", branch_name],
        cwd=scan_root,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "git switch failed"
        if "not a git repository" in message.lower():
            raise RemediationError("GitHub PR remediation requires a Git repository")
        raise RemediationError(f"Could not create remediation branch: {message}")
    return branch_name


def run_remediation(scan_root: Path, config: CliConfig, report_markdown: str, mode: str) -> str:
    branch_name = create_remediation_branch(scan_root) if mode == "github-pr" else None
    prompt = build_remediation_prompt(scan_root, report_markdown, mode)
    system_prompt = (
        "You are CodeSentinel's code remediation harness. "
        "You may edit local code in the target folder, but must never push to a default branch. "
        "For GitHub PR mode, use GitHub MCP for GitHub actions only."
    )

    log("starting remediation", scan_root=str(scan_root), mode=mode, branch=branch_name)
    completed = subprocess.run(
        build_oh_command(prompt, config, system_prompt=system_prompt),
        cwd=scan_root,
        env=build_oh_environment(config),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=2000,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        log(
            "remediation failed",
            returncode=completed.returncode,
            stdout=completed.stdout[-2000:],
            stderr=stderr[-2000:],
        )
        raise RemediationError(
            f"OpenHarness remediation failed with exit code {completed.returncode}."
            + (f"\n\nstderr:\n{stderr}" if stderr else "")
        )

    log("remediation completed", returncode=completed.returncode, stdout=completed.stdout[-2000:])
    try:
        return extract_report(completed.stdout)
    except OpenHarnessError as exc:
        raise RemediationError(str(exc)) from exc
