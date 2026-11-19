import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { qk } from "@/api/keys";
import type { PageListDTO, PageSummaryDTO, ProjectSnapshotDTO } from "@/api/types";
import { stageRoute } from "@/hooks/useProjectData";
import { errorText, messageFor } from "@/lib/messages";
import { useViewStore } from "@/stores/view";
import {
  advancePlanStage,
  fetchPages,
  fetchPlanArtifact,
  generatePlans,
  isApiConflict,
  isApiNotFound,
  isApiValidation,
  isGateViolation,
  regeneratePlanPage,
  retryPage,
  tweakPlanPage,
} from "./api";

export interface PlanBlocker {
  code: string;
  message: string;
  action?: string;
  href?: string;
}

export interface PlanActionNotice {
  pageId: string;
  message: string;
}

const STAGE_LABEL: Record<string, string> = {
  INTAKE: "material intake",
  RESEARCH: "research",
  OUTLINE: "outline",
  PLAN: "plan draft",
  STYLE: "style selection",
  DESIGN: "design draft",
};

export function usePlanWorkbench({
  projectId,
  snapshot,
}: {
  projectId: string;
  snapshot: ProjectSnapshotDTO;
}) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const selectedPageId = useViewStore((state) => state.selectedPageId);
  const setSelectedPage = useViewStore((state) => state.setSelectedPage);

  const [actionNotice, setActionNotice] = useState<PlanActionNotice | null>(null);
  const [tweakError, setTweakError] = useState<{ pageId: string; message: string } | null>(null);
  const [generationError, setGenerationError] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const [tweakDrafts, setTweakDrafts] = useState<Record<string, string>>({});

  const pagesQuery = useQuery({
    queryKey: qk.pages(projectId),
    queryFn: async () => (await fetchPages(projectId)).data,
    staleTime: 1_000,
    refetchInterval: (query) => {
      const data = query.state.data as PageListDTO | undefined;
      if (!data) return false;
      const active = data.pages.some(
        (page) => page.plan.status === "PLANNING" || Boolean(page.activeJob),
      );
      if (active) return 2_000;
      const incomplete = data.pages.some(
        (page) => page.plan.status === "PENDING" || page.plan.status === "STALE",
      );
      // Slow safety net only; status always comes from the server projection.
      return incomplete ? 5_000 : false;
    },
  });
  const pages = pagesQuery.data;

  useEffect(() => {
    if (!pages?.pages.length) return;
    const ids = new Set(pages.pages.map((page) => page.pageId));
    if (selectedPageId && ids.has(selectedPageId)) return;
    const fallback =
      pages.pages.find((page) => page.pageType === "BODY") ?? pages.pages[0];
    if (fallback) setSelectedPage(fallback.pageId);
  }, [pages, selectedPageId, setSelectedPage]);

  const selectedIndex = pages
    ? pages.pages.findIndex((page) => page.pageId === selectedPageId)
    : -1;
  const page: PageSummaryDTO | undefined =
    selectedIndex >= 0 ? pages?.pages[selectedIndex] : undefined;

  const selectPage = useCallback(
    (pageId: string) => {
      setSelectedPage(pageId);
      setActionNotice(null);
      setTweakError(null);
    },
    [setSelectedPage],
  );

  const goRelative = useCallback(
    (delta: number) => {
      if (!pages?.pages.length) return;
      const base = selectedIndex >= 0 ? selectedIndex : 0;
      const target = pages.pages[Math.max(0, Math.min(pages.pages.length - 1, base + delta))];
      if (target && target.pageId !== selectedPageId) selectPage(target.pageId);
    },
    [pages, selectedIndex, selectedPageId, selectPage],
  );

  const artifactQuery = useQuery({
    queryKey: qk.artifact(projectId, selectedPageId ?? "none", "plan"),
    queryFn: async () =>
      (await fetchPlanArtifact(projectId, selectedPageId as string)).data,
    enabled: Boolean(selectedPageId),
    retry: (failureCount, error) => !isApiNotFound(error) && failureCount < 2,
    staleTime: 0,
  });

  const versionRef = useRef(snapshot.project.version);
  useEffect(() => {
    if (snapshot.project.version > versionRef.current) {
      versionRef.current = snapshot.project.version;
    }
  }, [snapshot.project.version]);
  const bumpVersion = useCallback((value?: number | null) => {
    if (typeof value === "number" && Number.isFinite(value)) {
      versionRef.current = Math.max(versionRef.current, value);
    }
  }, []);
  const currentVersion = useCallback(() => versionRef.current, []);

  const invalidatePagesAndSnapshot = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: qk.pages(projectId) });
    void queryClient.invalidateQueries({ queryKey: qk.snapshot(projectId) });
  }, [queryClient, projectId]);

  const invalidatePageArtifact = useCallback(
    (pageId: string) => {
      void queryClient.invalidateQueries({ queryKey: qk.artifact(projectId, pageId, "plan") });
    },
    [queryClient, projectId],
  );

  const outlineStage = snapshot.stages.find((state) => state.stage === "OUTLINE");
  const planStage = snapshot.stages.find((state) => state.stage === "PLAN");
  const styleStage = snapshot.stages.find((state) => state.stage === "STYLE");

  const outlineUnconfirmed = Boolean(
    planStage?.blockers.some(
      (blocker) =>
        blocker.code === "outline_unconfirmed" ||
        blocker.messageKey === "error.gate.outline_unconfirmed",
    ),
  );
  const outlineConfirmed =
    Boolean(snapshot.pointers.outlineVersionId) &&
    !outlineUnconfirmed &&
    (outlineStage?.status === "COMPLETE" || Boolean(planStage?.reachable));

  const blockers = useMemo<PlanBlocker[]>(() => {
    const list: PlanBlocker[] = [];
    if (pages && pages.pages.length === 0) {
      list.push({
        code: "no_pages",
        message: "The deck has no pages yet. Generate and confirm the outline first.",
        action: "Open outline",
        href: stageRoute(projectId, "OUTLINE"),
      });
    }
    if (!snapshot.pointers.outlineVersionId) {
      list.push({
        code: "outline_missing",
        message: "Generate and confirm an outline before the plan draft can run.",
        action: "Open outline",
        href: stageRoute(projectId, "OUTLINE"),
      });
    } else if (!outlineConfirmed) {
      list.push({
        code: "outline_unconfirmed",
        message:
          "Confirm the current outline before the plan draft can be generated. Edits after confirmation require reconfirmation.",
        action: "Open outline",
        href: stageRoute(projectId, "OUTLINE"),
      });
    }
    const seen = new Set(list.map((item) => item.code));
    for (const blocker of planStage?.blockers ?? []) {
      if (
        seen.has(blocker.code) ||
        blocker.code === "outline_unconfirmed" ||
        blocker.code === "outline_missing"
      ) {
        continue;
      }
      seen.add(blocker.code);
      list.push({
        code: blocker.code,
        message: messageFor(blocker.messageKey),
        ...(blocker.stage
          ? {
              action: `Open ${STAGE_LABEL[blocker.stage] ?? "previous stage"}`,
              href: stageRoute(projectId, blocker.stage),
            }
          : {}),
      });
    }
    if (planStage && !planStage.reachable && list.length === 0) {
      list.push({
        code: "stage_locked",
        message: "The plan draft stage is not reachable yet.",
        action: "Open outline",
        href: stageRoute(projectId, "OUTLINE"),
      });
    }
    return list;
  }, [outlineConfirmed, pages, planStage, projectId, snapshot.pointers.outlineVersionId]);

  const total = pages?.counts.total ?? snapshot.counts.planTotal;
  const done = pages?.counts.planDone ?? snapshot.counts.planDone;
  const percent = total > 0 ? (done / total) * 100 : 0;
  const planErrorCount = pages?.counts.planError ?? 0;
  const planComplete = Boolean(
    pages && pages.pages.length > 0 && pages.pages.every((summary) => summary.plan.status === "DONE"),
  );
  const styleReachable = styleStage?.reachable ?? false;
  const planAdvanceToken = planStage?.advanceToken;
  // The confirm gate is exactly "all pages planned and none in error". Whether
  // the next route is reachable or a validated advance token is available is
  // resolved at the click with the server snapshot.
  const canContinue = planComplete;
  const locked = !outlineConfirmed || blockers.length > 0;

  const needsGeneration = useMemo(
    () =>
      (pages?.pages ?? []).filter(
        (summary) =>
          summary.plan.status === "PENDING" || summary.plan.status === "STALE",
      ),
    [pages],
  );

  const hasActivePlanJob = Boolean(
    snapshot.activeJobs.some((job) => job.type.toLowerCase().includes("plan")) ||
      pages?.pages.some((summary) => summary.plan.status === "PLANNING"),
  );

  const handleCommandError = useCallback(
    (error: unknown, pageId: string) => {
      if (isApiConflict(error)) {
        invalidatePagesAndSnapshot();
        void queryClient.invalidateQueries({ queryKey: qk.artifact(projectId, pageId, "plan") });
        toast.error(errorText(error));
        return;
      }
      if (isGateViolation(error, "error.gate.page_write_in_progress")) {
        void queryClient.invalidateQueries({ queryKey: qk.pages(projectId) });
        setActionNotice({ pageId, message: errorText(error) });
        return;
      }
      if (isGateViolation(error)) {
        invalidatePagesAndSnapshot();
        setActionNotice({ pageId, message: errorText(error) });
        return;
      }
      setActionNotice({ pageId, message: errorText(error) });
    },
    [invalidatePagesAndSnapshot, projectId, queryClient],
  );

  const generateMutation = useMutation({
    mutationFn: async () => {
      const result = await generatePlans(projectId, currentVersion());
      bumpVersion(result.meta?.projectVersion);
      return result.data;
    },
    onSuccess: (data) => {
      setGenerationError(null);
      invalidatePagesAndSnapshot();
      const scheduled = data.jobs?.length ?? 0;
      const required = data.counts?.required ?? scheduled;
      const reused = data.counts?.reused ?? 0;
      setAnnouncement(
        scheduled > 0
          ? `Planning ${scheduled} of ${required} pages. ${reused} pages reused an existing plan.`
          : "No new plan jobs were needed. Existing plan pages were reused.",
      );
    },
    onError: (error) => {
      setGenerationError(errorText(error));
      if (isApiConflict(error)) {
        invalidatePagesAndSnapshot();
        toast.error(errorText(error));
      } else if (isGateViolation(error)) {
        invalidatePagesAndSnapshot();
      } else {
        toast.error(errorText(error));
      }
    },
  });

  const regenerateMutation = useMutation({
    mutationFn: async (pageId: string) => {
      const result = await regeneratePlanPage(projectId, pageId, currentVersion());
      bumpVersion(result.meta?.projectVersion);
      return result.data;
    },
    onMutate: () => setActionNotice(null),
    onSuccess: (_data, pageId) => {
      toast.message(`Re-planning page ${pageNumberFor(pages, pageId)}…`);
      invalidatePagesAndSnapshot();
    },
    onError: (error, pageId) => handleCommandError(error, pageId),
  });

  const tweakMutation = useMutation({
    mutationFn: async (variables: { pageId: string; instruction: string }) => {
      const result = await tweakPlanPage(
        projectId,
        variables.pageId,
        variables.instruction,
        currentVersion(),
      );
      bumpVersion(result.meta?.projectVersion);
      return result.data;
    },
    onMutate: () => {
      setActionNotice(null);
      setTweakError(null);
    },
    onSuccess: (_data, variables) => {
      setTweakDrafts((current) => {
        const next = { ...current };
        delete next[variables.pageId];
        return next;
      });
      toast.message("Applying your plan tweak to this page…");
      invalidatePagesAndSnapshot();
    },
    onError: (error, variables) => {
      if (isApiValidation(error)) {
        setTweakError({ pageId: variables.pageId, message: errorText(error) });
        return;
      }
      handleCommandError(error, variables.pageId);
    },
  });

  const retryMutation = useMutation({
    mutationFn: async (pageId: string) => {
      const result = await retryPage(projectId, pageId, currentVersion());
      bumpVersion(result.meta?.projectVersion);
      return result.data;
    },
    onMutate: () => setActionNotice(null),
    onSuccess: (_data, pageId) => {
      toast.message(`Retrying page ${pageNumberFor(pages, pageId)}…`);
      invalidatePagesAndSnapshot();
    },
    onError: (error, pageId) => handleCommandError(error, pageId),
  });

  const advanceMutation = useMutation({
    mutationFn: async (token: string) => {
      const result = await advancePlanStage(projectId, token, currentVersion());
      bumpVersion(result.meta?.projectVersion);
      return result.data;
    },
  });

  const advancePendingRef = useRef(false);
  const goToStyle = useCallback(async () => {
    if (advancePendingRef.current) return;
    if (styleReachable) {
      navigate(stageRoute(projectId, "STYLE"));
      return;
    }
    if (!planAdvanceToken) {
      toast.error(messageFor("error.gate.auto_advance_ineligible"));
      return;
    }
    advancePendingRef.current = true;
    try {
      const result = await advanceMutation.mutateAsync(planAdvanceToken);
      queryClient.setQueryData<ProjectSnapshotDTO>(
        qk.snapshot(projectId),
        (old) => (old ? { ...old, project: result.project, stages: result.stages } : old),
      );
      invalidatePagesAndSnapshot();
      navigate(stageRoute(projectId, "STYLE"), { replace: true });
    } catch (error) {
      invalidatePagesAndSnapshot();
      toast.error(errorText(error));
    } finally {
      advancePendingRef.current = false;
    }
  }, [
    advanceMutation,
    invalidatePagesAndSnapshot,
    navigate,
    planAdvanceToken,
    projectId,
    styleReachable,
  ]);

  // Fan-out once per exact set of missing/stale pages. The guard is a ref so
  // re-renders, StrictMode effects, and SSE refreshes cannot queue a second
  // generation. ERROR pages are excluded so Retry stays an explicit action.
  const attemptedSignatureRef = useRef<string | null>(null);
  const generationSignature = `${projectId}|${pages?.outlineVersionId ?? "none"}|${needsGeneration
    .map((summary) => `${summary.pageId}:${summary.plan.status}`)
    .sort()
    .join(",")}`;

  const { mutate: runGenerate } = generateMutation;
  useEffect(() => {
    if (locked || !pages || needsGeneration.length === 0) return;
    if (hasActivePlanJob || generateMutation.isPending) return;
    if (attemptedSignatureRef.current === generationSignature) return;
    attemptedSignatureRef.current = generationSignature;
    setGenerationError(null);
    setAnnouncement(`Planning ${needsGeneration.length} pages in the background.`);
    runGenerate();
  }, [
    locked,
    pages,
    needsGeneration.length,
    hasActivePlanJob,
    generateMutation.isPending,
    generationSignature,
    runGenerate,
  ]);

  const retryGeneration = useCallback(() => {
    attemptedSignatureRef.current = null;
    setGenerationError(null);
    runGenerate();
  }, [runGenerate]);

  const autoNavigatedRef = useRef(false);
  useEffect(() => {
    if (snapshot.project.mode !== "FULLY_AUTOMATIC") return;
    if (!pages || !planComplete || blockers.length > 0) return;
    if (!styleReachable && !planAdvanceToken) return;
    if (autoNavigatedRef.current) return;
    autoNavigatedRef.current = true;
    setAnnouncement("All plan pages are ready. Continuing to style selection.");
    void goToStyle();
  }, [
    blockers.length,
    goToStyle,
    pages,
    planAdvanceToken,
    planComplete,
    snapshot.project.mode,
    styleReachable,
  ]);

  const previousDoneRef = useRef<number | null>(null);
  useEffect(() => {
    if (!pages) return;
    if (previousDoneRef.current === null) {
      previousDoneRef.current = done;
      return;
    }
    if (previousDoneRef.current === done) return;
    previousDoneRef.current = done;
    if (total > 0 && done >= total) {
      setAnnouncement("All plan pages are ready.");
    } else if (hasActivePlanJob) {
      setAnnouncement(`Plan progress: ${done} of ${total} pages ready.`);
    }
  }, [pages, done, total, hasActivePlanJob]);

  // Recovery when the SSE stream is unavailable: refetch an artifact as soon
  // as the page projection says the page is done.
  const previousStatusRef = useRef<Record<string, string>>({});
  useEffect(() => {
    if (!pages) return;
    for (const summary of pages.pages) {
      const previous = previousStatusRef.current[summary.pageId];
      if (previous && previous !== summary.plan.status && summary.plan.status === "DONE") {
        invalidatePageArtifact(summary.pageId);
      }
      previousStatusRef.current[summary.pageId] = summary.plan.status;
    }
  }, [pages, invalidatePageArtifact]);

  const setTweakDraft = useCallback(
    (pageId: string, value: string) =>
      setTweakDrafts((current) => ({ ...current, [pageId]: value })),
    [],
  );
  const clearActionNotice = useCallback(() => setActionNotice(null), []);
  const clearTweakError = useCallback(() => setTweakError(null), []);

  const pageGenerating = Boolean(
    page &&
      (page.plan.status === "PLANNING" ||
        Boolean(page.activeJob?.type.toLowerCase().includes("plan")) ||
        snapshot.activeJobs.some(
          (job) =>
            job.pageId === page.pageId && job.type.toLowerCase().includes("plan"),
        )),
  );

  const selectedPageMutationPending =
    (regenerateMutation.isPending && regenerateMutation.variables === selectedPageId) ||
    (tweakMutation.isPending && tweakMutation.variables?.pageId === selectedPageId) ||
    (retryMutation.isPending && retryMutation.variables === selectedPageId);

  return {
    pagesQuery,
    pages,
    page,
    selectedPageId,
    selectedIndex,
    selectPage,
    goRelative,
    artifact: artifactQuery.data?.kind === "PLAN" ? artifactQuery.data : undefined,
    artifactQuery,
    artifactMissing: isApiNotFound(artifactQuery.error),
    total,
    done,
    percent,
    planErrorCount,
    planComplete,
    needsGeneration,
    hasActivePlanJob,
    locked,
    blockers,
    outlineConfirmed,
    styleReachable,
    canContinue,
    generationError,
    retryGeneration,
    tweakDrafts,
    setTweakDraft,
    actionNotice: actionNotice && actionNotice.pageId === selectedPageId ? actionNotice : null,
    tweakError: tweakError && tweakError.pageId === selectedPageId ? tweakError.message : null,
    clearActionNotice,
    clearTweakError,
    announcement,
    setAnnouncement,
    pageGenerating,
    fanoutPending: generateMutation.isPending,
    selectedPageMutationPending,
    continuing: advanceMutation.isPending,
    confirm: () => void goToStyle(),
    actions: {
      regenerate: (pageId: string) => regenerateMutation.mutate(pageId),
      tweak: (pageId: string, instruction: string) =>
        tweakMutation.mutate({ pageId, instruction }),
      retry: (pageId: string) => retryMutation.mutate(pageId),
    },
  };
}

function pageNumberFor(pages: PageListDTO | undefined, pageId: string): number {
  const index = pages?.pages.findIndex((summary) => summary.pageId === pageId) ?? -1;
  return index >= 0 ? index + 1 : 1;
}

export type PlanWorkbenchState = ReturnType<typeof usePlanWorkbench>;
