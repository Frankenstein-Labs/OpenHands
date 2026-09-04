import { afterEach, describe, expect, it, vi } from "vitest";
import {
  configureTelegramWebhook,
  generateWebhookSecret,
  getTelegramWebhookInfo,
  validateBotToken,
  webhookSecretIsValid,
} from "./telegram-settings-service";

function telegramResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

describe("validateBotToken", () => {
  it("resolves a valid token to the bot username", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        telegramResponse({ ok: true, result: { username: "openhands_bot" } }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const status = await validateBotToken("123:abc");

    expect(status).toEqual({ ok: true, username: "openhands_bot" });
    expect(String(fetchMock.mock.calls[0][0])).toBe(
      "https://api.telegram.org/bot123:abc/getMe",
    );
  });

  it("returns an error for a rejected token", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        telegramResponse({ ok: false, description: "Unauthorized" }, 401),
      );
    vi.stubGlobal("fetch", fetchMock);

    const status = await validateBotToken("bad");

    expect(status.ok).toBe(false);
    expect(status.error).toContain("Unauthorized");
  });
});

describe("getTelegramWebhookInfo", () => {
  it("reports the configured webhook URL and pending updates", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      telegramResponse({
        ok: true,
        result: {
          url: "https://example.vercel.app/api/telegram",
          pending_update_count: 3,
          last_error_message: "",
        },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const info = await getTelegramWebhookInfo("123:abc");

    expect(info).toEqual({
      ok: true,
      url: "https://example.vercel.app/api/telegram",
      pendingUpdateCount: 3,
      lastError: "",
    });
  });
});

describe("configureTelegramWebhook", () => {
  it("sends setWebhook with the secret and message-only updates", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      telegramResponse({
        ok: true,
        result: { url: "https://example.vercel.app/api/telegram" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await configureTelegramWebhook({
      token: "123:abc",
      secret: "a".repeat(48),
      url: "https://example.vercel.app/api/telegram",
    });

    expect(result.ok).toBe(true);
    const [input, init] = fetchMock.mock.calls[0];
    expect(String(input)).toContain("/setWebhook");
    const body = JSON.parse(String(init?.body));
    expect(body.url).toBe("https://example.vercel.app/api/telegram");
    expect(body.secret_token).toBe("a".repeat(48));
    expect(body.allowed_updates).toEqual(["message"]);
  });

  it("rejects a secret shorter than 32 characters", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const result = await configureTelegramWebhook({
      token: "123:abc",
      secret: "short",
      url: "https://example.vercel.app/api/telegram",
    });

    expect(result.ok).toBe(false);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("webhook secret helpers", () => {
  it("accepts only 32-256 alphanumeric, '_' or '-'", () => {
    expect(webhookSecretIsValid("a".repeat(32))).toBe(true);
    expect(webhookSecretIsValid("a".repeat(256))).toBe(true);
    expect(webhookSecretIsValid("a".repeat(31))).toBe(false);
    expect(webhookSecretIsValid("a b")).toBe(false);
  });

  it("generates a 48-character hex secret", () => {
    const secret = generateWebhookSecret();
    expect(secret).toMatch(/^[a-f0-9]{48}$/);
  });
});
