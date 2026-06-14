FROM python:3.11-slim

LABEL maintainer="ashboi005"
LABEL description="CodeSentinel – AI-powered security scanner & defense agent"
LABEL org.opencontainers.image.source="https://github.com/ashboi005/code-sentinel"
LABEL org.opencontainers.image.licenses="MIT"

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        docker.io \
        git \
        npm \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv semgrep

# Install TruffleHog native binary
RUN curl -sSfL https://raw.githubusercontent.com/trufflesecurity/trufflehog/main/scripts/install.sh | sh -s -- -b /usr/local/bin

COPY apps/cli-tool/ /app/apps/cli-tool/

WORKDIR /app/apps/cli-tool

RUN uv sync

ENV CODESENTINEL_PROXY_URL="http://jmejndj82bqg6fdo8w6xhafc.51.38.51.147.sslip.io"
ENV CODESENTINEL_PROXY_TOKEN="fmP8J6vHIflp55DJV+0IOIxzDSHx3OBzmedq580DNgo="

ENTRYPOINT ["uv", "run", "codesentinel"]
