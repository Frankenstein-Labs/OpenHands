import { useSyncExternalStore } from "react";

export interface CortexConfig {
  apiUrl: string;
  supabaseUrl: string;
  supabaseAnonKey: string;
}

export interface CortexSession {
  accessToken: string;
  refreshToken: string;
  expiresAt: number;
  userId: string;
  email: string;
}

export interface Profile {
  id: string;
  full_name: string | null;
  avatar_url: string | null;
  locale: string;
  timezone: string;
  preferences: Record<string, unknown>;
  status: string;
  active_organization_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface Organization {
  id: string;
  slug: string;
  name: string;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface Membership {
  organization_id: string;
  user_id: string;
  role: "owner" | "admin" | "member" | "viewer";
  created_at: string;
}

export interface Invitation {
  id: string;
  organization_id: string;
  email: string;
  role: string;
  status: string;
  expires_at: string;
  created_at: string;
  token?: string;
}

export interface Provider {
  id: string;
  name: string;
  kind: string;
  base_url: string | null;
  enabled: boolean;
  capabilities: Record<string, unknown>;
}

export interface Model {
  id: string;
  provider_id: string;
  display_name: string;
  description: string | null;
  task: string;
  modalities: string[];
  context_window: number | null;
  supports_tools: boolean;
  supports_vision: boolean;
  status: string;
  input_cost_per_1k: number | null;
  output_cost_per_1k: number | null;
  currency: string;
  provider_enabled: boolean;
  available: boolean;
}

export interface UsageSummary {
  organization_id: string;
  plan_id: string | null;
  credits_limit: number;
  credits_used: number;
  credits_remaining: number;
  by_type: Record<string, number>;
}

export interface UsageLimits {
  organization_id: string;
  plan_id: string | null;
  limits: Record<string, unknown>;
  credits_limit: number;
  credits_used: number;
  credits_remaining: number;
}

export interface GenerateResult {
  model: string;
  content: string;
  finish_reason: string | null;
  usage: { input_tokens: number; output_tokens: number; total_tokens: number };
  credits_charged: number;
}

export interface DocumentSummary {
  id: string;
  title: string;
  source: string;
  status: string;
  size_bytes: number | null;
  created_at: string;
}

export interface SearchHit {
  document_id: string;
  document_title: string;
  chunk_index: number;
  content: string;
  rank: number;
}

export interface Installation {
  id: string;
  organization_id: string;
  installation_id: number;
  account_login: string;
  account_type: string | null;
  status: string;
  created_at: string;
}

export interface GitHubRepository {
  id: string;
  github_repo_id: number;
  full_name: string;
  default_branch: string | null;
  status: string;
}

export class CortexApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `request failed (${status})`);
    this.name = "CortexApiError";
    this.status = status;
    this.detail = detail;
  }
}

export class CortexConfigError extends Error {
  constructor() {
    super("Cortex is not configured");
    this.name = "CortexConfigError";
  }
}

const SESSION_STORAGE_KEY = "cortex.session";
const ACTIVE_ORG_STORAGE_KEY = "cortex.activeOrganizationId";
const SESSION_REFRESH_MARGIN_MS = 30_000;

export function getCortexConfig(): CortexConfig | null {
  const apiUrl = import.meta.env.VITE_CORTEX_API_URL as string | undefined;
  const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string | undefined;
  const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as
    string | undefined;
  if (!apiUrl || !supabaseUrl || !supabaseAnonKey) return null;
  return {
    apiUrl: apiUrl.replace(/\/$/, ""),
    supabaseUrl: supabaseUrl.replace(/\/$/, ""),
    supabaseAnonKey,
  };
}

export function isCortexConfigured(): boolean {
  return getCortexConfig() !== null;
}

function requireConfig(): CortexConfig {
  const config = getCortexConfig();
  if (!config) throw new CortexConfigError();
  return config;
}

function readJson<T>(key: string): T | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

function writeJson(key: string, value: unknown): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(key, JSON.stringify(value));
}

let cachedSession: CortexSession | null | undefined;
const sessionListeners = new Set<() => void>();

function decodeClaims(token: string): Record<string, unknown> {
  try {
    const payload = token.split(".")[1];
    if (!payload) return {};
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(normalized)) as Record<string, unknown>;
  } catch {
    return {};
  }
}

function toSession(payload: {
  access_token: string;
  refresh_token: string;
  expires_in?: number;
  user?: { id?: string; email?: string };
}): CortexSession {
  const claims = decodeClaims(payload.access_token);
  return {
    accessToken: payload.access_token,
    refreshToken: payload.refresh_token,
    expiresAt: Date.now() + (payload.expires_in ?? 3600) * 1000,
    userId: payload.user?.id ?? String(claims.sub ?? ""),
    email: payload.user?.email ?? String(claims.email ?? ""),
  };
}

function setSession(session: CortexSession | null): void {
  cachedSession = session;
  if (typeof window !== "undefined") {
    if (session) writeJson(SESSION_STORAGE_KEY, session);
    else window.localStorage.removeItem(SESSION_STORAGE_KEY);
  }
  sessionListeners.forEach((listener) => listener());
}

export function getSessionSnapshot(): CortexSession | null {
  if (cachedSession === undefined) {
    cachedSession = readJson<CortexSession>(SESSION_STORAGE_KEY);
  }
  return cachedSession;
}

export function subscribeSession(listener: () => void): () => void {
  sessionListeners.add(listener);
  return () => sessionListeners.delete(listener);
}

export function useCortexSession(): CortexSession | null {
  return useSyncExternalStore(subscribeSession, getSessionSnapshot, () => null);
}

export function getActiveOrganizationId(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ACTIVE_ORG_STORAGE_KEY);
}

export function setActiveOrganizationId(organizationId: string | null): void {
  if (typeof window === "undefined") return;
  if (organizationId) {
    window.localStorage.setItem(ACTIVE_ORG_STORAGE_KEY, organizationId);
  } else {
    window.localStorage.removeItem(ACTIVE_ORG_STORAGE_KEY);
  }
}

async function authRequest<T>(
  path: string,
  body: Record<string, unknown>,
): Promise<T> {
  const config = requireConfig();
  const response = await fetch(`${config.supabaseUrl}/auth/v1/${path}`, {
    method: "POST",
    headers: {
      apikey: config.supabaseAnonKey,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  const text = await response.text();
  const payload = text ? (JSON.parse(text) as Record<string, unknown>) : {};
  if (!response.ok) {
    const detail =
      (payload.msg as string | undefined) ??
      (payload.error_description as string | undefined) ??
      (payload.error as string | undefined) ??
      "authentication failed";
    throw new CortexApiError(response.status, detail);
  }
  return payload as T;
}

export async function signIn(email: string, password: string): Promise<void> {
  const payload = await authRequest<{
    access_token: string;
    refresh_token: string;
    expires_in?: number;
    user?: { id?: string; email?: string };
  }>("token?grant_type=password", { email, password });
  setSession(toSession(payload));
}

export async function signUp(email: string, password: string): Promise<void> {
  const payload = await authRequest<{
    access_token?: string;
    refresh_token?: string;
    expires_in?: number;
    user?: { id?: string; email?: string };
  }>("signup", { email, password });
  if (payload.access_token && payload.refresh_token) {
    setSession(
      toSession({
        access_token: payload.access_token,
        refresh_token: payload.refresh_token,
        expires_in: payload.expires_in,
        user: payload.user,
      }),
    );
  }
}

export async function refreshSession(): Promise<CortexSession> {
  const current = getSessionSnapshot();
  if (!current?.refreshToken) throw new CortexApiError(401, "no session");
  const payload = await authRequest<{
    access_token: string;
    refresh_token: string;
    expires_in?: number;
    user?: { id?: string; email?: string };
  }>("token?grant_type=refresh_token", {
    refresh_token: current.refreshToken,
  });
  const next = toSession(payload);
  setSession(next);
  return next;
}

export async function signOut(): Promise<void> {
  const current = getSessionSnapshot();
  setSession(null);
  if (!current) return;
  const config = getCortexConfig();
  if (!config) return;
  try {
    await fetch(`${config.supabaseUrl}/auth/v1/logout`, {
      method: "POST",
      headers: {
        apikey: config.supabaseAnonKey,
        Authorization: `Bearer ${current.accessToken}`,
      },
    });
  } catch {
    // Local sign-out already happened; a failed revoke must not block the UI.
  }
}

async function validAccessToken(): Promise<string> {
  const session = getSessionSnapshot();
  if (!session) throw new CortexApiError(401, "authentication required");
  if (session.expiresAt - SESSION_REFRESH_MARGIN_MS > Date.now()) {
    return session.accessToken;
  }
  const refreshed = await refreshSession();
  return refreshed.accessToken;
}

export interface CortexRequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  orgId?: string | null;
  query?: Record<string, string | number | undefined>;
  signal?: AbortSignal;
}

export async function cortexFetch<T>(
  path: string,
  options: CortexRequestOptions = {},
): Promise<T> {
  const config = requireConfig();
  const url = new URL(`${config.apiUrl}${path}`);
  if (options.orgId) url.searchParams.set("organization_id", options.orgId);
  Object.entries(options.query ?? {}).forEach(([key, value]) => {
    if (value !== undefined) url.searchParams.set(key, String(value));
  });

  const send = async (token: string) =>
    fetch(url, {
      method: options.method ?? "GET",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body:
        options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal,
    });

  let token = await validAccessToken();
  let response = await send(token);
  if (response.status === 401) {
    token = (await refreshSession()).accessToken;
    response = await send(token);
  }
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? (payload as { detail: unknown }).detail
        : payload;
    throw new CortexApiError(response.status, detail ?? response.statusText);
  }
  return payload as T;
}

export function describeCortexError(error: unknown): string {
  if (error instanceof CortexApiError) {
    return typeof error.detail === "string"
      ? error.detail
      : JSON.stringify(error.detail);
  }
  if (error instanceof Error) return error.message;
  return String(error);
}
