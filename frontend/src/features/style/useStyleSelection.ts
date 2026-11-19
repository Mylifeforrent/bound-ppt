import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { qk } from "@/api/keys";
import type {
  ProjectSnapshotDTO,
  StyleDTO,
  StyleSelectionDTO,
} from "@/api/types";
import { stageRoute } from "@/hooks/useProjectData";
import { errorText, messageFor } from "@/lib/messages";
import {
  confirmStyle,
  fetchStyles,
  isApiConflict,
  isGateViolation,
  putStyle,
} from "./api";

export interface StyleBlocker {
  code: string;
  message: string;
  action?: string;
  href?: string;
}

const STAGE_LABEL: Record<string, string> = {
  INTAKE: "material intake",
  RESEARCH: "research",
  OUTLINE: "outline",
  PLAN: "plan draft",
  STYLE: "style selection",
  DESIGN: "design draft",
};

function summaryFromSelection(selection: StyleSelectionDTO) {
  return {
    styleKey: selection.styleKey,
    styleVersion: selection.styleVersion,
    confirmed: selection.confirmed,
    confirmedAt: selection.confirmedAt,
  };
}

export function useStyleSelection({
  projectId,
  snapshot,
}: {
  projectId: string;
  snapshot: ProjectSnapshotDTO;
}) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [savedKey, setSavedKey] = useState<string | null>(null);
  const [remember, setRemember] = useState(false);
  const [selectionError, setSelectionError] = useState<string | null>(null);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const savedKeyRef = useRef<string | null>(null);

  const stylesQuery = useQuery({
    queryKey: qk.styles,
    queryFn: async () => (await fetchStyles()).data.styles,
    staleTime: 5 * 60_000,
    retry: 1,
  });
  const styles = stylesQuery.data ?? [];

  const initializedRef = useRef(false);
  useEffect(() => {
    if (initializedRef.current) return;
    const last = snapshot.styleSelection;
    if (last) {
      setSelectedKey(last.styleKey);
      setSavedKey(last.styleKey);
      savedKeyRef.current = last.styleKey;
    }
    initializedRef.current = true;
  }, [snapshot.styleSelection]);

  const selectedStyle = useMemo(
    () => styles.find((style) => style.styleKey === selectedKey) ?? null,
    [styles, selectedKey],
  );
  const lastUsed = snapshot.styleSelection;
  const lastUsedStyle = useMemo(
    () => styles.find((style) => style.styleKey === lastUsed?.styleKey),
    [lastUsed?.styleKey, styles],
  );

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

  const seedSnapshotSelection = useCallback(
    (selection: StyleSelectionDTO) => {
      queryClient.setQueryData<ProjectSnapshotDTO>(qk.snapshot(projectId), (old) =>
        old ? { ...old, styleSelection: summaryFromSelection(selection) } : old,
      );
    },
    [projectId, queryClient],
  );

  const invalidateSnapshot = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: qk.snapshot(projectId) });
  }, [projectId, queryClient]);

  const putMutation = useMutation({
    mutationFn: async (variables: {
      styleKey: string;
      styleVersion: number;
      rememberPreference: boolean;
    }) => {
      const result = await putStyle(projectId, variables, currentVersion());
      bumpVersion(result.meta?.projectVersion);
      return result.data.styleSelection;
    },
    onMutate: (variables) => {
      setSelectedKey(variables.styleKey);
      setSelectionError(null);
      setSavedKey(null);
      savedKeyRef.current = null;
    },
    onSuccess: (selection) => {
      setSelectedKey(selection.styleKey);
      setSavedKey(selection.styleKey);
      savedKeyRef.current = selection.styleKey;
      setRemember(selection.rememberPreference);
      seedSnapshotSelection(selection);
    },
    onError: (error) => {
      if (isApiConflict(error)) {
        invalidateSnapshot();
        toast.error(errorText(error));
        setSelectionError(errorText(error));
        return;
      }
      if (isGateViolation(error)) invalidateSnapshot();
      setSelectionError(errorText(error));
    },
  });

  const selectedStyleRef = useRef<StyleDTO | null>(selectedStyle);
  selectedStyleRef.current = selectedStyle;
  const rememberRef = useRef(remember);
  rememberRef.current = remember;

  const confirmMutation = useMutation({
    mutationFn: async () => {
      let version = currentVersion();
      const style = selectedStyleRef.current;
      if (!style) {
        throw new Error(messageFor("ui.form.style_required"));
      }
      if (savedKeyRef.current !== style.styleKey) {
        const putResult = await putStyle(
          projectId,
          {
            styleKey: style.styleKey,
            styleVersion: style.version,
            rememberPreference: rememberRef.current,
          },
          version,
        );
        bumpVersion(putResult.meta?.projectVersion);
        seedSnapshotSelection(putResult.data.styleSelection);
        savedKeyRef.current = style.styleKey;
        setSavedKey(style.styleKey);
        setSelectedKey(style.styleKey);
        version = currentVersion();
      }
      const result = await confirmStyle(projectId, version);
      bumpVersion(result.meta?.projectVersion);
      return result.data;
    },
    onMutate: () => {
      setConfirmError(null);
      setSelectionError(null);
    },
    onSuccess: async (data) => {
      seedSnapshotSelection(data.styleSelection);
      // Wait for the refreshed snapshot before navigating so the route guard
      // sees the unlocked design stage instead of redirecting back here.
      await queryClient.invalidateQueries({ queryKey: qk.snapshot(projectId) });
      await queryClient.invalidateQueries({ queryKey: qk.pages(projectId) });
      toast.success("Style confirmed. Opening the design draft.");
      navigate(stageRoute(projectId, "DESIGN"), { replace: true });
    },
    onError: (error) => {
      if (isApiConflict(error) || isGateViolation(error)) invalidateSnapshot();
      if (isApiConflict(error)) toast.error(errorText(error));
      setConfirmError(errorText(error));
    },
  });

  const selectStyle = useCallback(
    (style: StyleDTO) => {
      if (putMutation.isPending || confirmMutation.isPending) return;
      setSelectedKey(style.styleKey);
      setSelectionError(null);
      setConfirmError(null);
      if (
        savedKeyRef.current === style.styleKey &&
        snapshot.styleSelection?.styleKey === style.styleKey
      ) {
        return;
      }
      putMutation.mutate({
        styleKey: style.styleKey,
        styleVersion: style.version,
        rememberPreference: remember,
      });
    },
    [confirmMutation.isPending, putMutation, remember, snapshot.styleSelection?.styleKey],
  );

  const toggleRemember = useCallback(
    (next: boolean) => {
      setRemember(next);
      const style = selectedStyleRef.current;
      if (!style) return;
      if (savedKeyRef.current !== style.styleKey) return;
      if (putMutation.isPending) return;
      putMutation.mutate({
        styleKey: style.styleKey,
        styleVersion: style.version,
        rememberPreference: next,
      });
    },
    [putMutation],
  );

  const styleStage = snapshot.stages.find((state) => state.stage === "STYLE");
  const planBlocked = Boolean(
    styleStage?.blockers.some(
      (blocker) =>
        blocker.code === "plan_incomplete" ||
        blocker.messageKey === "error.gate.plan_incomplete",
    ),
  );
  const planTotal = snapshot.counts.planTotal;
  const planDone = snapshot.counts.planDone;
  const planIncomplete = planBlocked || planTotal === 0 || planDone < planTotal;

  const blockers = useMemo<StyleBlocker[]>(() => {
    const list: StyleBlocker[] = [];
    if (planIncomplete) {
      list.push({
        code: "plan_incomplete",
        message: `Finish the plan draft for every page before choosing a style. ${planDone} of ${planTotal} pages are planned.`,
        action: "Open plan draft",
        href: stageRoute(projectId, "PLAN"),
      });
    }
    const seen = new Set(list.map((item) => item.code));
    for (const blocker of styleStage?.blockers ?? []) {
      if (
        seen.has(blocker.code) ||
        blocker.code === "plan_incomplete" ||
        blocker.code === "style_unconfirmed" ||
        blocker.code === "style_not_selected"
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
    if (styleStage && !styleStage.reachable && list.length === 0) {
      list.push({
        code: "stage_locked",
        message: "Style selection is not available yet. Complete the previous stage first.",
        action: "Open plan draft",
        href: stageRoute(projectId, "PLAN"),
      });
    }
    return list;
  }, [planDone, planIncomplete, planTotal, projectId, styleStage]);

  const saving = putMutation.isPending;
  const confirming = confirmMutation.isPending;
  const styleLocked = Boolean(styleStage && !styleStage.reachable);
  const confirmed =
    snapshot.styleSelection?.confirmed === true &&
    snapshot.styleSelection.styleKey === selectedKey;
  const canConfirm =
    Boolean(selectedStyle) &&
    !planIncomplete &&
    !styleLocked &&
    blockers.length === 0 &&
    !saving &&
    !confirming;

  const confirm = useCallback(() => {
    if (!canConfirm) {
      if (planIncomplete) {
        setConfirmError("Finish the plan draft for every page first.");
      } else if (!selectedStyle) {
        setConfirmError(messageFor("ui.form.style_required"));
      }
      return;
    }
    confirmMutation.mutate();
  }, [canConfirm, confirmMutation, planIncomplete, selectedStyle]);

  const openDesign = useCallback(() => {
    navigate(stageRoute(projectId, "DESIGN"));
  }, [navigate, projectId]);

  return {
    stylesQuery,
    styles,
    selectedKey,
    selectedStyle,
    savedKey,
    remember,
    selectionError,
    confirmError,
    lastUsed,
    lastUsedStyle,
    planIncomplete,
    blockers,
    saving,
    confirming,
    confirmed,
    canConfirm,
    selectStyle,
    toggleRemember,
    confirm,
    openDesign,
    hasExistingDesign:
      snapshot.counts.designTotal > 0 || snapshot.counts.designDone > 0,
  };
}

export type StyleSelectionState = ReturnType<typeof useStyleSelection>;
