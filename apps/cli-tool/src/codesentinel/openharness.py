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


# Resolve the CLI tool root directory so tools/ paths work from any invocation point
_CLI_TOOL_ROOT = Path(__file__).resolve().parents[2]


class OpenHarnessError(RuntimeError):
    pass


@dataclass(frozen=True)
class OpenHarnessResult:
    raw_output: str
    report_markdown: str


def log(message: str, **details: object) -> None:
    payload = json.dumps(details, default=str, sort_keys=True)
    print(f"[codesentinel] {message} {payload}", file=sys.stderr)


TOOL_DOCS = f"""
## Available Tools

### Browser Automation (browser_use_tool)
For interacting with live websites: clicking, typing, navigating, inspecting network requests, cookies, and local storage.
```
cd {_CLI_TOOL_ROOT} && uv run python tools/browser_use_tool.py --task "Your instruction for the browser here"
```
Do NOT use the `--use-vision` flag. Rely on inspecting the DOM, network requests, cookies, local storage, and response headers instead.

### JS Bundle Analyzer (js_analyzer_tool)
For downloading and beautifying minified JavaScript bundles from a website. Use this to extract client-side source code for secret scanning or route discovery.
```
cd {_CLI_TOOL_ROOT} && uv run python tools/js_analyzer_tool.py --url https://example.com

cd {_CLI_TOOL_ROOT} && uv run python tools/js_analyzer_tool.py --js-url https://example.com/static/js/main.abc123.js
```
If you encounter SSL certificate errors, retry with `--no-verify-ssl`:
```
cd {_CLI_TOOL_ROOT} && uv run python tools/js_analyzer_tool.py --url https://example.com --no-verify-ssl
```
The beautified files will be saved to the `js_analysis/` directory. Read them with standard file tools to scan for exposed API keys, hidden routes, and hardcoded secrets.

### Cross-Platform Bash Tips
- macOS `grep` does NOT support `-P` (Perl regex). Use `grep -E` or `rg` (ripgrep) instead.
- For complex regex searches that must work everywhere, use: `python3 -c "import re; print('\n'.join(re.findall(r'PATTERN', open('FILE').read())))"`

### Web Search (exa_search_tool)
For searching the web when you need information beyond your training data: vulnerability databases, Docker commands, framework documentation, OSINT on the target, etc.
```
cd {_CLI_TOOL_ROOT} && uv run python tools/exa_search_tool.py --query "Your search query here"
```
"""

FALLBACK_API_SURFACES = """- `api.<domain>`
- `<domain>/api`
- `/health` and `/api/health`
- `/users` and `/api/users`
- `/data` and `/api/data`"""


def _dynamic_guardrails(target_url: str | None = None) -> str:
    url_boundary = ""
    if target_url:
        url_boundary = f"""- Treat `{target_url}` as a deployed-target boundary. Do not inspect unrelated local workspace or repository files.
- You may read only target-derived artifacts generated during the current scan, such as downloaded JS bundles in `js_analysis/`.
"""

    return f"""## Shared Dynamic Analysis Guardrails
{url_boundary}- Prefer verification over volume. Aim for one or two high-confidence findings instead of many weak probes.
- Do not repeat the same probe against the same endpoint unless new evidence changes the hypothesis.
- Prefer inspection over interaction when using the browser tool. Inspect the DOM, cookies, local storage, session storage, network requests, and response headers before clicking or submitting forms.
- Do NOT use screenshots or vision. The model does not support image input. Rely on DOM, network, and storage inspection instead.
- You may test whether protected-looking routes are accessible without authentication.
- You may reuse credentials, tokens, or API keys discovered during the same scan for focused verification on the most likely matching surface.
- Do not use default credentials, brute force, or credentials from outside the current scan.
- Multiple hops are allowed only when each hop is directly evidenced by the current surface.
- You may pivot across the same registrable domain and to other evidence-linked hosts explicitly referenced by the target's HTML, JS bundles, redirects, or observed network traffic.
- Internal-only targets such as `localhost`, private IP ranges, or clearly non-public infrastructure are report-only and must not be probed.
- Continue only while each step yields new evidence. Stop when the evidence trail goes cold or the next step would rely on speculative guessing.
- No destructive actions.
- **Environment awareness**: This scan runs on the OS shown in the system environment section. Adapt shell commands accordingly — for example, macOS `grep` does not support `-P`. Use `-E`, `rg`, or `python3 -c` for cross-platform regex searches. If any shell command fails, switch to using Python scripts. You can write your own custom Python helper scripts.
- **Docker**: You have access to a Docker MCP server. Use it to run tools, spawn containers, or download packages if you cannot run them natively.
- **Memory**: If you discover critical findings like leaked credentials, passwords, or hidden routes, append them to `memory.md` in the current working directory to persist across sessions.
"""


def _dynamic_workflow() -> str:
    return f"""## Shared Dynamic Analysis Workflow
1. **JS bundle analysis** — first, use the **JS Analyzer tool** to download and beautify bundles. Do not manually curl or minify. If SSL fails, retry with `--no-verify-ssl`.
   - Search beautified files with targeted grep/regex (do NOT read full files >500KB).
   - Focus on these patterns:
     - `https?://` — API hosts, backend URLs, webhooks
     - `/api`, `/v[0-9]/`, `/graphql`, `/rest` — route patterns
     - `password`, `secret`, `token`, `key`, `credential`, `jwt`, `bearer` — hardcoded secrets
     - `admin`, `dashboard`, `internal`, `private`, `staging` — hidden surfaces
     - `localhost`, `192\\.168\\.`, `10\\.`, `172\\.` — infrastructure leaks
     - `firebase`, `aws`, `stripe`, `sendgrid`, `twilio`, `s3` — third-party service keys
     - `.com`, `.io`, `.dev`, `.app` — linked external hosts
     - `Authorization`, `x-api-key`, `x-auth-token`, `apiKey` — auth header patterns
     - `baseURL`, `base_url`, `baseUrl`, `apiUrl`, `endpoint` — API base URL config
     - `ws://`, `wss://` — WebSocket endpoints
     - `webhook`, `github`, `slack`, `discord`, `callback` — webhook/callback URLs
     - `mongodb`, `postgres`, `mysql`, `redis://` — database connection strings
     - `-----BEGIN`, `ssh-rsa`, `ssh-ed25519` — embedded keys/certificates
     - `NEXT_PUBLIC_`, `REACT_APP_`, `VITE_`, `CODESENTINEL_` — exposed build-time env vars
     - `login`, `signin`, `authenticate`, `oauth`, `register`, `signup` — auth endpoint hints
     - `cookie`, `session`, `localStorage`, `sessionStorage` — client storage usage
   - On macOS use `grep -E` or `rg` (not `grep -P`).

2. **Direct HTTP probing** — immediately after JS analysis. This is your primary runtime verification method (cheaper and faster than the browser).
   - Use `curl` if available, or write a Python script with `urllib.request` / `requests` for cross-platform compatibility.
   - Probe all discovered routes from JS analysis **and** generic fallback routes in parallel. Batch multiple endpoints in one command or script:
     - `api.<domain>`, `<domain>/api`
     - `/api/health`, `/api/users`, `/api/data`, `/api/summary`
     - Any paths, routes, or endpoints found in the JS bundle
   - Try `GET` first, then `OPTIONS` to check allowed methods.

3. **Auth verification via HTTP** — reuse same-scan credentials. If JS analysis exposed usernames/passwords/tokens, try them against discovered login or auth endpoints.

4. **Browser tool — last resort only**. Use only when HTTP probing cannot answer the question:
   - Inspecting cookies, localStorage, or sessionStorage set by JavaScript
   - Observing SPA XHR/fetch requests not visible via direct HTTP
   - Checking WebSocket handshake behavior
   - Each call must be a single, focused goal. Bad: multi-step. Good: "Navigate to X and report all network requests."

5. **Probe lightly**. Prefer `GET`, `HEAD`, `OPTIONS`. `POST` only for auth flows. Never `PUT`, `PATCH`, or `DELETE`.

6. **Generic fallback**. If no concrete routes are found, try:
{FALLBACK_API_SURFACES}
   - Explicitly probe `/health`, `/users`, `/data` under `api.<domain>` and `<domain>/api`.

7. **Handle auth artifacts by type**:
   - Username/password → try login endpoint via POST.
   - Bearer/session token → try authenticated API request.
   - API key → try the most likely API host/path.
   - Opaque secret with no clear usage → report it.

8. **Verify impact**. Test if endpoints are accessible without auth. When safe, verify with same-scan credentials. One strong chain beats broad spraying.

9. **Exa** — only when target evidence creates a concrete research need.
"""


def _dynamic_reporting() -> str:
    return """## Shared Dynamic Analysis Reporting
- Distinguish clearly between `Observed Facts`, `Verified Access`, and `Inferred Risks`.
- Include negative verification results when they help bound the claim, such as an endpoint that existed but enforced auth or a credential that did not verify.
"""


def _local_report_template() -> str:
    return """Return a concise Markdown report with these sections:
# CodeSentinel Scan Report
## Summary
## Repository Facts
## Secret Scan Result
## Static Analysis Result
## Findings
## Dynamic Analysis
Only include this section if you actually used the browser or JS analyzer tools.
Under this section, use the subsections:
### Observed Facts
### Verified Access
### Inferred Risks
## Recommendations
## Limitations & Next Steps"""


def _url_report_template(target_url: str) -> str:
    return f"""Return a concise Markdown report with these sections:
# CodeSentinel Scan Report - {target_url}
## Summary
## Target Overview
## Observed Facts
## Verified Access
## Inferred Risks
## Recommendations
## Limitations & Next Steps"""


def build_prompt(
    scan_root: Path | None,
    trufflehog_summary: TruffleHogSummary | None = None,
    semgrep_summary: SemgrepSummary | None = None,
    target_url: str | None = None,
) -> str:
    if target_url:
        return _build_url_prompt(target_url)

    if scan_root is None or trufflehog_summary is None or semgrep_summary is None:
        raise OpenHarnessError(
            "Local scans require scan_root, a precomputed TruffleHog summary, "
            "and a precomputed Semgrep summary"
        )

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
Only use the browser or JS analyzer tools if static analysis is insufficient, for example if you find a live application URL and want to verify a runtime vulnerability, or if you need to test a specific endpoint behavior. When you do use dynamic tools, follow the shared workflow and guardrails below. The web search tool (Exa) is always available if target evidence creates a concrete research need.

{_dynamic_guardrails()}

{_dynamic_workflow()}

{_dynamic_reporting()}

Do not make code changes. Keep your answer short and focused.
{TOOL_DOCS}

Your final answer must be plain markdown text in the assistant message. Do not return an empty assistant message. Do not hide the answer in tool output or reasoning-only text.
Use tools first, then produce the final markdown report in the assistant message.

{_local_report_template()}

Be clear that authenticated Semgrep AppSec Platform scans, deployed URL scans, and PR creation are intentionally out of scope for local scans in the current phase.
"""


def _build_url_prompt(target_url: str) -> str:
    return f"""You are CodeSentinel, an active web defense agent.

You are scanning a DEPLOYED WEBSITE at:
{target_url}

## Primary Strategy
You do NOT have access to source code. Rely on deployed-target evidence only.

{_dynamic_guardrails(target_url)}

{_dynamic_workflow()}

{_dynamic_reporting()}

## URL-Mode Priorities
- Start with JS bundle analysis to discover routes, secrets, and API surfaces.
- Follow with direct HTTP probing of discovered and generic fallback routes — this is the primary runtime verification method.
- Use the browser only when HTTP probing is insufficient (cookies, localStorage, SPA network behavior).
- Treat repo-only static analysis techniques such as Semgrep, TruffleHog, and source-code-only reasoning as not applicable to deployed URL scans.

Do not make code changes. Keep your answer short and focused.
{TOOL_DOCS}

Your final answer must be plain markdown text in the assistant message. Do not return an empty assistant message. Do not hide the answer in tool output or reasoning-only text.
Use tools first, then produce the final markdown report in the assistant message.

{_url_report_template(target_url)}
"""


def _build_system_prompt(target_url: str | None = None) -> str:
    if target_url:
        return (
            "You are CodeSentinel scanning a deployed website. "
            "Treat the URL as a strict deployed-target boundary: do not inspect unrelated local workspace files, "
            "but you may inspect target-derived artifacts generated during the scan such as downloaded JS bundles. "
            "Use autonomous, evidence-backed dynamic verification with strong guardrails. "
            "Start with the JS analyzer, use direct HTTP requests for runtime verification, "
            "use the browser only when HTTP cannot answer the question, "
            "and use Exa only when target evidence creates a concrete research need. "
            "Prefer one or two high-confidence verification chains over broad probing. "
            "No destructive actions. "
            "Return a detailed markdown report as visible assistant text that separates observed facts, verified access, and inferred risks."
        )

    return (
        "You are CodeSentinel scanning a local codebase. "
        "Use file reading tools for static analysis, explain the precomputed TruffleHog result, "
        "and use browser, JS analyzer, or Exa tools only when static analysis is insufficient. "
        "When dynamic tools are used, follow the same evidence-backed dynamic verification discipline used for deployed targets. "
        "Then return a detailed markdown report as visible assistant text."
    )


def build_oh_command(
    prompt: str, config: CliConfig, target_url: str | None = None
) -> list[str]:
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


def build_oh_environment(
    config: CliConfig, base_env: Mapping[str, str] | None = None
) -> dict[str, str]:
    env = dict(base_env or os.environ)
    env["OPENAI_API_KEY"] = config.proxy_token
    env["OPENAI_BASE_URL"] = config.proxy_url
    env["OPENHARNESS_API_FORMAT"] = "openai"
    return env


_REPORT_HEADER = "# CodeSentinel Scan Report"


def _extract_report_from_conversation(conversation_text: str) -> str:
    """Find and return the final report from an agent conversation transcript.

    With `--output-format json`, OpenHarness returns
    ``{"type": "result", "text": "<all assistant messages concatenated>"}``.
    The agent is instructed to end with a structured markdown report, so we
    search from the last occurrence of the report header.
    """
    idx = conversation_text.rfind(_REPORT_HEADER)
    if idx != -1:
        return conversation_text[idx:]
    return conversation_text


def extract_report(stdout: str) -> str:
    text = stdout.strip()
    if not text:
        raise OpenHarnessError("OpenHarness returned no output")

    candidates: list[str] = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            candidates.append(line)
            continue

        if isinstance(parsed, str):
            candidates.append(parsed)
        elif isinstance(parsed, dict):
            if parsed.get("type") == "result" and "text" in parsed:
                candidates.append(_extract_report_from_conversation(parsed["text"]))
            else:
                for key in ("text", "content", "message", "output", "result"):
                    value = parsed.get(key)
                    if isinstance(value, str) and value.strip():
                        candidates.append(value.strip())
                        break

    report_candidates = [c for c in candidates if _REPORT_HEADER in c]
    if report_candidates:
        return max(report_candidates, key=len)

    if candidates:
        return max(candidates, key=len)

    raise OpenHarnessError(
        "OpenHarness completed but returned an empty structured result. "
        "That usually means the agent did not actually produce a report."
    )


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
    # For URL scans, always use the CLI tool root so tools/ paths resolve correctly
    cwd = scan_root if scan_root else _CLI_TOOL_ROOT
    try:
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
                command=" ".join(
                    build_oh_command(prompt, config, target_url)
                ),
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
    finally:
        memory_path = cwd / "memory.md"
        if memory_path.exists():
            try:
                memory_path.unlink()
            except OSError:
                pass
        todo_path = cwd / "TODO.md"
        if todo_path.exists():
            try:
                todo_path.write_text("")
            except OSError:
                pass
