import type { QueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { qk } from "@/api/keys";
import type { ProjectSnapshotDTO } from "@/api/types";

/**
 * Read the authoritative project version immediately before a command.
 * The snapshot is also written back to the query cache so the shell and stage
 * guards converge on the same server truth.
 */
export async function readProjectVersion(projectId: string, queryClient: QueryClient): Promise<number> {
  const { data, meta } = await api<ProjectSnapshotDTO>(`/api/projects/${projectId}/snapshot`);
  queryClient.setQueryData(qk.snapshot(projectId), data);
  return meta.projectVersion ?? data.project.version;
}

export function createVersionReader(projectId: string, queryClient: QueryClient): () => Promise<number> {
  return () => readProjectVersion(projectId, queryClient);
}

/** Patch only the version field of a cached snapshot from a command response. */
export function applyProjectVersion(
  queryClient: QueryClient,
  projectId: string,
  version: number | undefined,
): void {
  if (version === undefined) return;
  queryClient.setQueryData<ProjectSnapshotDTO>(qk.snapshot(projectId), (previous) =>
    previous ? { ...previous, project: { ...previous.project, version } } : previous,
  );
}
