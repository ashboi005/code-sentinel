# CodeSentinel CLI

Phase 1 CLI for running local CodeSentinel scans through OpenHarness.

## Setup

Keep your CLI secrets in `apps/cli-tool/.env`. The CLI loads that file first, then falls back to the process environment. This keeps the Python app self-contained and avoids mixing its settings with the proxy backend's `.env`.

Example `apps/cli-tool/.env`:

```sh
CODESENTINEL_PROXY_URL=http://localhost:8787/v1
CODESENTINEL_PROXY_TOKEN=replace-with-shared-demo-token
CODESENTINEL_OPENHARNESS_MAX_TURNS=8
CODESENTINEL_OPENHARNESS_ALLOWED_TOOLS=bash,read_file,grep,glob
```

```sh
uv sync
```

## Run

```sh
uv run codesentinel scan .
```

The CLI writes `codesentinel-report.md` into the scanned project root.

If OpenHarness returns an empty structured result, the CLI will fail instead of writing a blank report. That means the transport path worked, but the agent did not actually analyze the repository.

During Phase 1, the CLI prints progress logs to stderr and the proxy prints request/response logs to stdout. That is intentional so you can watch what the agent sent, what the proxy forwarded, and what came back.
Phase 1 runs OpenHarness in `--bare` mode with a higher turn budget and a configurable allowed-tool list so the agent can keep iterating during the smoke test.

## Dummy Tool

`apps/cli-tool/tools/dummy_tool.sh` is a tiny bash tool the agent can call to prove the tool plumbing before browser or security tools are added.
`apps/cli-tool/tools/dummy_tool.py` is the cross-platform version and is the preferred one on Windows.

Example:

```sh
python tools/dummy_tool.py --ping
```
