import type { KeyboardEvent } from "react";
import { ChevronLeft, ChevronRight, Loader2, RotateCcw } from "lucide-react";
import type { ArtifactDTO, PageSummaryDTO, PlanBodyV1 } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/primitives";
import { ErrorCard, Skeleton } from "@/components/ui/dialog";
import { PlanDeckPage, ScaledDeckCanvas } from "@/render/DeckRenderer";
import { getLayout } from "@/render/layouts";
import { errorText, messageFor } from "@/lib/messages";
import { cn } from "@/lib/utils";
import { StatusIcon, pageTypeLabel, planStatusInfo } from "./planStatus";

export function PlanWireframe({
  page,
  pageNumber,
  totalPages,
  artifact,
  artifactLoading,
  artifactMissing,
  artifactError,
  onRetryArtifact,
  generating,
  canPrev,
  canNext,
  onPrev,
  onNext,
  onKeyDown,
}: {
  page: PageSummaryDTO;
  pageNumber: number;
  totalPages: number;
  artifact?: ArtifactDTO;
  artifactLoading: boolean;
  artifactMissing: boolean;
  artifactError: unknown;
  onRetryArtifact: () => void;
  generating: boolean;
  canPrev: boolean;
  canNext: boolean;
  onPrev: () => void;
  onNext: () => void;
  onKeyDown: (event: KeyboardEvent<HTMLElement>) => void;
}) {
  const info = planStatusInfo(page.plan.status);
  const planArtifact = artifact?.kind === "PLAN" ? artifact : undefined;
  const body = planArtifact ? (planArtifact.body as PlanBodyV1) : undefined;
  const layout = body ? getLayout(body.layoutId) : null;
  const queryFailed = Boolean(artifactError) && !artifactMissing && !planArtifact;
  const label = `Page ${pageNumber} of ${totalPages}: ${page.title}. Plan status: ${info.description}.${
    layout ? ` Layout: ${layout.name}.` : ""
  }`;

  const waiting = page.plan.status === "PENDING" || page.plan.status === "PLANNING";

  return (
    <section
      aria-label="Plan wireframe"
      aria-busy={generating || artifactLoading}
      tabIndex={0}
      onKeyDown={onKeyDown}
      className="min-w-0 rounded-2xl outline-none"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted">
            Page {pageNumber} of {totalPages}
          </p>
          <h2 className="mt-0.5 truncate text-lg font-semibold text-ink sm:text-xl" title={page.title}>
            {page.title}
          </h2>
          <p className="mt-0.5 truncate text-xs text-muted">
            {pageTypeLabel(page.pageType)} · {page.sectionTitle || page.sectionKey}
            {layout ? ` · ${layout.name}` : ""}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge tone={info.tone}>
            <StatusIcon status={page.plan.status} />
            {info.label}
          </Badge>
          {planArtifact ? (
            <Badge tone="neutral" className="tabular-nums">
              V{planArtifact.version}
            </Badge>
          ) : null}
          <div className="ml-1 flex items-center gap-1">
            <Button
              variant="secondary"
              size="icon"
              aria-label="Previous page"
              onClick={onPrev}
              disabled={!canPrev}
            >
              <ChevronLeft className="h-4 w-4" aria-hidden="true" />
            </Button>
            <Button
              variant="secondary"
              size="icon"
              aria-label="Next page"
              onClick={onNext}
              disabled={!canNext}
            >
              <ChevronRight className="h-4 w-4" aria-hidden="true" />
            </Button>
          </div>
        </div>
      </div>

      {page.plan.status === "STALE" && planArtifact ? (
        <p
          role="status"
          className="mt-3 rounded-xl border border-amber-200 bg-warn-soft px-3 py-2 text-xs font-medium text-warn"
        >
          Needs rerun — this wireframe was produced from earlier outline or page inputs.
        </p>
      ) : null}
      {generating && planArtifact ? (
        <p
          role="status"
          className="mt-3 flex items-center gap-2 rounded-xl border border-indigo-200 bg-brand-soft px-3 py-2 text-xs font-medium text-brand-strong"
        >
          <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
          Re-planning this page. The current wireframe stays visible until the new plan lands.
        </p>
      ) : null}

      <div className="mt-3 max-[721px]:-mx-1 max-[721px]:overflow-x-auto max-[721px]:px-1 max-[721px]:pb-2">
        <div className="min-w-0 max-[721px]:min-w-[680px]">
          <div
            className={cn(
              "rounded-2xl border p-2 sm:p-3",
              page.plan.status === "STALE"
                ? "border-amber-200 bg-warn-soft/50"
                : "border-line bg-[#eceff8]",
            )}
          >
            {queryFailed ? (
              <ErrorCard message={errorText(artifactError)} onRetry={onRetryArtifact} />
            ) : planArtifact && body ? (
              <ScaledDeckCanvas ariaLabel={label}>
                <PlanDeckPage
                  body={body}
                  chrome={planArtifact.chrome}
                  pageType={page.pageType}
                />
              </ScaledDeckCanvas>
            ) : artifactLoading || waiting ? (
              <PlanSkeleton
                label={
                  page.plan.status === "PLANNING"
                    ? "Planning this page…"
                    : "Waiting for the plan draft…"
                }
              />
            ) : page.plan.status === "ERROR" ? (
              <div className="flex aspect-video w-full flex-col items-center justify-center gap-3 rounded-xl border border-red-200 bg-danger-soft p-6 text-center">
                <StatusIcon status="ERROR" className="h-6 w-6" />
                <p className="text-sm font-semibold text-ink">This page could not be planned</p>
                <p className="max-w-md text-xs text-muted">
                  {page.plan.error?.messageKey
                    ? messageFor(page.plan.error.messageKey)
                    : "Retry this page from the page actions. Other pages keep their plans."}
                </p>
              </div>
            ) : artifactMissing && page.plan.status === "DONE" ? (
              <div className="flex aspect-video w-full flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-line-strong bg-surface-2 p-6 text-center">
                <p className="text-sm font-semibold text-ink">The plan body is not available yet</p>
                <p className="max-w-md text-xs text-muted">
                  The page list reports this page as planned, but its wireframe could not be loaded.
                  Retry loading the body.
                </p>
                <Button variant="secondary" size="sm" onClick={onRetryArtifact}>
                  <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
                  Retry loading
                </Button>
              </div>
            ) : (
              <div className="flex aspect-video w-full flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-line-strong bg-surface-2 p-6 text-center">
                <StatusIcon status={page.plan.status} className="h-6 w-6 text-muted" />
                <p className="text-sm font-semibold text-ink">
                  {page.plan.status === "STALE" ? "This page needs a rerun" : "No plan draft yet"}
                </p>
                <p className="max-w-md text-xs text-muted">
                  {page.plan.status === "STALE"
                    ? "The outline or page inputs changed. A new plan is generated on entry; you can also re-plan this page."
                    : "The wireframe appears as soon as this page finishes planning."}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      <p className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-muted">
        <span>
          <kbd className="rounded border border-line bg-white px-1 py-0.5 font-sans text-[10px]">←</kbd>{" "}
          <kbd className="rounded border border-line bg-white px-1 py-0.5 font-sans text-[10px]">→</kbd>{" "}
          change pages when this canvas or the page list has focus.
        </span>
        <span>Grayscale wireframe · layout only, no style applied.</span>
      </p>
    </section>
  );
}

function PlanSkeleton({ label }: { label: string }) {
  return (
    <div
      className="rounded-xl border border-line bg-white p-4"
      aria-hidden="true"
      aria-busy="true"
    >
      <span className="sr-only" role="status">
        {label}
      </span>
      <div className="flex aspect-video gap-3">
        <div className="flex h-full w-1/3 flex-col gap-3">
          <Skeleton className="h-8 w-2/3" />
          <Skeleton className="h-full w-full" />
        </div>
        <div className="flex h-full flex-1 flex-col gap-3">
          <Skeleton className="h-10 w-1/2" />
          <Skeleton className="h-full w-full" />
          <div className="flex gap-3">
            <Skeleton className="h-16 flex-1" />
            <Skeleton className="h-16 flex-1" />
          </div>
        </div>
      </div>
      <p className="mt-3 text-center text-xs font-medium text-muted">{label}</p>
    </div>
  );
}
