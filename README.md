# CodeSentinel

AI-Powered Security Scanner & Defense Agent

CodeSentinel is an active web defense agent that helps developers find and understand security vulnerabilities before production. It combines static analysis tools (TruffleHog, Semgrep) with an AI-powered agent that performs intelligent code review and optional dynamic testing of live endpoints.

## Features

- **Static Analysis**: Automated secret scanning (TruffleHog) and code pattern analysis
- **AI Code Review**: Intelligent review of key architectural files (servers, middleware, auth, DB config)
- **Dynamic Testing**: Browser-based testing and JS bundle analysis for deployed URLs
- **Multiple Providers**: Use the built-in proxy, bring your own API key, or run locally with Ollama
- **Interactive TUI**: Beautiful terminal wizard for guided setup

## Quick Start

### Option 1: Docker (Recommended)

Pull and run the pre-built image:

```sh
# Scan a deployed URL
docker run --rm ghcr.io/ashboi005/code-sentinel scan --url https://example.com --api-key YOUR_KEY --base-url https://api.openai.com/v1 --model gpt-4o

# Scan a local repository (mount it into the container)
docker run --rm -v $(pwd):/scan ghcr.io/ashboi005/code-sentinel scan /scan --api-key YOUR_KEY --base-url https://api.openai.com/v1 --model gpt-4o
```

Or build it yourself:

```sh
git clone https://github.com/ashboi005/code-sentinel.git
cd code-sentinel
docker build -t codesentinel .
docker run --rm codesentinel scan --url https://example.com --api-key YOUR_KEY --base-url https://api.openai.com/v1 --model gpt-4o
```

### Option 2: Local Setup

```sh
git clone https://github.com/ashboi005/code-sentinel.git
cd code-sentinel/apps/cli-tool

# Copy and configure environment
cp .env.example .env
# Edit .env with your proxy URL and token

# Install dependencies
uv sync

# Run a scan
uv run codesentinel scan ../../   # scan the repo itself
uv run codesentinel scan --url https://example.com
```

### Option 3: Interactive Mode

Launch the guided setup wizard:

```sh
uv run codesentinel interactive
```

This walks you through choosing a provider, configuring your API key, and selecting a scan target.

## Provider Configuration

CodeSentinel supports three provider modes:

### 1. Built-in Proxy (Default)

Use the CodeSentinel cloud proxy. Requires `CODESENTINEL_PROXY_URL` and `CODESENTINEL_PROXY_TOKEN` in your `.env` file.

### 2. Bring Your Own Key

Use any OpenAI-compatible API:
CodeSentinel is an active web defense agent for helping developers find and understand security-impacting coding mistakes before production.

Phase 1 builds the shared foundation:

- a Bun/Elysia Groq proxy at `apps/proxy-backend`
- a Python/uv CLI at `apps/cli-tool`
- a local OpenHarness bridge through the documented `oh` subprocess interface
- a TruffleHog filesystem secret scan that feeds normalized findings into the agent report
- a Semgrep local static-analysis scan that feeds normalized findings into the agent report
- a Markdown report written to the scanned project root

## Proxy Backend

Create `apps/proxy-backend/.env`:

```sh
codesentinel scan ./my-project --api-key sk-... --base-url https://api.openai.com/v1 --model gpt-4o
```

Supported providers include: OpenAI, Groq, Anthropic (via proxy), OpenRouter, and any OpenAI-compatible API.

### 3. Local Ollama

Run scans with a local model:

```sh
# Make sure Ollama is running: ollama serve
codesentinel scan ./my-project --local-ollama --model llama3
```

## Scan Types

### Local Repository Scan

```sh
codesentinel scan ./my-project
```

Scans a local codebase using static analysis tools (TruffleHog for secrets, Semgrep for code patterns) combined with AI-powered review of key architectural files. The agent may also use browser tools for dynamic testing if it deems it necessary.

### Deployed URL Scan

```sh
codesentinel scan --url https://example.com
```

Performs dynamic analysis of a live website including JS bundle extraction, HTTP endpoint probing, and browser-based testing. No source code access is required.

## Architecture

- **CLI Tool** (`apps/cli-tool/`): Python CLI that orchestrates scanning, AI analysis, and report generation
- **Proxy Backend** (`apps/proxy-backend/`): Bun/Elysia proxy that forwards OpenAI-compatible requests to upstream LLM providers
- **Tools** (`apps/cli-tool/tools/`): Browser automation, JS analyzer, and web search tools

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Docker (optional, for containerized TruffleHog or running CodeSentinel itself)
- [TruffleHog](https://github.com/trufflesecurity/trufflehog) (optional, falls back to Docker)

## Development

### Proxy Backend

```sh
cd apps/proxy-backend
bun install
bun run start
```

### CLI Tool

```sh
cd apps/cli-tool
uv sync
uv run codesentinel --help
```
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

### Tests
## Team Handoff

- Add future tools behind the CLI/report pipeline, not inside the proxy.
- Use `apps/cli-tool/tools/dummy_tool.sh` only for manual historical plumbing checks.
- Scanner wrappers should follow the TruffleHog/Semgrep pattern: emit normalized findings before model explanation.
- Browser Use should later attach as a local MCP server to OpenHarness, not as custom Phase 1 browser code.

## Tests

```sh
bun test apps/proxy-backend
cd apps/cli-tool && uv run pytest
```

## License

MIT
