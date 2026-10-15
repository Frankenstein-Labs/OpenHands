import { describe, expect, it } from "vitest";
import {
  BRANDING,
  DOCS_URL_PREFIX,
  EXTERNAL_ORIGINS,
  docsUrl,
} from "#/constants/branding";

describe("BRANDING", () => {
  it("exposes the CORTEX AI product identity", () => {
    expect(BRANDING.productName).toBe("CORTEX AI");
    expect(BRANDING.organizationName).toBe("Frankenstein Labs");
    expect(BRANDING.defaultDocumentTitle).toBe("CORTEX AI");
  });

  it("keeps a non-empty meta description that names the product", () => {
    expect(BRANDING.metaDescription).toContain(BRANDING.productName);
  });
});

describe("EXTERNAL_ORIGINS", () => {
  it("stores every origin as a trailing-slash-free absolute https URL", () => {
    for (const origin of Object.values(EXTERNAL_ORIGINS)) {
      expect(origin).toMatch(/^https:\/\/\S+[^/\s]$/);
    }
  });
});

describe("docsUrl", () => {
  it("joins the docs origin and path with a single slash", () => {
    expect(docsUrl("overview/introduction")).toBe(
      `${EXTERNAL_ORIGINS.docs}/overview/introduction`,
    );
  });

  it("normalizes a leading slash in the path", () => {
    expect(docsUrl("/usage/local-setup")).toBe(
      `${EXTERNAL_ORIGINS.docs}/usage/local-setup`,
    );
  });

  it("stays consistent with DOCS_URL_PREFIX", () => {
    expect(DOCS_URL_PREFIX).toBe(`${EXTERNAL_ORIGINS.docs}/`);
    expect(docsUrl("x").startsWith(DOCS_URL_PREFIX)).toBe(true);
  });
});
