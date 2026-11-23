import { describe, expect, it } from "vitest";
import {
  CORTEX_CREATOR,
  CORTEX_IDENTITY_SYSTEM_SUFFIX,
  CORTEX_NAME,
} from "./cortex-identity";

describe("Cortex identity prompt", () => {
  it("names Cortex and Frankenstein-Labs as its creator", () => {
    expect(CORTEX_NAME).toBe("Cortex");
    expect(CORTEX_CREATOR).toBe("Frankenstein-Labs");
    expect(CORTEX_IDENTITY_SYSTEM_SUFFIX).toContain("Your name is Cortex");
    expect(CORTEX_IDENTITY_SYSTEM_SUFFIX).toContain(
      "built by Frankenstein-Labs",
    );
  });

  it("states a mission and the capabilities the agent really has", () => {
    const prompt = CORTEX_IDENTITY_SYSTEM_SUFFIX;

    expect(prompt).toContain("mission");
    expect(prompt).toContain("terminal");
    expect(prompt).toContain("tests");
    expect(prompt).toContain("Git");
  });

  it("forbids inventing capabilities, integrations or results", () => {
    const prompt = CORTEX_IDENTITY_SYSTEM_SUFFIX;

    expect(prompt).toContain("do not claim capabilities");
    expect(prompt).toContain("say so instead of pretending");
  });

  it("keeps the OpenHands lineage as a technical fact, not as its name", () => {
    const prompt = CORTEX_IDENTITY_SYSTEM_SUFFIX;

    expect(prompt).toContain("open-source OpenHands engine");
    expect(prompt).toContain("not your name");
    expect(prompt).not.toContain("OpenDevin");
    expect(prompt).not.toMatch(/your name is OpenHands/i);
  });

  it("asks the agent not to recite the identity block on every turn", () => {
    expect(CORTEX_IDENTITY_SYSTEM_SUFFIX).toContain("Do not recite");
  });
});
