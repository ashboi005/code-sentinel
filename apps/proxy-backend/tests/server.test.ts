import { describe, expect, test } from "bun:test";
import { createProxyApp } from "../src/server";
import type { ProxyConfig } from "../src/config";

const config: ProxyConfig = {
  groqApiKeys: ["key-a", "key-b"],
  proxyToken: "shared-token",
  groqBaseUrl: "https://groq.test/openai/v1",
  keyCooldownMs: 60_000,
  maxRetries: 1
};

function jsonRequest(body = { model: "demo", messages: [] }, token = "shared-token") {
  return new Request("http://localhost/v1/chat/completions", {
    method: "POST",
    headers: {
      authorization: `Bearer ${token}`,
      "content-type": "application/json"
    },
    body: JSON.stringify(body)
  });
}

describe("proxy server", () => {
  test("rejects missing bearer token", async () => {
    const app = createProxyApp(config);
    const response = await app.handle(
      new Request("http://localhost/v1/chat/completions", {
        method: "POST",
        body: "{}"
      })
    );

    expect(response.status).toBe(401);
  });

  test("forwards chat completions to Groq-compatible endpoint", async () => {
    const calls: string[] = [];
    const app = createProxyApp(config, {
      fetchImpl: async (input, init) => {
        calls.push((init?.headers as Headers).get("authorization") ?? "");
        expect(String(input)).toBe("https://groq.test/openai/v1/chat/completions");
        expect(init?.method).toBe("POST");

        return new Response(JSON.stringify({ id: "chatcmpl_test" }), {
          status: 200,
          headers: { "content-type": "application/json" }
        });
      }
    });

    const response = await app.handle(jsonRequest());

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ id: "chatcmpl_test" });
    expect(calls).toEqual(["Bearer key-a"]);
  });

  test("marks a 429 key as cooling down and retries another key", async () => {
    const calls: string[] = [];
    const app = createProxyApp(config, {
      now: () => 1_000,
      fetchImpl: async (_input, init) => {
        const auth = (init?.headers as Headers).get("authorization") ?? "";
        calls.push(auth);

        if (auth === "Bearer key-a") {
          return new Response("too many requests", { status: 429 });
        }

        return new Response(JSON.stringify({ id: "retry_ok" }), {
          status: 200,
          headers: { "content-type": "application/json" }
        });
      }
    });

    const response = await app.handle(jsonRequest());

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ id: "retry_ok" });
    expect(calls).toEqual(["Bearer key-a", "Bearer key-b"]);
  });

  test("returns capacity error when every key is cooling down", async () => {
    const app = createProxyApp(config, {
      now: () => 1_000,
      fetchImpl: async () => new Response("too many requests", { status: 429 })
    });

    const first = await app.handle(jsonRequest());
    const second = await app.handle(jsonRequest());

    expect(first.status).toBe(429);
    expect(second.status).toBe(503);
    expect(await second.json()).toEqual({
      error: {
        message: "All configured Groq keys are temporarily cooling down",
        type: "capacity_exhausted"
      }
    });
  });
});
