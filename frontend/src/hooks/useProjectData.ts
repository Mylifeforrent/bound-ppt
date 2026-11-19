import { useQuery } from "@tanstack/react-query";
import { ApiError, api } from "@/api/client";
import { qk } from "@/api/keys";
import type { AccountDTO, ClientConfigDTO, ProjectSnapshotDTO, UserDTO } from "@/api/types";

export function useAuth() {
  return useQuery({
    queryKey: qk.auth,
    queryFn: async () => {
      try {
        const { data } = await api<{ user: UserDTO; account: AccountDTO | null }>("/api/auth/me");
        return data;
      } catch (error) {
        if (error instanceof ApiError && (error.httpStatus === 401 || error.httpStatus === 403)) return null;
        throw error;
      }
    },
    staleTime: 60_000,
    retry: 1,
  });
}

export function useClientConfig(enabled = true) {
  return useQuery({
    queryKey: qk.config,
    queryFn: async () => (await api<{ config: ClientConfigDTO }>("/api/config")).data.config,
    staleTime: 10 * 60_000,
    enabled,
  });
}

export function useSnapshot(projectId: string | undefined) {
  return useQuery({
    queryKey: qk.snapshot(projectId ?? "none"),
    queryFn: async () => (await api<ProjectSnapshotDTO>(`/api/projects/${projectId}/snapshot`)).data,
    enabled: Boolean(projectId),
    retry: 1,
  });
}

export function stageRoute(projectId: string, stage: string): string {
  const map: Record<string, string> = {
    INTAKE: "intake",
    RESEARCH: "research",
    OUTLINE: "outline",
    PLAN: "plan",
    STYLE: "style",
    DESIGN: "design",
  };
  return `/projects/${projectId}/${map[stage] ?? "intake"}`;
}

export function deepestReachableStage(snapshot: ProjectSnapshotDTO): string {
  const order = ["INTAKE", "RESEARCH", "OUTLINE", "PLAN", "STYLE", "DESIGN"];
  let best = "INTAKE";
  for (const stage of order) {
    const state = snapshot.stages.find((s) => s.stage === stage);
    if (state?.reachable) best = stage;
  }
  return best;
}
