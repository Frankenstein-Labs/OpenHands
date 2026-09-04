const token = process.env.TELEGRAM_BOT_TOKEN?.trim();
const secret = process.env.TELEGRAM_WEBHOOK_SECRET?.trim();
const explicitUrl = process.env.TELEGRAM_WEBHOOK_URL?.trim();
const vercelUrl = process.env.VERCEL_URL?.trim();

if (!token) throw new Error("TELEGRAM_BOT_TOKEN is required");
if (!secret || !/^[A-Za-z0-9_-]{32,256}$/.test(secret)) {
  throw new Error(
    "TELEGRAM_WEBHOOK_SECRET must contain 32-256 letters, digits, '_' or '-'",
  );
}

const baseUrl = explicitUrl || (vercelUrl ? `https://${vercelUrl}` : null);
if (!baseUrl) {
  throw new Error(
    "Set TELEGRAM_WEBHOOK_URL or VERCEL_URL to the deployed Vercel URL",
  );
}

const webhookUrl = new URL("/api/telegram", baseUrl).toString();
const response = await fetch(
  `https://api.telegram.org/bot${token}/setWebhook`,
  {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      url: webhookUrl,
      secret_token: secret,
      allowed_updates: ["message"],
    }),
  },
);
const result = await response.json();
if (!response.ok || !result.ok) {
  throw new Error(
    `Telegram setWebhook failed (${response.status}): ${result.description ?? "unknown error"}`,
  );
}
console.log(`Telegram webhook configured: ${webhookUrl}`);
