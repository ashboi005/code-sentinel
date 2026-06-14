# CodeSentinel AI Handoff

## Project Context

CodeSentinel is an active web defense agent that combines static analysis, AI-powered code review, and dynamic testing to help developers find security vulnerabilities before production.

## Read First

- [README.md](/Users/ashwath/Code/code-sentinel/README.md)
- [CONTEXT.md](/Users/ashwath/Code/code-sentinel/CONTEXT.md)
- [ADR 001: CodeSentinel Architecture](/Users/ashwath/Code/code-sentinel/docs/adr/001-phase-1-architecture.md)
- [CLI README](/Users/ashwath/Code/code-sentinel/apps/cli-tool/README.md)

## What Exists Now

- **Interactive TUI mode** (`codesentinel interactive`): guided wizard that walks users through provider selection, API key entry, and scan target configuration.
- **BYOK support**: users can supply their own OpenAI-compatible API key, base URL, and model via CLI flags (`--api-key`, `--base-url`, `--model`).
- **Ollama support**: local model inference via `--local-ollama --model <name>`.
- **Docker distribution**: production Dockerfile at the repo root; pre-built image at `ghcr.io/ashboi005/code-sentinel`.
- **TruffleHog integration**: filesystem and git-history secret scanning with normalized findings fed into the agent report.
- **Browser tools**: browser-based dynamic testing and HTTP endpoint probing for deployed URLs.
- **JS analyzer**: JavaScript bundle extraction and analysis for client-side security review.
- **Web search tool**: agent-accessible web search for enriching vulnerability context.
- **Proxy backend**: Bun/Elysia proxy that supports multiple upstream LLM providers and streams OpenAI-compatible responses.
- **Report generation**: Markdown report (`codesentinel-report.md`) written to the scanned project root.

## Sub-Agents

- Semgrep and TruffleHog run as ordinary tools or wrappers, not sub-agents.
- A browser-focused sub-agent is a good addition if the agent layer supports delegation cleanly.
- If the underlying agent runtime exposes native delegation, use it there rather than building a proxy-side orchestration layer.
- The proxy should stay dumb: auth, model selection, request forwarding, and streaming only.

## Where Teammates Plug In

- **CLI orchestration and prompt shaping**: `apps/cli-tool/src/codesentinel/openharness.py`
- **CLI environment and defaults**: `apps/cli-tool/src/codesentinel/config.py`
- **Interactive TUI flow**: `apps/cli-tool/src/codesentinel/interactive.py` (provider selection, scan configuration)
- **CLI flags (BYOK, Ollama, model)**: handled via the CLI entry point and passed through to OpenHarness
- **Browser and JS analysis tools**: `apps/cli-tool/tools/`
- **Proxy auth and provider routing**: `apps/proxy-backend/src/server.ts`

## Handoff Rules

- If a change is about tools, agent behavior, or report shaping, make it in the CLI or agent layer.
- If a change is about provider access, keys, or deployment, make it in the proxy.
- If a change is about browser automation or JS analysis, keep it in the tools directory under the CLI.
