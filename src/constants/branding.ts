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
