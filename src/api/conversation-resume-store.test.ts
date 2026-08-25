import { beforeEach, describe, expect, it } from "vitest";
import {
  clearConversationResumeState,
  getConversationResumeState,
  rememberConversationEvent,
  setConversationReadPosition,
  setConversationResumeState,
} from "./conversation-resume-store";

describe("conversation resume store", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("persists the replay cursor and read position per conversation", () => {
    setConversationResumeState("conv-a", {
      lastEventId: "event-2",
      lastEventTimestamp: "2026-08-25T10:00:00.000Z",
    });
    setConversationReadPosition("conv-a", 420);

    expect(getConversationResumeState("conv-a")).toMatchObject({
      lastEventId: "event-2",
      lastEventTimestamp: "2026-08-25T10:00:00.000Z",
      lastReadScrollTop: 420,
    });
    expect(getConversationResumeState("conv-b")).toMatchObject({
      lastEventId: null,
      lastEventTimestamp: null,
      lastReadScrollTop: null,
    });
  });

  it("only advances the cursor for newer events", () => {
    rememberConversationEvent("conv-a", "event-2", "2026-08-25T10:00:00.000Z");
    rememberConversationEvent("conv-a", "event-1", "2026-08-25T09:00:00.000Z");

    expect(getConversationResumeState("conv-a")).toMatchObject({
      lastEventId: "event-2",
      lastEventTimestamp: "2026-08-25T10:00:00.000Z",
    });
  });

  it("does not persist provisional task conversation ids", () => {
    setConversationResumeState("task-abc", {
      lastEventId: "event-1",
      lastEventTimestamp: "2026-08-25T10:00:00.000Z",
    });
    setConversationReadPosition("task-abc", 100);

    expect(getConversationResumeState("task-abc").lastEventId).toBeNull();
    expect(localStorage.length).toBe(0);
  });

  it("can clear one conversation without affecting another", () => {
    setConversationResumeState("conv-a", { lastEventId: "a" });
    setConversationResumeState("conv-b", { lastEventId: "b" });

    clearConversationResumeState("conv-a");

    expect(getConversationResumeState("conv-a").lastEventId).toBeNull();
    expect(getConversationResumeState("conv-b").lastEventId).toBe("b");
  });
});
