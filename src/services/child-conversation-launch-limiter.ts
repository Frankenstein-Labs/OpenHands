/**
 * Process-local guardrails for child-conversation fan-out.
 *
 * Child conversations are real agent-server or Cloud sessions. Starting too
 * many of them at once can multiply model calls and, for shared children, can
 * create concurrent writers in the same workspace. This limiter protects the
 * launch boundary while the sessions are being provisioned. It deliberately
 * does not pretend to be a durable global scheduler: cross-tab and server-side
 * active-worker accounting belongs in a future backend orchestration service.
 */

export const CHILD_CONVERSATION_LAUNCH_LIMITS = {
  /** Maximum number of child starts being provisioned for one parent. */
  maxConcurrentLaunches: 4,
  /** Shared children are allowed one at a time because they share files. */
  maxConcurrentSharedLaunches: 1,
  /** Prevent unbounded fan-out over a short period. */
  maxLaunchesPerWindow: 8,
  launchWindowMs: 60_000,
} as const;

type Isolation = "worktree" | "shared";

type ParentState = {
  inFlight: number;
  sharedInFlight: number;
  startedAt: number[];
};

const stateByParent = new Map<string, ParentState>();

const getParentState = (parentConversationId: string): ParentState => {
  const existing = stateByParent.get(parentConversationId);
  if (existing) return existing;

  const created: ParentState = {
    inFlight: 0,
    sharedInFlight: 0,
    startedAt: [],
  };
  stateByParent.set(parentConversationId, created);
  return created;
};

const pruneWindow = (state: ParentState, now: number) => {
  const cutoff = now - CHILD_CONVERSATION_LAUNCH_LIMITS.launchWindowMs;
  state.startedAt = state.startedAt.filter((startedAt) => startedAt > cutoff);
};

export type ChildConversationLaunchLimitFailure = {
  ok: false;
  reason: "concurrency" | "shared_isolation" | "rate_limit";
  guidance: string;
};

export type ChildConversationLaunchLease = {
  ok: true;
  release: () => void;
};

export type ChildConversationLaunchDecision =
  | ChildConversationLaunchLease
  | ChildConversationLaunchLimitFailure;

/**
 * Claim a bounded launch slot. The returned lease must be released in a
 * finally block after the real child start request settles.
 */
export function acquireChildConversationLaunchSlot(
  parentConversationId: string,
  isolation: Isolation,
  now = Date.now(),
): ChildConversationLaunchDecision {
  const state = getParentState(parentConversationId);
  pruneWindow(state, now);

  if (
    state.startedAt.length >=
    CHILD_CONVERSATION_LAUNCH_LIMITS.maxLaunchesPerWindow
  ) {
    return {
      ok: false,
      reason: "rate_limit",
      guidance: `This parent has already started ${CHILD_CONVERSATION_LAUNCH_LIMITS.maxLaunchesPerWindow} child conversations within ${CHILD_CONVERSATION_LAUNCH_LIMITS.launchWindowMs / 1000} seconds. Wait for the current workers to settle before delegating more work.`,
    };
  }

  if (
    state.inFlight >= CHILD_CONVERSATION_LAUNCH_LIMITS.maxConcurrentLaunches
  ) {
    return {
      ok: false,
      reason: "concurrency",
      guidance: `At most ${CHILD_CONVERSATION_LAUNCH_LIMITS.maxConcurrentLaunches} child conversations can be provisioned at once for this parent. Wait for a launch result before starting another child.`,
    };
  }

  if (
    isolation === "shared" &&
    state.sharedInFlight >=
      CHILD_CONVERSATION_LAUNCH_LIMITS.maxConcurrentSharedLaunches
  ) {
    return {
      ok: false,
      reason: "shared_isolation",
      guidance:
        'Only one shared-workspace child can be provisioned at a time. Prefer isolation="worktree" for independent writers, or wait for the shared child launch to finish.',
    };
  }

  state.inFlight += 1;
  if (isolation === "shared") state.sharedInFlight += 1;
  state.startedAt.push(now);

  let released = false;
  return {
    ok: true,
    release: () => {
      if (released) return;
      released = true;
      state.inFlight = Math.max(0, state.inFlight - 1);
      if (isolation === "shared") {
        state.sharedInFlight = Math.max(0, state.sharedInFlight - 1);
      }
      if (
        state.inFlight === 0 &&
        state.sharedInFlight === 0 &&
        state.startedAt.length === 0
      ) {
        // Recent timestamps must survive release so the rate window remains
        // effective. The next acquire prunes expired entries using its clock.
        stateByParent.delete(parentConversationId);
      }
    },
  };
}

/** Test-only reset; production code never needs to clear the limiter. */
export function resetChildConversationLaunchLimiterForTests() {
  stateByParent.clear();
}
