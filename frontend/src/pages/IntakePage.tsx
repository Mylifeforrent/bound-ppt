import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useOutletContext } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowRight, Loader2, Lock, RotateCcw } from "lucide-react";
import { api } from "@/api/client";
import { qk } from "@/api/keys";
import type { ProjectDTO, ProjectSnapshotDTO } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Card, Badge } from "@/components/ui/primitives";
import { ErrorCard, Skeleton } from "@/components/ui/dialog";
import { stageRoute, useClientConfig } from "@/hooks/useProjectData";
import { messageFor } from "@/lib/messages";
import { uuid } from "@/lib/utils";
import { useViewStore } from "@/stores/view";
import type { ProjectContext } from "@/pages/ProjectLayout";
import { StageHeading } from "@/pages/ProjectLayout";
import { startResearch } from "@/features/intake/api";
import { DataNotice } from "@/features/intake/DataNotice";
import { TopicField } from "@/features/intake/IntakeControls";
import { MaterialComposer } from "@/features/intake/MaterialComposer";
import {
  errorInfo,
  isHttpConflict,
  reportCommandError,
  toastCommandError,
  type ErrorInfo,
} from "@/features/intake/errors";
import { usePolicyNotices } from "@/features/intake/policy";
import { applyProjectVersion, readProjectVersion } from "@/features/intake/projectVersion";
import { useMaterials } from "@/features/intake/queries";
import { useMaterialIntake } from "@/features/intake/useMaterialIntake";
import { noticeGate } from "@/features/intake/validation";

export function IntakePage() {
  const { projectId, snapshot } = useOutletContext<ProjectContext>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const configQuery = useClientConfig();
  const noticesQuery = usePolicyNotices();
  const materialsQuery = useMaterials(projectId);
  const setRestartOpen = useViewStore((state) => state.setRestartOpen);

  const locked = snapshot.project.stage !== "INTAKE";
  const [topicDraft, setTopicDraft] = useState(snapshot.project.topic);
  const [topicError, setTopicError] = useState<string | null>(null);
  const [topicErrorInfo, setTopicErrorInfo] = useState<ErrorInfo | null>(null);
  const [savingTopic, setSavingTopic] = useState(false);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<ErrorInfo | null>(null);
  const topicRef = useRef<HTMLInputElement>(null);
  const noticeRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setTopicDraft(snapshot.project.topic);
    setTopicError(null);
    setTopicErrorInfo(null);
  }, [snapshot.project.id, snapshot.project.topic]);

  const gate = noticeGate(noticesQuery.data);
  const noticeAccepted = Boolean(noticesQuery.data) && !gate.blocked;

  const limit = materialsQuery.data?.limit ?? snapshot.materialLimit ?? configQuery.data?.materialLimit ?? 0;
  const materialsReady = Boolean(materialsQuery.data);

  const controller = useMaterialIntake({
    limit,
    noticeAccepted,
    serverMaterials: materialsQuery.data?.materials ?? [],
    supportedFileTypes: configQuery.data?.supportedFileTypes,
    uploadMaxBytes: configQuery.data?.uploadMaxBytes,
    projectId,
    onChanged: async () => {
      void queryClient.invalidateQueries({ queryKey: qk.materials(projectId) });
      void queryClient.invalidateQueries({ queryKey: qk.snapshot(projectId) });
    },
    onError: (error) => {
      const info = reportCommandError(error, { queryClient, projectId, toastOnConflict: true });
      if (!isHttpConflict(error)) {
        toast.error(info.message, info.reference ? { description: `Reference: ${info.reference}` } : undefined);
      }
    },
  });

  const topicDirty = topicDraft.trim() !== snapshot.project.topic;
  const busy = starting || savingTopic || controller.isBusy;

  const saveTopic = async () => {
    const next = topicDraft.trim();
    if (!next) {
      setTopicError(messageFor("ui.form.topic_required"));
      topicRef.current?.focus();
      return;
    }
    if (!topicDirty) return;
    setSavingTopic(true);
    setTopicError(null);
    setTopicErrorInfo(null);
    try {
      const version = await readProjectVersion(projectId, queryClient);
      const { data, meta } = await api<{ project: ProjectDTO }>(`/api/projects/${projectId}`, {
        method: "PATCH",
        body: { topic: next },
        expectedVersion: version,
        idempotencyKey: uuid(),
      });
      applyProjectVersion(queryClient, projectId, meta.projectVersion);
      queryClient.setQueryData<ProjectSnapshotDTO>(qk.snapshot(projectId), (previous) =>
        previous ? { ...previous, project: data.project } : previous,
      );
      setTopicDraft(data.project.topic);
      void queryClient.invalidateQueries({ queryKey: qk.snapshot(projectId) });
      toast.success("Topic updated");
    } catch (error) {
      const info = reportCommandError(error, { queryClient, projectId, toastOnConflict: true });
      setTopicError(info.message);
      setTopicErrorInfo(info);
    } finally {
      setSavingTopic(false);
    }
  };

  const beginResearch = async () => {
    if (busy) return;
    if (topicDirty) {
      setTopicError("Save or discard the topic change before starting research.");
      topicRef.current?.focus();
      return;
    }
    setStarting(true);
    setStartError(null);
    try {
      const version = await readProjectVersion(projectId, queryClient);
      const { meta } = await startResearch(projectId, version);
      applyProjectVersion(queryClient, projectId, meta.projectVersion);
      await readProjectVersion(projectId, queryClient);
      await queryClient.invalidateQueries({ queryKey: qk.snapshot(projectId) });
      await queryClient.invalidateQueries({ queryKey: qk.research(projectId) });
      navigate(`/projects/${projectId}/research`);
    } catch (error) {
      const info = toastCommandError(error, { queryClient, projectId });
      setStartError(info);
      setStarting(false);
    }
  };

  return (
    <div>
      <StageHeading
        stage="Material intake"
        title={locked ? "Materials and topic" : "Material intake"}
        description={
          locked
            ? "Topic and materials are locked once research has started. Restart the project if they need to change."
            : "Review the topic, add first-party materials, and start research. An empty material list is valid: the agent will research the web."
        }
      />

      <div className="grid items-start gap-4 min-[1180px]:grid-cols-[minmax(0,1fr)_440px]">
        <div className="space-y-4">
          <Card className="p-5">
            <div className="space-y-4">
              {locked ? (
                <div>
                  <p className="mb-1.5 text-sm font-medium text-ink-2">Topic</p>
                  <p className="rounded-xl border border-line bg-surface-2 px-3 py-2 text-sm text-ink">
                    {snapshot.project.topic}
                  </p>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <Badge tone="neutral">
                      {snapshot.project.mode === "FULLY_AUTOMATIC" ? "Fully automatic" : "Expert copilot"}
                    </Badge>
                    <span className="text-xs text-muted">
                      Mode is fixed for this project; mid-project switching is not exposed.
                    </span>
                  </div>
                </div>
              ) : (
                <>
                  <TopicField
                    value={topicDraft}
                    onChange={(value) => {
                      setTopicDraft(value);
                      if (topicError) {
                        setTopicError(null);
                        setTopicErrorInfo(null);
                      }
                    }}
                    error={topicError}
                    hint="The topic can still change until research starts."
                    inputRef={topicRef}
                    disabled={savingTopic}
                  />
                  {topicErrorInfo?.reference ? (
                    <p className="mono -mt-2 text-xs text-danger/80">Reference: {topicErrorInfo.reference}</p>
                  ) : null}
                  {topicDirty ? (
                    <div className="flex flex-wrap items-center gap-2">
                      <Button type="button" size="sm" onClick={() => void saveTopic()} disabled={savingTopic}>
                        {savingTopic ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : null}
                        {savingTopic ? "Saving topic…" : "Save topic"}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          setTopicDraft(snapshot.project.topic);
                          setTopicError(null);
                          setTopicErrorInfo(null);
                        }}
                        disabled={savingTopic}
                      >
                        Discard change
                      </Button>
                    </div>
                  ) : null}
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="brand">
                      {snapshot.project.mode === "FULLY_AUTOMATIC" ? "Fully automatic" : "Expert copilot"}
                    </Badge>
                    <span className="text-xs text-muted">
                      Mode is fixed when the project is created; it changes the auto-advance behaviour.
                    </span>
                  </div>
                </>
              )}
            </div>
          </Card>

          {locked ? (
            <Card className="p-5">
              <div className="flex items-start gap-3">
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-warn-soft text-warn">
                  <Lock className="h-4 w-4" aria-hidden="true" />
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-ink">Materials are locked</p>
                  <p className="mt-1 text-sm text-muted">
                    Adding or removing materials after research starts is not available. Restart the project to change
                    the topic or materials; research, profile, and downstream artifacts are reset.
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button type="button" variant="secondary" size="sm" onClick={() => setRestartOpen(true)}>
                      <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
                      Restart project…
                    </Button>
                    <Button asChild variant="subtle" size="sm">
                      <Link to={stageRoute(projectId, snapshot.project.stage)}>
                        Go to current stage
                        <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
                      </Link>
                    </Button>
                  </div>
                </div>
              </div>
            </Card>
          ) : (
            <>
              <DataNotice
                notices={noticesQuery.data}
                loading={noticesQuery.isLoading}
                error={noticesQuery.error}
                onRetry={() => void noticesQuery.refetch()}
                containerRef={noticeRef}
                compact
                disabled={busy}
              />
              <div className="flex flex-col gap-2">
                <div className="flex flex-wrap items-center gap-3">
                  <Button
                    type="button"
                    size="lg"
                    onClick={() => void beginResearch()}
                    disabled={
                      starting ||
                      savingTopic ||
                      controller.isBusy ||
                      topicDirty ||
                      materialsQuery.isLoading ||
                      materialsQuery.isError
                    }
                    aria-busy={starting}
                  >
                    {starting ? (
                      <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                    ) : (
                      <ArrowRight className="h-4 w-4" aria-hidden="true" />
                    )}
                    {starting ? "Starting research…" : "Start research"}
                  </Button>
                  <p className="text-xs text-muted">
                    {materialsQuery.isError
                      ? "Retry loading materials before starting."
                      : topicDirty
                        ? "Save or discard the topic change first."
                        : controller.entries.length === 0
                          ? "No materials: research will start from the web."
                          : `${controller.count} ${
                              controller.count === 1 ? "material" : "materials"
                            } will be processed first.`}
                  </p>
                </div>
                {startError ? (
                  <div
                    role="alert"
                    className="rounded-xl border border-red-200 bg-danger-soft px-3 py-2 text-sm text-danger"
                  >
                    <p>{startError.message}</p>
                    {startError.reference ? (
                      <p className="mono mt-1 text-xs text-danger/80">Reference: {startError.reference}</p>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </>
          )}
        </div>

        <Card className="p-5">
          {materialsQuery.isLoading && !materialsQuery.data ? (
            <div className="mb-4 space-y-2" aria-busy="true">
              <p className="sr-only">Loading saved materials</p>
              <Skeleton className="h-5 w-40" />
              <Skeleton className="h-14 w-full" />
            </div>
          ) : null}
          {materialsQuery.isError ? (
            <div className="mb-4">
              <ErrorCard
                message={errorInfo(materialsQuery.error).message}
                reference={errorInfo(materialsQuery.error).reference}
                onRetry={() => void materialsQuery.refetch()}
              />
            </div>
          ) : null}
          <MaterialComposer
            controller={controller}
            config={configQuery.data}
            limitReady={materialsReady}
            consentBlocked={!noticeAccepted}
            consentLoading={noticesQuery.isLoading}
            disabled={savingTopic || starting}
            readOnly={locked}
            readOnlyNote={
              locked
                ? "Topic and materials are read-only after research starts. Use Restart in the top bar to change them."
                : undefined
            }
            retryEnabled={!locked}
            emptyText={
              materialsQuery.isError
                ? "Saved materials could not be loaded. Retry above."
                : undefined
            }
            onRequireConsent={() => {
              noticeRef.current?.scrollIntoView({ block: "center" });
              noticeRef.current?.focus({ preventScroll: true });
            }}
            heading="Materials"
          />
          {configQuery.isError ? (
            <p className="mt-3 text-xs text-warn">
              Supported file types could not be loaded; the server will still validate any upload.
            </p>
          ) : null}
        </Card>
      </div>
    </div>
  );
}
