# CodeSentinel

CodeSentinel is an active web defense agent for helping developers find and understand security-impacting coding mistakes before production.

Phase 1 builds the shared foundation:

- a Bun/Elysia Groq proxy at `apps/proxy-backend`
- a Python/uv CLI at `apps/cli-tool`
- a local OpenHarness bridge through the documented `oh` subprocess interface
- a Markdown report written to the scanned project root

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

Run the Phase 1 smoke test:

```sh
uv run codesentinel scan ../..
```

The CLI writes `codesentinel-report.md` into the scanned project root.

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

## Team Handoff

- Add future tools behind the CLI/report pipeline, not inside the proxy.
- Use `apps/cli-tool/tools/dummy_tool.sh` as the first plumbing check before wiring browser or security tools.
- Semgrep and TruffleHog wrappers should emit normalized JSON findings before model explanation.
- Browser Use should later attach as a local MCP server to OpenHarness, not as custom Phase 1 browser code.

## Tests

```sh
bun test apps/proxy-backend
cd apps/cli-tool
uv run pytest
```
