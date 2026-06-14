# CodeSentinel 🛡️

**The Autonomous Cyber-Defense Agent for Small Agencies & Developers**

We live in an era where even national-level organizations are vulnerable—recently, the CBSE OSM portal suffered a major hack, reminding us that no one is immune. If enterprise giants with dedicated security teams are getting breached, how are small businesses, freelance developers, and lean agencies supposed to survive?

CodeSentinel is your automated, intelligent cybersecurity auditor. It’s designed specifically for teams who don't have the massive budgets required for full-scale professional security audits, nor the time to painstakingly review every line of code before pushing to production.

---

## 🛑 The Problem with Existing Solutions

- **Professional Audits**: Prohibitively expensive and time-consuming.
- **GitGuardian**: Notorious for overwhelming developers with false flags.
- **TruffleHog & Semgrep**: Fantastic open-source tools, but difficult to configure for beginners and they lack the "big picture" contextual awareness.
- **Pasting into ChatGPT/Claude**: Extremely expensive at scale and a massive **privacy breach**. Do you really want to paste your proprietary codebase and `.env` files into a public cloud LLM?

## 🚀 Why CodeSentinel?

CodeSentinel bridges the gap by combining industry-standard static analysis tools with an intelligent, autonomous agent that actually *understands* your architecture.

- **Privacy First (Local Execution)**: CodeSentinel supports a fully local **Ollama configuration**. It might run a bit slower, but your code never leaves your machine. Your proprietary logic and `.env` files are 100% safe.
- **Frighteningly Smart**: Our agent doesn't just blindly follow rules. When we fed it an intentionally vulnerable demo app, it didn't just list the flaws—it actively realized the app was a fake and noted in its report that the vulnerabilities felt *"intentional and put there for a demo."*
- **Actionable Context**: It connects the dots. It doesn't just tell you a secret is exposed; it tells you *where*, *why*, and *how* to fix it.

---

## 🔍 Two Modes of Attack

### 1. Static Mode (Local Repo)
Point CodeSentinel at a local directory. It reads your codebase, understands the architectural context, runs underlying tools (like TruffleHog and Semgrep natively), filters out the noise, and provides a prioritized report of security flaws. It can then **automatically fix** the vulnerabilities it finds and package the changes into a GitHub PR.
👉 **[View a sample Static Analysis Report](./static-analysis-code-report.pdf)** | **[View the Auto-Fix Report](./static-code-fix.pdf)**

### 2. Dynamic Mode (Live URL)
This is where the magic happens. CodeSentinel spins up a headless browser, searches the web, extracts and beautifies minified JavaScript bundles, opens the network tab, and reads cookie headers—acting exactly like a real penetration tester.

> 📖 **Story Time: The InsureZeal Audit**
> Just last week, I was handed a freelance project. The previous developers had left, and the owner asked me to analyze the live website (I didn't even have the codebase yet!). Doing it manually, I found 2 or 3 unauthenticated endpoints. 
> 
> Then, I pointed CodeSentinel at the live URL.
> 
> It found **over 15 hidden endpoints**, including exposed Supabase REST and storage URLs. It extracted a JWT with an expiration of over 10 years, reverse-engineered the Anon Key, made its own HTTP requests to the Supabase endpoint, and successfully fetched a publicly accessible table dumping **plaintext passwords** and usernames. It did in 3 minutes what would have taken days to map out manually.
> 
> 👉 **[Read the terrifying InsureZeal Audit Report here](./codesentinel-insurezeal-report.pdf)**

---

## 🛠️ Technical Setup & Usage

CodeSentinel is designed to be frictionless to run. We package everything into a Docker container so you don't need to install Python, Node, Semgrep, or Go on your local machine.

### Quick Start (Docker)

To run an interactive scan on your current directory:

```bash
docker run -it \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$(pwd)":/scan \
  ashboi005/code-sentinel:latest interactive
```
*(Note: If you are on Windows, use `"%cd%":/scan` instead of `"$(pwd)":/scan`)*

### ⚠️ IMPORTANT: Bring Your Own Key (BYOK)
While the TUI currently offers a "Deployed Lightweight Model" proxy for demonstration purposes, **please prefer the Bring Your Own Key (BYOK) setup when running locally.** 

To protect API limits and tokens, the hosted proxy may be turned off without warning. Providing your own API key (e.g., OpenAI, Anthropic, or running local Ollama) guarantees you won't be rate-limited and ensures the highest quality results.

### Configuration Modes
During the interactive setup, you will be asked for:
1. **Target**: `repo` (Local directory) or `url` (Live website)
2. **Path/URL**: The path to your mounted code (`/scan`) or the `https://` URL.
3. **Model Provider**: Select between OpenAI, Anthropic, OpenRouter, or Ollama (Local).
4. **Remediation**: Choose whether you want the agent to just report vulnerabilities, fix them locally, or even create a GitHub PR with the patches!

---
*Built to democratize cybersecurity for the developers who build the web.*
