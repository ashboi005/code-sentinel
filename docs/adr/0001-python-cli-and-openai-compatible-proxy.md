# 0001. Python CLI With OpenAI-Compatible Proxy Boundary

## Status

Accepted

## Context

CodeSentinel is a hackathon project for HackPrix Season 3. The product goal is to help developers understand and fix security-impacting coding mistakes before production, using a local scan flow that combines repo inspection, local command execution, and agent-driven reasoning.

Phase 1 intentionally stops short of full static analysis, browser automation, deployed URL scanning, or PR generation. The immediate goal is to unblock the team with a working foundation:

- a lightweight proxy backend that can centralize Groq access
- a local agentic CLI that can run on a teammate's machine
- a reliable way to invoke OpenHarness without depending on unstable internals

The proxy backend is built around Groq, but the OpenHarness CLI exposes an OpenAI-compatible configuration surface. The proxy is therefore a translation boundary: the CLI speaks OpenAI-compatible model request shapes to the proxy, and the proxy forwards them to Groq using authorized keys we control.

## Decision

We will keep the public CodeSentinel CLI in Python and drive OpenHarness through the documented `oh` subprocess interface.

The CLI will:

- store its own secrets in `apps/cli-tool/.env`
- load that file first, then fall back to the process environment
- call OpenHarness in `openai` compatibility mode
- pass the proxy URL as the OpenAI base URL
- keep the shared proxy token in the subprocess environment, not on the command line

The proxy backend will:

- remain stateless
- expose `POST /v1/chat/completions`
- require a shared bearer token from the CLI
- round-robin across authorized Groq keys
- back off keys that return `429`

## Alternatives Considered

1. TypeScript CLI with a Python subprocess bridge

   Rejected because OpenHarness is Python-first and Browser Use is also Python-first, so a Python CLI makes the integration surface smaller and more natural.

2. Full hosted agent backend

   Rejected for Phase 1 because it would move repo contents and local tool execution off the user's machine, which is not the right tradeoff for the hackathon demo.

3. Direct Groq integration without a proxy

   Rejected because the proxy gives us a single place for token protection, key rotation, rate-limit handling, and future provider swaps.

4. Build against OpenHarness internals

   Rejected because the documented `oh` CLI surface is more stable and easier for teammates to reproduce.

## Consequences

This keeps the public interface simple for the team while preserving a clean future path:

- Semgrep and TruffleHog can be attached later as local CLI tools behind the same report pipeline
- Browser Use can be added later through the local MCP path
- the proxy can remain provider-agnostic as long as it preserves the OpenAI-compatible surface

The main cost is that the stack is intentionally split across two runtimes, Bun for the proxy and Python for the CLI, but that is the smallest reliable shape for the current phase.

## Next Phases

1. Add normalized static findings from Semgrep and TruffleHog to the CLI report pipeline.
2. Add Browser Use via local MCP for localhost and explicitly approved deployed targets.
3. Add local app startup heuristics and target detection for more realistic scans.
4. Add optional GitHub PR generation and fix suggestions after the report is stable.
5. Add Docker/Coolify packaging once the demo flow is stable.
