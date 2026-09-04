import { waitUntil } from "@vercel/functions";

const DEFAULT_CLOUD_HOST = "https://app.all-hands.dev";
const DEFAULT_REPOSITORY = "Frankenstein-dev197/OpenHands";
const TELEGRAM_MESSAGE_LIMIT = 4096;
const DEFAULT_POLL_INTERVAL_MS = 2_000;
const DEFAULT_START_TIMEOUT_MS = 120_000;
// Below Vercel's 300s maxDuration so the task timeout error can reach Telegram.
const DEFAULT_TASK_TIMEOUT_MS = 240_000;

type HeaderValue = string | string[] | undefined;

export interface TelegramRequest {
  method?: string;
  headers: Record<string, HeaderValue>;
  body?: unknown;
}

export interface TelegramResponse {
  status(code: number): TelegramResponse;
  json(body: unknown): TelegramResponse;
  end(): TelegramResponse;
}

interface TelegramUpdate {
  update_id?: number;
  message?: {
    chat?: { id?: number | string };
    text?: string;
  };
}

interface CloudStartTask {
  id: string;
  status: string;
  detail?: string | null;
  app_conversation_id?: string | null;
}

interface CloudConversation {
  id: string;
  title?: string | null;
  execution_status?: string | null;
  sandbox_status?: string | null;
  sandbox_id?: string | null;
}

interface CloudEvent {
  id?: string;
  kind?: string;
  llm_message?: {
    role?: string;
    content?: Array<{ type?: string; text?: string }>;
  };
}

interface CloudEventPage {
  items?: CloudEvent[];
  next_page_id?: string | null;
}

interface TelegramApiResponse<T = unknown> {
  ok: boolean;
  result?: T;
  description?: string;
}

function env(name: string): string | undefined {
  const serverProcess = (
    globalThis as {
      process?: { env?: Record<string, string | undefined> };
    }
  ).process;
  return serverProcess?.env?.[name]?.trim() || undefined;
}

function requiredEnv(name: string): string {
  const value = env(name);
  if (!value) throw new Error(`Missing required server configuration: ${name}`);
  return value;
}

function pollIntervalMs(): number {
  const value = Number(env("OPENHANDS_POLL_INTERVAL_MS"));
  return Number.isFinite(value) && value >= 0
    ? value
    : DEFAULT_POLL_INTERVAL_MS;
}

function cloudHost(): string {
  return (env("OPENHANDS_CLOUD_HOST") ?? DEFAULT_CLOUD_HOST).replace(
    /\/+$/,
    "",
  );
}

function repository(): string {
  return env("OPENHANDS_REPOSITORY") ?? DEFAULT_REPOSITORY;
}

function allowedChatId(): string | undefined {
  return env("TELEGRAM_ALLOWED_CHAT_ID");
}

function isAllowedChatId(chatId: string): boolean {
  const configuredChatId = allowedChatId();
  return Boolean(configuredChatId && configuredChatId === chatId);
}

function headerValue(
  request: TelegramRequest,
  name: string,
): string | undefined {
  const value = Object.entries(request.headers ?? {}).find(
    ([key]) => key.toLowerCase() === name.toLowerCase(),
  )?.[1];
  return Array.isArray(value) ? value[0] : value;
}

function parseBody(body: unknown): TelegramUpdate | null {
  if (body && typeof body === "object") return body as TelegramUpdate;
  if (typeof body !== "string") return null;
  try {
    const parsed: unknown = JSON.parse(body);
    return parsed && typeof parsed === "object"
      ? (parsed as TelegramUpdate)
      : null;
  } catch {
    return null;
  }
}

function telegramChatId(update: TelegramUpdate): string | null {
  const value = update.message?.chat?.id;
  return value === undefined || value === null ? null : String(value);
}

function commandName(text: string): string | null {
  if (!text.startsWith("/")) return null;
  return text.trim().split(/\s+/, 1)[0].split("@", 1)[0].toLowerCase();
}

function taskText(text: string): string {
  return text.trim();
}

function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return "Unexpected integration error";
}

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

// Serialize per-chat processing so concurrent webhook invocations sharing this
// instance cannot race to create duplicate Cloud conversations. Concurrent
// requests routed to different Vercel isolates remain possible without a
// durable store.
const chatQueues = new Map<string, Promise<unknown>>();

async function runExclusive<T>(
  chatId: string,
  task: () => Promise<T>,
): Promise<T> {
  const previous = chatQueues.get(chatId) ?? Promise.resolve();
  let release: () => void = () => {};
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  const next = previous.catch(() => undefined).then(() => gate);
  chatQueues.set(chatId, next);
  await previous.catch(() => undefined);
  try {
    return await task();
  } finally {
    release();
    if (chatQueues.get(chatId) === next) chatQueues.delete(chatId);
  }
}

async function telegramApi<T>(
  method: string,
  body: Record<string, unknown>,
): Promise<T> {
  const token = requiredEnv("TELEGRAM_BOT_TOKEN");
  const response = await fetch(
    `https://api.telegram.org/bot${token}/${method}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  let payload: TelegramApiResponse<T> | null = null;
  try {
    payload = (await response.json()) as TelegramApiResponse<T>;
  } catch {
    payload = null;
  }
  if (!response.ok || !payload?.ok) {
    throw new Error(
      `Telegram API request failed (${response.status}): ${payload?.description ?? "unknown error"}`,
    );
  }
  return payload.result as T;
}

function messageChunks(text: string): string[] {
  const chunks: string[] = [];
  for (let index = 0; index < text.length; index += TELEGRAM_MESSAGE_LIMIT) {
    chunks.push(text.slice(index, index + TELEGRAM_MESSAGE_LIMIT));
  }
  return chunks.length > 0 ? chunks : [""];
}

async function sendTelegramMessage(
  chatId: string,
  text: string,
): Promise<void> {
  for (const chunk of messageChunks(text)) {
    await telegramApi("sendMessage", { chat_id: chatId, text: chunk });
  }
}

function openHandsHeaders(): Record<string, string> {
  const apiKey = requiredEnv("OPENHANDS_CLOUD_API_KEY");
  // OpenHands Cloud documents Authorization: Bearer for Cloud API calls. The
  // X-Access-Token header is also accepted by the current API reference and
  // keeps this gateway compatible with both deployed auth handlers.
  return {
    Authorization: `Bearer ${apiKey}`,
    "X-Access-Token": apiKey,
    "Content-Type": "application/json",
  };
}

class OpenHandsError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "OpenHandsError";
    this.status = status;
  }
}

async function openHandsRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${cloudHost()}${path}`, {
    ...init,
    headers: { ...openHandsHeaders(), ...(init.headers ?? {}) },
  });
  const text = await response.text();
  let payload: unknown = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = text;
  }
  if (!response.ok) {
    const detail =
      typeof payload === "object" && payload !== null && "detail" in payload
        ? String((payload as { detail?: unknown }).detail)
        : `HTTP ${response.status}`;
    throw new OpenHandsError(
      `OpenHands Cloud request failed (${response.status}): ${detail.slice(0, 400)}`,
      response.status,
    );
  }
  return payload as T;
}

function encodeQuery(value: string): string {
  return encodeURIComponent(value);
}

async function searchTelegramConversation(
  chatId: string,
): Promise<CloudConversation | null> {
  let pageId: string | undefined;
  const seenCursors = new Set<string>();
  do {
    if (pageId) {
      if (seenCursors.has(pageId)) {
        throw new Error(
          "OpenHands Cloud conversations search repeated a page cursor",
        );
      }
      seenCursors.add(pageId);
    }
    const query = new URLSearchParams({
      limit: "100",
      sort_order: "UPDATED_AT_DESC",
    });
    if (pageId) query.set("page_id", pageId);
    const page = await openHandsRequest<{
      items?: CloudConversation[];
      next_page_id?: string | null;
    }>(`/api/v1/app-conversations/search?${query.toString()}`);
    const match = (page.items ?? []).find(
      (conversation) => conversation.title === `Telegram chat ${chatId}`,
    );
    if (match) return match;
    pageId = page.next_page_id ?? undefined;
  } while (pageId);
  return null;
}

async function getConversation(
  conversationId: string,
): Promise<CloudConversation | null> {
  const result = await openHandsRequest<CloudConversation[]>(
    `/api/v1/app-conversations?ids=${encodeQuery(conversationId)}`,
  );
  return result[0] ?? null;
}

async function getEvents(conversationId: string): Promise<CloudEvent[]> {
  const page = await openHandsRequest<CloudEventPage>(
    `/api/v1/conversation/${encodeQuery(conversationId)}/events/search?limit=100&sort_order=TIMESTAMP_DESC`,
  );
  return page.items ?? [];
}

function assistantText(
  events: CloudEvent[],
  excludedIds: Set<string>,
): string | null {
  for (const event of events) {
    if (
      event.kind !== "MessageEvent" ||
      event.llm_message?.role !== "assistant" ||
      (event.id && excludedIds.has(event.id))
    ) {
      continue;
    }
    const text = (event.llm_message.content ?? [])
      .filter(
        (block) => block.type === "text" && typeof block.text === "string",
      )
      .map((block) => block.text ?? "")
      .join("\n")
      .trim();
    if (text) return text;
  }
  return null;
}

function terminalStatus(status: string | null | undefined): boolean {
  return ["finished", "error", "stuck", "waiting_for_confirmation"].includes(
    status ?? "",
  );
}

async function waitForStartTask(task: CloudStartTask): Promise<string> {
  if (task.status === "READY" && task.app_conversation_id) {
    return task.app_conversation_id;
  }
  if (task.status === "ERROR") {
    throw new Error(
      task.detail || "OpenHands Cloud could not start the conversation",
    );
  }

  const deadline = Date.now() + DEFAULT_START_TIMEOUT_MS;
  while (Date.now() < deadline) {
    await delay(pollIntervalMs());
    const result = await openHandsRequest<CloudStartTask[] | CloudStartTask>(
      `/api/v1/app-conversations/start-tasks?ids=${encodeQuery(task.id)}`,
    );
    const current = Array.isArray(result) ? result[0] : result;
    if (!current) continue;
    if (current.status === "READY" && current.app_conversation_id) {
      return current.app_conversation_id;
    }
    if (current.status === "ERROR") {
      throw new Error(
        current.detail || "OpenHands Cloud could not start the conversation",
      );
    }
  }
  throw new Error("OpenHands Cloud conversation startup timed out");
}

async function createConversation(
  chatId: string,
  initialMessage: string | null,
): Promise<string> {
  const body: Record<string, unknown> = {
    initial_message: initialMessage
      ? {
          role: "user",
          content: [{ type: "text", text: initialMessage }],
        }
      : null,
    selected_repository: repository(),
    title: `Telegram chat ${chatId}`,
  };
  const task = await openHandsRequest<CloudStartTask>(
    "/api/v1/app-conversations",
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
  return waitForStartTask(task);
}

async function existingAssistantIds(
  conversationId: string,
): Promise<Set<string>> {
  const events = await getEvents(conversationId);
  return new Set(
    events
      .filter(
        (event) =>
          event.kind === "MessageEvent" &&
          event.llm_message?.role === "assistant",
      )
      .map((event) => event.id)
      .filter((id): id is string => Boolean(id)),
  );
}

async function sendToConversation(
  conversationId: string,
  conversation: CloudConversation | null,
  message: string,
): Promise<void> {
  try {
    const result = await openHandsRequest<{ success?: boolean }>(
      `/api/v1/app-conversations/${encodeQuery(conversationId)}/send-message`,
      {
        method: "POST",
        body: JSON.stringify({
          role: "user",
          content: [{ type: "text", text: message }],
          run: true,
        }),
      },
    );
    if (result.success === false)
      throw new Error("OpenHands Cloud rejected the message");
  } catch (error) {
    // A paused Cloud sandbox is explicitly resumed before retrying, matching
    // the documented send-message contract (HTTP 409 only). Check the numeric
    // status instead of the message text so a 5xx whose detail contains "409"
    // does not trigger an unnecessary resume and retry.
    if (!(error instanceof OpenHandsError) || error.status !== 409) throw error;
    const sandboxId = conversation?.sandbox_id;
    if (!sandboxId) throw error;
    await openHandsRequest(
      `/api/v1/sandboxes/${encodeQuery(sandboxId)}/resume`,
      {
        method: "POST",
        body: JSON.stringify({}),
      },
    );
    await openHandsRequest(
      `/api/v1/app-conversations/${encodeQuery(conversationId)}/send-message`,
      {
        method: "POST",
        body: JSON.stringify({
          role: "user",
          content: [{ type: "text", text: message }],
          run: true,
        }),
      },
    );
  }
}

async function waitForAgentResult(
  conversationId: string,
  excludedIds: Set<string>,
): Promise<string> {
  const deadline = Date.now() + DEFAULT_TASK_TIMEOUT_MS;
  while (Date.now() < deadline) {
    const [conversation, events] = await Promise.all([
      getConversation(conversationId),
      getEvents(conversationId),
    ]);
    const response = assistantText(events, excludedIds);
    if (response) return response;

    if (conversation?.execution_status === "error") {
      throw new Error("OpenHands Cloud reported an agent error");
    }
    if (conversation?.execution_status === "stuck") {
      throw new Error("OpenHands Cloud reported that the agent is stuck");
    }
    if (conversation?.execution_status === "waiting_for_confirmation") {
      return "L’agent attend une confirmation dans OpenHands Cloud avant de poursuivre.";
    }
    if (terminalStatus(conversation?.execution_status)) {
      throw new Error("OpenHands Cloud finished without a text response");
    }
    await delay(pollIntervalMs());
  }
  throw new Error("OpenHands Cloud task timed out");
}

async function statusMessage(chatId: string): Promise<string> {
  const conversation = await searchTelegramConversation(chatId);
  if (!conversation)
    return "Aucune conversation OpenHands n’est encore associée à ce chat.";
  return [
    `Conversation : ${conversation.id}`,
    `Sandbox : ${conversation.sandbox_status ?? "inconnu"}`,
    `Agent : ${conversation.execution_status ?? "inconnu"}`,
  ].join("\n");
}

async function stopConversation(chatId: string): Promise<string> {
  const conversation = await searchTelegramConversation(chatId);
  if (!conversation?.sandbox_id) return "Aucune conversation active à arrêter.";
  await openHandsRequest(
    `/api/v1/sandboxes/${encodeQuery(conversation.sandbox_id)}/pause`,
    {
      method: "POST",
      body: JSON.stringify({}),
    },
  );
  return "La conversation OpenHands a été mise en pause.";
}

async function processMessage(chatId: string, text: string): Promise<void> {
  await runExclusive(chatId, () => processMessageSerial(chatId, text));
}

async function processMessageSerial(
  chatId: string,
  text: string,
): Promise<void> {
  const command = commandName(text);
  if (command === "/start") {
    await sendTelegramMessage(
      chatId,
      "🤖 OpenHands connecté.\n\nEnvoie-moi simplement la tâche que tu veux que l’agent exécute.",
    );
    return;
  }
  if (command === "/help") {
    await sendTelegramMessage(
      chatId,
      "/start — vérifier la connexion\n/help — afficher cette aide\n/new — démarrer une nouvelle conversation\n/status — voir l’état de la conversation\n/stop — mettre en pause l’agent",
    );
    return;
  }
  if (command === "/status") {
    await sendTelegramMessage(chatId, await statusMessage(chatId));
    return;
  }
  if (command === "/stop") {
    await sendTelegramMessage(chatId, await stopConversation(chatId));
    return;
  }
  if (command === "/new") {
    await createConversation(chatId, null);
    await sendTelegramMessage(
      chatId,
      "Nouvelle conversation OpenHands prête. Envoie ta tâche.",
    );
    return;
  }
  if (command) {
    await sendTelegramMessage(
      chatId,
      "Commande inconnue. Utilise /help pour voir les commandes disponibles.",
    );
    return;
  }

  const message = taskText(text);
  if (!message) return;

  await sendTelegramMessage(
    chatId,
    "Tâche reçue. OpenHands Cloud travaille dessus…",
  );
  const existing = await searchTelegramConversation(chatId);
  const conversationId = existing
    ? existing.id
    : await createConversation(chatId, message);
  const excludedIds = existing
    ? await existingAssistantIds(conversationId)
    : new Set<string>();
  if (existing) await sendToConversation(conversationId, existing, message);
  const result = await waitForAgentResult(conversationId, excludedIds);
  await sendTelegramMessage(chatId, result);
}

export async function processTelegramUpdate(
  update: TelegramUpdate,
): Promise<void> {
  const chatId = telegramChatId(update);
  const text = update.message?.text?.trim();
  if (!chatId || !text) return;
  if (!isAllowedChatId(chatId)) return;
  await processMessage(chatId, text);
}

export default async function handler(
  request: TelegramRequest,
  response: TelegramResponse,
): Promise<void> {
  if (request.method !== "POST") {
    response.status(405).json({ ok: false, error: "Method not allowed" });
    return;
  }

  const secret = requiredEnv("TELEGRAM_WEBHOOK_SECRET");
  if (headerValue(request, "x-telegram-bot-api-secret-token") !== secret) {
    response.status(401).json({ ok: false, error: "Unauthorized" });
    return;
  }

  const update = parseBody(request.body);
  if (!update) {
    response.status(400).json({ ok: false, error: "Invalid Telegram update" });
    return;
  }

  const chatId = telegramChatId(update);
  if (chatId && isAllowedChatId(chatId)) {
    waitUntil(
      processTelegramUpdate(update).catch(async (error: unknown) => {
        try {
          await sendTelegramMessage(
            chatId,
            `Erreur OpenHands : ${errorMessage(error)}`,
          );
        } catch {
          // Do not turn a successful Telegram webhook acknowledgement into a
          // retry storm if the outbound Telegram call also fails.
        }
      }),
    );
  }

  response.status(200).json({ ok: true });
}

export const maxDuration = 300;
