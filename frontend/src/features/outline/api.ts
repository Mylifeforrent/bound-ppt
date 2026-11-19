import { ApiError, api, type ApiResult } from "@/api/client";
import type {
  AdvanceResultDTO,
  OutlineDTO,
  ProjectSnapshotDTO,
  StageStateDTO,
  StaleSummaryDTO,
} from "@/api/types";
import { uuid } from "@/lib/utils";
import type { InsertPageInput, MoveTarget } from "./types";

export interface OutlineMutationResult {
  outline: OutlineDTO;
  stale: StaleSummaryDTO;
}

export interface OutlineInsertResult extends OutlineMutationResult {
  pageId: string;
}

export interface OutlineConfirmResult {
  outline: OutlineDTO;
  stage: StageStateDTO;
  snapshot: ProjectSnapshotDTO;
}

export interface OutlineGenerateResult {
  jobId: string;
  outlineVersionId: string | null;
}

export function isNotFound(error: unknown): boolean {
  return error instanceof ApiError && error.httpStatus === 404;
}

export function isConflict(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    (error.category === "conflict" ||
      (error.httpStatus === 409 && error.messageKey.startsWith("error.conflict.")))
  );
}

function commandOptions(expectedVersion: number) {
  return { expectedVersion, idempotencyKey: uuid() };
}

export function fetchOutline(projectId: string): Promise<ApiResult<OutlineDTO>> {
  return api<OutlineDTO>(`/api/projects/${projectId}/outline`);
}

export function generateOutline(projectId: string, expectedVersion: number) {
  return api<OutlineGenerateResult>(`/api/projects/${projectId}/outline/generate`, {
    method: "POST",
    body: {},
    ...commandOptions(expectedVersion),
  });
}

export function confirmOutline(projectId: string, expectedVersion: number) {
  return api<OutlineConfirmResult>(`/api/projects/${projectId}/outline/confirm`, {
    method: "POST",
    body: {},
    ...commandOptions(expectedVersion),
  });
}

export function patchOutlineTitle(
  projectId: string,
  pageId: string,
  title: string,
  expectedVersion: number,
) {
  return api<OutlineMutationResult>(`/api/projects/${projectId}/outline/pages/${pageId}`, {
    method: "PATCH",
    body: { title },
    ...commandOptions(expectedVersion),
  });
}

export function moveOutlinePage(
  projectId: string,
  pageId: string,
  target: MoveTarget,
  expectedVersion: number,
) {
  const body: Record<string, unknown> = { toSectionKey: target.toSectionKey };
  if (target.beforePageId) body.beforePageId = target.beforePageId;
  else if (target.toPosition !== undefined) body.toPosition = target.toPosition;
  return api<OutlineMutationResult>(`/api/projects/${projectId}/outline/pages/${pageId}/move`, {
    method: "POST",
    body,
    ...commandOptions(expectedVersion),
  });
}

export function insertOutlinePage(
  projectId: string,
  input: InsertPageInput,
  expectedVersion: number,
) {
  const body: Record<string, unknown> = {
    sectionKey: input.sectionKey,
    title: input.title,
    keyPoints: input.keyPoints,
  };
  if (input.afterPageId) body.afterPageId = input.afterPageId;
  return api<OutlineInsertResult>(`/api/projects/${projectId}/outline/pages`, {
    method: "POST",
    body,
    ...commandOptions(expectedVersion),
  });
}

export function deleteOutlinePage(projectId: string, pageId: string, expectedVersion: number) {
  return api<OutlineMutationResult>(`/api/projects/${projectId}/outline/pages/${pageId}`, {
    method: "DELETE",
    ...commandOptions(expectedVersion),
  });
}

export function advanceStage(
  projectId: string,
  fromStage: "OUTLINE" | "PLAN",
  advanceToken: string,
  expectedVersion: number,
) {
  return api<AdvanceResultDTO>(`/api/projects/${projectId}/stages/advance`, {
    method: "POST",
    body: { fromStage, advanceToken },
    ...commandOptions(expectedVersion),
  });
}
