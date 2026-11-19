import { useEffect, useState } from "react";
import { Navigate, Outlet, useLocation, useNavigate, useParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import type { ProjectSnapshotDTO } from "@/api/types";
import { AppShell } from "@/components/AppShell";
import { ErrorCard, Spinner } from "@/components/ui/dialog";
import { useProjectStream } from "@/hooks/useProjectStream";
import { deepestReachableStage, stageRoute, useAuth, useSnapshot } from "@/hooks/useProjectData";
import { errorText } from "@/lib/messages";
import { useViewStore } from "@/stores/view";

const PATH_STAGE: Record<string, string> = {
  intake: "INTAKE",
  research: "RESEARCH",
  outline: "OUTLINE",
  plan: "PLAN",
  style: "STYLE",
  design: "DESIGN",
};

export function RequireSession({ children }: { children: React.ReactNode }) {
  const auth = useAuth();
  const location = useLocation();
  if (auth.isLoading) {
    return (
      <div className="grid min-h-screen place-items-center">
        <Spinner label="Loading your session" />
      </div>
    );
  }
  if (!auth.data) {
    return <Navigate to={`/login?returnTo=${encodeURIComponent(location.pathname)}`} replace />;
  }
  return <>{children}</>;
}

export function ProjectLayout() {
  const { projectId } = useParams();
  const snapshotQuery = useSnapshot(projectId);
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const resetProjectView = useViewStore((s) => s.resetProjectView);
  const [notified, setNotified] = useState<string | null>(null);

  const snapshot = snapshotQuery.data;
  useProjectStream({
    projectId,
    initialCursor: snapshot?.sequence,
    enabled: Boolean(projectId && snapshot),
  });

  useEffect(() => {
    resetProjectView();
    return () => {
      if (projectId) {
        queryClient.removeQueries({ predicate: (query) => query.queryKey[0] === "project" && query.queryKey[1] === projectId });
      }
    };
  }, [projectId, resetProjectView, queryClient]);

  const requestedStage = PATH_STAGE[location.pathname.split("/").filter(Boolean).pop() ?? ""] ?? null;

  useEffect(() => {
    if (!snapshot || !projectId) return;
    const current = requestedStage ? snapshot.stages.find((s) => s.stage === requestedStage) : null;
    if (current && !current.reachable) {
      const target = deepestReachableStage(snapshot);
      if (notified !== target) {
        setNotified(target);
        const firstBlocker = current.blockers[0];
        toast.message(firstBlocker ? "That stage is not available yet." : "Complete the previous stage first.");
      }
      navigate(stageRoute(projectId, target), { replace: true });
    }
  }, [snapshot, projectId, requestedStage, navigate, notified]);

  useEffect(() => {
    const heading = document.querySelector<HTMLElement>("[data-stage-heading]");
    heading?.focus({ preventScroll: true });
  }, [location.pathname]);

  if (snapshotQuery.isLoading) {
    return (
      <div className="grid min-h-screen place-items-center">
        <Spinner label="Loading project" />
      </div>
    );
  }
  if (snapshotQuery.isError || !snapshot || !projectId) {
    return (
      <div className="mx-auto max-w-xl p-8">
        <ErrorCard
          message={errorText(snapshotQuery.error) || "Project could not be loaded."}
          onRetry={() => void snapshotQuery.refetch()}
        />
      </div>
    );
  }

  return (
    <AppShell projectId={projectId} snapshot={snapshot}>
      <Outlet context={{ snapshot, projectId } satisfies ProjectContext} />
    </AppShell>
  );
}

export interface ProjectContext {
  snapshot: ProjectSnapshotDTO;
  projectId: string;
}

export function StageHeading({ stage, title, description }: { stage: string; title: string; description: string }) {
  return (
    <header className="mb-5">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">{stage}</p>
      <h1 data-stage-heading tabIndex={-1} className="mt-1 text-2xl font-bold tracking-tight text-ink outline-none">
        {title}
      </h1>
      <p className="mt-1 max-w-3xl text-sm text-muted">{description}</p>
    </header>
  );
}
