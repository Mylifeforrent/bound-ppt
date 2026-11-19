import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  CheckCircle2,
  Loader2,
  Lock,
  Search,
  Sparkles,
} from "lucide-react";
import { qk } from "@/api/keys";
import type { ProjectSnapshotDTO, QuestionDTO } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Badge, Card } from "@/components/ui/primitives";
import { ErrorCard, Skeleton } from "@/components/ui/dialog";
import { stageRoute } from "@/hooks/useProjectData";
import { errorText, messageFor } from "@/lib/messages";
import { cn } from "@/lib/utils";
import { errorInfo } from "@/features/intake/errors";
import { DigestSummaryCard, MaterialDigestCard } from "./DigestCards";
import { GapCard } from "./GapCard";
import { GapSearchList } from "./GapSearchList";
import { MilestoneStatus } from "./MilestoneStatus";
import { ProfileCard } from "./ProfileCard";
import { QuestionCard, type QuestionCardState } from "./QuestionCard";
import { SourcePanel } from "./SourcePanel";
import { isPastResearch, stageLabel, STAGE_ORDER } from "./status";
import { useResearchState, useSourcePanel } from "./queries";
import { useResearchActions } from "./useResearchActions";

export interface ResearchWorkspaceProps {
  projectId: string;
  snapshot: ProjectSnapshotDTO;
}

function ResearchSkeleton() {
  return (
    <div className="grid items-start gap-5 min-[1180px]:grid-cols-[minmax(0,1fr)_360px]" aria-busy="true">
      <div className="space-y-4">
        <Skeleton className="h-9 w-full" />
        <div className="space-y-3 rounded-2xl border border-line bg-white p-4">
          <p className="sr-only">Loading the research conversation</p>
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-4/5" />
        </div>
        <div className="space-y-3 rounded-2xl border border-line bg-white p-4">
          <Skeleton className="h-4 w-52" />
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-2/3" />
        </div>
      </div>
      <div className="rounded-2xl border border-line bg-white p-4">
        <Skeleton className="h-5 w-32" />
        <Skeleton className="mt-3 h-24 w-full" />
        <Skeleton className="mt-2 h-24 w-full" />
      </div>
    </div>
  );
}

function agentPrompt(materialsExist: boolean): string {
  return materialsExist
    ? "I’ll read your materials first. Then I’ll fill any content gaps with targeted web searches and ask four quick questions to shape the deck."
    : "You didn’t add materials, so I’ll research the web first. Then I’ll ask four quick questions to shape the requirements profile.";
}

export function ResearchWorkspace({ projectId, snapshot }: ResearchWorkspaceProps) {
  const queryClient = useQueryClient();
  const snapshotPastResearch = isPastResearch(snapshot.project.stage);
  const researchQuery = useResearchState(projectId, !snapshotPastResearch);
  const digestPending =
    researchQuery.data?.digest.items.some((item) => item.status === "PENDING") ?? false;
  const sourcesQuery = useSourcePanel(projectId, !snapshotPastResearch, digestPending);
  const actions = useResearchActions(projectId);

  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [reducedMotion, setReducedMotion] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);
  const followRef = useRef(true);
  const firstScrollRef = useRef(true);
  const digestStatusRef = useRef<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(media.matches);
    update();
    media.addEventListener?.("change", update);
    return () => media.removeEventListener?.("change", update);
  }, []);

  const state = researchQuery.data;
  const effectiveStage = state?.stage ?? snapshot.project.stage;
  const displayStage =
    STAGE_ORDER.indexOf(effectiveStage) >= STAGE_ORDER.indexOf(snapshot.project.stage)
      ? effectiveStage
      : snapshot.project.stage;
  const pastResearch = isPastResearch(effectiveStage) || isPastResearch(snapshot.project.stage);

  // When any digest changes state, the materials group in the source panel
  // usually changes too. The SSE event does this as well; this covers a
  // disconnected stream without polling forever on failed materials.
  const digestStatusKey = state?.digest.items.map((item) => item.status).join(",") ?? "";
  useEffect(() => {
    if (!state) return;
    if (digestStatusRef.current === null) {
      digestStatusRef.current = digestStatusKey;
      return;
    }
    if (digestStatusRef.current !== digestStatusKey) {
      digestStatusRef.current = digestStatusKey;
      void queryClient.invalidateQueries({ queryKey: qk.sources(projectId) });
    }
  }, [state, digestStatusKey, queryClient, projectId]);

  const questions = useMemo(
    () => (state ? [...state.questions].sort((a, b) => a.position - b.position) : []),
    [state],
  );

  useEffect(() => {
    if (editingKey && !questions.some((question) => question.key === editingKey)) {
      setEditingKey(null);
    }
  }, [editingKey, questions]);

  const scrollSignature = useMemo(() => {
    if (!state) return "";
    return [
      state.digest.status,
      state.digest.items.map((item) => item.status).join(","),
      state.questions.map((question) => question.answer?.revision ?? 0).join(","),
      state.gaps?.batch ?? 0,
      state.gaps?.decision?.decidedAt ?? "-",
      state.gapSearches.map((outcome) => outcome.outcome).join(","),
      state.profile?.version ?? 0,
      state.profileDirty ? "dirty" : "clean",
      state.sources.materials.count,
      state.sources.web.count,
      actions.pending.answerKey ?? "",
      actions.pending.gaps ? "gaps" : "",
      actions.pending.profile ? "profile" : "",
      actions.pending.outline ? "outline" : "",
    ].join("|");
  }, [state, actions.pending]);

  useEffect(() => {
    if (!followRef.current) return;
    const element = logRef.current;
    if (!element) return;
    if (element.scrollHeight <= element.clientHeight) {
      firstScrollRef.current = false;
      return;
    }
    element.scrollTo({
      top: element.scrollHeight,
      behavior: firstScrollRef.current || reducedMotion ? "auto" : "smooth",
    });
    firstScrollRef.current = false;
  }, [scrollSignature, reducedMotion]);

  const onLogScroll = () => {
    const element = logRef.current;
    if (!element) return;
    followRef.current = element.scrollHeight - element.scrollTop - element.clientHeight < 120;
  };

  if (pastResearch) {
    return (
      <Card className="p-6">
        <div className="flex items-start gap-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-brand-soft text-brand-strong">
            <Lock className="h-5 w-5" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <Badge tone="brand">Research complete</Badge>
            <h2 className="mt-2 text-lg font-semibold text-ink">This stage is read-only</h2>
            <p className="mt-1 max-w-2xl text-sm text-muted">
              Answers, gap decisions, and the requirements profile are locked once the project moves past research.
              Continue in {stageLabel(displayStage)}. To revisit the interview, restart the project from the top bar.
            </p>
            <Button asChild variant="secondary" className="mt-4">
              <Link to={stageRoute(projectId, displayStage)}>
                Go to {stageLabel(displayStage)}
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Link>
            </Button>
          </div>
        </div>
      </Card>
    );
  }

  if (researchQuery.isLoading && !state) {
    return <ResearchSkeleton />;
  }

  if (researchQuery.isError && !state) {
    const info = errorInfo(researchQuery.error);
    return (
      <ErrorCard
        message={errorText(researchQuery.error) || info.message}
        reference={info.reference}
        onRetry={() => void researchQuery.refetch()}
      />
    );
  }

  if (!state) {
    return <ResearchSkeleton />;
  }

  if (state.stage === "INTAKE" && state.questions.length === 0) {
    const starting = snapshot.project.stage === "RESEARCH" || state.activeJobs.length > 0;
    return (
      <Card className="p-6">
        <h2 className="text-lg font-semibold text-ink">
          {starting ? "Research is starting" : "Research has not started"}
        </h2>
        <p className="mt-1 max-w-2xl text-sm text-muted">
          {starting
            ? "The research job is being created. Refresh if the conversation does not appear shortly."
            : "Start research from material intake. Your topic and materials stay available there, and an empty material list selects the web-only research path."}
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button type="button" variant="secondary" onClick={() => void researchQuery.refetch()}>
            Refresh
          </Button>
          {!starting ? (
            <Button asChild>
              <Link to={stageRoute(projectId, "INTAKE")}>
                Go to material intake
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Link>
            </Button>
          ) : null}
        </div>
      </Card>
    );
  }

  const materialsExist = state.counts.materialsSelected > 0 || state.digest.items.length > 0;
  const answeredCount = questions.filter((question) => question.answer).length;
  const answersComplete = questions.length > 0 && questions.every((question) => question.answer);
  const currentQuestionKey = questions.find((question) => !question.answer)?.key ?? null;
  const gapsRequired = materialsExist && (state.gaps === null || state.gaps.suggestions.length > 0);
  const gapsPending = gapsRequired && !state.gaps?.decision;
  const canGenerateProfile = answersComplete && !gapsPending;
  const profileBlockReason = !answersComplete
    ? `${answeredCount} of ${questions.length || 4} answers recorded.`
    : gapsPending
      ? "Confirm or skip the suggested gaps first."
      : null;
  const canGenerateOutline = Boolean(state.profile) && !state.profileDirty;
  const outlineBlockReason = !state.profile
    ? canGenerateProfile
      ? "Generate the requirements profile first."
      : "Answer all questions and confirm the gaps first."
    : state.profileDirty
      ? messageFor("error.gate.profile_dirty")
      : null;

  const sourcePanel = sourcesQuery.data ?? state.sources;
  const sourcesLoading = sourcesQuery.isLoading && !sourcesQuery.data;
  const jobsActive =
    state.activeJobs.length > 0 ||
    Boolean(actions.pending.answerKey) ||
    actions.pending.gaps ||
    actions.pending.profile ||
    actions.pending.outline;

  const questionState = (question: QuestionDTO): QuestionCardState => {
    if (editingKey === question.key) return "editing";
    if (question.answer) return "answered";
    if (editingKey) return "locked";
    return question.key === currentQuestionKey ? "current" : "locked";
  };

  const handleAnswer = async (question: QuestionDTO, optionKey: string) => {
    const editing = editingKey === question.key;
    const ok = await actions.answer(question.key, optionKey);
    if (!ok) return;
    if (editing) setEditingKey(null);
    window.setTimeout(() => document.getElementById(`edit-${question.key}`)?.focus(), 0);
  };

  const gapSkeletonVisible = materialsExist && state.gaps === null;

  return (
    <div className="min-w-0" aria-busy={jobsActive}>
      <div className="grid items-start gap-5 min-[1180px]:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0">
          <div className="mb-3">
            <MilestoneStatus state={state} materialsExist={materialsExist} />
          </div>

          <div
            ref={logRef}
            role="log"
            aria-live="off"
            aria-relevant="additions"
            aria-label="Research conversation"
            tabIndex={0}
            onScroll={onLogScroll}
            className="space-y-4 min-[1180px]:max-h-[calc(100vh-260px)] min-[1180px]:overflow-y-auto min-[1180px]:pr-1"
          >
            <div className="flex items-start gap-3">
              <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-brand text-xs font-black text-white">
                A
              </span>
              <div className="min-w-0 rounded-2xl border border-line bg-white p-4 shadow-[var(--sh-1)]">
                <p className="text-sm font-medium text-ink">{agentPrompt(materialsExist)}</p>
                <p className="mt-2 text-xs text-muted">
                  Topic: <span className="font-medium text-ink-2">{snapshot.project.topic}</span>
                </p>
              </div>
            </div>

            {materialsExist ? (
              <section aria-labelledby="research-materials-title" className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <h2
                    id="research-materials-title"
                    className="text-xs font-semibold uppercase tracking-[0.08em] text-muted"
                  >
                    Material digestion
                  </h2>
                  <Badge tone={state.digest.status === "READY" ? "ok" : "neutral"}>
                    {state.digest.status === "READY"
                      ? "Complete"
                      : state.digest.items.some((item) => item.status === "FAILED")
                        ? "Needs attention"
                        : "Reading"}
                  </Badge>
                </div>
                {state.digest.items.length > 0 ? (
                  state.digest.items.map((item) => <MaterialDigestCard key={item.materialId} item={item} />)
                ) : (
                  <Card className="p-4" aria-busy="true">
                    <p className="text-sm text-muted">Reading your materials…</p>
                    <Skeleton className="mt-2 h-3 w-3/4" />
                    <Skeleton className="mt-1.5 h-3 w-1/2" />
                  </Card>
                )}
              </section>
            ) : null}

            {questions.length > 0 ? (
              <section aria-labelledby="research-questions-title" className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <h2
                    id="research-questions-title"
                    className="text-xs font-semibold uppercase tracking-[0.08em] text-muted"
                  >
                    Quick questions
                  </h2>
                  <Badge tone={answersComplete ? "ok" : "neutral"}>
                    {answeredCount} / {questions.length}
                  </Badge>
                </div>
                {questions.map((question) => (
                  <QuestionCard
                    key={question.key}
                    question={question}
                    state={questionState(question)}
                    pending={actions.pending.answerKey === question.key}
                    error={actions.errors.answer?.questionKey === question.key ? actions.errors.answer : null}
                    onEdit={() => {
                      actions.clearAnswerError();
                      setEditingKey(question.key);
                    }}
                    onCancelEdit={() => setEditingKey(null)}
                    onAnswer={(optionKey) => void handleAnswer(question, optionKey)}
                  />
                ))}
              </section>
            ) : null}

            {state.digest.status === "READY" ? <DigestSummaryCard items={state.digest.items} /> : null}

            {materialsExist && state.gaps && state.gaps.suggestions.length > 0 ? (
              <GapCard
                key={`gaps-${state.gaps.batch}`}
                gaps={state.gaps}
                pending={actions.pending.gaps}
                error={actions.errors.gaps}
                onConfirm={(input) => void actions.confirmGaps(input)}
              />
            ) : null}

            {gapSkeletonVisible ? (
              <Card className="p-4" aria-busy="true">
                <div className="flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin text-brand" aria-hidden="true" />
                  <p className="text-sm font-semibold text-ink">Looking for content gaps…</p>
                </div>
                <p className="mt-1 text-xs text-muted">
                  Suggestions appear after the material digests resolve. You can answer the questions above meanwhile.
                </p>
                <Skeleton className="mt-3 h-12 w-full" />
                <Skeleton className="mt-2 h-12 w-full" />
              </Card>
            ) : null}

            {state.gaps?.decision ? <GapSearchList gaps={state.gaps} outcomes={state.gapSearches} /> : null}

            {!materialsExist ? (
              <Card className="p-4">
                <div className="flex items-start gap-3">
                  <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-surface-2 text-brand-strong">
                    <Search className="h-4 w-4" aria-hidden="true" />
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-ink">Web research</p>
                    <p className="mt-1 text-sm text-muted">
                      {sourcePanel.web.status === "loading"
                        ? "Searching the web for the topic and collecting sources…"
                        : sourcePanel.web.count > 0
                          ? `${sourcePanel.web.count} web ${
                              sourcePanel.web.count === 1 ? "source" : "sources"
                            } collected. Review them in the source panel.`
                          : "The web search starts automatically; sources appear as they arrive."}
                    </p>
                    {sourcePanel.web.status === "loading" ? (
                      <div className="mt-2 space-y-1.5" aria-busy="true">
                        <Skeleton className="h-2.5 w-full" />
                        <Skeleton className="h-2.5 w-3/4" />
                      </div>
                    ) : null}
                  </div>
                </div>
              </Card>
            ) : null}

            {state.profile ? (
              <>
                {state.profileDirty ? (
                  <div className="rounded-xl border border-amber-200 bg-warn-soft p-3">
                    <p className="text-sm font-semibold text-warn">Interview answers changed</p>
                    <p className="mt-0.5 text-sm text-warn">
                      Update the requirements profile below to unblock outline generation.
                    </p>
                  </div>
                ) : null}
                <ProfileCard
                  profile={state.profile}
                  dirty={state.profileDirty}
                  pending={actions.pending.profile}
                  error={actions.errors.profile}
                  onUpdate={() => void actions.createProfile()}
                />
              </>
            ) : (
              <Card className="p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <Sparkles className="h-4 w-4 text-brand-strong" aria-hidden="true" />
                      <p className="text-sm font-semibold text-ink">Requirements profile</p>
                    </div>
                    <p className="mt-1 text-sm text-muted">
                      The profile turns your answers, materials, and gap decisions into constraints for the outline.
                    </p>
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    onClick={() => void actions.createProfile()}
                    disabled={!canGenerateProfile || actions.pending.profile}
                  >
                    {actions.pending.profile ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                    ) : null}
                    {actions.pending.profile ? "Generating…" : "Generate profile"}
                  </Button>
                </div>
                {profileBlockReason ? (
                  <p className="mt-2 text-xs text-muted">{profileBlockReason}</p>
                ) : (
                  <p className="mt-2 flex items-center gap-1.5 text-xs text-ok">
                    <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                    All inputs are ready.
                  </p>
                )}
                {actions.errors.profile ? (
                  <div
                    role="alert"
                    className="mt-3 rounded-lg border border-red-200 bg-danger-soft px-2.5 py-2 text-xs text-danger"
                  >
                    <p>{actions.errors.profile.message}</p>
                    {actions.errors.profile.reference ? (
                      <p className="mono mt-1 text-[11px] text-danger/80">
                        Reference: {actions.errors.profile.reference}
                      </p>
                    ) : null}
                  </div>
                ) : null}
              </Card>
            )}

            <Card className={cn("p-4", canGenerateOutline && "border-brand/40")}>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-ink">Continue to the outline</p>
                  <p className="mt-1 text-sm text-muted">
                    The outline uses the profile’s audience, goal, page count, and source priority.
                  </p>
                </div>
                <Button
                  type="button"
                  size="sm"
                  onClick={() => void actions.startOutline()}
                  disabled={!canGenerateOutline || actions.pending.outline}
                >
                  {actions.pending.outline ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                  ) : (
                    <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
                  )}
                  {actions.pending.outline ? "Starting…" : "Generate outline"}
                </Button>
              </div>
              {outlineBlockReason ? (
                <p className={cn("mt-2 text-xs", state.profileDirty ? "text-warn" : "text-muted")}>
                  {outlineBlockReason}
                </p>
              ) : (
                <p className="mt-2 flex items-center gap-1.5 text-xs text-ok">
                  <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                  The profile is clean. Outline generation is unlocked.
                </p>
              )}
              {actions.errors.outline ? (
                <div
                  role="alert"
                  className="mt-3 rounded-lg border border-red-200 bg-danger-soft px-2.5 py-2 text-xs text-danger"
                >
                  <p>{actions.errors.outline.message}</p>
                  {actions.errors.outline.reference ? (
                    <p className="mono mt-1 text-[11px] text-danger/80">
                      Reference: {actions.errors.outline.reference}
                    </p>
                  ) : null}
                </div>
              ) : null}
            </Card>
          </div>

          {researchQuery.isError ? (
            <div className="mt-3">
              <ErrorCard
                message={errorInfo(researchQuery.error).message}
                reference={errorInfo(researchQuery.error).reference}
                onRetry={() => void researchQuery.refetch()}
              />
            </div>
          ) : null}
        </div>

        <aside className="min-w-0 min-[1180px]:sticky min-[1180px]:top-[84px]" aria-label="Content sources">
          <SourcePanel
            panel={sourcePanel}
            materialsExist={materialsExist}
            loading={sourcesLoading}
            fetching={sourcesQuery.isFetching && !sourcesQuery.isLoading}
            materialsPending={digestPending}
            error={sourcesQuery.isError ? sourcesQuery.error : undefined}
            onRetry={() => void sourcesQuery.refetch()}
          />
        </aside>
      </div>
    </div>
  );
}
