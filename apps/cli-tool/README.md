# CodeSentinel CLI

Phase 1 CLI for running local CodeSentinel scans through OpenHarness.

## Setup

Keep your CLI secrets in `apps/cli-tool/.env`. The CLI loads that file first, then falls back to the process environment. This keeps the Python app self-contained and avoids mixing its settings with the proxy backend's `.env`.

Example `apps/cli-tool/.env`:

```sh
CODESENTINEL_PROXY_URL=http://localhost:8787/v1
CODESENTINEL_PROXY_TOKEN=replace-with-shared-demo-token
CODESENTINEL_OPENHARNESS_MAX_TURNS=30
CODESENTINEL_OPENHARNESS_ALLOWED_TOOLS=bash,read_file,grep,glob
```

```sh
uv sync
```

Install TruffleHog and Semgrep, or make Docker available. The CLI prefers native `trufflehog` and `semgrep` binaries on `PATH`; if either is missing, it falls back to Docker for that scanner.

Filesystem fallback:

```sh
docker run --rm -v "<scan-root>:/pwd:ro" trufflesecurity/trufflehog:latest filesystem /pwd --json --results=verified,unknown,unverified,filtered_unverified --no-update
```

Git history fallback for Git repositories:

```sh
docker run --rm -v "<scan-root>:/pwd:ro" trufflesecurity/trufflehog:latest git file:///pwd --json --results=verified,unknown,unverified,filtered_unverified --no-update
```

Semgrep fallback:

```sh
docker run --rm -v "<scan-root>:/src:ro" semgrep/semgrep semgrep scan --config=p/ci --config=p/security-audit --config=p/owasp-top-ten --json --metrics=off /src
```

## Run

```sh
uv run codesentinel scan .
```

The CLI runs TruffleHog first, then Semgrep, then OpenHarness. It writes `codesentinel-report.md` into the scanned project root.

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

## Semgrep Static Analysis

After TruffleHog completes, the CLI scans the target directory with Semgrep's local OSS rules:

```sh
semgrep scan --config=p/ci --config=p/security-audit --config=p/owasp-top-ten --json --metrics=off <scan-root>
```

Semgrep findings are advisory in this integration. CodeSentinel normalizes Semgrep JSON before sending it to OpenHarness and includes rule id, severity, message, path, line/column data, category, technology metadata, and the Semgrep configs used when available. The CLI exits nonzero only if Semgrep itself cannot run or returns a scanner error.

By default, CodeSentinel does not load `.semgrep.yml` from scanned repositories. This keeps Docker-based user scans useful without requiring target projects to ship Semgrep rule files and avoids treating demo rules as production coverage.

To override the default registry rulesets:

```sh
CODESENTINEL_SEMGREP_CONFIGS=p/ci,p/security-audit,p/owasp-top-ten
```

To explicitly include a target-local `.semgrep.yml` after the registry rulesets:

```sh
CODESENTINEL_SEMGREP_INCLUDE_LOCAL_CONFIG=1
```

Authenticated `semgrep ci`, Semgrep AppSec Platform features, Supply Chain, Secrets, and `semgrep mcp` are intentionally left for later phases.

`apps/cli-tool/tools/dummy_tool.sh` remains available as a manual historical plumbing check, but the active scan flow no longer calls it.

```sh
python tools/dummy_tool.py --ping
```
