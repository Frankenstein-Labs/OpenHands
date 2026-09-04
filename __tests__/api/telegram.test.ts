import { afterEach, describe, expect, it, vi } from "vitest";
import handler, { processTelegramUpdate } from "../../api/telegram";

type FetchMock = ReturnType<typeof vi.fn>;

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function update(text: string) {
  return {
    update_id: 1,
    message: { chat: { id: 12345 }, text },
  };
}

function configureEnvironment() {
  vi.stubEnv("TELEGRAM_BOT_TOKEN", "telegram-token");
  vi.stubEnv("TELEGRAM_WEBHOOK_SECRET", "telegram-secret");
  vi.stubEnv("TELEGRAM_ALLOWED_CHAT_ID", "12345");
  vi.stubEnv("OPENHANDS_CLOUD_API_KEY", "openhands-key");
  vi.stubEnv("OPENHANDS_CLOUD_HOST", "https://cloud.example.test");
  vi.stubEnv("OPENHANDS_REPOSITORY", "Frankenstein-dev197/OpenHands");
  vi.stubEnv("OPENHANDS_POLL_INTERVAL_MS", "0");
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

describe("Telegram webhook", () => {
  it("rejects requests without the Telegram secret", async () => {
    configureEnvironment();
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const json = vi.fn();
    const end = vi.fn();
    const res = { status: vi.fn().mockReturnThis(), json, end };

    await handler({ method: "POST", headers: {}, body: update("/start") }, res);

    expect(res.status).toHaveBeenCalledWith(401);
    expect(json).toHaveBeenCalledWith({ ok: false, error: "Unauthorized" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("does not process updates when no allowed chat is configured", async () => {
    configureEnvironment();
    vi.stubEnv("TELEGRAM_ALLOWED_CHAT_ID", "");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await processTelegramUpdate(update("Analyse le repository"));

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("creates a Cloud conversation and sends its assistant response to Telegram", async () => {
    configureEnvironment();
    const fetchMock: FetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.includes("api.telegram.org"))
          return response({ ok: true, result: {} });
        if (url.includes("/api/v1/app-conversations/search")) {
          return response({ items: [], next_page_id: null });
        }
        if (url.endsWith("/api/v1/app-conversations")) {
          expect(init?.method).toBe("POST");
          const body = JSON.parse(String(init?.body));
          expect(body.selected_repository).toBe(
            "Frankenstein-dev197/OpenHands",
          );
          expect(body.initial_message.content[0].text).toBe(
            "Analyse le repository",
          );
          return response({
            id: "start-1",
            status: "READY",
            app_conversation_id: "conversation-1",
          });
        }
        if (url.includes("/api/v1/app-conversations?ids=conversation-1")) {
          return response([
            { id: "conversation-1", execution_status: "finished" },
          ]);
        }
        if (url.includes("/api/v1/conversation/conversation-1/events/search")) {
          return response({
            items: [
              {
                id: "assistant-1",
                kind: "MessageEvent",
                llm_message: {
                  role: "assistant",
                  content: [{ type: "text", text: "Analyse terminée." }],
                },
              },
            ],
          });
        }
        throw new Error(`Unexpected URL: ${url}`);
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    await processTelegramUpdate(update("Analyse le repository"));

    const telegramCalls = fetchMock.mock.calls.filter(([input]) =>
      String(input).includes("api.telegram.org"),
    );
    expect(telegramCalls).toHaveLength(2);
    expect(JSON.parse(String(telegramCalls[1][1]?.body))).toMatchObject({
      chat_id: "12345",
      text: "Analyse terminée.",
    });
  });

  it("uses the existing Cloud conversation for a follow-up message", async () => {
    configureEnvironment();
    const fetchMock: FetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.includes("api.telegram.org"))
          return response({ ok: true, result: {} });
        if (url.includes("/api/v1/app-conversations/search")) {
          return response({
            items: [
              {
                id: "conversation-1",
                title: "Telegram chat 12345",
                sandbox_id: "sandbox-1",
                execution_status: "idle",
                sandbox_status: "RUNNING",
              },
            ],
            next_page_id: null,
          });
        }
        if (url.includes("/api/v1/conversation/conversation-1/events/search")) {
          if (init?.method === "POST") throw new Error("Unexpected POST");
          const calls = fetchMock.mock.calls.filter(([item]) =>
            String(item).includes(
              "/api/v1/conversation/conversation-1/events/search",
            ),
          );
          return response({
            items:
              calls.length === 1
                ? [
                    {
                      id: "old-assistant",
                      kind: "MessageEvent",
                      llm_message: {
                        role: "assistant",
                        content: [{ type: "text", text: "Ancienne réponse." }],
                      },
                    },
                  ]
                : [
                    {
                      id: "new-assistant",
                      kind: "MessageEvent",
                      llm_message: {
                        role: "assistant",
                        content: [{ type: "text", text: "Nouvelle réponse." }],
                      },
                    },
                  ],
          });
        }
        if (
          url.includes("/api/v1/app-conversations/conversation-1/send-message")
        ) {
          expect(init?.method).toBe("POST");
          expect(JSON.parse(String(init?.body))).toMatchObject({
            role: "user",
            run: true,
          });
          return response({ success: true, sandbox_status: "RUNNING" });
        }
        if (url.includes("/api/v1/app-conversations?ids=conversation-1")) {
          return response([
            { id: "conversation-1", execution_status: "finished" },
          ]);
        }
        throw new Error(`Unexpected URL: ${url}`);
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    await processTelegramUpdate(update("Corrige le problème"));

    const telegramCalls = fetchMock.mock.calls.filter(([input]) =>
      String(input).includes("api.telegram.org"),
    );
    expect(JSON.parse(String(telegramCalls[1][1]?.body))).toMatchObject({
      text: "Nouvelle réponse.",
    });
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).includes(
          "/api/v1/app-conversations/conversation-1/send-message",
        ),
      ),
    ).toBe(true);
  });
});
