import { useOutletContext } from "react-router-dom";
import type { ProjectContext } from "@/pages/ProjectLayout";
import { StageHeading } from "@/pages/ProjectLayout";
import { StyleGallery } from "@/features/style/StyleGallery";

export function StylePage() {
  const { projectId, snapshot } = useOutletContext<ProjectContext>();
  return (
    <div className="min-w-0">
      <StageHeading
        stage="Style selection"
        title="Style selection"
        description="Each card renders a representative page from the real theme tokens. Choose one style for the whole deck, confirm it, and the agent applies it to every design page."
      />
      <StyleGallery projectId={projectId} snapshot={snapshot} />
    </div>
  );
}
