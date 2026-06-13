import { generateText } from "ai";
import { groq } from "@ai-sdk/groq";
import { GoogleGenAI } from "@google/genai";
import OpenAI from "openai";
import { SarvamAIClient } from "sarvamai";
import { Elysia } from "elysia";
import { KeyPool } from "./key-pool";
import type { ProxyConfig } from "./config";

interface AppOptions {
  now?: () => number;
  logger?: Pick<Console, "info" | "warn" | "error">;
}

type ChatMessage = {
  role?: string;
  content?: unknown;
  name?: string;
  tool_call_id?: string;
  tool_calls?: unknown;
};

type ChatCompletionRequest = {
  model?: string;
  messages?: ChatMessage[];
  stream?: boolean;
  tools?: unknown;
  tool_choice?: unknown;
};

function hasValidBearer(authHeader: string | null, token: string): boolean {
  return authHeader === `Bearer ${token}`;
}

function toText(value: unknown): string {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(toText).join("");
  if (value && typeof value === "object") {
    const candidate = (value as { text?: unknown; content?: unknown }).text ?? (value as { content?: unknown }).content;
    if (candidate !== undefined) return toText(candidate);
  }
  return "";
}

function normalizeMessages(raw: unknown): ChatMessage[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .map((item) => {
      if (!item || typeof item !== "object") return null;
      const message = item as ChatMessage;
      return {
        role: typeof message.role === "string" ? message.role : "user",
        content: message.content,
        name: typeof message.name === "string" ? message.name : undefined,
        tool_call_id: typeof message.tool_call_id === "string" ? message.tool_call_id : undefined,
        tool_calls: message.tool_calls
      };
    })
    .filter(Boolean) as ChatMessage[];
}

function splitSystem(messages: ChatMessage[]): { system?: string; conversation: { role: "user" | "assistant"; content: string }[] } {
  const systemParts: string[] = [];
  const conversation: { role: "user" | "assistant"; content: string }[] = [];

  for (const message of messages) {
    const content = toText(message.content);
    if (!content) continue;

    if (message.role === "system") {
      systemParts.push(content);
      continue;
    }

    conversation.push({
      role: message.role === "assistant" ? "assistant" : "user",
      content
    });
  }

  return {
    system: systemParts.length > 0 ? systemParts.join("\n\n") : undefined,
    conversation
  };
}

function toOpenAIResponse(model: string, text: string, promptTokens = 0, completionTokens = 0) {
  return {
    id: `chatcmpl_${crypto.randomUUID().replace(/-/g, "")}`,
    object: "chat.completion",
    created: Math.floor(Date.now() / 1000),
    model,
    choices: [
      {
        index: 0,
        message: {
          role: "assistant",
          content: text
        },
        finish_reason: "stop"
      }
    ],
    usage: {
      prompt_tokens: promptTokens,
      completion_tokens: completionTokens,
      total_tokens: promptTokens + completionTokens
    }
  };
}

function toOpenAIChatMessages(messages: ChatMessage[]) {
  return messages.map((message) => ({
    role: message.role === "assistant" ? "assistant" : message.role === "system" ? "system" : "user",
    content: toText(message.content)
  }));
}

function toOpenRouterChatMessages(messages: ChatMessage[]) {
  return messages.map((message) => {
    const role =
      message.role === "assistant"
        ? "assistant"
        : message.role === "system"
          ? "system"
          : message.role === "tool"
            ? "tool"
            : "user";

    return {
      role,
      content: role === "assistant" && message.tool_calls ? (message.content ?? null) : (message.content ?? ""),
      name: message.name,
      tool_call_id: message.tool_call_id,
      tool_calls: message.tool_calls
    };
  });
}

function openAIJsonToSseStream(response: ReturnType<typeof toOpenAIResponse>) {
  const encoder = new TextEncoder();
  const content = response.choices[0]?.message?.content ?? "";
  const chunk = {
    id: response.id,
    object: "chat.completion.chunk",
    created: response.created,
    model: response.model,
    choices: [
      {
        index: 0,
        delta: {
          role: "assistant",
          content
        },
        finish_reason: "stop"
      }
    ],
    usage: response.usage
  };

  return new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(`data: ${JSON.stringify(chunk)}\n\n`));
      controller.enqueue(encoder.encode("data: [DONE]\n\n"));
      controller.close();
    }
  });
}

function sseHeaders() {
  return {
    "content-type": "text/event-stream",
    "cache-control": "no-cache",
    connection: "keep-alive"
  };
}

async function callGroq(model: string, apiKey: string, messages: ChatMessage[]) {
  const result = await generateText({
    model: groq(model, {
      apiKey
    }),
    messages: messages.map((message) => ({
      role: message.role === "assistant" ? "assistant" : message.role === "system" ? "system" : "user",
      content: toText(message.content)
    }))
  });

  return toOpenAIResponse(model, result.text, result.usage?.promptTokens ?? 0, result.usage?.completionTokens ?? 0);
}

async function callGemini(model: string, apiKey: string, messages: ChatMessage[]) {
  const client = new GoogleGenAI({ apiKey });
  const { system, conversation } = splitSystem(messages);
  const contents = conversation.map((message) => ({
    role: message.role === "assistant" ? "model" : "user",
    parts: [{ text: message.content }]
  }));

  const response = await client.models.generateContent({
    model,
    contents,
    systemInstruction: system ? { parts: [{ text: system }] } : undefined
  });

  const text = response.text ?? "";
  return toOpenAIResponse(
    model,
    text,
    response.usageMetadata?.promptTokenCount ?? 0,
    response.usageMetadata?.candidatesTokenCount ?? 0
  );
}

async function callSarvam(model: string, apiKey: string, messages: ChatMessage[]) {
  const client = new SarvamAIClient({ apiSubscriptionKey: apiKey });
  const response = await client.chat.completions({
    model,
    messages: messages.map((message) => ({
      role: message.role === "assistant" ? "assistant" : message.role === "system" ? "system" : "user",
      content: toText(message.content)
    }))
  });

  const text = response.choices?.[0]?.message?.content ?? "";
  return toOpenAIResponse(
    model,
    text,
    response.usage?.prompt_tokens ?? 0,
    response.usage?.completion_tokens ?? 0
  );
}

async function callOpenRouter(
  model: string,
  apiKey: string,
  messages: ChatMessage[],
  siteUrl: string,
  siteName: string,
  tools?: unknown,
  toolChoice?: unknown
) {
  const client = new OpenAI({
    apiKey,
    baseURL: "https://openrouter.ai/api/v1",
    defaultHeaders: {
      "HTTP-Referer": siteUrl,
      "X-OpenRouter-Title": siteName
    }
  });

  const response = await client.chat.completions.create({
    model,
    messages: toOpenRouterChatMessages(messages),
    tools: Array.isArray(tools) ? (tools as never) : undefined,
    tool_choice: toolChoice as never
  } as never);

  const message = response.choices?.[0]?.message;
  const text =
    toText((message as { content?: unknown; reasoning?: unknown })?.content) ||
    toText((message as { reasoning?: unknown })?.reasoning) ||
    JSON.stringify(message ?? response);
  return toOpenAIResponse(model, text, response.usage?.prompt_tokens ?? 0, response.usage?.completion_tokens ?? 0);
}

async function callOpenRouterStream(
  model: string,
  apiKey: string,
  messages: ChatMessage[],
  siteUrl: string,
  siteName: string,
  tools?: unknown,
  toolChoice?: unknown
) {
  const client = new OpenAI({
    apiKey,
    baseURL: "https://openrouter.ai/api/v1",
    defaultHeaders: {
      "HTTP-Referer": siteUrl,
      "X-OpenRouter-Title": siteName
    }
  });

  const upstreamStream = await client.chat.completions.create({
    model,
    messages: toOpenRouterChatMessages(messages),
    tools: Array.isArray(tools) ? (tools as never) : undefined,
    tool_choice: toolChoice as never,
    stream: true
  } as never);

  const encoder = new TextEncoder();
  return new ReadableStream({
    async start(controller) {
      try {
        for await (const chunk of upstreamStream as AsyncIterable<unknown>) {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(chunk)}\n\n`));
        }
        controller.enqueue(encoder.encode("data: [DONE]\n\n"));
        controller.close();
      } catch (error) {
        controller.error(error);
      }
    }
  });
}

export function createProxyApp(config: ProxyConfig, options: AppOptions = {}) {
  const keyPool = new KeyPool(config.apiKeys);
  const now = options.now ?? Date.now;
  const logger = options.logger ?? console;

  function logRequest(message: string, details: Record<string, unknown>) {
    logger.info(`[proxy] ${message} ${JSON.stringify(details)}`);
  }

  return new Elysia()
    .get("/health", () => ({
      ok: true,
      service: "codesentinel-proxy",
      provider: config.provider,
      model: config.model,
      availableKeys: keyPool.availableCount(),
      totalKeys: keyPool.size()
    }))
    .post("/v1/chat/completions", async ({ request }) => {
      const requestId = crypto.randomUUID();

      if (!hasValidBearer(request.headers.get("authorization"), config.proxyToken)) {
        logRequest("reject unauthorized request", {
          requestId,
          path: "/v1/chat/completions"
        });

        return new Response(
          JSON.stringify({
            error: {
              message: "Missing or invalid CodeSentinel proxy token",
              type: "authentication_error"
            }
          }),
          {
            status: 401,
            headers: { "content-type": "application/json" }
          }
        );
      }

      const body = await request.text();
      let parsedBody: ChatCompletionRequest | null = null;
      try {
        parsedBody = JSON.parse(body) as ChatCompletionRequest;
      } catch {
        parsedBody = null;
      }

      const messages = normalizeMessages(parsedBody?.messages);
      const wantsStream = parsedBody?.stream === true;
      const openRouterSiteUrl = Bun.env.CODESENTINEL_OPENROUTER_SITE_URL?.trim() || "http://localhost:8787";
      const openRouterSiteName = Bun.env.CODESENTINEL_OPENROUTER_SITE_NAME?.trim() || "CodeSentinel";

      logRequest("incoming chat request", {
        requestId,
        provider: config.provider,
        model: config.model,
        hasMessages: messages.length > 0,
        stream: wantsStream,
        hasTools: Array.isArray(parsedBody?.tools),
        bodyBytes: body.length
      });

      let lastError = "";

      for (let attempt = 0; attempt <= config.maxRetries; attempt += 1) {
        const selected = keyPool.select();

        logRequest("forwarding request upstream", {
          requestId,
          attempt: attempt + 1,
          selectedKeyIndex: selected.index,
          provider: config.provider,
          upstreamModel: config.model
        });

        try {
          if (config.provider === "openrouter" && wantsStream) {
            const stream = await callOpenRouterStream(
              config.model,
              selected.value,
              messages,
              openRouterSiteUrl,
              openRouterSiteName,
              parsedBody?.tools,
              parsedBody?.tool_choice
            );

            logRequest("upstream streaming response", {
              requestId,
              attempt: attempt + 1,
              selectedKeyIndex: selected.index,
              provider: config.provider,
              status: 200
            });

            return new Response(stream, {
              status: 200,
              headers: sseHeaders()
            });
          }

          const response =
            config.provider === "groq"
              ? await callGroq(config.model, selected.value, messages)
              : config.provider === "gemini"
                ? await callGemini(config.model, selected.value, messages)
                : config.provider === "openrouter"
                  ? await callOpenRouter(
                      config.model,
                      selected.value,
                      messages,
                      openRouterSiteUrl,
                      openRouterSiteName,
                      parsedBody?.tools,
                      parsedBody?.tool_choice
                    )
                  : await callSarvam(config.model, selected.value, messages);

          logRequest("upstream response", {
            requestId,
            attempt: attempt + 1,
            selectedKeyIndex: selected.index,
            provider: config.provider,
            status: 200
          });

          if (wantsStream) {
            return new Response(openAIJsonToSseStream(response), {
              status: 200,
              headers: sseHeaders()
            });
          }

          return new Response(JSON.stringify(response), {
            status: 200,
            headers: { "content-type": "application/json" }
          });
        } catch (error) {
          lastError = error instanceof Error ? error.message : String(error);
          logger.warn(
            `[proxy] upstream error ${JSON.stringify({
              requestId,
              attempt: attempt + 1,
              selectedKeyIndex: selected.index,
              provider: config.provider,
              error: lastError
            })}`
          );

          continue;
        }
      }

      return new Response(
        JSON.stringify({
          error: {
            message: "Upstream request failed after retrying available keys",
            type: "upstream_error",
            detail: lastError
          }
        }),
        {
          status: 502,
          headers: { "content-type": "application/json" }
        }
      );
    });
}
