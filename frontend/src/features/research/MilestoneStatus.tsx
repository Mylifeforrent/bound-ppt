import type { ResearchStateDTO } from "@/api/types";
import { cn } from "@/lib/utils";

function allGapSearchesResolved(state: ResearchStateDTO): boolean {
  return state.gapSearches.length > 0 && state.gapSearches.every((outcome) => outcome.outcome !== "PENDING");
}

function milestoneText(state: ResearchStateDTO, materialsExist: boolean): string {
  if (state.profileDirty) {
    return "Interview answers changed. Update the requirements profile before generating the outline.";
  }
  if (state.profile) {
    return `Requirements profile v${state.profile.version} is ready. Generate the outline when you are happy with it.`;
  }
  if (state.gapSearches.some((outcome) => outcome.outcome === "PENDING")) {
    return "Searching the web for the gaps you selected…";
  }
  if (state.gaps?.decision) {
    if (state.gaps.decision.webSkipped) {
      return "Gap decision recorded. Web research skipped; your materials are used first.";
    }
    if (allGapSearchesResolved(state)) {
      return "Web supplement search complete. Review the profile step below.";
    }
    return "Gap decision recorded. Targeted searches are running…";
  }
  if (materialsExist) {
    if (state.digest.status === "READY") {
      return "Material digestion complete. Review the suggested gaps.";
    }
    if (state.digest.items.some((item) => item.status === "FAILED")) {
      return "Some materials could not be read. The other materials are unaffected.";
    }
    if (state.digest.items.length > 0) {
      return "Reading your materials…";
    }
  }
  const answered = state.questions.filter((question) => question.answer).length;
  const total = state.questions.length;
  if (total > 0 && answered < total) {
    return `Question ${answered + 1} of ${total} is ready.`;
  }
  if (total > 0 && answered === total && materialsExist) {
    return state.gaps ? "All answers are recorded. Confirm the suggested gaps." : "All answers are recorded.";
  }
  if (total > 0 && answered === total) {
    return "All answers are recorded. Generate the requirements profile.";
  }
  return "Research is in progress.";
}

function busy(state: ResearchStateDTO): boolean {
  return (
    state.activeJobs.length > 0 ||
    state.gapSearches.some((outcome) => outcome.outcome === "PENDING") ||
    state.digest.items.some((item) => item.status === "PENDING")
  );
}

/**
 * A single polite live region for milestones. The conversation itself is
 * `aria-live="off"` so per-token updates are never announced.
 */
export function MilestoneStatus({ state, materialsExist }: { state: ResearchStateDTO; materialsExist: boolean }) {
  const active = busy(state);
  return (
    <div
      role="status"
      aria-live="polite"
      aria-atomic="true"
      className="flex items-center gap-2 rounded-xl border border-line bg-surface-2 px-3 py-2 text-xs font-medium text-ink-2"
    >
      <span
        className={cn("h-2 w-2 shrink-0 rounded-full", active ? "bg-brand" : "bg-ok", active && "animate-pulse")}
        aria-hidden="true"
      />
      <span>{milestoneText(state, materialsExist)}</span>
    </div>
  );
}
