import type { StageName } from "@/api/types";

export const STAGE_ORDER: StageName[] = ["INTAKE", "RESEARCH", "OUTLINE", "PLAN", "STYLE", "DESIGN"];

export const STAGE_LABELS: Record<StageName, string> = {
  INTAKE: "Material intake",
  RESEARCH: "Research + interview",
  OUTLINE: "Outline",
  PLAN: "Plan draft",
  STYLE: "Style selection",
  DESIGN: "Design draft",
};

export function isPastResearch(stage: StageName): boolean {
  return STAGE_ORDER.indexOf(stage) > STAGE_ORDER.indexOf("RESEARCH");
}

export function stageLabel(stage: StageName): string {
  return STAGE_LABELS[stage] ?? "Current stage";
}
