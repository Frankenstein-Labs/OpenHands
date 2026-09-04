import { HttpError } from "@openhands/typescript-client";
import { SecretsService } from "#/api/secrets-service";
import { getActiveBackend } from "#/api/backend-registry/active-store";
import { callCloudProxy } from "#/api/cloud/proxy";

const TELEGRAM_API_BASE = "https://api.telegram.org";

export const TELEGRAM_SECRET_NAMES = {
  botToken: "TELEGRAM_BOT_TOKEN",
  webhookSecret: "TELEGRAM_WEBHOOK_SECRET",
  allowedChatId: "TELEGRAM_ALLOWED_CHAT_ID",
  cloudApiKey: "OPENHANDS_CLOUD_API_KEY",
} as const;

export interface BotTokenStatus {
  ok: boolean;
  username?: string;
  error?: string;
}

export interface WebhookInfo {
  ok: boolean;
  url?: string | null;
  pendingUpdateCount?: number;
  lastError?: string;
  error?: string;
}

const WEBHOOK_SECRET_PATTERN = /^[A-Za-z0-9_-]{32,256}$/;

export function webhookSecretIsValid(secret: string): boolean {
  return WEBHOOK_SECRET_PATTERN.test(secret);
}

export function generateWebhookSecret(): string {
  const bytes = new Uint8Array(24);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join(
    "",
  );
}

async function telegramApi<T>(
  token: string,
  method: string,
  body: Record<string, unknown> = {},
): Promise<{ ok: boolean; result?: T; description?: string }> {
  const active = getActiveBackend().backend;

  // api.telegram.org does not allow browser CORS, so the request must be
  // forwarded server-side by the local agent-server's `/api/cloud-proxy`.
  if (active.kind !== "cloud") {
    return {
      ok: false,
      description:
        "Telegram settings require a cloud backend to proxy Bot API requests.",
    };
  }

  try {
    const payload = await callCloudProxy<{
      ok?: boolean;
      result?: T;
      description?: string;
    }>({
      backend: active,
      method: "POST",
      hostOverride: TELEGRAM_API_BASE,
      path: `/bot${token}/${method}`,
      body,
      authMode: "none",
    });

    if (!payload?.ok) {
      return {
        ok: false,
        description: payload?.description ?? "Telegram API request failed.",
      };
    }
    return { ok: true, result: payload.result };
  } catch (error) {
    // The proxy envelopes upstream HTTP errors into HttpError; the upstream
    // JSON body (ok/description) rides in `error.response`.
    const upstream = error instanceof HttpError ? error.response : undefined;
    const description =
      typeof upstream === "object" &&
      upstream !== null &&
      "description" in upstream &&
      typeof (upstream as { description?: unknown }).description === "string"
        ? String((upstream as { description: string }).description)
        : error instanceof Error
          ? error.message
          : "Telegram API request failed.";
    return { ok: false, description };
  }
}

export async function validateBotToken(token: string): Promise<BotTokenStatus> {
  const trimmed = token.trim();
  if (!trimmed) return { ok: false, error: "Bot token is required." };

  const result = await telegramApi<{ username?: string }>(trimmed, "getMe");
  if (!result.ok) {
    return { ok: false, error: result.description ?? "Invalid bot token" };
  }
  return { ok: true, username: result.result?.username };
}

export async function getTelegramWebhookInfo(
  token: string,
): Promise<WebhookInfo> {
  const result = await telegramApi<{
    url?: string;
    pending_update_count?: number;
    last_error_message?: string;
  }>(token.trim(), "getWebhookInfo");
  if (!result.ok) return { ok: false, error: result.description };
  return {
    ok: true,
    url: result.result?.url ?? null,
    pendingUpdateCount: result.result?.pending_update_count ?? 0,
    lastError: result.result?.last_error_message,
  };
}

export interface ConfigureWebhookInput {
  token: string;
  secret: string;
  url: string;
}

export async function configureTelegramWebhook({
  token,
  secret,
  url,
}: ConfigureWebhookInput): Promise<{
  ok: boolean;
  error?: string;
  url?: string;
}> {
  if (!webhookSecretIsValid(secret)) {
    return {
      ok: false,
      error: "Webhook secret must contain 32-256 letters, digits, '_' or '-'.",
    };
  }
  const result = await telegramApi<{ url?: string }>(
    token.trim(),
    "setWebhook",
    {
      url: url.trim(),
      secret_token: secret,
      allowed_updates: ["message"],
    },
  );
  if (!result.ok) return { ok: false, error: result.description };
  return { ok: true, url: result.result?.url ?? url.trim() };
}

export async function clearTelegramWebhook(
  token: string,
): Promise<{ ok: boolean; error?: string }> {
  const result = await telegramApi(token.trim(), "deleteWebhook");
  if (!result.ok) return { ok: false, error: result.description };
  return { ok: true };
}

export interface TelegramSecretInput {
  botToken?: string;
  webhookSecret?: string;
  allowedChatId?: string;
  cloudApiKey?: string;
}

export async function saveTelegramSecrets(
  secrets: TelegramSecretInput,
): Promise<{ ok: boolean; saved: string[] }> {
  const saved: string[] = [];
  const entries: Array<[string, string | undefined]> = [
    [TELEGRAM_SECRET_NAMES.botToken, secrets.botToken],
    [TELEGRAM_SECRET_NAMES.webhookSecret, secrets.webhookSecret],
    [TELEGRAM_SECRET_NAMES.allowedChatId, secrets.allowedChatId],
    [TELEGRAM_SECRET_NAMES.cloudApiKey, secrets.cloudApiKey],
  ];
  for (const [name, value] of entries) {
    const trimmed = value?.trim();
    if (!trimmed) continue;
    await SecretsService.createSecret(name, trimmed, "Telegram gateway");
    saved.push(name);
  }
  return { ok: true, saved };
}
