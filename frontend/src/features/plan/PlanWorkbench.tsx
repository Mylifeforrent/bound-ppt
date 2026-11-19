import { useCallback, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Loader2, Lock, RefreshCw } from "lucide-react";
import type { ProjectSnapshotDTO } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/primitives";
import { Progress } from "@/components/ui/controls";
import { ErrorCard, Skeleton, Spinner } from "@/components/ui/dialog";
import { errorText } from "@/lib/messages";
import { PlanActions } from "./PlanActions";
import { PlanPageList } from "./PlanPageList";
import { PlanWireframe } from "./PlanWireframe";
import { usePlanWorkbench } from "./usePlanWorkbench";

export function PlanWorkbench({
  projectId,
  snapshot,
}: {
  projectId: string;
  snapshot: ProjectSnapshotDTO;
}) {
  const workbench = usePlanWorkbench({ projectId, snapshot });
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
    return <PlanWorkbenchSkeleton />;
  }

  if (workbench.pagesQuery.isError || !workbench.pages) {
    return (
      <ErrorCard
        message={errorText(workbench.pagesQuery.error) || "The page list could not be loaded."}
        reference={
          workbench.pagesQuery.error &&
          typeof workbench.pagesQuery.error === "object" &&
          "requestId" in workbench.pagesQuery.error
            ? (workbench.pagesQuery.error as { requestId?: string }).requestId
            : undefined
        }
        onRetry={() => void workbench.pagesQuery.refetch()}
      />
    );
  }

  if (workbench.locked || workbench.blockers.length > 0) {
    return <PlanBlockerCard blockers={workbench.blockers} />;
  }

  if (!workbench.page) {
    return (
      <div className="app-card p-6">
        <p className="text-sm font-semibold text-ink">Select a page to inspect its plan.</p>
        <p className="mt-1 text-sm text-muted">
          The deck has {workbench.pages.pages.length} pages. Pick one from the page list.
        </p>
      </div>
    );
  }

  const page = workbench.page;
  const pages = workbench.pages;
  const pageNumber = workbench.selectedIndex + 1;
  const totalPages = pages.pages.length;
  const tweakDraft = workbench.tweakDrafts[page.pageId] ?? "";
  const active = workbench.hasActivePlanJob;

  return (
    <div className="min-w-0">
      <div className="sr-only" role="status" aria-live="polite">
        {workbench.announcement}
      </div>

      <div className="grid min-w-0 grid-cols-1 gap-4 min-[1180px]:grid-cols-[248px_minmax(0,1fr)_332px] min-[1180px]:items-start">
        <div className="order-1 min-w-0 min-[1180px]:col-start-2 min-[1180px]:row-start-1">
          <section aria-label="Plan progress" className="app-card mb-4 p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <h2 className="text-sm font-semibold text-ink">Plan progress</h2>
                <p className="mt-0.5 text-xs text-muted">
                  <span className="font-semibold tabular-nums text-ink">
                    {workbench.done} / {workbench.total}
                  </span>{" "}
                  pages planned
                  {active ? " · planning…" : ""}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-1.5">
                {active ? (
                  <Badge tone="brand">
                    <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
                    Planning
                  </Badge>
                ) : workbench.planComplete ? (
                  <Badge tone="ok">Complete</Badge>
                ) : workbench.planErrorCount > 0 ? (
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
              label="Plan pages completed"
              className="mt-3"
            />
            {workbench.planErrorCount > 0 ? (
              <p className="mt-2 text-xs font-medium text-danger">
                {workbench.planErrorCount} page
                {workbench.planErrorCount === 1 ? "" : "s"} failed. Select the page and use Retry.
              </p>
            ) : null}
            {workbench.generationError ? (
              <div
                role="alert"
                className="mt-3 rounded-xl border border-red-200 bg-danger-soft p-3 text-xs text-danger"
              >
                <p className="font-medium">Plan generation could not start.</p>
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

          <PlanWireframe
            page={page}
            pageNumber={pageNumber}
            totalPages={totalPages}
            artifact={workbench.artifact}
            artifactLoading={workbench.artifactQuery.isLoading}
            artifactMissing={workbench.artifactMissing}
            artifactError={workbench.artifactQuery.error}
            onRetryArtifact={() => void workbench.artifactQuery.refetch()}
            generating={workbench.pageGenerating}
            canPrev={workbench.selectedIndex > 0}
            canNext={workbench.selectedIndex >= 0 && workbench.selectedIndex < totalPages - 1}
            onPrev={() => workbench.goRelative(-1)}
            onNext={() => workbench.goRelative(1)}
            onKeyDown={handlePageKeyDown}
          />
        </div>

        <div className="order-2 min-w-0 min-[1180px]:col-start-3 min-[1180px]:row-start-1">
          <PlanActions
            page={page}
            pageNumber={pageNumber}
            totalPages={totalPages}
            artifact={workbench.artifact}
            done={workbench.done}
            total={workbench.total}
            errorCount={workbench.planErrorCount}
            planComplete={workbench.planComplete}
            activeJob={workbench.pageGenerating || workbench.fanoutPending}
            busy={workbench.pageGenerating || workbench.fanoutPending}
            pending={workbench.selectedPageMutationPending}
            tweakDraft={tweakDraft}
            onTweakDraftChange={(value) => workbench.setTweakDraft(page.pageId, value)}
            onRegenerate={() => workbench.actions.regenerate(page.pageId)}
            onTweak={(instruction) => workbench.actions.tweak(page.pageId, instruction)}
            onRetry={() => workbench.actions.retry(page.pageId)}
            actionNotice={workbench.actionNotice}
            tweakError={workbench.tweakError}
            canContinue={workbench.canContinue}
            continuing={workbench.continuing}
            modeAuto={snapshot.project.mode === "FULLY_AUTOMATIC"}
            onConfirm={workbench.confirm}
          />
        </div>

        <div className="order-3 min-w-0 min-[1180px]:col-start-1 min-[1180px]:row-start-1">
          <PlanPageList
            pages={pages.pages}
            selectedPageId={workbench.selectedPageId}
            onSelect={workbench.selectPage}
            onKeyDown={handlePageKeyDown}
          />
        </div>
      </div>
    </div>
  );
}

function PlanBlockerCard({
  blockers,
}: {
  blockers: Array<{ code: string; message: string; action?: string; href?: string }>;
}) {
  return (
    <section aria-label="Plan draft blockers" className="app-card p-6">
      <div className="flex items-start gap-3">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-warn-soft text-warn">
          <Lock className="h-5 w-5" aria-hidden="true" />
        </span>
        <div>
          <h2 className="text-lg font-semibold text-ink">Plan draft is not ready yet</h2>
          <p className="mt-1 max-w-2xl text-sm text-muted">
            The agent plans pages only after the outline is confirmed. Resolve the items below, then
            return to this stage.
          </p>
        </div>
      </div>
      <ul className="mt-5 space-y-3">
        {blockers.map((blocker) => (
          <li
            key={`${blocker.code}-${blocker.message}`}
            className="rounded-xl border border-amber-200 bg-warn-soft/70 p-4"
          >
            <p className="text-sm font-medium text-ink">{blocker.message}</p>
            {blocker.href && blocker.action ? (
              <Link
                to={blocker.href}
                className="mt-2 inline-flex items-center gap-1.5 text-sm font-semibold text-brand-strong hover:underline"
              >
                {blocker.action}
                <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
              </Link>
            ) : null}
          </li>
        ))}
        {blockers.length === 0 ? (
          <li className="text-sm text-muted">
            The plan draft stage is not reachable yet. Refresh the project state and retry.
          </li>
        ) : null}
      </ul>
    </section>
  );
}

function PlanWorkbenchSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading plan workbench">
      <div className="sr-only">
        <Spinner label="Loading plan pages" />
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
          <div className="app-card space-y-2 p-3">
            <Skeleton className="h-4 w-20" />
            {Array.from({ length: 6 }).map((_, index) => (
              <Skeleton key={index} className="h-11 w-full" />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
