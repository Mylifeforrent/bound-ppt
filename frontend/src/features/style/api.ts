import { ApiError, api } from "@/api/client";
import type { StageStateDTO, StaleSummaryDTO, StyleDTO, StyleSelectionDTO } from "@/api/types";
import { uuid } from "@/lib/utils";

function commandOptions(expectedVersion: number) {
  return { expectedVersion, idempotencyKey: uuid() };
}

export function fetchStyles() {
  return api<{ styles: StyleDTO[] }>("/api/styles");
}

export interface PutStyleInput {
  styleKey: string;
  styleVersion: number;
  rememberPreference: boolean;
}

export function putStyle(
  projectId: string,
  input: PutStyleInput,
  expectedVersion: number,
) {
  return api<{ styleSelection: StyleSelectionDTO }>(`/api/projects/${projectId}/style`, {
    method: "PUT",
    body: input,
    ...commandOptions(expectedVersion),
  });
}

export interface StyleConfirmResult {
  styleSelection: StyleSelectionDTO;
  stage: StageStateDTO;
  stale: StaleSummaryDTO | null;
}

export function confirmStyle(projectId: string, expectedVersion: number) {
  return api<StyleConfirmResult>(`/api/projects/${projectId}/style/confirm`, {
    method: "POST",
    body: {},
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

export function isApiValidation(error: unknown): boolean {
  return error instanceof ApiError && (error.httpStatus === 422 || error.category === "validation");
}

export function isGateViolation(error: unknown): boolean {
  return error instanceof ApiError && error.category === "gate_violation";
}
