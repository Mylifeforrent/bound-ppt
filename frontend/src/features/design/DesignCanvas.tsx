import type { KeyboardEvent } from "react";
import { ChevronLeft, ChevronRight, Loader2, Pin, RotateCcw } from "lucide-react";
import type { ArtifactDTO, DesignBodyV1, PageSummaryDTO } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/primitives";
import { ErrorCard, Skeleton } from "@/components/ui/dialog";
import { DesignDeckPage, ScaledDeckCanvas } from "@/render/DeckRenderer";
import { errorText, messageFor } from "@/lib/messages";
import { cn } from "@/lib/utils";
import { StatusIcon, designStatusInfo, pageTypeLabel } from "./designStatus";

export function DesignCanvas({
  page,
  pageNumber,
  totalPages,
  artifact,
  artifactLoading,
  artifactMissing,
  artifactError,
  onRetryArtifact,
  generating,
  pinned,
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
  pinned: boolean;
  canPrev: boolean;
  canNext: boolean;
  onPrev: () => void;
  onNext: () => void;
  onKeyDown: (event: KeyboardEvent<HTMLElement>) => void;
}) {
  const info = designStatusInfo(page.design.status);
  const designArtifact = artifact?.kind === "DESIGN" ? artifact : undefined;
  const body = designArtifact ? (designArtifact.body as DesignBodyV1) : undefined;
  const label = `Page ${pageNumber} of ${totalPages}: ${page.title}. Status: ${
    info.description
  }.${pinned ? " Pinned." : ""}`;
  const queryFailed = Boolean(artifactError) && !artifactMissing && !designArtifact;

  return (
    <section
      aria-label="Design canvas"
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
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {pinned ? (
            <Badge tone="brand">
              <Pin className="h-3 w-3" aria-hidden="true" />
              Pinned
            </Badge>
          ) : null}
          <Badge tone={info.tone}>
            <StatusIcon status={page.design.status} />
            {info.label}
          </Badge>
          {designArtifact ? (
            <Badge tone="neutral" className="tabular-nums">
              V{designArtifact.version}
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

      {page.design.status === "STALE" && designArtifact ? (
        <p
          role="status"
          className="mt-3 rounded-xl border border-amber-200 bg-warn-soft px-3 py-2 text-xs font-medium text-warn"
        >
          Needs rerun — this preview does not include the latest plan or style yet.
        </p>
      ) : null}
      {generating && designArtifact ? (
        <p
          role="status"
          className="mt-3 flex items-center gap-2 rounded-xl border border-indigo-200 bg-brand-soft px-3 py-2 text-xs font-medium text-brand-strong"
        >
          <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
          Generating a new version. The current preview stays visible.
        </p>
      ) : null}

      <div className="mt-3 max-[721px]:-mx-1 max-[721px]:overflow-x-auto max-[721px]:px-1 max-[721px]:pb-2">
        <div className="min-w-0 max-[721px]:min-w-[680px]">
          <div
            className={cn(
              "rounded-2xl border p-2 sm:p-3",
              page.design.status === "STALE"
                ? "border-amber-200 bg-warn-soft/50"
                : "border-line bg-[#eceff8]",
            )}
          >
            {queryFailed ? (
              <ErrorCard
                message={errorText(artifactError)}
                onRetry={onRetryArtifact}
              />
            ) : designArtifact && body ? (
              <ScaledDeckCanvas ariaLabel={label}>
                <DesignDeckPage body={body} chrome={designArtifact.chrome} />
              </ScaledDeckCanvas>
            ) : artifactLoading ? (
              <div className="rounded-xl border border-line bg-white p-4" aria-hidden="true">
                <span className="sr-only" role="status">
                  Loading design page…
                </span>
                <div className="flex aspect-video gap-3">
                  <Skeleton className="h-full w-1/3" />
                  <div className="flex h-full flex-1 flex-col gap-3">
                    <Skeleton className="h-8 w-2/3" />
                    <Skeleton className="h-full w-full" />
                    <Skeleton className="h-6 w-1/2" />
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex aspect-video w-full flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-line-strong bg-surface-2 p-6 text-center">
                <StatusIcon
                  status={page.design.status}
                  className={cn(
                    "h-6 w-6",
                    page.design.status === "ERROR" ? "text-danger" : "text-muted",
                  )}
                />
                <p className="text-sm font-semibold text-ink">
                  {artifactMissing && page.design.status === "DONE"
                    ? "The design body is not available yet"
                    : page.design.status === "DESIGNING"
                      ? "Applying the selected style"
                      : page.design.status === "ERROR"
                        ? "This page could not be designed"
                        : page.design.status === "STALE"
                          ? "This page needs a rerun"
                          : "Waiting to be designed"}
                </p>
                <p className="max-w-md text-xs text-muted">
                  {artifactMissing && page.design.status === "DONE"
                    ? "The page list reports this page as done, but its design body could not be loaded. Retry loading the page body."
                    : page.design.status === "DESIGNING"
                      ? "This page is being generated. Completed pages stay inspectable while the rest of the deck renders."
                      : page.design.status === "ERROR"
                        ? page.design.error?.messageKey
                          ? messageFor(page.design.error.messageKey)
                          : "Retry this page from the page actions instead of regenerating the deck."
                        : page.design.status === "STALE"
                          ? "Regeneration is queued for the latest plan or style. The previous version is kept until the new one lands."
                          : "This page has no current design yet. It will appear as soon as generation completes."}
                </p>
                {artifactMissing && page.design.status === "DONE" ? (
                  <Button variant="secondary" size="sm" onClick={onRetryArtifact}>
                    <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
                    Retry loading
                  </Button>
                ) : null}
              </div>
            )}
          </div>
        </div>
      </div>

      <p className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-muted">
        <span>
          <kbd className="rounded border border-line bg-white px-1 py-0.5 font-sans text-[10px]">←</kbd>{" "}
          <kbd className="rounded border border-line bg-white px-1 py-0.5 font-sans text-[10px]">→</kbd>{" "}
          change pages when the canvas or page rail has focus.
        </span>
      </p>
    </section>
  );
}
