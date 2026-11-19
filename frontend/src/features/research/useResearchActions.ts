import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { qk } from "@/api/keys";
import type { ResearchStateDTO } from "@/api/types";
import { messageFor } from "@/lib/messages";
import { isHttpConflict, reportCommandError, type ErrorInfo } from "@/features/intake/errors";
import { applyProjectVersion, readProjectVersion } from "@/features/intake/projectVersion";
import { decideGaps, generateOutline, generateProfile, putAnswer, type GapDecisionInput } from "./api";

export interface ResearchAnswerError extends ErrorInfo {
  questionKey: string;
}

export interface ResearchActionErrors {
  answer: ResearchAnswerError | null;
  gaps: ErrorInfo | null;
  profile: ErrorInfo | null;
  outline: ErrorInfo | null;
}

export function useResearchActions(projectId: string) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const locksRef = useRef<Set<string>>(new Set());
  const [pendingAnswerKey, setPendingAnswerKey] = useState<string | null>(null);
  const [pendingGaps, setPendingGaps] = useState(false);
  const [pendingProfile, setPendingProfile] = useState(false);
  const [pendingOutline, setPendingOutline] = useState(false);
  const [errors, setErrors] = useState<ResearchActionErrors>({
    answer: null,
    gaps: null,
    profile: null,
    outline: null,
  });

  const patchError = (patch: Partial<ResearchActionErrors>) => {
    setErrors((previous) => ({ ...previous, ...patch }));
  };

  /** A conflicting command means server state moved on; refresh the conversation too. */
  const refreshAfterConflict = (error: unknown) => {
    if (isHttpConflict(error)) {
      void queryClient.invalidateQueries({ queryKey: qk.research(projectId) });
    }
  };

  const answer = async (questionKey: string, optionKey: string): Promise<boolean> => {
    const lock = `answer:${questionKey}`;
    if (locksRef.current.has(lock)) return false;
    locksRef.current.add(lock);
    setPendingAnswerKey(questionKey);
    patchError({ answer: null });
    try {
      const version = await readProjectVersion(projectId, queryClient);
      const { data, meta } = await putAnswer(projectId, questionKey, optionKey, version);
      applyProjectVersion(queryClient, projectId, meta.projectVersion);
      queryClient.setQueryData<ResearchStateDTO>(qk.research(projectId), (previous) =>
        previous
          ? {
              ...previous,
              questions: previous.questions.map((question) =>
                question.key === questionKey
                  ? {
                      ...question,
                      answer: {
                        optionKey: data.question.optionKey,
                        revision: data.question.revision,
                        answeredAt: data.question.answeredAt,
                      },
                    }
                  : question,
              ),
              profileDirty: data.profileDirty,
            }
          : previous,
      );
      void queryClient.invalidateQueries({ queryKey: qk.research(projectId) });
      void queryClient.invalidateQueries({ queryKey: qk.snapshot(projectId) });
      return true;
    } catch (error) {
      const info = reportCommandError(error, { queryClient, projectId, toastOnConflict: true });
      refreshAfterConflict(error);
      patchError({ answer: { ...info, questionKey } });
      return false;
    } finally {
      locksRef.current.delete(lock);
      setPendingAnswerKey(null);
    }
  };

  const confirmGaps = async (input: GapDecisionInput): Promise<boolean> => {
    if (input.webSkipped && input.selectedSuggestionIds.length > 0) {
      patchError({ gaps: { message: messageFor("ui.form.gap_web_skip_conflict") } });
      return false;
    }
    if (locksRef.current.has("gaps")) return false;
    locksRef.current.add("gaps");
    setPendingGaps(true);
    patchError({ gaps: null });
    try {
      const version = await readProjectVersion(projectId, queryClient);
      const { data, meta } = await decideGaps(projectId, input, version);
      applyProjectVersion(queryClient, projectId, meta.projectVersion);
      queryClient.setQueryData<ResearchStateDTO>(qk.research(projectId), (previous) =>
        previous
          ? {
              ...previous,
              gaps: data.gaps,
              gapSearches: data.gapSearches,
              counts: {
                ...previous.counts,
                selectedGaps: data.gaps.decision?.selectedSuggestionIds.length ?? 0,
              },
            }
          : previous,
      );
      void queryClient.invalidateQueries({ queryKey: qk.research(projectId) });
      void queryClient.invalidateQueries({ queryKey: qk.sources(projectId) });
      void queryClient.invalidateQueries({ queryKey: qk.snapshot(projectId) });
      return true;
    } catch (error) {
      const info = reportCommandError(error, { queryClient, projectId, toastOnConflict: true });
      refreshAfterConflict(error);
      patchError({ gaps: info });
      return false;
    } finally {
      locksRef.current.delete("gaps");
      setPendingGaps(false);
    }
  };

  const createProfile = async (): Promise<boolean> => {
    if (locksRef.current.has("profile")) return false;
    locksRef.current.add("profile");
    setPendingProfile(true);
    patchError({ profile: null });
    try {
      const version = await readProjectVersion(projectId, queryClient);
      const { data, meta } = await generateProfile(projectId, version);
      applyProjectVersion(queryClient, projectId, meta.projectVersion);
      queryClient.setQueryData<ResearchStateDTO>(qk.research(projectId), (previous) =>
        previous
          ? {
              ...previous,
              profile: data.profile,
              profileDirty: data.profileDirty,
            }
          : previous,
      );
      void queryClient.invalidateQueries({ queryKey: qk.research(projectId) });
      void queryClient.invalidateQueries({ queryKey: qk.snapshot(projectId) });
      void queryClient.invalidateQueries({ queryKey: qk.outline(projectId) });
      if (data.outlineUnconfirmed) {
        toast.message("Profile updated. The outline needs reconfirmation before plan and design.");
      }
      return true;
    } catch (error) {
      const info = reportCommandError(error, { queryClient, projectId, toastOnConflict: true });
      refreshAfterConflict(error);
      patchError({ profile: info });
      return false;
    } finally {
      locksRef.current.delete("profile");
      setPendingProfile(false);
    }
  };

  const startOutline = async (): Promise<boolean> => {
    if (locksRef.current.has("outline")) return false;
    locksRef.current.add("outline");
    setPendingOutline(true);
    patchError({ outline: null });
    try {
      const version = await readProjectVersion(projectId, queryClient);
      const { meta } = await generateOutline(projectId, version);
      applyProjectVersion(queryClient, projectId, meta.projectVersion);
      void queryClient.invalidateQueries({ queryKey: qk.outline(projectId) });
      void queryClient.invalidateQueries({ queryKey: qk.pages(projectId) });
      void queryClient.invalidateQueries({ queryKey: qk.snapshot(projectId) });
      // Refresh the stage before the route guard evaluates it.
      await readProjectVersion(projectId, queryClient);
      navigate(`/projects/${projectId}/outline`);
      return true;
    } catch (error) {
      const info = reportCommandError(error, { queryClient, projectId, toastOnConflict: true });
      refreshAfterConflict(error);
      patchError({ outline: info });
      return false;
    } finally {
      locksRef.current.delete("outline");
      setPendingOutline(false);
    }
  };

  return {
    answer,
    confirmGaps,
    createProfile,
    startOutline,
    pending: {
      answerKey: pendingAnswerKey,
      gaps: pendingGaps,
      profile: pendingProfile,
      outline: pendingOutline,
    },
    errors,
    clearAnswerError: () => patchError({ answer: null }),
  };
}
