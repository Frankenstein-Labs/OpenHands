import { beforeEach, describe, expect, it } from "vitest";

import {
  acquireChildConversationLaunchSlot,
  CHILD_CONVERSATION_LAUNCH_LIMITS,
  resetChildConversationLaunchLimiterForTests,
} from "#/services/child-conversation-launch-limiter";

const PARENT_ID = "parent-conversation";
const NOW = 1_000_000;

const acquire = (isolation: "worktree" | "shared" = "worktree") =>
  acquireChildConversationLaunchSlot(PARENT_ID, isolation, NOW);

describe("child conversation launch limiter", () => {
  beforeEach(() => {
    resetChildConversationLaunchLimiterForTests();
  });

  it("allows the configured number of concurrent launches and rejects the next one", () => {
    const leases = Array.from(
      { length: CHILD_CONVERSATION_LAUNCH_LIMITS.maxConcurrentLaunches },
      () => acquire(),
    );

    expect(leases.every((decision) => decision.ok)).toBe(true);

    const rejected = acquire();
    expect(rejected).toMatchObject({
      ok: false,
      reason: "concurrency",
    });

    for (const decision of leases) {
      if (decision.ok) decision.release();
    }

    expect(acquire()).toMatchObject({ ok: true });
  });

  it("allows only one shared-workspace launch at a time", () => {
    const first = acquire("shared");
    expect(first).toMatchObject({ ok: true });

    const second = acquire("shared");
    expect(second).toMatchObject({
      ok: false,
      reason: "shared_isolation",
    });

    if (first.ok) first.release();
    expect(acquire("shared")).toMatchObject({ ok: true });
  });

  it("keeps independent worktree launches available beside a shared launch", () => {
    const shared = acquire("shared");
    const worktree = acquire("worktree");

    expect(shared).toMatchObject({ ok: true });
    expect(worktree).toMatchObject({ ok: true });

    if (shared.ok) shared.release();
    if (worktree.ok) worktree.release();
  });

  it("bounds fan-out over the configured time window", () => {
    for (
      let index = 0;
      index < CHILD_CONVERSATION_LAUNCH_LIMITS.maxLaunchesPerWindow;
      index += 1
    ) {
      const decision = acquire();
      expect(decision).toMatchObject({ ok: true });
      if (decision.ok) decision.release();
    }

    expect(acquire()).toMatchObject({
      ok: false,
      reason: "rate_limit",
    });

    expect(
      acquireChildConversationLaunchSlot(
        PARENT_ID,
        "worktree",
        NOW + CHILD_CONVERSATION_LAUNCH_LIMITS.launchWindowMs + 1,
      ),
    ).toMatchObject({ ok: true });
  });

  it("makes releasing a lease idempotent", () => {
    const first = acquire();
    expect(first).toMatchObject({ ok: true });

    if (first.ok) {
      first.release();
      first.release();
    }

    const leases = Array.from(
      { length: CHILD_CONVERSATION_LAUNCH_LIMITS.maxConcurrentLaunches },
      () => acquire(),
    );
    expect(leases.every((decision) => decision.ok)).toBe(true);
    for (const decision of leases) {
      if (decision.ok) decision.release();
    }
  });
});
