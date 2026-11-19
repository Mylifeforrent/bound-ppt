import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/api/client";
import { qk } from "@/api/keys";
import type {
  ArtifactDTO,
  PageHistoryDTO,
  PageListDTO,
  PageSummaryDTO,
  ProjectSnapshotDTO,
  StaleSummaryDTO,
} from "@/api/types";
import { stageRoute } from "@/hooks/useProjectData";
import { errorText, messageFor } from "@/lib/messages";
import { useViewStore } from "@/stores/view";
import { uuid } from "@/lib/utils";
import {
  isApiConflict,
  isApiNotFound,
  isApiValidation,
  isGateViolation,
} from "./apiErrors";

export interface PageJobAcceptedDTO {
  jobId: string;
  pageId: string;
}

export interface GenerateDesignResultDTO {
  jobs: Array<{ pageId: string; jobId: string }>;
  skippedPageIds: string[];
  counts: { required: number; scheduled: number; reused: number };
}

export interface UndoDesignResultDTO {
  artifact: ArtifactDTO;
  history: PageHistoryDTO;
  stale: StaleSummaryDTO | null;
}

export interface DesignBlocker {
  code: string;
  message: string;
  action?: string;
  href?: string;
}

export interface DesignActionNotice {
  pageId: string;
  kind: "single_layout" | "error";
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

interface UseDesignWorkbenchArgs {
  projectId: string;
  snapshot: ProjectSnapshotDTO;
}

/**
 * All server truth for the design workbench. Every status, version, history
 * entry, and progress number comes from the API; nothing is computed from a
 * local timer or counter.
 */
export function useDesignWorkbench({ projectId, snapshot }: UseDesignWorkbenchArgs) {
  const queryClient = useQueryClient();

  const selectedPageId = useViewStore((s) => s.selectedPageId);
  const pinnedPageId = useViewStore((s) => s.pinnedPageId);
  const lastDesignPageId = useViewStore((s) => s.lastDesignPageId);
  const setSelectedPage = useViewStore((s) => s.setSelectedPage);
  const setPinnedPage = useViewStore((s) => s.setPinnedPage);
  const setLastDesignPage = useViewStore((s) => s.setLastDesignPage);

  const [actionNotice, setActionNotice] = useState<DesignActionNotice | null>(null);
  const [tweakError, setTweakError] = useState<{ pageId: string; message: string } | null>(null);
  const [generationError, setGenerationError] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const [tweakDrafts, setTweakDrafts] = useState<Record<string, string>>({});

  const pagesQuery = useQuery({
    queryKey: qk.pages(projectId),
    queryFn: async () => (await api<PageListDTO>(`/api/projects/${projectId}/pages`)).data,
    staleTime: 1_000,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return false;
      const active = data.pages.some(
        (page) => page.design.status === "DESIGNING" || page.activeJob,
      );
      if (active) return 2_000;
      const incomplete = data.pages.some(
        (page) => page.design.status === "PENDING" || page.design.status === "STALE",
      );
      // A slow safety net for a dropped SSE stream; page status stays
      // server-derived and never advances from a local timer.
      return incomplete ? 5_000 : false;
    },
  });
  const pages = pagesQuery.data;

  // Restore the selection, but never let a background generation move it.
  // The effect only acts when the stored page is missing from the deck.
  useEffect(() => {
    if (!pages?.pages.length) return;
    const ids = new Set(pages.pages.map((page) => page.pageId));
    if (selectedPageId && ids.has(selectedPageId)) {
      if (lastDesignPageId !== selectedPageId) setLastDesignPage(selectedPageId);
      return;
    }
    const fallback =
      pages.pages.find((page) => page.pageId === lastDesignPageId) ??
      (selectedPageId ? undefined : pages.pages.find((page) => page.design.status !== "DONE")) ??
      pages.pages[0];
    if (!fallback) return;
    setSelectedPage(fallback.pageId);
    setLastDesignPage(fallback.pageId);
  }, [pages, selectedPageId, lastDesignPageId, setSelectedPage, setLastDesignPage]);

  useEffect(() => {
    if (!pages || !pinnedPageId) return;
    if (!pages.pages.some((page) => page.pageId === pinnedPageId)) setPinnedPage(null);
  }, [pages, pinnedPageId, setPinnedPage]);

  const selectedIndex = pages ? pages.pages.findIndex((page) => page.pageId === selectedPageId) : -1;
  const page: PageSummaryDTO | undefined = selectedIndex >= 0 ? pages?.pages[selectedIndex] : undefined;

  const selectPage = useCallback(
    (pageId: string, pin = true) => {
      setSelectedPage(pageId);
      setLastDesignPage(pageId);
      if (pin) setPinnedPage(pageId);
      setActionNotice(null);
      setTweakError(null);
    },
    [setSelectedPage, setLastDesignPage, setPinnedPage],
  );

  const goRelative = useCallback(
    (delta: number) => {
      if (!pages?.pages.length) return;
      const base = selectedIndex >= 0 ? selectedIndex : 0;
      const target = pages.pages[Math.max(0, Math.min(pages.pages.length - 1, base + delta))];
      if (target && target.pageId !== selectedPageId) selectPage(target.pageId, true);
    },
    [pages, selectedIndex, selectedPageId, selectPage],
  );

  const artifactQuery = useQuery({
    queryKey: qk.artifact(projectId, selectedPageId ?? "none", "design"),
    queryFn: async () =>
      (
        await api<ArtifactDTO>(
          `/api/projects/${projectId}/pages/${selectedPageId}/artifacts/design`,
        )
      ).data,
    enabled: Boolean(selectedPageId),
    retry: (failureCount, error) => !isApiNotFound(error) && failureCount < 2,
    staleTime: 0,
  });

  const historyQuery = useQuery({
    queryKey: qk.history(projectId, selectedPageId ?? "none", "design"),
    queryFn: async () =>
      (
        await api<PageHistoryDTO>(
          `/api/projects/${projectId}/pages/${selectedPageId}/history?kind=design`,
        )
      ).data,
    enabled: Boolean(selectedPageId),
    staleTime: 30_000,
    retry: 1,
  });

  const thumbnailPages = useMemo(
    () => (pages?.pages ?? []).filter((summary) => Boolean(summary.design.artifactVersionId)),
    [pages],
  );
  const thumbnailQueries = useQueries({
    queries: thumbnailPages.map((summary) => ({
      queryKey: qk.artifact(projectId, summary.pageId, "design"),
      queryFn: async () =>
        (
          await api<ArtifactDTO>(
            `/api/projects/${projectId}/pages/${summary.pageId}/artifacts/design`,
          )
        ).data,
      staleTime: 60_000,
      retry: false,
    })),
  });
  const thumbnails = useMemo(() => {
    const map: Record<string, ArtifactDTO | undefined> = {};
    thumbnailPages.forEach((summary, index) => {
      map[summary.pageId] = thumbnailQueries[index]?.data;
    });
    return map;
  }, [thumbnailPages, thumbnailQueries]);

  const total = pages?.counts.total ?? snapshot.counts.designTotal;
  const done = pages?.counts.designDone ?? snapshot.counts.designDone;
  const percent = total > 0 ? (done / total) * 100 : 0;

  const planTotal = pages?.counts.total ?? snapshot.counts.planTotal;
  const planDone = pages?.counts.planDone ?? snapshot.counts.planDone;
  const planComplete = planTotal > 0 && planDone >= planTotal;
  const styleSelection = snapshot.styleSelection;
  const styleConfirmed = styleSelection?.confirmed === true;
  const designStage = snapshot.stages.find((state) => state.stage === "DESIGN");

  const needsGeneration = useMemo(
    () =>
      (pages?.pages ?? []).filter(
        (summary) => summary.design.status === "PENDING" || summary.design.status === "STALE",
      ),
    [pages],
  );

  const blockers = useMemo<DesignBlocker[]>(() => {
    if (!pages) return [];
    const list: DesignBlocker[] = [];
    if (pages.pages.length === 0) {
      list.push({
        code: "no_pages",
        message: "There are no deck pages yet. Generate and confirm the outline first.",
        action: "Open outline",
        href: stageRoute(projectId, "OUTLINE"),
      });
    } else if (!planComplete) {
      list.push({
        code: "plan_incomplete",
        message: "Finish the plan draft for every page before the design draft can run.",
        action: "Open plan draft",
        href: stageRoute(projectId, "PLAN"),
      });
    }
    if (!styleConfirmed) {
      list.push({
        code: "style_unconfirmed",
        message: styleSelection
          ? "Confirm the selected style before design pages can be generated."
          : "Choose and confirm a style before design pages can be generated.",
        action: "Open style selection",
        href: stageRoute(projectId, "STYLE"),
      });
    }
    const seen = new Set(list.map((item) => item.code));
    const coveredCodes = new Set(["plan_incomplete", "style_unconfirmed"]);
    for (const blocker of designStage?.blockers ?? []) {
      if (coveredCodes.has(blocker.code) || seen.has(blocker.code)) continue;
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
    return list;
  }, [pages, planComplete, styleConfirmed, styleSelection, designStage, projectId]);

  const ready =
    styleConfirmed &&
    planComplete &&
    Boolean(pages?.pages.length) &&
    blockers.length === 0 &&
    (designStage?.reachable ?? true);
  const hasSnapshotDesignJob = snapshot.activeJobs.some((job) =>
    job.type.toLowerCase().includes("design"),
  );

  const invalidatePagesAndSnapshot = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: qk.pages(projectId) });
    void queryClient.invalidateQueries({ queryKey: qk.snapshot(projectId) });
  }, [queryClient, projectId]);

  const invalidatePageArtifact = useCallback(
    (pageId: string) => {
      void queryClient.invalidateQueries({ queryKey: qk.artifact(projectId, pageId, "design") });
      void queryClient.invalidateQueries({ queryKey: qk.history(projectId, pageId, "design") });
    },
    [queryClient, projectId],
  );

  const handleCommandError = useCallback(
    (error: unknown, pageId: string) => {
      if (isApiConflict(error)) {
        void queryClient.invalidateQueries({ queryKey: qk.snapshot(projectId) });
        void queryClient.invalidateQueries({ queryKey: qk.pages(projectId) });
        invalidatePageArtifact(pageId);
        toast.error(errorText(error));
        return;
      }
      if (isGateViolation(error, "error.gate.page_write_in_progress")) {
        void queryClient.invalidateQueries({ queryKey: qk.pages(projectId) });
        setActionNotice({ pageId, kind: "error", message: errorText(error) });
        return;
      }
      if (isGateViolation(error, "error.gate.single_layout_use_tweak")) {
        setActionNotice({ pageId, kind: "single_layout", message: errorText(error) });
        return;
      }
      setActionNotice({ pageId, kind: "error", message: errorText(error) });
    },
    [queryClient, projectId, invalidatePageArtifact],
  );

  const pageNumberFor = useCallback(
    (pageId: string) => {
      const index = pages?.pages.findIndex((summary) => summary.pageId === pageId) ?? -1;
      return index >= 0 ? index + 1 : 1;
    },
    [pages],
  );

  const generateMutation = useMutation({
    mutationFn: async () =>
      (
        await api<GenerateDesignResultDTO>(`/api/projects/${projectId}/design/generate`, {
          method: "POST",
          body: {},
          expectedVersion: snapshot.project.version,
          idempotencyKey: uuid(),
        })
      ).data,
    onSuccess: (data) => {
      setGenerationError(null);
      invalidatePagesAndSnapshot();
      const scheduled = data.jobs?.length ?? 0;
      const required = data.counts?.required ?? data.jobs?.length ?? 0;
      const reused = data.counts?.reused ?? 0;
      setAnnouncement(
        scheduled > 0
          ? `Design generation started for ${scheduled} of ${required} pages. ${reused} pages reused an existing design.`
          : "No new design jobs were needed. Existing design pages were reused.",
      );
    },
    onError: (error) => {
      setGenerationError(errorText(error));
      if (isApiConflict(error)) {
        void queryClient.invalidateQueries({ queryKey: qk.snapshot(projectId) });
        void queryClient.invalidateQueries({ queryKey: qk.pages(projectId) });
        toast.error(errorText(error));
      } else if (isGateViolation(error)) {
        void queryClient.invalidateQueries({ queryKey: qk.snapshot(projectId) });
        void queryClient.invalidateQueries({ queryKey: qk.pages(projectId) });
      } else {
        toast.error(errorText(error));
      }
    },
  });

  const regenerateMutation = useMutation({
    mutationFn: async (pageId: string) =>
      (
        await api<PageJobAcceptedDTO>(
          `/api/projects/${projectId}/pages/${pageId}/design/regenerate`,
          {
            method: "POST",
            body: {},
            expectedVersion: snapshot.project.version,
            idempotencyKey: uuid(),
          },
        )
      ).data,
    onMutate: () => setActionNotice(null),
    onSuccess: (_data, pageId) => {
      toast.message(`Regenerating page ${pageNumberFor(pageId)}…`);
      invalidatePagesAndSnapshot();
    },
    onError: (error, pageId) => handleCommandError(error, pageId),
  });

  const tweakMutation = useMutation({
    mutationFn: async (variables: { pageId: string; instruction: string }) =>
      (
        await api<PageJobAcceptedDTO>(
          `/api/projects/${projectId}/pages/${variables.pageId}/design/tweak`,
          {
            method: "POST",
            body: { instruction: variables.instruction },
            expectedVersion: snapshot.project.version,
            idempotencyKey: uuid(),
          },
        )
      ).data,
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
      toast.message("Applying your tweak to this page…");
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

  const undoMutation = useMutation({
    mutationFn: async (pageId: string) =>
      (
        await api<UndoDesignResultDTO>(
          `/api/projects/${projectId}/pages/${pageId}/undo`,
          {
            method: "POST",
            body: { kind: "design" },
            expectedVersion: snapshot.project.version,
            idempotencyKey: uuid(),
          },
        )
      ).data,
    onMutate: () => setActionNotice(null),
    onSuccess: (data, pageId) => {
      queryClient.setQueryData(qk.artifact(projectId, pageId, "design"), data.artifact);
      queryClient.setQueryData(qk.history(projectId, pageId, "design"), data.history);
      invalidatePageArtifact(pageId);
      invalidatePagesAndSnapshot();
      toast.success("Restored the previous version of this page.");
    },
    onError: (error, pageId) => handleCommandError(error, pageId),
  });

  const retryMutation = useMutation({
    mutationFn: async (pageId: string) =>
      (
        await api<PageJobAcceptedDTO>(`/api/projects/${projectId}/pages/${pageId}/retry`, {
          method: "POST",
          body: { kind: "design" },
          expectedVersion: snapshot.project.version,
          idempotencyKey: uuid(),
        })
      ).data,
    onMutate: () => setActionNotice(null),
    onSuccess: (_data, pageId) => {
      toast.message(`Retrying page ${pageNumberFor(pageId)}…`);
      invalidatePagesAndSnapshot();
    },
    onError: (error, pageId) => handleCommandError(error, pageId),
  });

  const activeDesignJob =
    generateMutation.isPending ||
    hasSnapshotDesignJob ||
    Boolean(
      pages?.pages.some(
        (summary) => summary.design.status === "DESIGNING" || Boolean(summary.activeJob),
      ),
    );

  // One entry-time fan-out per exact set of missing/stale pages. The guard is
  // a ref so re-renders, StrictMode double effects, and SSE refreshes cannot
  // queue a second generation. ERROR pages are intentionally excluded: they
  // expose Retry instead of silently re-running.
  const attemptedSignatureRef = useRef<string | null>(null);
  const generationSignature = `${projectId}|${pages?.outlineVersionId ?? "none"}|${
    styleSelection?.styleKey ?? "none"
  }@${styleSelection?.styleVersion ?? 0}|${needsGeneration
    .map((summary) => `${summary.pageId}:${summary.design.status}`)
    .sort()
    .join(",")}`;

  const { mutate: runGenerate } = generateMutation;
  useEffect(() => {
    if (!ready || !pages || needsGeneration.length === 0) return;
    if (activeDesignJob || generateMutation.isPending) return;
    if (attemptedSignatureRef.current === generationSignature) return;
    attemptedSignatureRef.current = generationSignature;
    setGenerationError(null);
    setAnnouncement(`Generating design pages. ${done} of ${total} pages are ready.`);
    runGenerate();
  }, [
    ready,
    pages,
    needsGeneration.length,
    activeDesignJob,
    generateMutation.isPending,
    generationSignature,
    runGenerate,
    done,
    total,
  ]);

  const retryGeneration = useCallback(() => {
    attemptedSignatureRef.current = null;
    setGenerationError(null);
    runGenerate();
  }, [runGenerate]);

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
      setAnnouncement("All design pages are ready.");
    } else if (activeDesignJob) {
      setAnnouncement(`Design progress: ${done} of ${total} pages ready.`);
    }
  }, [pages, done, total, activeDesignJob]);

  // Recovery when the SSE stream is unavailable: a page that finishes gets
  // its artifact and history refetched as soon as the pages projection says
  // DONE.
  const previousStatusRef = useRef<Record<string, string>>({});
  useEffect(() => {
    if (!pages) return;
    for (const summary of pages.pages) {
      const previous = previousStatusRef.current[summary.pageId];
      if (previous && previous !== summary.design.status && summary.design.status === "DONE") {
        invalidatePageArtifact(summary.pageId);
      }
      previousStatusRef.current[summary.pageId] = summary.design.status;
    }
  }, [pages, invalidatePageArtifact]);

  const artifact = artifactQuery.data;
  const history = historyQuery.data;
  const canUndo = history?.canUndo ?? artifact?.history.canUndo ?? false;
  const historyDepth = history?.depth ?? artifact?.history.depth ?? 0;
  const historyMissing = isApiNotFound(historyQuery.error);

  const selectedPageMutationPending =
    (regenerateMutation.isPending && regenerateMutation.variables === selectedPageId) ||
    (tweakMutation.isPending && tweakMutation.variables?.pageId === selectedPageId) ||
    (undoMutation.isPending && undoMutation.variables === selectedPageId) ||
    (retryMutation.isPending && retryMutation.variables === selectedPageId);

  const pageGenerating = Boolean(
    page &&
      (page.design.status === "DESIGNING" ||
        Boolean(page.activeJob) ||
        snapshot.activeJobs.some((job) => job.pageId === page.pageId)),
  );

  const setTweakDraft = useCallback(
    (pageId: string, value: string) =>
      setTweakDrafts((current) => ({ ...current, [pageId]: value })),
    [],
  );
  const clearActionNotice = useCallback(() => setActionNotice(null), []);
  const clearTweakError = useCallback(() => setTweakError(null), []);

  return {
    pagesQuery,
    pages,
    page,
    selectedPageId,
    selectedIndex,
    pinnedPageId,
    selectPage,
    goRelative,
    artifact,
    artifactQuery,
    artifactMissing: isApiNotFound(artifactQuery.error),
    history,
    historyQuery,
    historyMissing,
    canUndo,
    historyDepth,
    thumbnails,
    total,
    done,
    percent,
    planComplete,
    styleConfirmed,
    styleSelection,
    ready,
    blockers,
    needsGeneration,
    activeDesignJob,
    pageGenerating,
    selectedPageMutationPending,
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
    actions: {
      regenerate: (pageId: string) => regenerateMutation.mutate(pageId),
      tweak: (pageId: string, instruction: string) =>
        tweakMutation.mutate({ pageId, instruction }),
      undo: (pageId: string) => undoMutation.mutate(pageId),
      retry: (pageId: string) => retryMutation.mutate(pageId),
    },
  };
}

export type DesignWorkbenchState = ReturnType<typeof useDesignWorkbench>;
