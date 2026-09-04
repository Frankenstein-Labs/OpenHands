import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  setActiveSelection,
  setRegisteredBackends,
} from "#/api/backend-registry/active-store";
import type { Backend } from "#/api/backend-registry/types";
import {
  configureTelegramWebhook,
  generateWebhookSecret,
  getTelegramWebhookInfo,
  validateBotToken,
  webhookSecretIsValid,
} from "./telegram-settings-service";

const { callCloudProxy } = vi.hoisted(() => ({
  callCloudProxy: vi.fn(),
}));

vi.mock("#/api/cloud/proxy", () => ({
  callCloudProxy,
}));

const cloudBackend: Backend = {
  id: "cloud-test",
  name: "Cloud test backend",
  host: "https://app.example.test",
  apiKey: "cloud-api-key",
  kind: "cloud",
};

beforeEach(() => {
  callCloudProxy.mockReset();
  setRegisteredBackends([cloudBackend]);
  setActiveSelection({ backendId: cloudBackend.id });
});

afterEach(() => {
  setActiveSelection(null);
  setRegisteredBackends([]);
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

describe("validateBotToken", () => {
  it("resolves a valid token to the bot username", async () => {
    callCloudProxy.mockResolvedValue({
      ok: true,
      result: { username: "openhands_bot" },
    });

    const status = await validateBotToken("123:abc");

    expect(status).toEqual({ ok: true, username: "openhands_bot" });
    expect(callCloudProxy).toHaveBeenCalledWith({
      backend: cloudBackend,
      method: "POST",
      hostOverride: "https://api.telegram.org",
      path: "/bot123:abc/getMe",
      body: {},
      authMode: "none",
    });
  });

  it("returns an error for a rejected token", async () => {
    callCloudProxy.mockResolvedValue({
      ok: false,
      description: "Unauthorized",
    });

    const status = await validateBotToken("bad");

    expect(status.ok).toBe(false);
    expect(status.error).toContain("Unauthorized");
  });
});

describe("getTelegramWebhookInfo", () => {
  it("reports the configured webhook URL and pending updates", async () => {
    callCloudProxy.mockResolvedValue({
      ok: true,
      result: {
        url: "https://example.vercel.app/api/telegram",
        pending_update_count: 3,
        last_error_message: "",
      },
    });

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
    callCloudProxy.mockResolvedValue({
      ok: true,
      result: { url: "https://example.vercel.app/api/telegram" },
    });

    const result = await configureTelegramWebhook({
      token: "123:abc",
      secret: "a".repeat(48),
      url: "https://example.vercel.app/api/telegram",
    });

    expect(result.ok).toBe(true);
    expect(callCloudProxy).toHaveBeenCalledWith({
      backend: cloudBackend,
      method: "POST",
      hostOverride: "https://api.telegram.org",
      path: "/bot123:abc/setWebhook",
      body: {
        url: "https://example.vercel.app/api/telegram",
        secret_token: "a".repeat(48),
        allowed_updates: ["message"],
      },
      authMode: "none",
    });
  });

  it("rejects a secret shorter than 32 characters", async () => {
    const result = await configureTelegramWebhook({
      token: "123:abc",
      secret: "short",
      url: "https://example.vercel.app/api/telegram",
    });

    expect(result.ok).toBe(false);
    expect(callCloudProxy).not.toHaveBeenCalled();
  });
  it("maps upstream HTTP errors to the Telegram description", async () => {
    const { HttpError } = await import("@openhands/typescript-client");
    callCloudProxy.mockRejectedValue(
      new HttpError(401, "Unauthorized", { description: "Unauthorized" }),
    );

    const status = await validateBotToken("bad");

    expect(status).toEqual({
      ok: false,
      error: "Unauthorized",
    });
  });

  it("surfaces an error when no cloud backend is active", async () => {
    setActiveSelection(null);
    setRegisteredBackends([]);

    const status = await validateBotToken("123:abc");

    expect(status).toEqual({
      ok: false,
      error:
        "Telegram settings require a cloud backend to proxy Bot API requests.",
    });
    expect(callCloudProxy).not.toHaveBeenCalled();
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
