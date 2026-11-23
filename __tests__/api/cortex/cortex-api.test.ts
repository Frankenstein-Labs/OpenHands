import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  CortexApiError,
  cortexFetch,
  getSessionSnapshot,
  signIn,
  signOut,
} from "#/api/cortex/cortex-api";

const fetchMock = vi.fn();

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function authPayload(overrides: Record<string, unknown> = {}) {
  return {
    access_token: "access-1",
    refresh_token: "refresh-1",
    expires_in: 3600,
    user: { id: "user-1", email: "user@example.com" },
    ...overrides,
  };
}

describe("cortex API client", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_CORTEX_API_URL", "http://api.test");
    vi.stubEnv("VITE_SUPABASE_URL", "http://auth.test");
    vi.stubEnv("VITE_SUPABASE_ANON_KEY", "anon-key");
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockReset();
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("stores the session after sign-in and sends it to the API", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(authPayload()));
    await signIn("user@example.com", "password");

    expect(getSessionSnapshot()?.email).toBe("user@example.com");

    fetchMock.mockResolvedValueOnce(jsonResponse([{ id: "org-1" }]));
    const organizations = await cortexFetch<{ id: string }[]>(
      "/api/v1/organizations",
      { orgId: "org-1" },
    );

    expect(organizations).toEqual([{ id: "org-1" }]);
    const [url, init] = fetchMock.mock.calls[1];
    expect(String(url)).toBe(
      "http://api.test/api/v1/organizations?organization_id=org-1",
    );
    expect((init as RequestInit).headers).toMatchObject({
      Authorization: "Bearer access-1",
    });
  });

  it("refreshes once on 401 and retries the request", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(authPayload()));
    await signIn("user@example.com", "password");

    fetchMock
      .mockResolvedValueOnce(jsonResponse({ detail: "expired" }, 401))
      .mockResolvedValueOnce(
        jsonResponse(authPayload({ access_token: "access-2" })),
      )
      .mockResolvedValueOnce(jsonResponse({ ok: true }));

    const result = await cortexFetch<{ ok: boolean }>("/api/v1/profile");

    expect(result).toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect((fetchMock.mock.calls[3][1] as RequestInit).headers).toMatchObject({
      Authorization: "Bearer access-2",
    });
  });

  it("surfaces API error details without leaking the token", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(authPayload()));
    await signIn("user@example.com", "password");
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: "organization credit limit reached" }, 402),
    );

    const error = await cortexFetch("/api/v1/ai/generate").catch(
      (cause: unknown) => cause,
    );
    expect(error).toBeInstanceOf(CortexApiError);
    expect(error).toMatchObject({
      status: 402,
      detail: "organization credit limit reached",
    });
  });

  it("clears the session on sign-out", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(authPayload()));
    await signIn("user@example.com", "password");
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));

    await signOut();

    expect(getSessionSnapshot()).toBeNull();
    expect(window.localStorage.getItem("cortex.session")).toBeNull();
  });
});
