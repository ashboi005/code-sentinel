export type LlmProvider = "groq" | "sarvam" | "gemini" | "openrouter";

export interface ProxyConfig {
  provider: LlmProvider;
  apiKeys: string[];
  proxyToken: string;
  model: string;
  keyCooldownMs: number;
  maxRetries: number;
}

function readRequired(name: string): string {
  const value = Bun.env[name]?.trim();
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

function readNumber(name: string, fallback: number): number {
  const raw = Bun.env[name]?.trim();
  if (!raw) return fallback;

  const parsed = Number(raw);
  if (!Number.isFinite(parsed) || parsed < 0) {
    throw new Error(`Environment variable ${name} must be a non-negative number`);
  }

  return parsed;
}

function readProvider(name: string, fallback: LlmProvider): LlmProvider {
  const raw = Bun.env[name]?.trim().toLowerCase();
  if (!raw) return fallback;

  if (raw === "groq" || raw === "sarvam" || raw === "gemini" || raw === "openrouter") {
    return raw;
  }

  throw new Error(`Environment variable ${name} must be one of: groq, sarvam, gemini, openrouter`);
}

export function loadConfig(): ProxyConfig {
  const provider = readProvider("CODESENTINEL_LLM_PROVIDER", "groq");
  const apiKeys = (
    Bun.env.CODESENTINEL_LLM_API_KEYS?.trim() ||
    Bun.env.GROQ_API_KEYS?.trim() ||
    Bun.env.SARVAM_API_KEYS?.trim() ||
    Bun.env.GEMINI_API_KEYS?.trim() ||
    ""
  )
    .split(",")
    .map((key) => key.trim())
    .filter(Boolean);

  if (apiKeys.length === 0) {
    throw new Error("CODESENTINEL_LLM_API_KEYS must contain at least one key");
  }

  return {
    provider,
    apiKeys,
    proxyToken: readRequired("CODESENTINEL_PROXY_TOKEN"),
    model:
      Bun.env.CODESENTINEL_LLM_MODEL?.trim() ||
      (
        provider === "gemini"
          ? "gemini-2.5-flash"
          : provider === "sarvam"
            ? "sarvam-30b"
            : provider === "openrouter"
              ? "openai/gpt-5.2"
              : "llama-3.1-8b-instant"
      ),
    keyCooldownMs: readNumber("KEY_COOLDOWN_MS", 0),
    maxRetries: readNumber("MAX_GROQ_RETRIES", 1)
  };
}
