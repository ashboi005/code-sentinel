# CodeSentinel Docker Guide

This document answers common questions about how the CodeSentinel Docker image is packaged and how it actually works in production.

## 1. How is the Proxy URL handled in the Docker image?

The Docker image **does not** contain the proxy backend code. It only contains the CLI tool. 

The image is built with two environment variables ready to be used:
- `CODESENTINEL_PROXY_URL`
- `CODESENTINEL_PROXY_TOKEN`

Right now, in the `Dockerfile`, these are blank. When a user runs the image, they can either:
1. Provide their own keys via the CLI flags (e.g. `--api-key sk-...`) and ignore the proxy completely.
2. Pass the environment variables when running the Docker container using the `-e` flag:
   `docker run -e CODESENTINEL_PROXY_URL=https://your-production-proxy.com -e CODESENTINEL_PROXY_TOKEN=your-token ashboi005/code-sentinel interactive`

*If you want to bake your production proxy URL into the image permanently so users don't have to type it, you can just edit the `ENV CODESENTINEL_PROXY_URL="https://your-url.com"` line inside the `Dockerfile` before building it.*

## 2. Where is the interactive TUI tool? Why is it "just the CLI"?

The "CLI tool" **is** the interactive TUI tool! 

In Python, the TUI and the CLI are the exact same application. The `apps/cli-tool` folder contains all the code for both the terminal flags and the beautiful interactive wizard.

When you run `codesentinel interactive`, it triggers the rich visual TUI. When you package the `cli-tool` into Docker, the TUI comes with it automatically.

### How to run the TUI from Docker
To run an interactive tool inside Docker, you must pass the `-it` (interactive terminal) flag to Docker:

```bash
docker run -it ashboi005/code-sentinel interactive
```
This drops the user right into the beautiful setup wizard without needing to `cd` into anything.

## 3. How do I publish this to Docker Hub so people don't have to git clone?

The whole point of Docker is that once you publish the image, **nobody else needs to `git clone` your repository.** They just need Docker installed on their computer.

### Step-by-Step Publishing

**1. Build the image locally on your computer:**
Run this from the root of your project (where the Dockerfile is):
```bash
docker build -t ashboi005/code-sentinel .
```

**2. Log in to Docker Hub:**
```bash
docker login
```

**3. Push the image to Docker Hub:**
```bash
docker push ashboi005/code-sentinel
```

### What your users will do

Once the image is pushed to Docker Hub, any user on Mac, Windows, or Linux can run CodeSentinel with a single command. **They do not need to clone the repo, install Python, or install bun.**

They just run:
```bash
# To run the interactive TUI
docker run -it -v /var/run/docker.sock:/var/run/docker.sock ashboi005/code-sentinel interactive

# To scan a URL directly without the TUI
docker run -v /var/run/docker.sock:/var/run/docker.sock ashboi005/code-sentinel scan --url https://example.com
```

*(Note: The `-v /var/run/docker.sock:/var/run/docker.sock` part is required so the AI agent inside the container can spawn its own test containers using the user's host Docker).*
