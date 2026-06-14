# CodeSentinel

CodeSentinel is an active web defense agent for helping developers find and understand security-impacting coding mistakes before production.

Phase 1 builds the shared foundation:

- a Bun/Elysia Groq proxy at `apps/proxy-backend`
- a Python/uv CLI at `apps/cli-tool`
- a local OpenHarness bridge through the documented `oh` subprocess interface
- a TruffleHog filesystem secret scan that feeds normalized findings into the agent report
- a Semgrep local static-analysis scan that feeds normalized findings into the agent report
- a Markdown report written to the scanned project root
- optional scan flags that run remediation after report generation and can apply fixes locally or prepare a GitHub PR

## Proxy Backend

Create `apps/proxy-backend/.env`:

```sh
GROQ_API_KEYS=gsk_first,gsk_second,gsk_third
CODESENTINEL_PROXY_TOKEN=replace-with-shared-demo-token
PORT=8787
```

If you are deploying the proxy on Coolify, use the repo root as the build context and `apps/proxy-backend/Dockerfile` as the Dockerfile path. Set the application port to `8787` and expose that same port publicly. Coolify should inject the same environment variables listed above, plus the provider-specific model variables:

- `CODESENTINEL_LLM_PROVIDER`
- `CODESENTINEL_LLM_API_KEYS`
- `CODESENTINEL_LLM_MODEL`
- `CODESENTINEL_OPENROUTER_SITE_URL` and `CODESENTINEL_OPENROUTER_SITE_NAME` when using OpenRouter

Install and run:

```sh
bun install
bun run proxy:dev
```

Health check:

```sh
curl http://localhost:8787/health
```

The proxy exposes `POST /v1/chat/completions` and forwards OpenAI-compatible chat requests to Groq. It does not store chats, repo contents, scan state, or reports.
The same deployment pattern works for Sarvam and Gemini by changing `CODESENTINEL_LLM_PROVIDER` and the matching key list.

## CLI Tool

Keep the Python CLI's secrets in `apps/cli-tool/.env`. The proxy backend keeps its own `.env` in `apps/proxy-backend/.env`.

From `apps/cli-tool`, create `.env` or export:

```sh
CODESENTINEL_PROXY_URL=http://localhost:8787/v1
CODESENTINEL_PROXY_TOKEN=replace-with-shared-demo-token
```

Install:

```sh
cd apps/cli-tool
uv sync
```

Install TruffleHog and Semgrep, or ensure Docker is running. The CLI prefers native `trufflehog` and `semgrep` binaries on `PATH`; if either is not installed, it runs the matching scanner image through Docker.

Run the Phase 1 smoke test:

```sh
uv run codesentinel scan ../..
```

The CLI runs TruffleHog first, Semgrep second, then OpenHarness. It writes `codesentinel-report.md` into the scanned project root.

TruffleHog always runs in filesystem mode with `--json --results=verified,unknown,unverified,filtered_unverified --no-update`. If the target contains `.git`, CodeSentinel also runs `trufflehog git file://<scan-root>` with the same result buckets to inspect commit history. Findings are advisory for now: the scan report includes verified, unknown, unverified, and filtered unverified secret candidates, but the CLI exits nonzero only if TruffleHog itself fails or OpenHarness cannot produce a report. Raw secret values are not passed to the model; CodeSentinel uses TruffleHog redacted output.

Semgrep runs in local OSS mode with `semgrep scan --config=p/ci --config=p/security-audit --config=p/owasp-top-ten --json --metrics=off <scan-root>`. Findings are advisory for now: the scan report includes normalized static-analysis findings and the Semgrep configs used, but the CLI exits nonzero only if Semgrep itself fails or OpenHarness cannot produce a report. If native Semgrep is unavailable, Docker fallback uses `semgrep/semgrep`.

CodeSentinel does not load target-local `.semgrep.yml` files by default. Users can override registry configs with `CODESENTINEL_SEMGREP_CONFIGS` or explicitly include local rules with `CODESENTINEL_SEMGREP_INCLUDE_LOCAL_CONFIG=1`.

If OpenHarness returns an empty structured result, treat that as a failed analysis rather than a success. The proxy path worked, but the agent did not produce a usable report.

For debugging, the CLI logs to stderr and the proxy logs request/response summaries to stdout. That makes it easier to see whether the model call, proxy forwarding, or harness output is the weak point.

Run scan with local remediation:

```sh
uv run codesentinel scan ../.. --fix
```

This runs the normal read-only scan first, writes `codesentinel-report.md`, then starts a second OpenHarness run that consumes the report and applies focused fixes directly in the target folder. The remediation result is also written to `fix.md` in the same folder, including fixed findings, changed lines, tests run, and remaining risks. Plain `codesentinel scan ../..` remains report-only.

To create a pull request after fixing locally:

```sh
CODESENTINEL_GITHUB_TOKEN=github_pat_or_token_here uv run codesentinel scan ../.. --fix-pr
```

GitHub PR mode requires the target to be a Git repository. It creates a `codesentinel/fix-<timestamp>` branch before remediation, then expects GitHub MCP to be available to the remediation harness for GitHub operations. Prefer GitHub's official MCP server in local Docker mode, but do not add a Docker MCP server: when Docker is needed, CodeSentinel agents use ordinary shell commands against the host Docker CLI and daemon, as described in `docs/handoff.md`. The token should have least-privilege repository contents and pull request permissions. CodeSentinel never instructs the agent to push directly to `main`, `master`, or another default branch, and it never instructs the agent to merge the PR.

`codesentinel remediate <repo> --apply-local` and `codesentinel remediate <repo> --github-pr` remain available when you want to rerun remediation from an existing `codesentinel-report.md`.

## OpenHarness Setup

Phase 1 drives OpenHarness through `oh -p ... --output-format json`. The CLI expects `oh` to be available in `PATH` after `uv sync` or your local OpenHarness setup.

The CLI calls OpenHarness with explicit `--api-format openai`, `--base-url`, and `--model` flags. It keeps the shared proxy token in the subprocess environment instead of putting it on the command line.
Phase 1 now uses `--bare`, a higher turn budget, and a configurable allowed-tool list so the agent can iterate on its own and exercise teammate-provided tools.

The CLI configures the subprocess environment with:

- `OPENAI_API_KEY`: the shared proxy token, because OpenHarness expects OpenAI-compatible provider settings
- `OPENAI_BASE_URL`: `CODESENTINEL_PROXY_URL`, which points at the Groq-compatible proxy
- `OPENHARNESS_API_FORMAT`: `openai`
- `OPENHARNESS_MODEL`: `CODESENTINEL_MODEL`
- `OPENHARNESS_ALLOWED_TOOLS`: `CODESENTINEL_OPENHARNESS_ALLOWED_TOOLS`
- `OPENHARNESS_MAX_TURNS`: `CODESENTINEL_OPENHARNESS_MAX_TURNS`

## Team Handoff

- Add future tools behind the CLI/report pipeline, not inside the proxy.
- Use `apps/cli-tool/tools/dummy_tool.sh` only for manual historical plumbing checks.
- Scanner wrappers should follow the TruffleHog/Semgrep pattern: emit normalized findings before model explanation.
- Browser Use should later attach as a local MCP server to OpenHarness, not as custom Phase 1 browser code.

## Tests

```sh
bun test apps/proxy-backend
cd apps/cli-tool
uv run pytest
```
