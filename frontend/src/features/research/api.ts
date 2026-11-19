import { api } from "@/api/client";
import type {
  GapSearchOutcomeDTO,
  GapStateDTO,
  ProfileDTO,
  ResearchStateDTO,
  SourcePanelDTO,
  StaleSummaryDTO,
} from "@/api/types";
import { uuid } from "@/lib/utils";

export interface AnswerResult {
  question: {
    key: string;
    optionKey: string;
    revision: number;
    answeredAt: string;
  };
  profileDirty: boolean;
  stale: StaleSummaryDTO | null;
}

export interface GapDecisionResult {
  gaps: GapStateDTO;
  searchJobIds: string[];
  gapSearches: GapSearchOutcomeDTO[];
  webSkipped: boolean;
}

export interface ProfileResult {
  profile: ProfileDTO;
  profileDirty: boolean;
  outlineUnconfirmed: boolean;
  stale: StaleSummaryDTO | null;
}

export interface GapDecisionInput {
  selectedSuggestionIds: string[];
  webSkipped: boolean;
}

export interface OutlineGenerateResult {
  jobId: string;
  outlineVersionId: string | null;
}

function commandOptions(expectedVersion: number) {
  return { expectedVersion, idempotencyKey: uuid() };
}

export function fetchResearch(projectId: string) {
  return api<ResearchStateDTO>(`/api/projects/${projectId}/research`);
}

export function fetchSources(projectId: string) {
  return api<SourcePanelDTO>(`/api/projects/${projectId}/sources`);
}

export function putAnswer(projectId: string, questionKey: string, optionKey: string, expectedVersion: number) {
  return api<AnswerResult>(
    `/api/projects/${projectId}/research/answers/${encodeURIComponent(questionKey)}`,
    {
      method: "PUT",
      body: { optionKey },
      ...commandOptions(expectedVersion),
    },
  );
}

export function decideGaps(projectId: string, input: GapDecisionInput, expectedVersion: number) {
  return api<GapDecisionResult>(`/api/projects/${projectId}/research/gaps/decisions`, {
    method: "POST",
    body: {
      selectedSuggestionIds: input.selectedSuggestionIds,
      webSkipped: input.webSkipped,
    },
    ...commandOptions(expectedVersion),
  });
}

export function generateProfile(projectId: string, expectedVersion: number) {
  return api<ProfileResult>(`/api/projects/${projectId}/research/profile`, {
    method: "POST",
    body: {},
    ...commandOptions(expectedVersion),
  });
}

export function generateOutline(projectId: string, expectedVersion: number) {
  return api<OutlineGenerateResult>(`/api/projects/${projectId}/outline/generate`, {
    method: "POST",
    body: {},
    ...commandOptions(expectedVersion),
  });
}
