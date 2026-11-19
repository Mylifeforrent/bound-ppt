import { useEffect, useRef, useState } from "react";
import { ArrowRight, Loader2, RefreshCw, RotateCcw, Wand2 } from "lucide-react";
import type { ArtifactDTO, PageSummaryDTO } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/primitives";
import { Label, Textarea } from "@/components/ui/dialog";
import { messageFor } from "@/lib/messages";
import { pluralize } from "@/lib/utils";
import { StatusIcon, pageTypeLabel, planStatusInfo } from "./planStatus";
import type { PlanActionNotice } from "./usePlanWorkbench";

export function PlanActions({
  page,
  pageNumber,
  totalPages,
  artifact,
  done,
  total,
  errorCount,
  planComplete,
  activeJob,
  busy,
  pending,
  tweakDraft,
  onTweakDraftChange,
  onRegenerate,
  onTweak,
  onRetry,
  actionNotice,
  tweakError,
  canContinue,
  continuing,
  modeAuto,
  onConfirm,
}: {
  page: PageSummaryDTO;
  pageNumber: number;
  totalPages: number;
  artifact?: ArtifactDTO;
  done: number;
  total: number;
  errorCount: number;
  planComplete: boolean;
  activeJob: boolean;
  busy: boolean;
  pending: boolean;
  tweakDraft: string;
  onTweakDraftChange: (value: string) => void;
  onRegenerate: () => void;
  onTweak: (instruction: string) => void;
  onRetry: () => void;
  actionNotice: PlanActionNotice | null;
  tweakError: string | null;
  canContinue: boolean;
  continuing: boolean;
  modeAuto: boolean;
  onConfirm: () => void;
}) {
  const tweakRef = useRef<HTMLTextAreaElement>(null);
  const [localTweakError, setLocalTweakError] = useState<string | null>(null);
  const info = planStatusInfo(page.plan.status);
  const disabled = busy || pending;
  const isError = page.plan.status === "ERROR";
  const fieldError = localTweakError ?? tweakError;

  useEffect(() => {
    setLocalTweakError(null);
  }, [page.pageId]);

  const submitTweak = () => {
    if (disabled) return;
    const instruction = tweakDraft.trim();
    if (!instruction) {
      setLocalTweakError(messageFor("ui.form.instruction_required"));
      tweakRef.current?.focus();
      return;
    }
    setLocalTweakError(null);
    onTweak(instruction);
  };

  return (
    <section
      aria-label="Plan page actions"
      aria-busy={busy}
      className="app-card min-w-0 p-4 min-[1180px]:sticky min-[1180px]:top-[88px] min-[1180px]:max-h-[calc(100vh-112px)] min-[1180px]:overflow-y-auto"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted">
            Page actions
          </p>
          <h2 className="mt-0.5 line-clamp-2 text-base font-semibold text-ink" title={page.title}>
            {page.title}
          </h2>
          <p className="mt-0.5 truncate text-xs text-muted">
            {pageNumber} of {totalPages} · {pageTypeLabel(page.pageType)}
          </p>
        </div>
        <Badge tone={info.tone}>
          <StatusIcon status={page.plan.status} />
          {info.label}
        </Badge>
      </div>

      <dl className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div className="rounded-lg border border-line bg-surface-2 px-2.5 py-1.5">
          <dt className="text-[10px] uppercase tracking-wide text-faint">Plan version</dt>
          <dd className="mt-0.5 font-semibold tabular-nums text-ink">
            {artifact ? `V${artifact.version}` : "—"}
          </dd>
        </div>
        <div className="rounded-lg border border-line bg-surface-2 px-2.5 py-1.5">
          <dt className="text-[10px] uppercase tracking-wide text-faint">Layout</dt>
          <dd className="mt-0.5 truncate font-semibold text-ink">
            {artifact ? artifact.body.layoutId.replace("_", " ") : "—"}
          </dd>
        </div>
      </dl>

      {activeJob || busy ? (
        <p
          role="status"
          className="mt-3 flex items-center gap-2 rounded-xl border border-indigo-200 bg-brand-soft px-3 py-2 text-xs font-semibold text-brand-strong"
        >
          <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
          Generating, please wait…
        </p>
      ) : pending ? (
        <p role="status" className="mt-3 rounded-xl border border-line bg-surface-2 px-3 py-2 text-xs text-muted">
          Sending your request…
        </p>
      ) : null}

      <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2 min-[1180px]:grid-cols-1 min-[1320px]:grid-cols-2">
        <Button variant="secondary" size="sm" onClick={onRegenerate} disabled={disabled}>
          <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
          Re-plan this page
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={onRetry}
          disabled={disabled || !isError}
          title={isError ? "Retry this failed page" : "Retry is available when this page fails"}
        >
          <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
          Retry this page
        </Button>
      </div>
      <p className="mt-1.5 text-[11px] leading-snug text-muted">
        Re-plan rotates the Bento layout variant for this page only. Other pages keep their plans; the
        page's design is marked for rerun by the server.
      </p>

      {isError ? (
        <div
          role="alert"
          className="mt-3 rounded-xl border border-red-200 bg-danger-soft p-3 text-xs text-danger"
        >
          <p className="font-medium leading-snug">
            {page.plan.error?.messageKey
              ? messageFor(page.plan.error.messageKey)
              : "This page could not be planned. Retry this page; the other pages continue."}
          </p>
          <Button variant="primary" size="sm" className="mt-2 w-full" onClick={onRetry} disabled={disabled}>
            <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
            Retry this page
          </Button>
        </div>
      ) : null}

      {actionNotice ? (
        <div
          role="alert"
          className="mt-3 rounded-xl border border-amber-200 bg-warn-soft p-3 text-xs text-warn"
        >
          <p className="font-medium leading-snug">{actionNotice.message}</p>
        </div>
      ) : null}

      <form
        className="mt-4 border-t border-line pt-4"
        onSubmit={(event) => {
          event.preventDefault();
          submitTweak();
        }}
      >
        <Label htmlFor={`plan-tweak-${page.pageId}`}>Tweak this wireframe</Label>
        <Textarea
          id={`plan-tweak-${page.pageId}`}
          ref={tweakRef}
          value={tweakDraft}
          onChange={(event) => {
            setLocalTweakError(null);
            onTweakDraftChange(event.target.value);
          }}
          disabled={disabled}
          aria-invalid={fieldError ? true : undefined}
          aria-describedby={
            fieldError ? `plan-tweak-error-${page.pageId}` : `plan-tweak-hint-${page.pageId}`
          }
          placeholder="e.g. Make the data card larger and move the quote to the right."
        />
        {fieldError ? (
          <p
            id={`plan-tweak-error-${page.pageId}`}
            role="alert"
            className="mt-1.5 rounded-lg border border-red-200 bg-danger-soft px-2.5 py-1.5 text-xs text-danger"
          >
            {fieldError}
          </p>
        ) : (
          <p id={`plan-tweak-hint-${page.pageId}`} className="mt-1.5 text-[11px] text-muted">
            Only this page changes. The page's design is marked for rerun.
          </p>
        )}
        <Button type="submit" size="sm" className="mt-2 w-full" disabled={disabled}>
          <Wand2 className="h-3.5 w-3.5" aria-hidden="true" />
          Apply tweak
        </Button>
      </form>

      <div className="mt-4 border-t border-line pt-4">
        <h3 className="text-sm font-semibold text-ink">Plan completion</h3>
        <p className="mt-1 text-xs text-muted">
          <span className="font-semibold tabular-nums text-ink">
            {done} / {total}
          </span>{" "}
          pages planned
          {planComplete ? " · all pages done" : ""}
        </p>
        {errorCount > 0 ? (
          <div
            role="alert"
            className="mt-2 rounded-xl border border-red-200 bg-danger-soft p-3 text-xs text-danger"
          >
            <p className="font-medium">
              {pluralize(errorCount, "page")} failed to plan. Retry the failed pages before confirming;
              the gate stays closed until every page is done.
            </p>
          </div>
        ) : null}
        {!planComplete && errorCount === 0 ? (
          <p className="mt-2 text-xs text-muted">
            Confirm unlocks when every page is done and none is in error.
          </p>
        ) : null}
        <Button
          className="mt-3 w-full"
          onClick={onConfirm}
          disabled={!planComplete || !canContinue || continuing}
        >
          {continuing ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          ) : (
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          )}
          Confirm plan draft, choose style
        </Button>
        <p className="mt-1.5 text-[11px] leading-snug text-muted">
          {modeAuto
            ? "Fully automatic mode continues to style selection as soon as every page is planned."
            : "Expert copilot waits here for your confirmation. If the next stage is unavailable, refresh the project state and retry."}
        </p>
      </div>
    </section>
  );
}
