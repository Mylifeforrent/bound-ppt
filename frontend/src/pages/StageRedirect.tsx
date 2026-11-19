import { Link, Navigate, useParams } from "react-router-dom";
import { useOutletContext } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useSnapshot, stageRoute } from "@/hooks/useProjectData";
import type { ProjectContext } from "@/pages/ProjectLayout";

export function StageRedirect() {
  const { projectId } = useParams();
  const snapshotQuery = useSnapshot(projectId);
  if (!projectId) return <Navigate to="/" replace />;
  if (!snapshotQuery.data) return null;
  return <Navigate to={stageRoute(projectId, snapshotQuery.data.project.stage)} replace />;
}

export function ProjectOutlet() {
  return useOutletContext<ProjectContext>();
}

export function NotFoundPage() {
  return (
    <div className="grid min-h-screen place-items-center px-4">
      <div className="text-center">
        <p className="text-sm font-semibold uppercase tracking-widest text-muted">404</p>
        <h1 className="mt-2 text-2xl font-bold text-ink">This page does not exist</h1>
        <p className="mt-2 text-sm text-muted">The project may have been deleted, or the link is wrong.</p>
        <Button asChild className="mt-5">
          <Link to="/">Back to new project</Link>
        </Button>
      </div>
    </div>
  );
}
