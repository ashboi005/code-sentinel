# CodeSentinel Docker Architecture Handoff

This document is intended for AI agents (like the GitHub MCP tool) and developers to understand how the CodeSentinel agent interacts with Docker.

## How the Agent Uses Docker

The CodeSentinel agent relies on the ability to fetch, run, and manage containers dynamically to test and analyze code vulnerabilities (like testing a deployed URL or fetching a Postgres instance).

### Native Bash Execution
1. **No External MCP Server:** The CodeSentinel agent does *not* use a third-party Docker MCP server (like `mcp-docker-server`).
2. **Bash Tooling:** The agent has native access to the terminal via its built-in `bash` tool. It executes standard Docker commands (e.g., `docker run`, `docker pull`, `docker rm`) directly in the shell environment it is running in.
3. **Environment Requirement:** For the agent to successfully manage containers, the host environment where CodeSentinel is running must have the `docker` CLI installed and the Docker Daemon running. 

### Why this matters for the AI Agent:
If you are an AI agent analyzing or running this tool (e.g., via GitHub MCP):
- You **do not** need to install, configure, or search for an MCP Docker server. 
- You can trust that the agent will use its native `bash` tool to interact with Docker natively.
- When generating instructions or prompts for the CodeSentinel agent, you can confidently ask it to "use Docker to spin up a container," and it will automatically know to use the terminal to achieve this.
