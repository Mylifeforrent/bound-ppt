import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowRight, Loader2, ShieldCheck, Sparkles } from "lucide-react";
import { qk } from "@/api/keys";
import type { ProjectMode } from "@/api/types";
import { PublicHeader } from "@/components/PublicHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/primitives";
import { ErrorCard } from "@/components/ui/dialog";
import { useClientConfig } from "@/hooks/useProjectData";
import { errorText, messageFor } from "@/lib/messages";
import { uuid } from "@/lib/utils";
import { StageHeading } from "@/pages/ProjectLayout";
import { createProject, startResearch } from "@/features/intake/api";
import { DataNotice } from "@/features/intake/DataNotice";
import { ModeSelector, ScenarioChips, TopicField } from "@/features/intake/IntakeControls";
import { MaterialComposer } from "@/features/intake/MaterialComposer";
import { isHttpConflict, reportCommandError, toastCommandError, type ErrorInfo } from "@/features/intake/errors";
import { usePolicyNotices } from "@/features/intake/policy";
import { applyProjectVersion, readProjectVersion } from "@/features/intake/projectVersion";
import { useMaterialIntake } from "@/features/intake/useMaterialIntake";
import { noticeGate } from "@/features/intake/validation";

type Phase = "editing" | "creating" | "uploading" | "starting" | "created";

export function HomePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const configQuery = useClientConfig();
  const noticesQuery = usePolicyNotices();

  const [topic, setTopic] = useState("");
  const [mode, setMode] = useState<ProjectMode>("FULLY_AUTOMATIC");
  const [topicError, setTopicError] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>("editing");
  const [projectId, setProjectId] = useState<string | undefined>();
  const [formError, setFormError] = useState<ErrorInfo | null>(null);

  const topicRef = useRef<HTMLInputElement>(null);
  const startRef = useRef<HTMLButtonElement>(null);
  const noticeRef = useRef<HTMLDivElement>(null);
  const createIntentRef = useRef<{ signature: string; key: string } | null>(null);

  const gate = noticeGate(noticesQuery.data);
  const noticeAccepted = Boolean(noticesQuery.data) && !gate.blocked;
  const busy = phase === "creating" || phase === "uploading" || phase === "starting";
  const created = Boolean(projectId);
  const controller = useMaterialIntake({
    limit: configQuery.data?.materialLimit ?? 0,
    noticeAccepted,
    supportedFileTypes: configQuery.data?.supportedFileTypes,
    uploadMaxBytes: configQuery.data?.uploadMaxBytes,
    projectId,
    onChanged: async () => {
      if (!projectId) return;
      setFormError(null);
      void queryClient.invalidateQueries({ queryKey: qk.materials(projectId) });
      void queryClient.invalidateQueries({ queryKey: qk.snapshot(projectId) });
    },
    onError: (error) => {
      if (!projectId) return;
      const info = reportCommandError(error, { queryClient, projectId, toastOnConflict: true });
      if (!isHttpConflict(error)) {
        toast.error(info.message, info.reference ? { description: `Reference: ${info.reference}` } : undefined);
      }
    },
  });

  const focusNotice = () => {
    noticeRef.current?.scrollIntoView({ block: "center" });
    noticeRef.current?.focus({ preventScroll: true });
  };

  const failedMaterialCount = controller.entries.filter((entry) => entry.status === "FAILED").length;

  const focusStart = () => {
    window.requestAnimationFrame(() => startRef.current?.focus());
  };

  const ensureCreateKey = (topicValue: string, modeValue: ProjectMode) => {
    const signature = `${topicValue.trim()}|${modeValue}`;
    if (!createIntentRef.current || createIntentRef.current.signature !== signature) {
      createIntentRef.current = { signature, key: uuid() };
    }
    return createIntentRef.current.key;
  };

  const startResearchFlow = async (targetProjectId: string) => {
    setPhase("starting");
    setFormError(null);
    try {
      const version = await readProjectVersion(targetProjectId, queryClient);
      const { meta } = await startResearch(targetProjectId, version);
      applyProjectVersion(queryClient, targetProjectId, meta.projectVersion);
      // Await the fresh snapshot so the research route sees the new stage.
      await readProjectVersion(targetProjectId, queryClient);
      await queryClient.invalidateQueries({ queryKey: qk.snapshot(targetProjectId) });
      navigate(`/projects/${targetProjectId}/research`);
    } catch (error) {
      const info = reportCommandError(error, {
        queryClient,
        projectId: targetProjectId,
        toastOnConflict: true,
      });
      setFormError(info);
      setPhase("created");
    }
  };

  const handleSubmit = async (event?: React.FormEvent<HTMLFormElement>) => {
    event?.preventDefault();
    if (busy || controller.isBusy) return;

    if (!topic.trim()) {
      setTopicError(messageFor("ui.form.topic_required"));
      topicRef.current?.focus();
      return;
    }
    setTopicError(null);

    if (controller.entries.length > 0 && !noticeAccepted) {
      setFormError({ message: messageFor("error.gate.consent_required") });
      focusNotice();
      return;
    }

    if (projectId) {
      await startResearchFlow(projectId);
      return;
    }

    setPhase("creating");
    setFormError(null);
    try {
      const { data } = await createProject({
        topic,
        mode,
        idempotencyKey: ensureCreateKey(topic, mode),
      });
      createIntentRef.current = null;
      queryClient.setQueryData(qk.snapshot(data.project.id), data.snapshot);
      setProjectId(data.project.id);

      if (controller.entries.length > 0) {
        setPhase("uploading");
        const result = await controller.commitAll(data.project.id);
        if (result.failed > 0) {
          setPhase("created");
          setFormError({
            message: `${result.failed} ${
              result.failed === 1 ? "material could not be added" : "materials could not be added"
            }. Retry or remove the failed items, or continue with the materials that were saved.`,
          });
          return;
        }
      }
      await startResearchFlow(data.project.id);
    } catch (error) {
      const info = toastCommandError(error, { queryClient });
      setFormError(info);
      setPhase("editing");
    }
  };

  const buttonLabel =
    phase === "creating"
      ? "Creating project…"
      : phase === "uploading"
        ? "Adding materials…"
        : phase === "starting"
          ? "Starting research…"
          : projectId
            ? "Continue to research"
            : "Start generating";

  return (
    <div className="min-h-screen">
      <PublicHeader />
      <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 sm:py-10">
        <StageHeading
          stage="New project"
          title="Start a deck"
          description="Describe the deck, optionally add first-party materials, and the agent will research, interview you, and build the outline."
        />

        <div className="grid items-start gap-4 min-[1180px]:grid-cols-[minmax(0,1fr)_440px]">
          <div className="space-y-4">
            <form id="new-project-form" noValidate onSubmit={(event) => void handleSubmit(event)}>
              <Card className="p-5">
                <div className="space-y-4">
                  <TopicField
                    value={topic}
                    onChange={(value) => {
                      setTopic(value);
                      if (topicError) setTopicError(null);
                    }}
                    error={topicError}
                    hint="A topic is enough. Materials make the deck more specific and are used before web sources."
                    disabled={created || busy}
                    inputRef={topicRef}
                  />
                  <ScenarioChips
                    disabled={created || busy}
                    onSelect={(scenario) => {
                      setTopic(scenario);
                      setTopicError(null);
                      focusStart();
                    }}
                  />
                  <ModeSelector value={mode} onChange={setMode} disabled={created || busy} />
                </div>
              </Card>
            </form>

            <DataNotice
              notices={noticesQuery.data}
              loading={noticesQuery.isLoading}
              error={noticesQuery.error}
              onRetry={() => void noticesQuery.refetch()}
              containerRef={noticeRef}
              disabled={busy}
            />

            <div className="flex flex-col gap-2">
              <div className="flex flex-wrap items-center gap-3">
                <Button
                  ref={startRef}
                  type="submit"
                  form="new-project-form"
                  size="lg"
                  disabled={busy || controller.isBusy}
                  aria-busy={busy || controller.isBusy}
                >
                  {busy || controller.isBusy ? (
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <Sparkles className="h-4 w-4" aria-hidden="true" />
                  )}
                  {controller.isBusy ? "Saving materials…" : buttonLabel}
                  {!busy && !controller.isBusy ? (
                    <ArrowRight className="h-4 w-4" aria-hidden="true" />
                  ) : null}
                </Button>
                <p className="text-xs text-muted">
                  No materials? That is fine — the agent researches the web for you.
                </p>
              </div>
              {projectId ? (
                <p className="flex items-center gap-1.5 text-xs text-ok">
                  <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
                  Project created. New materials are saved as you add them.
                </p>
              ) : null}
              {formError ? (
                <div role="alert" className="rounded-xl border border-red-200 bg-danger-soft px-3 py-2 text-sm text-danger">
                  <p>{formError.message}</p>
                  {formError.reference ? (
                    <p className="mono mt-1 text-xs text-danger/80">Reference: {formError.reference}</p>
                  ) : null}
                </div>
              ) : null}
            </div>
          </div>

          <Card className="p-5">
            {configQuery.isError ? (
              <div className="mb-4">
                <ErrorCard
                  message={errorText(configQuery.error) || "Material limits could not be loaded."}
                  onRetry={() => void configQuery.refetch()}
                />
              </div>
            ) : null}
            <MaterialComposer
              controller={controller}
              config={configQuery.data}
              limitReady={Boolean(configQuery.data)}
              consentBlocked={!noticeAccepted}
              consentLoading={noticesQuery.isLoading}
              disabled={busy}
              retryEnabled={created}
              onRequireConsent={focusNotice}
              heading="Materials"
            />
            {failedMaterialCount > 0 ? (
              <p className="mt-3 text-xs text-warn">
                {failedMaterialCount} {failedMaterialCount === 1 ? "item still shows" : "items still show"} an error.
                Use Retry or Remove above; saved materials can start research without them.
              </p>
            ) : null}
          </Card>
        </div>
      </main>
    </div>
  );
}
