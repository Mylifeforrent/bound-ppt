import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { qk } from "@/api/keys";
import { api } from "@/api/client";
import type {
  OutlineDTO,
  ProjectSnapshotDTO,
  StageStateDTO,
} from "@/api/types";
import { stageRoute } from "@/hooks/useProjectData";
import { isEditableFocus, useCountdown } from "@/hooks/useCountdown";
import { errorText } from "@/lib/messages";
import { useStreamStore } from "@/stores/view";
import {
  advanceStage,
  confirmOutline,
  deleteOutlinePage,
  fetchOutline,
  generateOutline,
  insertOutlinePage,
  isConflict,
  isNotFound,
  moveOutlinePage,
  patchOutlineTitle,
  type OutlineInsertResult,
  type OutlineMutationResult,
} from "./api";
import { isGateViolation, isValidationError } from "./errors";
import type { InsertPageInput, MoveTarget } from "./types";
import { buildOptimisticMove, buildSectionGroups, fixedPageSlots } from "./types";

export interface MutationCallbacks<T> {
  onSuccess?: (data: T) => void;
  onError?: (error: unknown) => void;
}

interface UseOutlineBoardArgs {
  projectId: string;
  snapshot: ProjectSnapshotDTO;
}

const COUNTDOWN_MS = 3_000;

function tokenIsFresh(stage: StageStateDTO | undefined): boolean {
  if (!stage?.advanceToken) return false;
  if (!stage.advanceTokenExpiresAt) return true;
  const expires = Date.parse(stage.advanceTokenExpiresAt);
  return Number.isFinite(expires) && expires > Date.now();
}

/**
 * Server truth plus command wiring for the outline board.
 *
 * The outline, counts, confirmation state, stage blockers, and advance token
 * all come from the API. The optimistic move preview is only a local
 * preview and is replaced by the server-authored outline after every command.
 */
export function useOutlineBoard({ projectId, snapshot }: UseOutlineBoardArgs) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const [preview, setPreview] = useState<OutlineDTO | null>(null);
  const [pauseOverride, setPauseOverride] = useState<string | null>(null);
  const [advancing, setAdvancing] = useState(false);
  const [advanceError, setAdvanceError] = useState<string | null>(null);
  const [generationError, setGenerationError] = useState<string | null>(null);
  const [commandError, setCommandError] = useState<string | null>(null);

  const outlineQuery = useQuery({
    queryKey: qk.outline(projectId),
    queryFn: async () => (await fetchOutline(projectId)).data,
    retry: (failureCount, error) => !isNotFound(error) && failureCount < 2,
    staleTime: 2_000,
  });

  const committedOutline = outlineQuery.data;
  const outline = preview ?? committedOutline ?? null;
  const outlineNotFound = isNotFound(outlineQuery.error) && !committedOutline;
  const groups = useMemo(() => (outline ? buildSectionGroups(outline) : []), [outline]);
  const fixed = useMemo(() => (outline ? fixedPageSlots(outline) : null), [outline]);

  const streamDeltas = useStreamStore((state) => state.outlineDeltas[projectId]);
  const hasStreamDeltas = Boolean(
    streamDeltas && (streamDeltas.sections.length > 0 || streamDeltas.pages.length > 0),
  );

  const stage = snapshot.stages.find((state) => state.stage === "OUTLINE");
  const outlineActiveJob =
    snapshot.activeJobs.find((job) => job.type.toLowerCase().includes("outline")) ?? null;
  const profileDirty = snapshot.profileDirty;
  const stageBlockers = stage?.blockers ?? [];
  const blocked =
    profileDirty ||
    stageBlockers.length > 0 ||
    stage?.reachable === false;
  const modeAuto = snapshot.project.mode === "FULLY_AUTOMATIC";

  // Project version tracking. Every command sends the version last observed
  // from the snapshot or a command response, never a locally invented value.
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

  const committedRef = useRef<OutlineDTO | undefined>(committedOutline);
  committedRef.current = committedOutline;

  const invalidateViews = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: qk.snapshot(projectId) });
    void queryClient.invalidateQueries({ queryKey: qk.pages(projectId) });
  }, [queryClient, projectId]);

  const applyOutlineMutation = useCallback(
    (result: OutlineMutationResult) => {
      queryClient.setQueryData(qk.outline(projectId), result.outline);
      bumpVersion(result.stale?.projectVersion);
      invalidateViews();
    },
    [bumpVersion, invalidateViews, projectId, queryClient],
  );

  const handleMutationError = useCallback(
    (error: unknown) => {
      const message = errorText(error);
      if (isConflict(error)) {
        void queryClient.invalidateQueries({ queryKey: qk.outline(projectId) });
        invalidateViews();
        toast.error(message);
        return;
      }
      if (isGateViolation(error)) {
        invalidateViews();
        toast.error(message);
        return;
      }
      if (isValidationError(error)) return;
      toast.error(message);
    },
    [invalidateViews, projectId, queryClient],
  );

  const countdownEligible = Boolean(
    outline &&
      committedOutline &&
      committedOutline.pages.length > 0 &&
      !committedOutline.confirmed &&
      !blocked &&
      !outlineActiveJob &&
      modeAuto &&
      (stage?.reachable ?? false),
  );

  const runAdvanceRef = useRef<() => Promise<void>>(async () => undefined);

  const countdown = useCountdown({
    durationMs: COUNTDOWN_MS,
    enabled: countdownEligible && pauseOverride === null,
    onComplete: () => {
      void runAdvanceRef.current();
    },
    canComplete: () => !isEditableFocus(),
  });

  const pauseCountdown = useCallback((reason: string) => {
    setPauseOverride((current) => current ?? reason);
  }, []);

  const resumeCountdown = useCallback(() => {
    setPauseOverride(null);
    setAdvanceError(null);
    countdown.resume();
  }, [countdown]);

  /**
   * Reconcile with the server and confirm explicitly. Used when an advance token
   * or expected version went stale between the snapshot and the click; without
   * this fallback a user could be stuck on a fully generated outline.
   */
  const freshConfirm = useCallback(async () => {
    const fresh = await queryClient.fetchQuery<ProjectSnapshotDTO>({
      queryKey: qk.snapshot(projectId),
      queryFn: async () => (await api<ProjectSnapshotDTO>(`/api/projects/${projectId}/snapshot`)).data,
      staleTime: 0,
    });
    bumpVersion(fresh.project.version);
    const result = await confirmOutline(projectId, fresh.project.version);
    queryClient.setQueryData(qk.outline(projectId), result.data.outline);
    queryClient.setQueryData(qk.snapshot(projectId), result.data.snapshot);
    bumpVersion(result.data.snapshot.project.version);
    countdown.cancel();
    invalidateViews();
    navigate(stageRoute(projectId, "PLAN"), { replace: true });
  }, [bumpVersion, countdown, invalidateViews, navigate, projectId, queryClient]);

  const moveMutation = useMutation({
    mutationFn: async (variables: { pageId: string; target: MoveTarget }) => {
      const result = await moveOutlinePage(
        projectId,
        variables.pageId,
        variables.target,
        currentVersion(),
      );
      bumpVersion(result.meta?.projectVersion);
      return result.data;
    },
    onMutate: (variables) => {
      setCommandError(null);
      pauseCountdown("edit");
      const base = committedRef.current;
      if (!base) return;
      const optimistic = buildOptimisticMove(base, variables.pageId, variables.target);
      if (optimistic) setPreview(optimistic);
    },
    onSuccess: (result) => {
      setPreview(null);
      applyOutlineMutation(result);
    },
    onError: (error) => {
      setPreview(null);
      if (isValidationError(error)) setCommandError(errorText(error));
      handleMutationError(error);
    },
  });

  const titleMutation = useMutation({
    mutationFn: async (variables: { pageId: string; title: string }) => {
      const result = await patchOutlineTitle(
        projectId,
        variables.pageId,
        variables.title,
        currentVersion(),
      );
      bumpVersion(result.meta?.projectVersion);
      return result.data;
    },
    onMutate: () => {
      setCommandError(null);
      pauseCountdown("edit");
    },
    onSuccess: (result) => applyOutlineMutation(result),
    onError: (error) => handleMutationError(error),
  });

  const insertMutation = useMutation({
    mutationFn: async (input: InsertPageInput) => {
      const result = await insertOutlinePage(projectId, input, currentVersion());
      bumpVersion(result.meta?.projectVersion);
      return result.data;
    },
    onMutate: () => {
      setCommandError(null);
      pauseCountdown("edit");
    },
    onSuccess: (result) => applyOutlineMutation(result),
    onError: (error) => handleMutationError(error),
  });

  const deleteMutation = useMutation({
    mutationFn: async (pageId: string) => {
      const result = await deleteOutlinePage(projectId, pageId, currentVersion());
      bumpVersion(result.meta?.projectVersion);
      return result.data;
    },
    onMutate: () => {
      setCommandError(null);
      pauseCountdown("edit");
    },
    onSuccess: (result) => applyOutlineMutation(result),
    onError: (error) => {
      if (isValidationError(error)) setCommandError(errorText(error));
      handleMutationError(error);
    },
  });

  const generateMutation = useMutation({
    mutationFn: async () => {
      const result = await generateOutline(projectId, currentVersion());
      bumpVersion(result.meta?.projectVersion);
      return result.data;
    },
    onMutate: () => {
      setGenerationError(null);
      pauseCountdown("edit");
    },
    onSuccess: () => {
      toast.message("Generating the outline…");
      void queryClient.invalidateQueries({ queryKey: qk.outline(projectId) });
      invalidateViews();
    },
    onError: (error) => {
      setGenerationError(errorText(error));
      handleMutationError(error);
    },
  });

  const advanceMutation = useMutation({
    mutationFn: async (advanceToken: string) => {
      const result = await advanceStage(projectId, "OUTLINE", advanceToken, currentVersion());
      bumpVersion(result.meta?.projectVersion);
      return result.data;
    },
  });

  const confirmMutation = useMutation({
    mutationFn: async () => {
      const result = await confirmOutline(projectId, currentVersion());
      bumpVersion(result.meta?.projectVersion);
      return result.data;
    },
  });

  const latestRef = useRef({ stage, blocked, outline });
  latestRef.current = { stage, blocked, outline };

  const advancingRef = useRef(false);
  const advance = useCallback(async () => {
    if (advancingRef.current) return;
    const latest = latestRef.current;
    if (!latest.outline || latest.outline.confirmed) return;
    if (latest.blocked) {
      setPauseOverride("user");
      setAdvanceError(
        "The outline cannot advance while the requirements profile or a stage blocker is unresolved.",
      );
      return;
    }
    advancingRef.current = true;
    setAdvancing(true);
    setAdvanceError(null);
    try {
      const token = latest.stage?.advanceToken;
      if (token && tokenIsFresh(latest.stage)) {
        const result = await advanceMutation.mutateAsync(token);
        bumpVersion(result.project.version);
        queryClient.setQueryData<ProjectSnapshotDTO>(
          qk.snapshot(projectId),
          (old) => (old ? { ...old, project: result.project, stages: result.stages } : old),
        );
      } else {
        const result = await confirmMutation.mutateAsync();
        queryClient.setQueryData(qk.outline(projectId), result.outline);
        queryClient.setQueryData(qk.snapshot(projectId), result.snapshot);
        bumpVersion(result.snapshot.project.version);
      }
      pauseCountdown("user");
      countdown.cancel();
      invalidateViews();
      void queryClient.invalidateQueries({ queryKey: qk.outline(projectId) });
      navigate(stageRoute(projectId, "PLAN"), { replace: true });
    } catch (error) {
      if (isConflict(error) || isGateViolation(error)) {
        try {
          await freshConfirm();
          return;
        } catch (retryError) {
          setPauseOverride("user");
          setAdvanceError(errorText(retryError));
          handleMutationError(retryError);
          return;
        }
      }
      setPauseOverride("user");
      setAdvanceError(errorText(error));
      handleMutationError(error);
    } finally {
      advancingRef.current = false;
      setAdvancing(false);
    }
  }, [
    advanceMutation,
    bumpVersion,
    confirmMutation,
    countdown,
    freshConfirm,
    handleMutationError,
    invalidateViews,
    navigate,
    pauseCountdown,
    projectId,
    queryClient,
  ]);
  runAdvanceRef.current = advance;

  const confirmNow = useCallback(async () => {
    if (advancingRef.current) return;
    advancingRef.current = true;
    setAdvancing(true);
    setAdvanceError(null);
    setPauseOverride("user");
    try {
      const result = await confirmMutation.mutateAsync();
      queryClient.setQueryData(qk.outline(projectId), result.outline);
      queryClient.setQueryData(qk.snapshot(projectId), result.snapshot);
      bumpVersion(result.snapshot.project.version);
      countdown.cancel();
      invalidateViews();
      navigate(stageRoute(projectId, "PLAN"), { replace: true });
    } catch (error) {
      if (isConflict(error) || isGateViolation(error)) {
        try {
          await freshConfirm();
          return;
        } catch (retryError) {
          setAdvanceError(errorText(retryError));
          handleMutationError(retryError);
          return;
        }
      }
      setAdvanceError(errorText(error));
      handleMutationError(error);
    } finally {
      advancingRef.current = false;
      setAdvancing(false);
    }
  }, [
    bumpVersion,
    confirmMutation,
    countdown,
    freshConfirm,
    handleMutationError,
    invalidateViews,
    navigate,
    projectId,
    queryClient,
  ]);

  const continueToPlan = useCallback(() => {
    navigate(stageRoute(projectId, "PLAN"));
  }, [navigate, projectId]);

  const move = useCallback(
    (pageId: string, target: MoveTarget, callbacks?: MutationCallbacks<OutlineMutationResult>) =>
      moveMutation.mutate({ pageId, target }, callbacks),
    [moveMutation],
  );

  const saveTitle = useCallback(
    (
      pageId: string,
      title: string,
      callbacks?: MutationCallbacks<OutlineMutationResult>,
    ) => titleMutation.mutate({ pageId, title }, callbacks),
    [titleMutation],
  );

  const insert = useCallback(
    (input: InsertPageInput, callbacks?: MutationCallbacks<OutlineInsertResult>) =>
      insertMutation.mutate(input, callbacks),
    [insertMutation],
  );

  const removePage = useCallback(
    (pageId: string, callbacks?: MutationCallbacks<OutlineMutationResult>) =>
      deleteMutation.mutate(pageId, callbacks),
    [deleteMutation],
  );

  const generate = useCallback(() => generateMutation.mutate(), [generateMutation]);

  const busy =
    moveMutation.isPending ||
    titleMutation.isPending ||
    insertMutation.isPending ||
    deleteMutation.isPending ||
    generateMutation.isPending ||
    confirmMutation.isPending ||
    advancing ||
    Boolean(outlineActiveJob);

  const pendingPageId = moveMutation.isPending
    ? moveMutation.variables?.pageId
    : titleMutation.isPending
      ? titleMutation.variables?.pageId
      : deleteMutation.isPending
        ? deleteMutation.variables
        : null;

  const paused = pauseOverride !== null || countdown.status === "paused";
  const running =
    pauseOverride === null &&
    (countdown.status === "running" ||
      (countdownEligible && countdown.status === "idle"));
  const pausedReason = pauseOverride ?? countdown.pauseReason;
  const progress = Math.max(
    0,
    Math.min(100, ((pauseOverride !== null ? COUNTDOWN_MS : countdown.remainingMs) / COUNTDOWN_MS) * 100),
  );

  return {
    projectId,
    snapshot,
    outlineQuery,
    outline,
    committedOutline,
    outlineNotFound,
    groups,
    fixed,
    isLoading: outlineQuery.isLoading,
    queryError: outlineQuery.error,
    streamDeltas,
    hasStreamDeltas,
    stage,
    stageBlockers,
    profileDirty,
    blocked,
    modeAuto,
    countdownEligible,
    countdown: {
      status: countdown.status,
      remainingSeconds: pauseOverride !== null ? Math.ceil(COUNTDOWN_MS / 1000) : countdown.remainingSeconds,
      remainingMs: countdown.remainingMs,
      progress,
      paused,
      running,
      pausedReason,
      pauseOverride,
      durationMs: COUNTDOWN_MS,
    },
    advancing,
    advanceError,
    pauseCountdown,
    resumeCountdown,
    advance,
    confirmNow,
    continueToPlan,
    generationError,
    commandError,
    clearCommandError: () => setCommandError(null),
    busy,
    inserting: insertMutation.isPending,
    generating: generateMutation.isPending,
    pendingPageId,
    activeOutlineJob: outlineActiveJob,
    actions: {
      move,
      saveTitle,
      insert,
      removePage,
      generate,
    },
  };
}

export type OutlineBoardState = ReturnType<typeof useOutlineBoard>;
