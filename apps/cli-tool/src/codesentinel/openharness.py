from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .config import CliConfig
from .semgrep import SemgrepSummary
from .trufflehog import TruffleHogSummary


class OpenHarnessError(RuntimeError):
    pass


@dataclass(frozen=True)
class OpenHarnessResult:
    raw_output: str
    report_markdown: str


def log(message: str, **details: object) -> None:
    payload = json.dumps(details, default=str, sort_keys=True)
    print(f"[codesentinel] {message} {payload}", file=sys.stderr)


TOOL_DOCS = """
## Available Tools

### Browser Automation (browser_use_tool)
For interacting with live websites: clicking, typing, navigating, inspecting network requests, cookies, and local storage.
```
python apps/cli-tool/tools/browser_use_tool.py --task "Your instruction for the browser here"
```
Add `--no-headless` for visual debugging. Add `--use-vision` to enable screenshot-based reasoning.

### JS Bundle Analyzer (js_analyzer_tool)
For downloading and beautifying minified JavaScript bundles from a website. Use this to extract client-side source code for secret scanning or route discovery.
```
# Crawl a page and download all JS bundles
python apps/cli-tool/tools/js_analyzer_tool.py --url https://example.com

# Download a specific JS file directly
python apps/cli-tool/tools/js_analyzer_tool.py --js-url https://example.com/static/js/main.abc123.js
```
The beautified files will be saved to the `js_analysis/` directory. Read them with standard file tools to scan for exposed API keys, hidden routes, and hardcoded secrets.

### Web Search (exa_search_tool)
For searching the web when you need information beyond your training data: vulnerability databases, Docker commands, framework documentation, OSINT on the target, etc.
```
python apps/cli-tool/tools/exa_search_tool.py --query "Your search query here"
```
"""


def build_prompt(
    scan_root: Path | None,
    trufflehog_summary: TruffleHogSummary | None = None,
    semgrep_summary: SemgrepSummary | None = None,
    target_url: str | None = None,
) -> str:
    if target_url:
        return _build_url_prompt(target_url)

    if scan_root is None or trufflehog_summary is None or semgrep_summary is None:
        raise OpenHarnessError("Local scans require scan_root, a precomputed TruffleHog summary, and a precomputed Semgrep summary")

    return _build_local_prompt(scan_root, trufflehog_summary, semgrep_summary)


def _build_local_prompt(scan_root: Path, trufflehog_summary: TruffleHogSummary, semgrep_summary: SemgrepSummary) -> str:
    return f"""You are CodeSentinel, an active web defense agent.

You are scanning a LOCAL codebase at:
{scan_root}

## Primary Strategy
You have direct access to the source files. Rely on static analysis first:
- Read files directly to understand the project structure, dependencies, and configuration.
- Use the precomputed TruffleHog result below when writing the secret scan section. It may include current filesystem findings and Git history findings. Do not rerun TruffleHog.
- Use the precomputed Semgrep result below when writing the static analysis section. Do not rerun Semgrep.
- Look for insecure patterns and misconfigurations in the source.

Precomputed TruffleHog result:
{trufflehog_summary.to_prompt_text()}

Precomputed Semgrep result:
{semgrep_summary.to_prompt_text()}

## When to Use Dynamic Tools
Only use the browser or JS analyzer tools if static analysis is insufficient, for example if you find a local dev server URL and want to verify a runtime vulnerability, or if you need to test a specific endpoint behavior. The web search tool (Exa) is always available if you need to look up unfamiliar technologies, CVEs, or documentation.

Do not make code changes. Keep your answer short and focused.
{TOOL_DOCS}

Your final answer must be plain markdown text in the assistant message. Do not return an empty assistant message. Do not hide the answer in tool output or reasoning-only text.
Use tools first, then produce the final markdown report in the assistant message.

Return a concise Markdown report with these sections:
# CodeSentinel Scan Report
## Summary
## Repository Facts
## Secret Scan Result
## Static Analysis Result
## Findings
## Recommendations
## Limitations & Next Steps

Be clear that authenticated Semgrep AppSec Platform scans, deployed URL scans, and PR creation are intentionally out of scope for local scans in the current phase.
"""


def _build_url_prompt(target_url: str) -> str:
    return f"""You are CodeSentinel, an active web defense agent.

You are scanning a DEPLOYED WEBSITE at:
{target_url}

## Primary Strategy
You do NOT have access to source code. You must rely on dynamic analysis:
1. JS Bundle Analysis (recommended first step): Use the JS Analyzer tool to crawl the target URL and download all client-side JavaScript bundles. The tool will automatically beautify them. Then read the beautified files to look for exposed API keys, hidden routes, hardcoded backend URLs, and internal service endpoints.
2. Browser Automation: Use the browser tool to interact with the live site, inspect cookies/local storage/network requests, test access-control paths, and check security-relevant runtime behavior.
3. Web Search (Exa): Use it to research technologies, libraries, known CVEs, default credentials, or common misconfiguration patterns.

Do not make code changes. Keep your answer short and focused.
{TOOL_DOCS}

Your final answer must be plain markdown text in the assistant message. Do not return an empty assistant message. Do not hide the answer in tool output or reasoning-only text.
Use tools first, then produce the final markdown report in the assistant message.

Return a concise Markdown report with these sections:
# CodeSentinel Scan Report - {target_url}
## Summary
## Target Overview
## JS Bundle Analysis Findings
## Dynamic Interaction Findings
## Recommendations
## Limitations & Next Steps
"""


def _build_system_prompt(target_url: str | None = None) -> str:
    if target_url:
        return (
            "You are CodeSentinel scanning a deployed website. "
            "Use the JS analyzer tool, browser tool, and Exa search tool to perform dynamic analysis. "
            "Then return a detailed markdown report as visible assistant text."
        )

    return (
        "You are CodeSentinel scanning a local codebase. "
        "Use file reading tools for static analysis, explain the precomputed TruffleHog result, "
        "and use browser, JS analyzer, or Exa tools only when static analysis is insufficient. "
        "Then return a detailed markdown report as visible assistant text."
    )


def build_oh_command(prompt: str, config: CliConfig, target_url: str | None = None) -> list[str]:
    return [
        "oh",
        "-p",
        prompt,
        "--output-format",
        "json",
        "--api-format",
        "openai",
        "--base-url",
        config.proxy_url,
        "--model",
        "codesentinel-proxy",
        "--bare",
        "--system-prompt",
        _build_system_prompt(target_url),
        "--allowed-tools",
        config.openharness_allowed_tools,
        "--max-turns",
        str(config.openharness_max_turns),
    ]


def build_oh_environment(config: CliConfig, base_env: Mapping[str, str] | None = None) -> dict[str, str]:
    env = dict(base_env or os.environ)
    env["OPENAI_API_KEY"] = config.proxy_token
    env["OPENAI_BASE_URL"] = config.proxy_url
    env["OPENHARNESS_API_FORMAT"] = "openai"
    return env


def extract_report(stdout: str) -> str:
    text = stdout.strip()
    if not text:
        raise OpenHarnessError("OpenHarness returned no output")

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return text

    if isinstance(parsed, str):
        return parsed

    if isinstance(parsed, dict):
        for key in ("result", "text", "content", "message", "output"):
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        raise OpenHarnessError(
            "OpenHarness completed but returned an empty structured result. "
            "That usually means the agent did not actually produce a report."
        )

    return text


def run_openharness(
    scan_root: Path | None,
    config: CliConfig,
    trufflehog_summary: TruffleHogSummary | None = None,
    semgrep_summary: SemgrepSummary | None = None,
    target_url: str | None = None,
) -> OpenHarnessResult:
    if shutil.which("oh") is None:
        raise OpenHarnessError(
            "OpenHarness command `oh` was not found. Run `uv sync` in apps/cli-tool "
            "or install/configure openharness-ai so `oh` is on PATH."
        )

    prompt = build_prompt(
        scan_root,
        trufflehog_summary=trufflehog_summary,
        semgrep_summary=semgrep_summary,
        target_url=target_url,
    )
    cwd = scan_root or Path.cwd()
    log(
        "starting openharness",
        scan_root=str(scan_root) if scan_root else None,
        target_url=target_url,
        proxy_url=config.proxy_url,
    )
    completed = subprocess.run(
        build_oh_command(prompt, config, target_url),
        cwd=cwd,
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
            "openharness failed",
            returncode=completed.returncode,
            stdout=completed.stdout[-2000:],
            stderr=stderr[-2000:],
            command=" ".join(build_oh_command(prompt, config, target_url)),
        )
        raise OpenHarnessError(
            f"OpenHarness failed with exit code {completed.returncode}."
            + (f"\n\nstderr:\n{stderr}" if stderr else "")
        )

    log(
        "openharness completed",
        returncode=completed.returncode,
        stdout=completed.stdout[-2000:],
        stderr=completed.stderr[-2000:],
    )
    report = extract_report(completed.stdout)
    log("openharness parsed report", report_preview=report[:400])
    return OpenHarnessResult(raw_output=completed.stdout, report_markdown=report)
