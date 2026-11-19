import { useQuery } from "@tanstack/react-query";
import { qk } from "@/api/keys";
import type { ResearchStateDTO, SourcePanelDTO } from "@/api/types";
import { fetchResearch, fetchSources } from "./api";

function researchNeedsRefresh(state: ResearchStateDTO | undefined): boolean {
  if (!state) return false;
  return (
    state.activeJobs.length > 0 ||
    state.gapSearches.some((outcome) => outcome.outcome === "PENDING") ||
    state.digest.items.some((item) => item.status === "PENDING")
  );
}

function sourcesNeedRefresh(state: SourcePanelDTO | undefined, materialDigestPending: boolean): boolean {
  if (!state) return false;
  return state.web.status === "loading" || materialDigestPending;
}

/**
 * The SSE stream invalidates this key on research events. The interval is a
 * safety net while server jobs are active so a dropped stream does not leave
 * the conversation frozen mid-stage.
 */
export function useResearchState(projectId: string, enabled = true) {
  return useQuery({
    queryKey: qk.research(projectId),
    queryFn: async () => (await fetchResearch(projectId)).data,
    enabled: Boolean(projectId) && enabled,
    staleTime: 5_000,
    refetchInterval: (query) => (researchNeedsRefresh(query.state.data) ? 3_000 : false),
  });
}

/** The source panel is fetched separately from the conversation state. */
export function useSourcePanel(projectId: string, enabled = true, materialDigestPending = false) {
  return useQuery({
    queryKey: qk.sources(projectId),
    queryFn: async () => (await fetchSources(projectId)).data,
    enabled: Boolean(projectId) && enabled,
    staleTime: 2_000,
    refetchInterval: (query) => (sourcesNeedRefresh(query.state.data, materialDigestPending) ? 3_000 : false),
  });
}
