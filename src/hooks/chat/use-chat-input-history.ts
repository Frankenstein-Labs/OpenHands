import { useCallback, useEffect, useRef } from "react";

const MAX_CHAT_HISTORY_ENTRIES = 50;
const CHAT_HISTORY_STORAGE_PREFIX = "oh:chat-input-history:";

type HistoryDirection = "backward" | "forward";

const getStorageKey = (conversationId?: string | null): string =>
  `${CHAT_HISTORY_STORAGE_PREFIX}${conversationId || "home"}`;

const loadHistory = (storageKey: string): string[] => {
  if (typeof window === "undefined") return [];

  try {
    const stored = window.sessionStorage.getItem(storageKey);
    if (!stored) return [];

    const parsed: unknown = JSON.parse(stored);
    if (!Array.isArray(parsed)) return [];

    return parsed.filter(
      (entry): entry is string =>
        typeof entry === "string" && entry.trim().length > 0,
    );
  } catch {
    return [];
  }
};

const saveHistory = (storageKey: string, entries: string[]): void => {
  if (typeof window === "undefined") return;

  try {
    window.sessionStorage.setItem(storageKey, JSON.stringify(entries));
  } catch {
    // Storage can be unavailable in private browsing or constrained embeds.
  }
};

const getTextLength = (node: Node): number =>
  node.nodeType === Node.TEXT_NODE
    ? (node.textContent?.length ?? 0)
    : Array.from(node.childNodes).reduce(
        (length, child) => length + getTextLength(child),
        0,
      );

const getCursorOffset = (element: HTMLElement): number | null => {
  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0) return null;

  const range = selection.getRangeAt(0);
  if (!element.contains(range.startContainer)) return null;

  if (range.startContainer.nodeType === Node.TEXT_NODE) {
    let offset = 0;
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
    let currentNode = walker.nextNode();

    while (currentNode) {
      if (currentNode === range.startContainer) {
        return offset + range.startOffset;
      }
      offset += getTextLength(currentNode);
      currentNode = walker.nextNode();
    }

    return null;
  }

  if (range.startContainer === element) {
    return Array.from(element.childNodes)
      .slice(0, range.startOffset)
      .reduce((offset, child) => offset + getTextLength(child), 0);
  }

  return null;
};

const isCaretAtBoundary = (element: HTMLElement): boolean => {
  const text = element.innerText || "";
  if (text.includes("\n")) return false;

  const cursorOffset = getCursorOffset(element);
  if (cursorOffset === null) return false;

  // For a single-line chat prompt, both vertical arrows are history controls
  // when the caret is at either edge. A cursor in the middle must remain a
  // normal editing position. Multiline prompts deliberately keep both arrows.
  return cursorOffset === 0 || cursorOffset === text.length;
};

/**
 * Provides VS Code-like prompt history for the Chat input.
 *
 * History is scoped to the active conversation (or the home composer), kept in
 * sessionStorage, and only activates on a single-line input when the caret is
 * at the corresponding boundary. This preserves normal cursor navigation for
 * multiline prompts while allowing ArrowUp/ArrowDown to revisit submitted
 * prompts like the native Chat input.
 */
export const useChatInputHistory = (conversationId?: string | null) => {
  const storageKey = getStorageKey(conversationId);
  const historyRef = useRef<string[]>(loadHistory(storageKey));
  const historyIndexRef = useRef(-1);
  const draftBeforeHistoryRef = useRef("");
  const storageKeyRef = useRef(storageKey);

  useEffect(() => {
    if (storageKeyRef.current === storageKey) return;

    storageKeyRef.current = storageKey;
    historyRef.current = loadHistory(storageKey);
    historyIndexRef.current = -1;
    draftBeforeHistoryRef.current = "";
  }, [storageKey]);

  const record = useCallback((message: string) => {
    const normalized = message.trim();
    if (!normalized) return;

    const currentHistory = historyRef.current;
    const nextHistory =
      currentHistory.at(-1) === normalized
        ? currentHistory
        : [...currentHistory, normalized].slice(-MAX_CHAT_HISTORY_ENTRIES);

    historyRef.current = nextHistory;
    historyIndexRef.current = -1;
    draftBeforeHistoryRef.current = "";
    saveHistory(storageKeyRef.current, nextHistory);
  }, []);

  const navigate = useCallback(
    (
      element: HTMLElement | null,
      direction: HistoryDirection,
    ): string | undefined => {
      if (!element || !isCaretAtBoundary(element)) return undefined;

      const currentHistory = historyRef.current;
      if (currentHistory.length === 0) return undefined;

      const currentValue = element.innerText || "";
      let nextIndex = historyIndexRef.current;

      if (direction === "backward") {
        if (nextIndex === -1) {
          draftBeforeHistoryRef.current = currentValue;
          nextIndex = currentHistory.length - 1;
        } else {
          nextIndex = Math.max(0, nextIndex - 1);
        }
      } else {
        if (nextIndex === -1) return undefined;
        nextIndex += 1;
        if (nextIndex >= currentHistory.length) {
          historyIndexRef.current = -1;
          return draftBeforeHistoryRef.current;
        }
      }

      historyIndexRef.current = nextIndex;
      return currentHistory[nextIndex];
    },
    [],
  );

  const reset = useCallback(() => {
    historyIndexRef.current = -1;
    draftBeforeHistoryRef.current = "";
  }, []);

  return { record, navigate, reset };
};
