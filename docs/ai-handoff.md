# CodeSentinel AI Handoff

## Project Context

CodeSentinel is an active web defense agent for hackathon use. The current goal is to keep the Phase 1 foundation stable so the team can extend it with real tools and browser automation in later phases.

## Read First

- [README.md](/Users/ashwath/Code/code-sentinel/README.md)
- [CONTEXT.md](/Users/ashwath/Code/code-sentinel/CONTEXT.md)
- [ADR 001: Phase 1 CodeSentinel Architecture](/Users/ashwath/Code/code-sentinel/docs/adr/001-phase-1-architecture.md)
- [CLI README](/Users/ashwath/Code/code-sentinel/apps/cli-tool/README.md)

## What Exists Now

- The CLI runs `codesentinel scan <local-path>`.
- The CLI launches OpenHarness through `oh` and forwards requests to the proxy.
- The proxy supports multiple upstream providers and streams OpenAI-compatible responses.
- The agent can call tools and is no longer pinned to a tiny repo-specific file list.
- `apps/cli-tool/tools/dummy_tool.sh` is the current plumbing check for tool execution.

## Sub-Agents

- The current CodeSentinel spine does not require a sub-agent framework for Phase 1.
- Semgrep and TruffleHog should stay as ordinary tools or wrappers.
- A browser-focused sub-agent is a good Phase 2 addition if the agent layer supports delegation cleanly.
- If the underlying agent runtime exposes native delegation, use it there rather than building a proxy-side orchestration layer.
- The proxy should stay dumb: auth, model selection, request forwarding, and streaming only.

## Phase 2 Direction

- Add browser-use as a dedicated browser-capable tool or worker.
- Add Semgrep and TruffleHog as normalized tool outputs that feed the report pipeline.
- Add code editing only after read-only inspection and browser tooling are stable.
- Keep the CLI as the orchestrator and keep the proxy out of tool logic.

## Where Teammates Plug In

- CLI orchestration and prompt shaping: `apps/cli-tool/src/codesentinel/openharness.py`
- CLI environment and defaults: `apps/cli-tool/src/codesentinel/config.py`
- Proxy auth and provider routing: `apps/proxy-backend/src/server.ts`
- Tool smoke testing: `apps/cli-tool/tools/dummy_tool.sh`

## Handoff Rule

- If a change is about tools, agent behavior, or report shaping, make it in the CLI or agent layer.
- If a change is about provider access, keys, or deployment, make it in the proxy.
- If a change is about Phase 2 browser use, keep it in a separate browser tool or worker instead of the proxy.
