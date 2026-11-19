import { describe, expect, it } from "vitest";
import { isPastResearch, stageLabel } from "./status";

describe("research stage helpers", () => {
  it("treats outline and later stages as past research", () => {
    expect(isPastResearch("INTAKE")).toBe(false);
    expect(isPastResearch("RESEARCH")).toBe(false);
    expect(isPastResearch("OUTLINE")).toBe(true);
    expect(isPastResearch("PLAN")).toBe(true);
    expect(isPastResearch("STYLE")).toBe(true);
    expect(isPastResearch("DESIGN")).toBe(true);
  });

  it("labels every stage", () => {
    expect(stageLabel("RESEARCH")).toBe("Research + interview");
    expect(stageLabel("DESIGN")).toBe("Design draft");
  });
});
