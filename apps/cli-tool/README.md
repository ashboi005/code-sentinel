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

Install TruffleHog or make Docker available. The CLI prefers a native `trufflehog` binary on `PATH`; if it is missing, it falls back to Docker.

Filesystem fallback:

```sh
docker run --rm -v "<scan-root>:/pwd:ro" trufflesecurity/trufflehog:latest filesystem /pwd --json --results=verified,unknown,unverified,filtered_unverified --no-update
```

Git history fallback for Git repositories:

```sh
docker run --rm -v "<scan-root>:/pwd:ro" trufflesecurity/trufflehog:latest git file:///pwd --json --results=verified,unknown,unverified,filtered_unverified --no-update
```

## Run

```sh
uv run codesentinel scan .
```

The CLI writes `codesentinel-report.md` into the scanned project root.

If OpenHarness returns an empty structured result, the CLI will fail instead of writing a blank report. That means the transport path worked, but the agent did not actually analyze the repository.

During Phase 1, the CLI prints progress logs to stderr and the proxy prints request/response logs to stdout. That is intentional so you can watch what the agent sent, what the proxy forwarded, and what came back.
Phase 1 runs OpenHarness in `--bare` mode with a higher turn budget and a configurable allowed-tool list so the agent can keep iterating during the smoke test.

## TruffleHog Secret Scan

Before OpenHarness runs, the CLI scans the target directory with TruffleHog filesystem mode:

```sh
trufflehog filesystem <scan-root> --json --results=verified,unknown,unverified,filtered_unverified --no-update
```

When the target contains a `.git` directory, CodeSentinel also scans Git history:

```sh
trufflehog git file://<scan-root> --json --results=verified,unknown,unverified,filtered_unverified --no-update
```

Findings are advisory in this first integration. CodeSentinel includes verified, unknown, unverified, and filtered unverified TruffleHog results so local test fixtures, suspicious hardcoded tokens, and historical leaks are visible. The CLI fails only when TruffleHog itself cannot run or returns a scanner error. The CLI normalizes TruffleHog JSON output before sending it to OpenHarness and includes redacted secrets only, never raw secret values.

`apps/cli-tool/tools/dummy_tool.sh` remains available as a manual historical plumbing check, but the active scan flow no longer calls it.

```sh
python tools/dummy_tool.py --ping
```
