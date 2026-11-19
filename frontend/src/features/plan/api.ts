import { ApiError, api } from "@/api/client";
import type { AdvanceResultDTO, ArtifactDTO, PageListDTO } from "@/api/types";
import { uuid } from "@/lib/utils";

export interface PlanJobAcceptedDTO {
  jobId: string;
  pageId: string;
}

export interface GeneratePlanResultDTO {
  jobs: Array<{ pageId: string; jobId: string }>;
  skippedPageIds: string[];
  counts: { required: number; scheduled: number; reused: number };
}

function commandOptions(expectedVersion: number) {
  return { expectedVersion, idempotencyKey: uuid() };
}

export function fetchPages(projectId: string) {
  return api<PageListDTO>(`/api/projects/${projectId}/pages`);
}

export function fetchPlanArtifact(projectId: string, pageId: string) {
  return api<ArtifactDTO>(`/api/projects/${projectId}/pages/${pageId}/artifacts/plan`);
}

export function generatePlans(projectId: string, expectedVersion: number) {
  return api<GeneratePlanResultDTO>(`/api/projects/${projectId}/plan/generate`, {
    method: "POST",
    body: {},
    ...commandOptions(expectedVersion),
  });
}

export function regeneratePlanPage(
  projectId: string,
  pageId: string,
  expectedVersion: number,
) {
  return api<PlanJobAcceptedDTO>(
    `/api/projects/${projectId}/pages/${pageId}/plan/regenerate`,
    {
      method: "POST",
      body: {},
      ...commandOptions(expectedVersion),
    },
  );
}

export function tweakPlanPage(
  projectId: string,
  pageId: string,
  instruction: string,
  expectedVersion: number,
) {
  return api<PlanJobAcceptedDTO>(`/api/projects/${projectId}/pages/${pageId}/plan/tweak`, {
    method: "POST",
    body: { instruction },
    ...commandOptions(expectedVersion),
  });
}

export function retryPage(
  projectId: string,
  pageId: string,
  expectedVersion: number,
) {
  return api<PlanJobAcceptedDTO>(`/api/projects/${projectId}/pages/${pageId}/retry`, {
    method: "POST",
    body: { kind: "plan" },
    ...commandOptions(expectedVersion),
  });
}

export function advancePlanStage(
  projectId: string,
  advanceToken: string,
  expectedVersion: number,
) {
  return api<AdvanceResultDTO>(`/api/projects/${projectId}/stages/advance`, {
    method: "POST",
    body: { fromStage: "PLAN", advanceToken },
    ...commandOptions(expectedVersion),
  });
}

export function isApiConflict(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    (error.category === "conflict" ||
      (error.httpStatus === 409 && error.messageKey.startsWith("error.conflict.")))
  );
}

export function isApiNotFound(error: unknown): boolean {
  return (
    error instanceof ApiError && (error.httpStatus === 404 || error.category === "not_found")
  );
}

export function isApiValidation(error: unknown): boolean {
  return error instanceof ApiError && (error.httpStatus === 422 || error.category === "validation");
}

export function isGateViolation(error: unknown, messageKey?: string): boolean {
  if (!(error instanceof ApiError)) return false;
  if (messageKey) return error.messageKey === messageKey;
  return error.category === "gate_violation";
}
