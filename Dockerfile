# ──────────────────────────────────────────────────────────────
# CodeSentinel – production container
# ──────────────────────────────────────────────────────────────
FROM python:3.11-slim

LABEL maintainer="ashboi005"
LABEL description="CodeSentinel – AI-powered security scanner & defense agent"
LABEL org.opencontainers.image.source="https://github.com/ashboi005/code-sentinel"
LABEL org.opencontainers.image.licenses="MIT"

# ── System dependencies ─────────────────────────────────────
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        docker.io \
        git \
        npm \
    && rm -rf /var/lib/apt/lists/*

# ── Python tooling ──────────────────────────────────────────
RUN pip install --no-cache-dir uv

# ── Application code ────────────────────────────────────────
COPY apps/cli-tool/ /app/apps/cli-tool/

WORKDIR /app/apps/cli-tool

# ── Install Python dependencies ─────────────────────────────
RUN uv sync

# ── Runtime configuration ───────────────────────────────────
ENV CODESENTINEL_PROXY_URL="http://localhost:8787/v1"
ENV CODESENTINEL_PROXY_TOKEN=""

ENTRYPOINT ["uv", "run", "codesentinel"]
