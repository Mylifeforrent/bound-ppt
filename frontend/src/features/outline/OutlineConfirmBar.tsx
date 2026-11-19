import { ArrowRight, CheckCircle2, Loader2, Pause, Play, TimerReset, TriangleAlert } from "lucide-react";
import type { OutlineDTO } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/primitives";
import { Progress } from "@/components/ui/controls";
import { cn } from "@/lib/utils";

function pauseReasonText(reason: string | null): string {
  switch (reason) {
    case "user":
      return "you paused it";
    case "edit":
      return "the outline was edited, so auto-advance stopped";
    case "hidden":
      return "the tab is hidden";
    case "focus":
      return "focus is in a text field";
    default:
      return "it is paused";
  }
}

export function OutlineConfirmBar({
  outline,
  modeAuto,
  autoEligible,
  blocked,
  advancing,
  advanceError,
  pauseReason,
  running,
  remainingSeconds,
  progress,
  onPause,
  onResume,
  onConfirm,
  onContinue,
}: {
  outline: OutlineDTO;
  modeAuto: boolean;
  autoEligible: boolean;
  blocked: boolean;
  advancing: boolean;
  advanceError: string | null;
  pauseReason: string | null;
  running: boolean;
  remainingSeconds: number;
  progress: number;
  onPause: () => void;
  onResume: () => void;
  onConfirm: () => void;
  onContinue: () => void;
}) {
  if (outline.confirmed) {
    return (
      <section
        aria-label="Outline confirmation"
        className="app-card mt-4 flex flex-wrap items-center justify-between gap-3 border-green-200 bg-ok-soft/60 p-4"
      >
        <div className="flex items-center gap-3">
          <CheckCircle2 className="h-5 w-5 shrink-0 text-ok" aria-hidden="true" />
          <div>
            <p className="text-sm font-semibold text-ink">Outline confirmed</p>
            <p className="text-xs text-muted">
              {blocked
                ? "The profile or a stage blocker must be resolved before the plan draft can run."
                : "The structure is locked in and the plan draft can be generated page by page."}
            </p>
          </div>
        </div>
        <Button onClick={onContinue} disabled={blocked}>
          Open plan draft
          <ArrowRight className="h-4 w-4" aria-hidden="true" />
        </Button>
      </section>
    );
  }

  const autoAvailable = modeAuto && !blocked && autoEligible;
  const paused = !running;
  const reasonText = pauseReasonText(pauseReason);
  const announcement = advancing
    ? "Advancing to the plan draft."
    : autoAvailable && running
      ? "Auto-advancing to the plan draft. Press Pause to stay here."
      : autoAvailable && paused
        ? `Auto-advance paused because ${reasonText}.`
        : "";

  return (
    <section
      aria-label="Outline confirmation"
      className={cn(
        "app-card mt-4 border-indigo-200 p-4",
        modeAuto && !blocked ? "bg-brand-soft/40" : "bg-surface-2",
      )}
    >
      <div className="sr-only" role="status" aria-live="polite">
        {announcement}
      </div>

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-ink">
              {blocked
                ? "Confirmation is blocked"
                : modeAuto
                  ? "Review, then let the agent continue"
                  : "Does the structure look right?"}
            </p>
            <Badge tone="warn">Not confirmed</Badge>
          </div>
          <p className="mt-1 max-w-2xl text-xs leading-relaxed text-muted">
            {blocked
              ? "Resolve the blocker above before the outline can be confirmed or advanced."
              : modeAuto
                ? "Fully automatic mode continues to the plan draft after a 3-second countdown. Editing or sorting a note pauses it."
                : "Expert copilot pauses here. Confirm when the sticky notes are right; editing later requires reconfirmation."}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {modeAuto && !blocked && autoEligible && !advancing ? (
            running ? (
              <Button variant="secondary" size="sm" onClick={onPause}>
                <Pause className="h-3.5 w-3.5" aria-hidden="true" />
                Pause
              </Button>
            ) : (
              <Button variant="secondary" size="sm" onClick={onResume} disabled={advancing}>
                <Play className="h-3.5 w-3.5" aria-hidden="true" />
                Resume
              </Button>
            )
          ) : null}
          <Button
            size="sm"
            onClick={onConfirm}
            disabled={blocked || advancing}
            aria-describedby="outline-confirm-hint"
          >
            {advancing ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
            ) : (
              <TimerReset className="h-3.5 w-3.5" aria-hidden="true" />
            )}
            {modeAuto ? "Confirm and continue now" : "Outline looks good, generate plan draft"}
          </Button>
        </div>
      </div>

      {modeAuto && !blocked && autoEligible ? (
        <div className="mt-3">
          {advancing ? (
            <p
              role="status"
              className="flex items-center gap-2 text-xs font-semibold text-brand-strong"
            >
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
              Advancing to the plan draft…
            </p>
          ) : running ? (
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs font-medium text-brand-strong" aria-live="off">
                Auto-advancing to the plan draft in{" "}
                <strong className="tabular-nums">{remainingSeconds}</strong>{" "}
                {remainingSeconds === 1 ? "second" : "seconds"}
              </p>
              <span className="text-[11px] font-medium text-muted">Pause anytime</span>
            </div>
          ) : (
            <p className="flex flex-wrap items-center gap-1.5 text-xs font-medium text-warn">
              <TriangleAlert className="h-3.5 w-3.5" aria-hidden="true" />
              Auto-advance paused — {reasonText}.
              {pauseReason === "focus"
                ? " Move focus out of the text field, then resume."
                : " Press Resume to restart the 3-second countdown."}
            </p>
          )}
          <Progress
            className="mt-2"
            value={progress}
            label="Time remaining before auto-advance"
          />
        </div>
      ) : modeAuto && !blocked && !autoEligible ? (
        <p className="mt-2 text-[11px] leading-snug text-muted">
          Automatic advance is not available for this outline right now. Confirm it manually when
          the structure is right.
        </p>
      ) : null}

      {!modeAuto && !blocked ? (
        <p className="mt-2 text-[11px] text-muted" id="outline-confirm-hint">
          Confirming locks the current structure. Edits after confirmation require reconfirmation.
        </p>
      ) : null}

      {advanceError ? (
        <div
          role="alert"
          className="mt-3 rounded-xl border border-red-200 bg-danger-soft px-3 py-2 text-xs text-danger"
        >
          <p className="font-semibold">The outline could not advance automatically.</p>
          <p className="mt-0.5 leading-snug">{advanceError}</p>
          <p className="mt-1 leading-snug">
            The project state was refreshed. Confirm the outline manually when it is ready.
          </p>
        </div>
      ) : null}
    </section>
  );
}
