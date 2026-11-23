import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { server } from "#/mocks/node";
import CortexUsage from "#/routes/cortex-usage";
import { CortexWorkspaceProvider } from "#/components/features/cortex/cortex-workspace";

const ORGANIZATION_ID = "org-1";

function renderUsage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <CortexWorkspaceProvider>
        <CortexUsage />
      </CortexWorkspaceProvider>
    </QueryClientProvider>,
  );
}

describe("Cortex usage route", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_CORTEX_API_URL", "http://api.test");
    vi.stubEnv("VITE_SUPABASE_URL", "http://auth.test");
    vi.stubEnv("VITE_SUPABASE_ANON_KEY", "anon-key");
    window.localStorage.clear();
    window.localStorage.setItem(
      "cortex.session",
      JSON.stringify({
        accessToken: "token",
        refreshToken: "refresh",
        expiresAt: Date.now() + 3_600_000,
        userId: "user-1",
        email: "user@example.com",
      }),
    );
    window.localStorage.setItem("cortex.activeOrganizationId", ORGANIZATION_ID);
    server.use(
      http.get("http://api.test/api/v1/organizations", () =>
        HttpResponse.json([
          {
            id: ORGANIZATION_ID,
            slug: "acme",
            name: "Acme",
            created_by: "user-1",
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
          },
        ]),
      ),
      http.get(
        `http://api.test/api/v1/organizations/${ORGANIZATION_ID}/members`,
        () =>
          HttpResponse.json([
            {
              organization_id: ORGANIZATION_ID,
              user_id: "user-1",
              role: "owner",
              created_at: "2026-01-01T00:00:00Z",
            },
          ]),
      ),
      http.get("http://api.test/api/v1/usage", () =>
        HttpResponse.json({
          organization_id: ORGANIZATION_ID,
          plan_id: "free",
          credits_limit: 120,
          credits_used: 20,
          credits_remaining: 100,
          by_type: { llm_tokens: 20 },
        }),
      ),
      http.get("http://api.test/api/v1/usage/limits", () =>
        HttpResponse.json({
          organization_id: ORGANIZATION_ID,
          plan_id: "free",
          limits: { max_concurrent_runs: 1 },
          credits_limit: 120,
          credits_used: 20,
          credits_remaining: 100,
        }),
      ),
    );
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    server.resetHandlers();
    window.localStorage.clear();
  });

  it("renders credits and plan limits from the API", async () => {
    renderUsage();

    await waitFor(() => {
      expect(screen.getByText("120.00")).toBeInTheDocument();
    });
    expect(screen.getByText("20.00")).toBeInTheDocument();
    expect(screen.getByText("100.00")).toBeInTheDocument();
    expect(screen.getByText("llm_tokens")).toBeInTheDocument();
    expect(screen.getByText(/max_concurrent_runs/)).toBeInTheDocument();
  });
});
