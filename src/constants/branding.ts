/**
 * Centralized product branding for the CORTEX AI frontend.
 *
 * This module is the single source of truth for the user-facing product and
 * organization names shown by the web app (document title, metadata, shell).
 *
 * The underlying OpenHands agent engine, its provider IDs, package names, wire
 * contracts and third-party service URLs are intentionally NOT branded here:
 * renaming those would break functional integrations and license obligations.
 */
export const BRANDING = {
  /** User-facing product name. */
  productName: "CORTEX AI",
  /** Organization that builds and operates the product. */
  organizationName: "Frankenstein Labs",
  /** Default document title when no conversation is open. */
  defaultDocumentTitle: "CORTEX AI",
  /** Meta description used on the app shell. */
  metaDescription: "CORTEX AI — build and automate software with AI agents.",
} as const;

export type Branding = typeof BRANDING;

/**
 * External service origins the app dials or links to.
 *
 * These point at live OpenHands services today and are the single place to
 * change once CORTEX AI has its own infrastructure. They are intentionally NOT
 * replaced with invented CORTEX domains: doing so would silently break the
 * working integration. See docs/CORTEX_ARCHITECTURE.md for the migration plan
 * and docs/BRANDING.md for the per-dependency notes.
 */
export const EXTERNAL_ORIGINS = {
  /**
   * Hosted OpenHands Cloud app (default cloud backend + device-flow auth +
   * a few settings deep-links). Overridable per deployment via
   * `VITE_LOCK_TO_CLOUD` and the backend registry.
   */
  cloudApp: "https://app.all-hands.dev",
  /** Product documentation site. */
  docs: "https://docs.openhands.dev",
  /** Community Slack invite. */
  slackCommunity: "https://openhands.dev/joinslack",
  /**
   * Reverse proxy that fronts the PostHog telemetry endpoint (ad-blocker
   * bypass). Overridable via `VITE_POSTHOG_HOST`.
   */
  telemetryProxy: "https://z.openhands.dev",
} as const;

/** Trailing-slash documentation origin prefix (for consumer-URL validation). */
export const DOCS_URL_PREFIX = `${EXTERNAL_ORIGINS.docs}/`;

/** Build an absolute documentation URL from a path such as `overview/introduction`. */
export const docsUrl = (path: string): string =>
  `${EXTERNAL_ORIGINS.docs}/${path.replace(/^\/+/, "")}`;
