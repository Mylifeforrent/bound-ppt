import { useCallback, useEffect, useRef, type KeyboardEvent } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import type { ProjectSnapshotDTO } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/primitives";
import { Progress } from "@/components/ui/controls";
import { ErrorCard, Skeleton, Spinner } from "@/components/ui/dialog";
import { ExportDialog } from "@/features/export/ExportDialog";
import { errorText } from "@/lib/messages";
import { useViewStore } from "@/stores/view";
import { DesignBlockerCard } from "./DesignBlockerCard";
import { DesignCanvas } from "./DesignCanvas";
import { DesignPageActions } from "./DesignPageActions";
import { DesignThumbnailRail } from "./DesignThumbnailRail";
import { useDesignWorkbench } from "./useDesignWorkbench";

export function DesignWorkbench({
  projectId,
  snapshot,
}: {
  projectId: string;
  snapshot: ProjectSnapshotDTO;
}) {
  const workbench = useDesignWorkbench({ projectId, snapshot });
  const exportOpen = useViewStore((s) => s.exportOpen);
  const setExportOpen = useViewStore((s) => s.setExportOpen);
  const exportButtonRef = useRef<HTMLButtonElement>(null);

  const { ready } = workbench;
  useEffect(() => {
    if (!ready && exportOpen) setExportOpen(false);
  }, [ready, exportOpen, setExportOpen]);

  const goRelative = workbench.goRelative;
  const handlePageKeyDown = useCallback(
    (event: KeyboardEvent<HTMLElement>) => {
      if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return;
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      const target = event.target as HTMLElement | null;
      if (target?.closest("input, textarea, select, [contenteditable='true']")) return;
      event.preventDefault();
      goRelative(event.key === "ArrowRight" ? 1 : -1);
    },
    [goRelative],
  );

  if (workbench.pagesQuery.isLoading) {
    return <DesignWorkbenchSkeleton />;
  }

  if (workbench.pagesQuery.isError || !workbench.pages) {
    return (
      <ErrorCard
        message={errorText(workbench.pagesQuery.error) || "The page list could not be loaded."}
        reference={
          workbench.pagesQuery.error && "requestId" in workbench.pagesQuery.error
            ? (workbench.pagesQuery.error as { requestId?: string }).requestId
            : undefined
        }
        onRetry={() => void workbench.pagesQuery.refetch()}
      />
    );
  }

  if (!ready || workbench.blockers.length > 0) {
    return <DesignBlockerCard blockers={workbench.blockers} />;
  }

  if (!workbench.page) {
    return (
      <div className="app-card p-6">
        <p className="text-sm font-semibold text-ink">Select a page to inspect its design.</p>
        <p className="mt-1 text-sm text-muted">
          The deck has {workbench.pages.pages.length} pages. Pick one from the page rail.
        </p>
      </div>
    );
  }

  const page = workbench.page;
  const pages = workbench.pages;
  const pageNumber = workbench.selectedIndex + 1;
  const totalPages = pages.pages.length;
  const designComplete =
    pages.counts.total > 0 &&
    pages.counts.designDone >= pages.counts.total &&
    pages.counts.designError === 0;
  const allDone = workbench.total > 0 && workbench.done >= workbench.total;
  const errorPages = pages.counts.designError;
  const tweakDraft = workbench.tweakDrafts[page.pageId] ?? "";

  return (
    <div className="min-w-0">
      <div role="status" aria-live="polite" className="sr-only">
        {workbench.announcement}
      </div>

      <div className="grid min-w-0 grid-cols-1 gap-4 min-[1180px]:grid-cols-[248px_minmax(0,1fr)_332px] min-[1180px]:items-start">
        <div className="order-1 min-w-0 min-[1180px]:col-start-2 min-[1180px]:row-start-1">
          <section aria-label="Design progress" className="app-card mb-4 p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <h2 className="text-sm font-semibold text-ink">Design progress</h2>
                <p className="mt-0.5 text-xs text-muted">
                  {workbench.done} of {workbench.total} pages ready
                  {workbench.activeDesignJob ? " · generating…" : ""}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-1.5">
                {workbench.activeDesignJob ? (
                  <Badge tone="brand">
                    <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
                    Generating
                  </Badge>
                ) : allDone ? (
                  <Badge tone="ok">Complete</Badge>
                ) : errorPages > 0 ? (
                  <Badge tone="danger">Action needed</Badge>
                ) : (
                  <Badge tone="neutral">Queued</Badge>
                )}
                <span className="text-xs font-medium tabular-nums text-muted">
                  {Math.round(workbench.percent)}%
                </span>
              </div>
            </div>
            <Progress
              value={workbench.percent}
              label="Design pages completed"
              className="mt-3"
            />
            {workbench.generationError ? (
              <div
                role="alert"
                className="mt-3 rounded-xl border border-red-200 bg-danger-soft p-3 text-xs text-danger"
              >
                <p className="font-medium">Design generation could not start.</p>
                <p className="mt-0.5 leading-snug">{workbench.generationError}</p>
                {workbench.needsGeneration.length > 0 ? (
                  <Button
                    variant="secondary"
                    size="sm"
                    className="mt-2"
                    onClick={workbench.retryGeneration}
                  >
                    <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                    Retry generation
                  </Button>
                ) : null}
              </div>
            ) : null}
          </section>

          <DesignCanvas
            page={page}
            pageNumber={pageNumber}
            totalPages={totalPages}
            artifact={workbench.artifact}
            artifactLoading={workbench.artifactQuery.isLoading}
            artifactMissing={workbench.artifactMissing}
            artifactError={workbench.artifactQuery.error}
            onRetryArtifact={() => void workbench.artifactQuery.refetch()}
            generating={workbench.pageGenerating}
            pinned={workbench.pinnedPageId === page.pageId}
            canPrev={workbench.selectedIndex > 0}
            canNext={workbench.selectedIndex >= 0 && workbench.selectedIndex < totalPages - 1}
            onPrev={() => workbench.goRelative(-1)}
            onNext={() => workbench.goRelative(1)}
            onKeyDown={handlePageKeyDown}
          />
        </div>

        <div className="order-2 min-w-0 min-[1180px]:col-start-3 min-[1180px]:row-start-1">
          <DesignPageActions
            page={page}
            pageNumber={pageNumber}
            totalPages={totalPages}
            artifact={workbench.artifact}
            history={workbench.history}
            historyLoading={workbench.historyQuery.isLoading}
            historyError={workbench.historyQuery.isError}
            historyMissing={workbench.historyMissing}
            canUndo={workbench.canUndo}
            historyDepth={workbench.historyDepth}
            generating={workbench.pageGenerating}
            pending={workbench.selectedPageMutationPending}
            tweakDraft={tweakDraft}
            onTweakDraftChange={(value) => workbench.setTweakDraft(page.pageId, value)}
            onRegenerate={() => workbench.actions.regenerate(page.pageId)}
            onTweak={(instruction) => workbench.actions.tweak(page.pageId, instruction)}
            onUndo={() => workbench.actions.undo(page.pageId)}
            onRetry={() => workbench.actions.retry(page.pageId)}
            actionNotice={workbench.actionNotice}
            tweakError={workbench.tweakError}
            onRetryHistory={() => void workbench.historyQuery.refetch()}
            exportButtonRef={exportButtonRef}
            onOpenExport={() => setExportOpen(true)}
            designComplete={designComplete}
          />
        </div>

        <div className="order-3 min-w-0 min-[1180px]:col-start-1 min-[1180px]:row-start-1">
          <DesignThumbnailRail
            pages={pages.pages}
            selectedPageId={workbench.selectedPageId}
            pinnedPageId={workbench.pinnedPageId}
            thumbnails={workbench.thumbnails}
            onSelect={(pageId) => workbench.selectPage(pageId, true)}
            onKeyDown={handlePageKeyDown}
          />
        </div>
      </div>

      <ExportDialog
        open={exportOpen}
        onOpenChange={setExportOpen}
        projectId={projectId}
        snapshot={snapshot}
        pages={pages}
        onSelectPage={(pageId) => {
          workbench.selectPage(pageId, true);
          setExportOpen(false);
        }}
        returnFocusRef={exportButtonRef}
      />
    </div>
  );
}

function DesignWorkbenchSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading design workbench">
      <div className="sr-only">
        <Spinner label="Loading design pages" />
      </div>
      <div className="grid min-w-0 grid-cols-1 gap-4 min-[1180px]:grid-cols-[248px_minmax(0,1fr)_332px] min-[1180px]:items-start">
        <div className="order-1 min-w-0 min-[1180px]:col-start-2 min-[1180px]:row-start-1">
          <div className="app-card mb-4 p-4">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="mt-3 h-2 w-full" />
          </div>
          <div className="app-card p-4">
            <Skeleton className="h-5 w-2/3" />
            <Skeleton className="mt-3 aspect-video w-full" />
          </div>
        </div>
        <div className="order-2 min-w-0 min-[1180px]:col-start-3 min-[1180px]:row-start-1">
          <div className="app-card space-y-3 p-4">
            <Skeleton className="h-4 w-28" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        </div>
        <div className="order-3 min-w-0 min-[1180px]:col-start-1 min-[1180px]:row-start-1">
          <div className="app-card space-y-3 p-3">
            <Skeleton className="h-4 w-20" />
            {Array.from({ length: 4 }).map((_, index) => (
              <div key={index} className="space-y-1">
                <Skeleton className="aspect-video w-full" />
                <Skeleton className="h-3 w-3/4" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
