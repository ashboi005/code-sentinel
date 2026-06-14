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

### Tests

```sh
bun test apps/proxy-backend
cd apps/cli-tool && uv run pytest
```

## License

MIT
