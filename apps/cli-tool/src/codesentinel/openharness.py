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


def build_prompt(scan_root: Path, trufflehog_summary: TruffleHogSummary) -> str:
    return f"""You are CodeSentinel, an active web defense agent.

Inspect the local project at:
{scan_root}

Use tools freely to inspect only what you need for this target, but stay within the scanned project unless the task explicitly requires a dependency or referenced path outside it.
Do not make code changes.
Keep your answer short and focused.
Use the precomputed TruffleHog result below when writing the secret scan section. It may include current filesystem findings and Git history findings. Do not rerun TruffleHog.

Precomputed TruffleHog result:
{trufflehog_summary.to_prompt_text()}

Your final answer must be plain markdown text in the assistant message. Do not return an empty assistant message. Do not hide the answer in tool output or reasoning-only text.
Use tools first, then produce the final markdown report in the assistant message.

Return a concise Markdown report with these sections:
# CodeSentinel Phase 1 Report
## Summary
## Repository Facts
## Secret Scan Result
## Proxy/Agent Smoke Result
## Phase 1 Limitations
## Next Steps

Be clear that Semgrep, browser automation, deployed URL scans, and PR creation are intentionally out of scope for Phase 1.
"""


def build_oh_command(prompt: str, config: CliConfig) -> list[str]:
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
        "You are CodeSentinel. Use tools to inspect the target project, explain the precomputed TruffleHog result, then return a short markdown report as visible assistant text.",
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


def run_openharness(scan_root: Path, config: CliConfig, trufflehog_summary: TruffleHogSummary) -> OpenHarnessResult:
    if shutil.which("oh") is None:
        raise OpenHarnessError(
            "OpenHarness command `oh` was not found. Run `uv sync` in apps/cli-tool "
            "or install/configure openharness-ai so `oh` is on PATH."
        )

    prompt = build_prompt(scan_root, trufflehog_summary)
    log(
        "starting openharness",
        scan_root=str(scan_root),
        proxy_url=config.proxy_url,
    )
    completed = subprocess.run(
        build_oh_command(prompt, config),
        cwd=scan_root,
        env=build_oh_environment(config),
        text=True,
        capture_output=True,
        check=False,
        timeout=180,
    )

    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        log(
            "openharness failed",
            returncode=completed.returncode,
            stdout=completed.stdout[-2000:],
            stderr=stderr[-2000:],
            command=" ".join(build_oh_command(prompt, config)),
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
