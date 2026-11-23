# Cortex.ai security model

## Authentication

- Supabase Auth is the only identity provider. The API verifies the JWT
  signature against the project JWKS, then issuer, audience, expiry, subject and
  algorithm.
- Password storage, email verification, session refresh and revocation are
  Supabase responsibilities. Cortex never stores passwords.
- OAuth providers (Google, GitHub) are enabled in Supabase once credentials
  exist; no parallel password store is created.

## Authorization (defense in depth)

1. **JWT verification** in the API dependency layer.
2. **Server-side organization context**: the organization id comes from the
   path or the caller's active membership, never from a client "role" claim.
3. **Role checks** (`require_role`) for owner/admin-only operations.
4. **PostgreSQL RLS** as the final authority, evaluated with the user's JWT for
   every read and write. A bug in a service cannot leak another tenant's rows.
5. **Server-owned writes** (usage, audit, billing, webhook events) use the
   service-role key and are never exposed to the browser.

Isolation tests create two users and two organizations and assert that user A
cannot read or mutate user B's organizations, memberships, agents, runs, files
or invitations.

## Data isolation rules

- Every tenant table carries `organization_id` with RLS policies calling
  `is_org_member` / `has_org_role`.
- File object paths must start with `<organization_id>/`; this is enforced in
  the API and again by a `files` RLS check.
- Storage buckets are private. Downloads use short-lived signed URLs issued
  after an ownership check.
- Invitation tokens are stored only as SHA-256 hashes. Acceptance is an RPC
  that verifies the authenticated email and expiry and runs as `SECURITY
  DEFINER`.

## Secrets

- Provider API keys, GitHub App private keys, Supabase service-role keys and
  billing secrets live only in server environment variables.
- Secrets are never sent to React, logged, committed, or returned in errors.
- The AI gateway reads keys server-side and records only metadata and costs.

## Agent execution

- Agent commands run in the Agent Server sandbox, never in the FastAPI process.
- Each run gets its own environment, scoped credentials, timeout, CPU/RAM/disk
  limits and network policy.
- Containers do not receive the host Docker socket or host secrets.
- SSRF controls: outbound calls are restricted to allow-listed providers;
  cloud metadata endpoints are blocked; user-supplied URLs are never fetched by
  the API process.

## Webhooks

- GitHub webhooks verify `X-Hub-Signature-256` with HMAC-SHA256 over the raw
  body before any storage.
- Deliveries are deduplicated by `delivery_id` (unique constraint) so replays
  are idempotent.
- Billing webhooks follow the same rule once a provider is configured.

## Logging and audit

- Structured logs with correlation ids; no tokens, passwords or private payloads.
- Security-relevant actions are recorded in `audit_logs` (server write only).

## Known gaps (tracked, not hidden)

- Hosted Supabase, RLS and Storage have not been executed yet; only SQL syntax
  and unit tests exist locally.
- Rate limiting and CSRF protection depend on deployment (reverse proxy / cookie
  mode) and are not yet enabled.
- Load and concurrency tests beyond the unit suite are not yet run.
