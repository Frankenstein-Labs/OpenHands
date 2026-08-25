import { describe, expect, it, vi } from "vitest";
import {
  MonoWriterError,
  MonoWriterIntegrationQueue,
} from "../../src/services/mono-writer-integration";

describe("MonoWriterIntegrationQueue", () => {
  it("serializes writers and advances the canonical commit", async () => {
    const queue = new MonoWriterIntegrationQueue("base", ["src"]);
    const calls: string[] = [];
    const integrate = vi.fn(async (proposal, token) => {
      calls.push(`${proposal.id}:${token}`);
      return `${proposal.commitSha}-integrated`;
    });

    const first = queue.enqueue(
      {
        id: "one",
        baseCommit: "base",
        commitSha: "a",
        changedPaths: ["src/a.ts"],
      },
      integrate,
    );
    await expect(first).resolves.toMatchObject({
      fencingToken: 1,
      canonicalCommit: "a-integrated",
    });
    await expect(
      queue.enqueue(
        {
          id: "two",
          baseCommit: "a-integrated",
          commitSha: "b",
          changedPaths: ["src/b.ts"],
        },
        integrate,
      ),
    ).resolves.toMatchObject({
      fencingToken: 2,
      canonicalCommit: "b-integrated",
    });
    expect(calls).toEqual(["one:1", "two:2"]);
  });

  it("rejects stale bases, forbidden paths and duplicate commits", async () => {
    const queue = new MonoWriterIntegrationQueue("base", ["src"]);
    const integrate = vi.fn(async () => "next");
    await expect(
      queue.enqueue(
        {
          id: "stale",
          baseCommit: "old",
          commitSha: "a",
          changedPaths: ["src/a.ts"],
        },
        integrate,
      ),
    ).rejects.toThrow(MonoWriterError);
    await expect(
      queue.enqueue(
        {
          id: "forbidden",
          baseCommit: "base",
          commitSha: "b",
          changedPaths: ["README.md"],
        },
        integrate,
      ),
    ).rejects.toThrow("forbidden");
    await expect(
      queue.enqueue(
        {
          id: "ok",
          baseCommit: "base",
          commitSha: "c",
          changedPaths: ["src/c.ts"],
        },
        integrate,
      ),
    ).resolves.toBeTruthy();
    await expect(
      queue.enqueue(
        {
          id: "duplicate",
          baseCommit: "next",
          commitSha: "c",
          changedPaths: ["src/c.ts"],
        },
        integrate,
      ),
    ).rejects.toThrow("already integrated");
  });

  it("rejects overlapping active paths and issues unique fencing tokens", async () => {
    const queue = new MonoWriterIntegrationQueue("base");
    let release!: () => void;
    const blocked = new Promise<void>((resolve) => {
      release = resolve;
    });
    const first = queue.enqueue(
      {
        id: "one",
        baseCommit: "base",
        commitSha: "a",
        changedPaths: ["src/shared.ts"],
      },
      async () => {
        await blocked;
        return "a1";
      },
    );
    const second = queue.enqueue(
      {
        id: "two",
        baseCommit: "base",
        commitSha: "b",
        changedPaths: ["src/shared.ts"],
      },
      async () => "b1",
    );
    release();
    await expect(first).resolves.toMatchObject({ fencingToken: 1 });
    await expect(second).rejects.toThrow("stale");
  });
});
