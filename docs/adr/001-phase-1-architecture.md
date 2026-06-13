# ADR 001: Phase 1 CodeSentinel Architecture

## Status

Accepted

## Context

CodeSentinel Phase 1 needs to prove the spine of the system without overbuilding:

- a local CLI that can scan any project path
- a proxy backend that hides provider keys and speaks OpenAI-compatible chat
- an agent loop that can call tools and write a markdown report
- a future extension path for browser automation, static analysis, and custom tools

The team also needs a clean handoff surface so browser tooling, Semgrep, and TruffleHog can be added later without rewriting the proxy or CLI core.

## Decision

- Keep the CLI local and let it orchestrate scans, reporting, and agent configuration.
- Keep the proxy stateless and limited to auth, provider routing, and OpenAI-compatible forwarding.
- Keep provider secrets in the proxy environment, not in the CLI.
- Let tools be attached at the OpenHarness/OpenHands layer or through shell/MCP wrappers, not inside the proxy.
- Use a simple dummy tool as the first plumbing check before browser integration.
- Defer sub-agent orchestration until Phase 2 unless a teammate explicitly needs it for browser work.

## Consequences

- TruffleHog and Semgrep can start as ordinary tools or wrappers.
- Browser use is best treated as a dedicated tool surface or a separate browser-capable worker.
- The core repo can be cloned anywhere; the scan target is whatever local path the user passes to `codesentinel scan`.
- The proxy can be deployed independently on Coolify.

## Phase 2 Direction

- Add browser tooling through MCP or a browser-specific worker.
- If sub-agents are needed, add them in the agent layer, not the proxy.
- Keep the report pipeline stable so new tools only affect the findings stage.
