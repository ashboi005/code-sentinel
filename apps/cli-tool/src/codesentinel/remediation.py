from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, parse, request

from .config import CliConfig
from .openharness import (
    OpenHarnessError,
    build_oh_command,
    build_oh_environment,
    extract_report,
    log,
)
from .report import FIX_REPORT_NAME, REPORT_NAME


class RemediationError(RuntimeError):
    pass


def build_remediation_prompt(scan_root: Path, report_markdown: str, mode: str) -> str:
    if mode not in {"apply-local", "github-pr"}:
        raise RemediationError(f"Unsupported remediation mode: {mode}")

    mode_guidance = (
        "Apply fixes locally only. Do not create a pull request. Do not push any branch."
        if mode == "apply-local"
        else (
            "Apply fixes locally only. Do not commit, push, or create a pull request. "
            "The CLI will handle branch publishing and pull request creation after you finish."
        )
    )

    github_guidance = (
        """
## GitHub PR Mode
- Do not perform any GitHub operations yourself.
- Keep GitHub credentials out of the prompt and out of committed files.
- Never push to main, master, or any default branch.
- Do not create a pull request yourself. The CLI will do that after your remediation run completes.
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
- Perform one focused verification pass after your edits. Do not repeatedly re-read or re-verify the full set of changed files once tests have passed.
- Do not spend turns on planning, repeated TODO updates, or repeated summaries after the work is already complete.
- Prefer editing files and running tests over narrating intent.
- Summarize changed files, tests run, and any remaining risks.
- Report every fix with the finding title or type, file path, original vulnerable line number if known, new fixed line number if changed, and the exact change made.
- If the report does not include a line number for a fix, write `Line: unknown`; do not invent line numbers.
- Never push to main, master, or any default branch.

## Stop Conditions
- Stop immediately after both of these are true:
  1. The requested fixes have been applied.
  2. One verification pass has completed successfully.
- After that, return the final fix report directly.
- If you believe the code changes are done but you are low on turns, skip further inspection and return the final fix report.

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


def run_remediation(
    scan_root: Path, config: CliConfig, report_markdown: str, mode: str
) -> str:
    branch_name = create_remediation_branch(scan_root) if mode == "github-pr" else None
    prompt = build_remediation_prompt(scan_root, report_markdown, mode)
    system_prompt = (
        "You are CodeSentinel's code remediation harness. "
        "You may edit local code in the target folder, but must never push to a default branch. "
        "For GitHub PR mode, use GitHub MCP for GitHub actions only."
    )

    log("starting remediation", scan_root=str(scan_root), mode=mode, branch=branch_name)
    completed = subprocess.run(
        build_oh_command(
            prompt,
            config,
            system_prompt=system_prompt,
            max_turns=config.remediation_max_turns,
        ),
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

    log(
        "remediation completed",
        returncode=completed.returncode,
        stdout=completed.stdout[-2000:],
    )
    try:
        return extract_report(completed.stdout)
    except OpenHarnessError as exc:
        log("remediation missing final report", error=str(exc))
        if _has_remediation_changes(scan_root):
            return _run_wrap_up_remediation(scan_root, config, report_markdown, mode)
        raise RemediationError(str(exc)) from exc


def _has_remediation_changes(scan_root: Path) -> bool:
    return bool(_committable_files(scan_root))


def _wrap_up_prompt(scan_root: Path, report_markdown: str, mode: str) -> str:
    return f"""You are CodeSentinel's remediation harness.

You are in wrap-up mode for a remediation run at:
{scan_root}

The scan report remains the source of truth:

{report_markdown.strip()}

Important:
- Do NOT make any further code changes.
- Do NOT run another full verification sweep.
- Do NOT revisit the whole codebase.
- Assume the fixes already present in the working tree are the final changes.
- Your only job is to inspect the current changed files just enough to write the final fix report.
- If needed, run at most one lightweight check to support the report.

Return concise Markdown with exactly this structure:
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


def _run_wrap_up_remediation(
    scan_root: Path, config: CliConfig, report_markdown: str, mode: str
) -> str:
    system_prompt = (
        "You are CodeSentinel's remediation wrap-up harness. "
        "Do not edit code. Summarize the existing remediation changes and finish the required fix report."
    )
    prompt = _wrap_up_prompt(scan_root, report_markdown, mode)
    log("starting remediation wrap-up", scan_root=str(scan_root), mode=mode)
    completed = subprocess.run(
        build_oh_command(
            prompt,
            config,
            system_prompt=system_prompt,
            max_turns=min(config.remediation_max_turns, 25),
        ),
        cwd=scan_root,
        env=build_oh_environment(config),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=900,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise RemediationError(
            "OpenHarness remediation wrap-up failed with exit code "
            f"{completed.returncode}." + (f"\n\nstderr:\n{stderr}" if stderr else "")
        )
    try:
        return extract_report(completed.stdout)
    except OpenHarnessError as exc:
        raise RemediationError(
            "Remediation changes were applied, but the final fix report could not be recovered."
        ) from exc


def _run_git(scan_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=scan_root,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        message = (
            completed.stderr.strip() or completed.stdout.strip() or "git command failed"
        )
        raise RemediationError(f"git {' '.join(args)} failed: {message}")
    return completed.stdout.strip()


def _origin_repo_slug(scan_root: Path) -> str:
    remote_url = _run_git(scan_root, "remote", "get-url", "origin")
    remote_url = remote_url.strip()
    if remote_url.startswith("git@github.com:"):
        slug = remote_url.removeprefix("git@github.com:")
    elif remote_url.startswith("https://github.com/"):
        slug = remote_url.removeprefix("https://github.com/")
    else:
        raise RemediationError(
            f"Unsupported origin remote for GitHub PR mode: {remote_url}"
        )
    if slug.endswith(".git"):
        slug = slug[:-4]
    owner, _, repo = slug.partition("/")
    if not owner or not repo:
        raise RemediationError(
            f"Could not parse GitHub repository from origin remote: {remote_url}"
        )
    return f"{owner}/{repo}"


def _github_request(
    token: str, method: str, url: str, payload: dict | None = None
) -> dict:
    data = None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "codesentinel",
    }
    if payload is not None:
        import json

        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req) as response:
            import json

            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RemediationError(
            f"GitHub API {method} {url} failed: {exc.code} {body}"
        ) from exc
    except error.URLError as exc:
        raise RemediationError(
            f"GitHub API {method} {url} failed: {exc.reason}"
        ) from exc


def _default_branch(scan_root: Path, token: str) -> str:
    repo_slug = _origin_repo_slug(scan_root)
    repo = _github_request(token, "GET", f"https://api.github.com/repos/{repo_slug}")
    default_branch = str(repo.get("default_branch", "")).strip()
    if not default_branch:
        raise RemediationError("Could not determine default GitHub branch")
    return default_branch


def _current_branch(scan_root: Path) -> str:
    branch = _run_git(scan_root, "rev-parse", "--abbrev-ref", "HEAD")
    if branch in {"HEAD", "main", "master"}:
        raise RemediationError(
            f"Refusing to publish pull request from branch: {branch}"
        )
    return branch


def _committable_files(scan_root: Path) -> list[str]:
    status = _run_git(scan_root, "status", "--short")
    paths: list[str] = []
    for line in status.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        name = Path(path).name
        if name in {REPORT_NAME, FIX_REPORT_NAME}:
            continue
        if name == ".env" or name.startswith(".env."):
            continue
        paths.append(path)
    return paths


def _commit_message() -> str:
    return "fix: remediate CodeSentinel findings"


def _pr_body(scan_root: Path) -> str:
    fix_report = scan_root / FIX_REPORT_NAME
    if fix_report.exists():
        body = fix_report.read_text(encoding="utf-8").strip()
        if body:
            return body
    return "## Summary\n- Apply CodeSentinel remediation changes\n\n## Testing\n- See local fix report for validation details"


def _push_branch(scan_root: Path, token: str, branch: str) -> None:
    repo_slug = _origin_repo_slug(scan_root)
    encoded_token = parse.quote(token, safe="")
    remote_url = f"https://x-access-token:{encoded_token}@github.com/{repo_slug}.git"
    completed = subprocess.run(
        ["git", "push", "-u", remote_url, branch],
        cwd=scan_root,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    if completed.returncode != 0:
        message = (
            completed.stderr.strip() or completed.stdout.strip() or "git push failed"
        )
        raise RemediationError(f"Could not push remediation branch: {message}")


def finalize_github_pr(scan_root: Path, token: str) -> str:
    files = _committable_files(scan_root)
    if not files:
        raise RemediationError("No committable remediation changes were found")

    branch = _current_branch(scan_root)
    _run_git(scan_root, "add", "--", *files)

    staged = _run_git(scan_root, "diff", "--cached", "--name-only")
    if not staged.strip():
        raise RemediationError("No staged remediation changes were available to commit")

    commit = subprocess.run(
        ["git", "commit", "-m", _commit_message()],
        cwd=scan_root,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if commit.returncode != 0:
        message = commit.stderr.strip() or commit.stdout.strip() or "git commit failed"
        raise RemediationError(f"Could not create remediation commit: {message}")

    _push_branch(scan_root, token, branch)

    repo_slug = _origin_repo_slug(scan_root)
    base_branch = _default_branch(scan_root, token)
    pull = _github_request(
        token,
        "POST",
        f"https://api.github.com/repos/{repo_slug}/pulls",
        {
            "title": _commit_message(),
            "head": branch,
            "base": base_branch,
            "body": _pr_body(scan_root),
        },
    )
    pr_url = str(pull.get("html_url", "")).strip()
    if not pr_url:
        raise RemediationError("GitHub API did not return a pull request URL")
    log("github pr created", branch=branch, pr_url=pr_url)
    return pr_url
