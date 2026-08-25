import { isTaskConversationId } from "#/utils/conversation-local-storage";

export const CONVERSATION_RESUME_STORAGE_KEY =
  "openhands-conversation-resume-state";
const MAX_PERSISTED_CONVERSATIONS = 200;

export interface ConversationResumeState {
  /** Latest durable event already observed for this conversation. */
  lastEventId: string | number | null;
  lastEventTimestamp: string | null;
  /** Best-effort UI position; conversation content remains server-authoritative. */
  lastReadScrollTop: number | null;
  updatedAt: string | null;
}

const DEFAULT_RESUME_STATE: ConversationResumeState = {
  lastEventId: null,
  lastEventTimestamp: null,
  lastReadScrollTop: null,
  updatedAt: null,
};

type ResumeStateMap = Record<string, ConversationResumeState>;

const canPersist = (conversationId: string): boolean =>
  conversationId.length > 0 && !isTaskConversationId(conversationId);

const readAll = (): ResumeStateMap => {
  if (typeof localStorage === "undefined") return {};

  try {
    const raw = localStorage.getItem(CONVERSATION_RESUME_STORAGE_KEY);
    if (!raw) return {};
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return {};
    }

    const result: ResumeStateMap = {};
    for (const [conversationId, value] of Object.entries(
      parsed as Record<string, unknown>,
    )) {
      if (!value || typeof value !== "object" || Array.isArray(value)) {
        continue;
      }
      const candidate = value as Record<string, unknown>;
      result[conversationId] = {
        lastEventId:
          typeof candidate.lastEventId === "string" ||
          typeof candidate.lastEventId === "number"
            ? candidate.lastEventId
            : null,
        lastEventTimestamp:
          typeof candidate.lastEventTimestamp === "string"
            ? candidate.lastEventTimestamp
            : null,
        lastReadScrollTop:
          typeof candidate.lastReadScrollTop === "number" &&
          Number.isFinite(candidate.lastReadScrollTop) &&
          candidate.lastReadScrollTop >= 0
            ? candidate.lastReadScrollTop
            : null,
        updatedAt:
          typeof candidate.updatedAt === "string" ? candidate.updatedAt : null,
      };
    }
    return result;
  } catch {
    return {};
  }
};

const writeAll = (state: ResumeStateMap): void => {
  if (typeof localStorage === "undefined") return;

  try {
    localStorage.setItem(
      CONVERSATION_RESUME_STORAGE_KEY,
      JSON.stringify(state),
    );
  } catch (error) {
    console.warn("Failed to persist conversation resume state", error);
  }
};

export function getConversationResumeState(
  conversationId: string,
): ConversationResumeState {
  if (!canPersist(conversationId)) return { ...DEFAULT_RESUME_STATE };
  return { ...DEFAULT_RESUME_STATE, ...(readAll()[conversationId] ?? {}) };
}

export function setConversationResumeState(
  conversationId: string,
  updates: Partial<ConversationResumeState>,
): void {
  if (!canPersist(conversationId)) return;

  const all = readAll();
  const current = getConversationResumeState(conversationId);
  all[conversationId] = {
    ...current,
    ...updates,
    updatedAt: new Date().toISOString(),
  };

  const retainedEntries = Object.entries(all)
    .sort(([, left], [, right]) =>
      (left.updatedAt ?? "").localeCompare(right.updatedAt ?? ""),
    )
    .slice(-MAX_PERSISTED_CONVERSATIONS);
  writeAll(Object.fromEntries(retainedEntries));
}

/**
 * Advance the durable replay cursor only when the event is newer than the
 * cursor already stored. Streaming deltas are intentionally excluded by the
 * caller because they are transient UI updates rather than durable events.
 */
export function rememberConversationEvent(
  conversationId: string,
  eventId: string | number | undefined,
  timestamp: string | undefined,
): void {
  if (!timestamp || !canPersist(conversationId)) return;

  const current = getConversationResumeState(conversationId);
  if (current.lastEventTimestamp && timestamp <= current.lastEventTimestamp) {
    return;
  }

  setConversationResumeState(conversationId, {
    lastEventId: eventId ?? null,
    lastEventTimestamp: timestamp,
  });
}

export function setConversationReadPosition(
  conversationId: string,
  scrollTop: number,
): void {
  if (!Number.isFinite(scrollTop) || scrollTop < 0) return;
  setConversationResumeState(conversationId, {
    lastReadScrollTop: scrollTop,
  });
}

export function clearConversationResumeState(conversationId: string): void {
  if (!canPersist(conversationId) || typeof localStorage === "undefined") {
    return;
  }

  const all = readAll();
  delete all[conversationId];
  writeAll(all);
}
