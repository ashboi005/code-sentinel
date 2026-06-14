# CodeSentinel 🛡️

**The Autonomous Self-Aware Cyber-Defense Agent**

We live in an era where even massive institutions can be brought to their knees by a single security failure. The recent CBSE OSM portal hack was a brutal reminder: nobody is untouchable. If giants with entire security teams are still getting hit, what chance does a small business, freelance developer, or lean agency have on its own?

CodeSentinel is an automated cybersecurity force multiplier built for the people who cannot afford giant audit budgets, endless manual reviews, or the cost of getting it wrong.

---

## 🛑 The Problem with Existing Solutions

- **Professional Audits**: Painfully slow. Brutally expensive.
- **GitGuardian**: Too often overwhelms developers with noise.
- **TruffleHog & Semgrep**: Powerful, but intimidating for beginners and blind to the bigger story.
- **Pasting into ChatGPT/Claude**: Expensive, risky, and a direct threat to privacy. Your codebase and .env files deserve better than being thrown into a public cloud prompt.

## 🚀 Why CodeSentinel?

CodeSentinel closes that gap by combining proven security checks with an autonomous agent that actually *understands* what it is looking at.

- **Privacy First**: Your sensitive code, secrets, and business logic stay under your control.
- **Frighteningly Sharp**: It does not just flag issues. It understands intent, context, and patterns.
- **Actually Actionable**: It does not stop at warning you. It tells you what matters, why it matters, and what to do next.

---

## 🔍 Two Modes of Attack

### 1. Static Mode (Local Repo)
Point CodeSentinel at a local directory and it tears through the codebase, separates real danger from noise, and delivers a prioritized report of what could hurt you most. Then it can go one step further and **automatically fix** the vulnerabilities it finds and package the changes into a GitHub PR.
👉 **[View a sample Static Analysis Report](https://github.com/ashboi005/code-sentinel/blob/main/static-analysis-code-report.pdf)** | **[View the Auto-Fix Report](https://github.com/ashboi005/code-sentinel/blob/main/static-code-fix.pdf)**

### 2. Dynamic Mode (Live URL)
This is where CodeSentinel becomes genuinely terrifying. It explores a live target like a relentless security researcher, uncovering what should never have been exposed in the first place.

> 📖 **Story Time**
> Just last week, I was handed a freelance project. The previous developers had left, and the owner asked me to analyze the live website (I didn't even have the codebase yet!). Doing it manually, I found 2 or 3 unauthenticated endpoints. 
> 
> Then, I pointed CodeSentinel at the live URL while building it at HackPrix Season 3.
> 
> It found **over 15 hidden endpoints**, including exposed Supabase REST and storage URLs. It uncovered a JWT with an absurdly long expiration, derived the Anon Key, made its own requests, and reached a publicly accessible table leaking **plaintext passwords** and usernames. It achieved in 10 minutes what would normally demand a dedicated cybersecurity researcher.
> 
> 👉 **[Read the terrifying Audit Report here](https://github.com/ashboi005/code-sentinel/blob/main/codesentinel-report.pdf)**

---

## 🛠️ Technical Setup & Usage

CodeSentinel is built to feel effortless. We package everything into Docker so you can focus on the mission, not the setup.

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
While the TUI currently offers a "Deployed Lightweight Model" proxy for demonstration purposes, **the recommended path is still Bring Your Own Key (BYOK) when running locally.**

To protect API limits and tokens, the hosted proxy may be turned off without warning. Bringing your own API key gives you stability, freedom, and the strongest results.

### Configuration Modes
During the interactive setup, you will be asked for:
1. **Target**: `repo` (Local directory) or `url` (Live website)
2. **Path/URL**: The path to your mounted code (`/scan`) or the `https://` URL.
3. **Model Provider**: Select between OpenAI, Anthropic, OpenRouter, or Ollama (Local).
4. **Remediation**: Choose whether you want the agent to just report vulnerabilities, fix them locally, or even create a GitHub PR with the patches!

---
*Built to put world-class cyber defense in the hands of the developers who build the web.*
*Built to democratize cybersecurity for the developers who build the web.*

🛡️❤️ Made with love by Ashwath, Tushar, and Aditya 🚀

