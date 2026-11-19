import { useOutletContext } from "react-router-dom";
import type { ProjectContext } from "@/pages/ProjectLayout";
import { StageHeading } from "@/pages/ProjectLayout";
import { DesignWorkbench } from "@/features/design/DesignWorkbench";

export function DesignPage() {
  const { projectId, snapshot } = useOutletContext<ProjectContext>();
  return (
    <div className="min-w-0">
      <StageHeading
        stage="Design draft"
        title="Design draft"
        description="Inspect the styled deck page by page. Regenerate or tweak a single page, restore the previous version, then export the deck."
      />
      <DesignWorkbench projectId={projectId} snapshot={snapshot} />
    </div>
  );
}
