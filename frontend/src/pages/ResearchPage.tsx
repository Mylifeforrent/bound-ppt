import { useOutletContext } from "react-router-dom";
import type { ProjectContext } from "@/pages/ProjectLayout";
import { StageHeading } from "@/pages/ProjectLayout";
import { ResearchWorkspace } from "@/features/research/ResearchWorkspace";

export function ResearchPage() {
  const { projectId, snapshot } = useOutletContext<ProjectContext>();
  return (
    <div className="min-w-0">
      <StageHeading
        stage="Research + interview"
        title="Research + interview"
        description="The agent reads your materials, fills confirmed gaps with targeted web searches, records four answers, and turns them into a requirements profile."
      />
      <ResearchWorkspace projectId={projectId} snapshot={snapshot} />
    </div>
  );
}
