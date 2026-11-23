import { describe, expect, it } from "vitest";
import fs from "fs";
import path from "path";

type TranslationMap = Record<string, Record<string, string>>;

const translations: TranslationMap = JSON.parse(
  fs.readFileSync(
    path.join(__dirname, "../../src/i18n/translation.json"),
    "utf-8",
  ),
);

// Surfaces where the user meets the product itself, so they must say Cortex.
const PRODUCT_KEYS = [
  "BRANDING$OPENHANDS",
  "BRANDING$OPENHANDS_LOGO",
  "ONBOARDING$TITLE",
  "ONBOARDING$HELLO_SUBTITLE",
  "ONBOARDING$HELLO_DEFAULT_MESSAGE",
  "ONBOARDING$AGENT_OPENHANDS_DESCRIPTION",
  "SETTINGS$AGENT_TYPE_OPENHANDS",
  "SETTINGS$AGENT_PROFILE_NO_LLM",
  "COMMAND_MENU$NEW_CHAT_DESCRIPTION",
  "BROWSER$NO_PAGE_LOADED",
  "TELEMETRY$CONSENT_TITLE",
];

// Third-party products and legal notices keep their real names.
const EXTERNAL_KEYS = [
  "BACKEND$CLOUD_TITLE",
  "SCHEMA$VERIFICATION$CRITIC_API_KEY$DESCRIPTION",
  "LICENSE$EXPIRED",
];

describe("Cortex branding", () => {
  it("names the product Cortex in every locale", () => {
    for (const key of PRODUCT_KEYS) {
      const entry = translations[key];
      expect(entry, `missing translation key ${key}`).toBeDefined();
      for (const [locale, value] of Object.entries(entry)) {
        expect(value, `${key} (${locale}) should say Cortex`).toContain(
          "Cortex",
        );
        expect(value, `${key} (${locale}) still says OpenHands`).not.toContain(
          "OpenHands",
        );
      }
    }
  });

  it("keeps the real names of external services and licence notices", () => {
    for (const key of EXTERNAL_KEYS) {
      const entry = translations[key];
      expect(entry, `missing translation key ${key}`).toBeDefined();
      expect(Object.values(entry).join(" ")).toContain("OpenHands");
    }
  });
});
