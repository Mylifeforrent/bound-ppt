import { useOutletContext } from "react-router-dom";
import type { ProjectContext } from "@/pages/ProjectLayout";
import { StageHeading } from "@/pages/ProjectLayout";
import { PlanWorkbench } from "@/features/plan/PlanWorkbench";

export function PlanPage() {
  const { projectId, snapshot } = useOutletContext<ProjectContext>();
  return (
    <div className="min-w-0">
      <StageHeading
        stage="Plan draft"
        title="Plan draft"
        description="Each page gets a grayscale Bento wireframe before any style is applied. Inspect pages as they finish planning, re-plan or tweak a single page, then continue to style selection."
      />
      <PlanWorkbench projectId={projectId} snapshot={snapshot} />
    </div>
  );
}
