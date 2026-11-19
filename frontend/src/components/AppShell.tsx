import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ListChecks, LogOut, RotateCcw, Trash2 } from "lucide-react";
import { api } from "@/api/client";
import { qk } from "@/api/keys";
import type { ActiveJobRef, ProjectSnapshotDTO, StageName } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/primitives";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { stageRoute } from "@/hooks/useProjectData";
import { errorText } from "@/lib/messages";
import { cn, uuid } from "@/lib/utils";
import { useStreamStore, useViewStore } from "@/stores/view";

const STAGES: Array<{ key: StageName; label: string; short: string }> = [
  { key: "INTAKE", label: "Material intake", short: "New" },
  { key: "RESEARCH", label: "Research + interview", short: "Research" },
  { key: "OUTLINE", label: "Outline", short: "Outline" },
  { key: "PLAN", label: "Plan draft", short: "Plan" },
  { key: "STYLE", label: "Style selection", short: "Style" },
  { key: "DESIGN", label: "Design draft", short: "Design" },
];

export function AppShell({ projectId, snapshot, children }: { projectId: string; snapshot: ProjectSnapshotDTO; children: React.ReactNode }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const restartOpen = useViewStore((s) => s.restartOpen);
  const deleteOpen = useViewStore((s) => s.deleteOpen);
  const setRestartOpen = useViewStore((s) => s.setRestartOpen);
  const setDeleteOpen = useViewStore((s) => s.setDeleteOpen);
  const streamStatus = useStreamStore((s) => s.status);
  const [jobsOpen, setJobsOpen] = useState(false);

  const stageState = (stage: StageName) => snapshot.stages.find((s) => s.stage === stage);
  const currentStage = snapshot.project.stage;

  const logout = async () => {
    try {
      await api("/api/auth/logout", { method: "POST" });
    } finally {
      queryClient.clear();
      navigate("/login", { replace: true });
    }
  };

  return (
    <div className="min-h-screen">
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>
      <header className="sticky top-0 z-40 border-b border-line bg-white/92 backdrop-blur">
        <div className="mx-auto flex h-[64px] max-w-[1440px] items-center gap-4 px-4 sm:px-6">
          <Link to="/" className="flex items-center gap-2 font-bold tracking-tight text-ink">
            <span className="grid h-8 w-8 place-items-center rounded-xl bg-brand text-sm font-black text-white">B</span>
            <span className="hidden sm:inline">Bound PPT</span>
          </Link>
          <div className="min-w-0 flex-1 border-l border-line pl-4">
            <p className="truncate text-sm font-semibold text-ink" title={snapshot.project.name}>
              {snapshot.project.name}
            </p>
            <p className="text-[11px] text-muted">v{snapshot.project.version} · epoch {snapshot.project.epoch}</p>
          </div>

          <nav aria-label="Deck stages" className="hidden lg:block">
            <ol className="flex items-center gap-1">
              {STAGES.map((stage) => {
                const state = stageState(stage.key);
                const reachable = Boolean(state?.reachable);
                const stale = state?.status === "STALE";
                const current = currentStage === stage.key;
                const content = (
                  <span
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-semibold",
                      reachable ? "text-ink-2 hover:bg-surface-2" : "cursor-not-allowed text-faint",
                      current && "bg-brand-soft text-brand-strong",
                    )}
                    aria-label={stale ? `${stage.label} (needs rerun)` : stage.label}
                  >
                    {stale ? <span className="h-1.5 w-1.5 rounded-full bg-amber-500" aria-hidden="true" /> : null}
                    {stage.short}
                  </span>
                );
                return (
                  <li key={stage.key}>
                    {reachable ? (
                      <Link to={stageRoute(projectId, stage.key)} aria-current={current ? "step" : undefined}>
                        {content}
                      </Link>
                    ) : (
                      <span aria-disabled="true">{content}</span>
                    )}
                  </li>
                );
              })}
            </ol>
          </nav>

          <div className="flex items-center gap-2">
            <Badge tone="brand" className="hidden sm:inline-flex">
              {snapshot.project.mode === "FULLY_AUTOMATIC" ? "Fully automatic" : "Expert copilot"}
            </Badge>
            {snapshot.activeJobs.length > 0 ? (
              <Button
                variant="secondary"
                size="sm"
                className="h-8 gap-1.5 px-2"
                aria-label={`Active jobs (${snapshot.activeJobs.length})`}
                onClick={() => setJobsOpen(true)}
              >
                <ListChecks className="h-4 w-4" aria-hidden="true" />
                <span className="text-xs font-semibold">{snapshot.activeJobs.length}</span>
              </Button>
            ) : null}
            <Button variant="ghost" size="icon" aria-label="Restart project" onClick={() => setRestartOpen(true)}>
              <RotateCcw className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="icon" aria-label="Delete project" onClick={() => setDeleteOpen(true)}>
              <Trash2 className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="icon" aria-label="Sign out" onClick={() => void logout()}>
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="border-t border-line px-4 py-2 lg:hidden">
          <label className="sr-only" htmlFor="stage-select">
            Choose a stage
          </label>
          <select
            id="stage-select"
            className="field h-9 py-1"
            value={currentStage}
            onChange={(event) => {
              const target = STAGES.find((s) => s.key === event.target.value);
              if (target) navigate(stageRoute(projectId, target.key));
            }}
          >
            {STAGES.map((stage) => {
              const state = stageState(stage.key);
              return (
                <option key={stage.key} value={stage.key} disabled={!state?.reachable}>
                  {stage.short}
                  {state?.status === "STALE" ? " (needs rerun)" : ""}
                </option>
              );
            })}
          </select>
        </div>
      </header>

      {(streamStatus === "reconnecting" || streamStatus === "resyncing") && (
        <div role="status" className="border-b border-amber-200 bg-warn-soft px-4 py-2 text-center text-xs font-medium text-warn">
          {streamStatus === "reconnecting" ? "Reconnecting to live updates…" : "Resynchronising project state…"}
        </div>
      )}

      <main id="main-content" className="mx-auto w-full max-w-[1440px] px-4 py-6 sm:px-6">
        {children}
      </main>

      <RestartDialog
        open={restartOpen}
        onOpenChange={setRestartOpen}
        projectId={projectId}
        version={snapshot.project.version}
      />
      <DeleteDialog open={deleteOpen} onOpenChange={setDeleteOpen} projectId={projectId} version={snapshot.project.version} />
      <ActiveJobsDialog
        open={jobsOpen}
        onOpenChange={setJobsOpen}
        projectId={projectId}
        jobs={snapshot.activeJobs}
        version={snapshot.project.version}
      />
    </div>
  );
}

function jobLabel(type: string): string {
  return (
    {
      INGEST: "Reading material",
      DIGEST: "Digesting material",
      SEARCH: "Searching the web",
      GAP_SUGGEST: "Suggesting gaps",
      PROFILE: "Building the profile",
      OUTLINE: "Generating the outline",
      PLAN_PAGE: "Planning a page",
      DESIGN_PAGE: "Designing a page",
      EXPORT: "Exporting the deck",
      DELETE_PROJECT: "Deleting the project",
    }[type] ?? type
  );
}

function ActiveJobsDialog({
  open,
  onOpenChange,
  projectId,
  jobs,
  version,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  jobs: ActiveJobRef[];
  version: number;
}) {
  const queryClient = useQueryClient();
  const [currentVersion, setCurrentVersion] = useState(version);
  const [cancelling, setCancelling] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const cancel = async (job: ActiveJobRef) => {
    setCancelling(job.jobId);
    setError(null);
    try {
      const { meta } = await api(`/api/projects/${projectId}/jobs/${job.jobId}/cancel`, {
        method: "POST",
        body: {},
        expectedVersion: currentVersion,
        idempotencyKey: uuid(),
      });
      if (meta.projectVersion) setCurrentVersion(meta.projectVersion);
      await queryClient.invalidateQueries({ queryKey: qk.snapshot(projectId) });
      await queryClient.invalidateQueries({ queryKey: qk.pages(projectId) });
      toast.success("Cancellation requested. The job stops at the next safe checkpoint.");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setCancelling(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>Active jobs</DialogTitle>
        <DialogDescription>
          Generation continues in the background when you change stages. Cancelling is cooperative: a page never
          installs a half-written artifact.
        </DialogDescription>
        {error ? (
          <p role="alert" className="mt-3 rounded-lg border border-red-200 bg-danger-soft px-3 py-2 text-sm text-danger">
            {error}
          </p>
        ) : null}
        <ul className="mt-4 space-y-2" aria-label="Active job list">
          {jobs.map((job) => (
            <li key={job.jobId} className="flex items-center justify-between gap-3 rounded-xl border border-line px-3 py-2">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-ink">{jobLabel(job.type)}</p>
                <p className="mono text-[11px] text-muted">
                  {job.state}
                  {job.pageId ? ` · page ${job.pageId.slice(0, 8)}` : ""}
                </p>
              </div>
              <Button
                variant="secondary"
                size="sm"
                disabled={cancelling === job.jobId}
                onClick={() => void cancel(job)}
              >
                {cancelling === job.jobId ? "Cancelling…" : "Cancel"}
              </Button>
            </li>
          ))}
          {jobs.length === 0 ? <li className="text-sm text-muted">No active jobs.</li> : null}
        </ul>
        <div className="mt-4 flex justify-end">
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function RestartDialog({
  open,
  onOpenChange,
  projectId,
  version,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  version: number;
}) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent onOpenAutoFocus={(event) => { event.preventDefault(); cancelRef.current?.focus(); }}>
        <DialogTitle>Restart this project?</DialogTitle>
        <DialogDescription>
          Active jobs are cancelled and the project returns to material intake. Previous artifacts are tombstoned under
          the retention policy and cannot be recovered from this screen.
        </DialogDescription>
        <div className="mt-5 flex justify-end gap-2">
          <Button ref={cancelRef} variant="secondary" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="danger"
            onClick={async () => {
              try {
                const { data } = await api<{ snapshot: ProjectSnapshotDTO }>(`/api/projects/${projectId}/restart`, {
                  method: "POST",
                  body: { confirm: true },
                  expectedVersion: version,
                  idempotencyKey: uuid(),
                });
                queryClient.setQueryData(qk.snapshot(projectId), data.snapshot);
                await queryClient.invalidateQueries({
                  predicate: (query) => query.queryKey[0] === "project" && query.queryKey[1] === projectId,
                });
                onOpenChange(false);
                navigate(`/projects/${projectId}/intake`, { replace: true });
                toast.success("Project restarted");
              } catch (error) {
                toast.error(errorText(error));
              }
            }}
          >
            Restart project
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function DeleteDialog({
  open,
  onOpenChange,
  projectId,
  version,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  version: number;
}) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent onOpenAutoFocus={(event) => { event.preventDefault(); cancelRef.current?.focus(); }}>
        <DialogTitle>Delete this project?</DialogTitle>
        <DialogDescription>
          Deletion removes materials, plans, designs, and exports. This request is asynchronous; access ends immediately.
        </DialogDescription>
        <div className="mt-5 flex justify-end gap-2">
          <Button ref={cancelRef} variant="secondary" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="danger"
            onClick={async () => {
              try {
                await api(`/api/projects/${projectId}`, {
                  method: "DELETE",
                  expectedVersion: version,
                  idempotencyKey: uuid(),
                });
                onOpenChange(false);
                queryClient.clear();
                navigate("/", { replace: true });
                toast.success("Deletion requested");
              } catch (error) {
                toast.error(errorText(error));
              }
            }}
          >
            Delete project
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
