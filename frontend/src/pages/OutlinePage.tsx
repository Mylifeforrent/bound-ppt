import { useOutletContext } from "react-router-dom";
import type { ProjectContext } from "@/pages/ProjectLayout";
import { StageHeading } from "@/pages/ProjectLayout";
import { OutlineBoard } from "@/features/outline/OutlineBoard";

export function OutlinePage() {
  const { projectId, snapshot } = useOutletContext<ProjectContext>();
  return (
    <div className="min-w-0">
      <StageHeading
        stage="Outline"
        title="Outline"
        description="Review the cover, contents, and closing notes, then shape the body sections. Edit a title, reorder with buttons, drag, or the keyboard, and confirm when the structure is right."
      />
      <OutlineBoard projectId={projectId} snapshot={snapshot} />
    </div>
  );
}
