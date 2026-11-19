import { api } from "@/api/client";
import type {
  ProjectDTO,
  ProjectMode,
  ProjectSnapshotDTO,
  StageName,
  StageStatus,
} from "@/api/types";
import { uuid } from "@/lib/utils";

export interface CreateProjectInput {
  topic: string;
  mode: ProjectMode;
  /** Reused for retries of the same form intent so a lost response cannot create a duplicate. */
  idempotencyKey: string;
}

export interface CreateProjectResult {
  project: ProjectDTO;
  snapshot: ProjectSnapshotDTO;
}

export function createProject(input: CreateProjectInput) {
  const topic = input.topic.trim();
  return api<CreateProjectResult>("/api/projects", {
    method: "POST",
    body: { topic, name: topic, mode: input.mode },
    idempotencyKey: input.idempotencyKey,
  });
}

export interface StartResearchResult {
  stage: StageName;
  stageStatus: StageStatus;
  jobIds: string[];
}

export function startResearch(projectId: string, expectedVersion: number) {
  return api<StartResearchResult>(`/api/projects/${projectId}/research/start`, {
    method: "POST",
    body: {},
    expectedVersion,
    idempotencyKey: uuid(),
  });
}
