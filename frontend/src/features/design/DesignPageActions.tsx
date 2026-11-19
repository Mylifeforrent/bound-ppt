import { useEffect, useRef, useState } from "react";
import {
  FileDown,
  History,
  Loader2,
  RefreshCw,
  RotateCcw,
  Wand2,
} from "lucide-react";
import type { ArtifactDTO, PageHistoryDTO, PageSummaryDTO } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/primitives";
import { Label, Textarea } from "@/components/ui/dialog";
import { messageFor } from "@/lib/messages";
import { cn, pluralize } from "@/lib/utils";
import {
  StatusIcon,
  designStatusInfo,
  formatTimestamp,
  historyReasonLabel,
  pageTypeLabel,
} from "./designStatus";
import type { DesignActionNotice } from "./useDesignWorkbench";

export function DesignPageActions({
  page,
  pageNumber,
  totalPages,
  artifact,
  history,
  historyLoading,
  historyError,
  historyMissing,
  canUndo,
  historyDepth,
  generating,
  pending,
  tweakDraft,
  onTweakDraftChange,
  onRegenerate,
  onTweak,
  onUndo,
  onRetry,
  actionNotice,
  tweakError,
  onRetryHistory,
  exportButtonRef,
  onOpenExport,
  designComplete,
}: {
  page: PageSummaryDTO;
  pageNumber: number;
  totalPages: number;
  artifact?: ArtifactDTO;
  history?: PageHistoryDTO;
  historyLoading: boolean;
  historyError: boolean;
  historyMissing: boolean;
  canUndo: boolean;
  historyDepth: number;
  generating: boolean;
  pending: boolean;
  tweakDraft: string;
  onTweakDraftChange: (value: string) => void;
  onRegenerate: () => void;
  onTweak: (instruction: string) => void;
  onUndo: () => void;
  onRetry: () => void;
  actionNotice: DesignActionNotice | null;
  tweakError: string | null;
  onRetryHistory: () => void;
  exportButtonRef: React.RefObject<HTMLButtonElement | null>;
  onOpenExport: () => void;
  designComplete: boolean;
}) {
  const tweakRef = useRef<HTMLTextAreaElement>(null);
  const [localTweakError, setLocalTweakError] = useState<string | null>(null);
  const info = designStatusInfo(page.design.status);
  const busy = generating || pending;
  const isError = page.design.status === "ERROR";
  const entries = history?.entries ?? [];
  const showHistoryError = historyError && !historyMissing;
  const fieldError = localTweakError ?? tweakError;

  useEffect(() => {
    setLocalTweakError(null);
  }, [page.pageId]);

  const submitTweak = () => {
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
      aria-label="Page actions"
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
          <StatusIcon status={page.design.status} />
          {info.label}
        </Badge>
      </div>

      <dl className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div className="rounded-lg border border-line bg-surface-2 px-2.5 py-1.5">
          <dt className="text-[10px] uppercase tracking-wide text-faint">Current version</dt>
          <dd className="mt-0.5 font-semibold tabular-nums text-ink">
            {artifact ? `V${artifact.version}` : "—"}
          </dd>
        </div>
        <div className="rounded-lg border border-line bg-surface-2 px-2.5 py-1.5">
          <dt className="text-[10px] uppercase tracking-wide text-faint">History</dt>
          <dd className="mt-0.5 font-semibold tabular-nums text-ink">
            {pluralize(historyDepth, "version")}
          </dd>
        </div>
      </dl>

      {generating ? (
        <p
          role="status"
          className="mt-3 flex items-center gap-2 rounded-xl border border-indigo-200 bg-brand-soft px-3 py-2 text-xs font-semibold text-brand-strong"
        >
          <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
          Generating, please wait…
        </p>
      ) : null}
      {pending && !generating ? (
        <p role="status" className="mt-3 rounded-xl border border-line bg-surface-2 px-3 py-2 text-xs text-muted">
          Sending your request…
        </p>
      ) : null}

      <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2 min-[1180px]:grid-cols-1 min-[1320px]:grid-cols-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={onRegenerate}
          disabled={busy}
          aria-describedby={`regenerate-note-${page.pageId}`}
        >
          <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
          Regenerate
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={onUndo}
          disabled={busy || !canUndo}
          title={canUndo ? "Restore the previous version" : "No earlier version is available yet"}
        >
          <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
          Previous version
        </Button>
      </div>
      <p id={`regenerate-note-${page.pageId}`} className="mt-1.5 text-[11px] leading-snug text-muted">
        {page.pageType === "COVER" || page.pageType === "TOC" || page.pageType === "END"
          ? "Cover, contents, and closing pages have a single layout — use Tweak for changes."
          : "Regenerate rotates the layout variant for this page only. Previous versions stay in history."}
      </p>

      {isError ? (
        <div
          role="alert"
          className="mt-3 rounded-xl border border-red-200 bg-danger-soft p-3 text-xs text-danger"
        >
          <p className="font-medium leading-snug">
            {page.design.error?.messageKey
              ? messageFor(page.design.error.messageKey)
              : "This page could not be designed. Retry this page instead of regenerating the deck."}
          </p>
          <Button variant="primary" size="sm" className="mt-2 w-full" onClick={onRetry} disabled={busy}>
            <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
            Retry this page
          </Button>
        </div>
      ) : null}

      {actionNotice ? (
        <div
          role="alert"
          className={cn(
            "mt-3 rounded-xl border p-3 text-xs",
            actionNotice.kind === "single_layout"
              ? "border-amber-200 bg-warn-soft text-warn"
              : "border-red-200 bg-danger-soft text-danger",
          )}
        >
          <p className="font-medium leading-snug">{actionNotice.message}</p>
          {actionNotice.kind === "single_layout" ? (
            <>
              <p className="mt-1 leading-snug">
                No variant was created. Describe the change you want and apply it with Tweak.
              </p>
              <Button
                variant="secondary"
                size="sm"
                className="mt-2"
                onClick={() => tweakRef.current?.focus()}
              >
                <Wand2 className="h-3.5 w-3.5" aria-hidden="true" />
                Use Tweak instead
              </Button>
            </>
          ) : null}
        </div>
      ) : null}

      <form
        className="mt-4 border-t border-line pt-4"
        onSubmit={(event) => {
          event.preventDefault();
          submitTweak();
        }}
      >
        <Label htmlFor={`design-tweak-${page.pageId}`}>Tweak this page</Label>
        <Textarea
          id={`design-tweak-${page.pageId}`}
          ref={tweakRef}
          value={tweakDraft}
          onChange={(event) => {
            setLocalTweakError(null);
            onTweakDraftChange(event.target.value);
          }}
          disabled={busy}
          aria-invalid={fieldError ? true : undefined}
          aria-describedby={
            fieldError
              ? `design-tweak-error-${page.pageId}`
              : `design-tweak-hint-${page.pageId}`
          }
          placeholder="e.g. Make the metric card larger and move the quote to the right."
        />
        {fieldError ? (
          <p
            id={`design-tweak-error-${page.pageId}`}
            role="alert"
            className="mt-1.5 rounded-lg border border-red-200 bg-danger-soft px-2.5 py-1.5 text-xs text-danger"
          >
            {fieldError}
          </p>
        ) : (
          <p id={`design-tweak-hint-${page.pageId}`} className="mt-1.5 text-[11px] text-muted">
            Only this page changes. The previous version is kept in history.
          </p>
        )}
        <Button type="submit" size="sm" className="mt-2 w-full" disabled={busy}>
          <Wand2 className="h-3.5 w-3.5" aria-hidden="true" />
          Apply tweak
        </Button>
      </form>

      <div className="mt-4 border-t border-line pt-4">
        <div className="flex items-center justify-between gap-2">
          <h3 className="flex items-center gap-1.5 text-sm font-semibold text-ink">
            <History className="h-4 w-4 text-muted" aria-hidden="true" />
            Version history
          </h3>
          <Badge tone="neutral" className="tabular-nums">
            {pluralize(historyDepth, "version")}
          </Badge>
        </div>
        {historyLoading && !history ? (
          <div className="mt-2 space-y-2" aria-hidden="true">
            <div className="h-12 animate-pulse rounded-lg bg-line" />
            <div className="h-12 animate-pulse rounded-lg bg-line" />
          </div>
        ) : showHistoryError ? (
          <p className="mt-2 text-xs text-danger">
            History could not be loaded.{" "}
            <button
              type="button"
              className="font-semibold underline"
              onClick={onRetryHistory}
            >
              Retry
            </button>
          </p>
        ) : entries.length > 0 ? (
          <ol className="mt-2 space-y-2" aria-label="Page version history">
            {entries.map((entry) => (
              <li
                key={entry.artifactVersionId}
                className={cn(
                  "rounded-lg border px-2.5 py-2",
                  entry.isCurrent
                    ? "border-indigo-200 bg-brand-soft/50"
                    : "border-line bg-surface-2",
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="mono text-[11px] font-semibold tabular-nums text-ink">
                    V{entry.version}
                  </span>
                  <span className="flex flex-wrap items-center justify-end gap-1">
                    {entry.isCurrent ? <Badge tone="brand">Current</Badge> : null}
                    {entry.undone ? <Badge tone="neutral">Undone</Badge> : null}
                  </span>
                </div>
                <p className="mt-0.5 text-xs font-medium text-ink-2">
                  {historyReasonLabel(entry.reason)}
                </p>
                <p className="text-[10px] text-muted">{formatTimestamp(entry.createdAt)}</p>
              </li>
            ))}
          </ol>
        ) : (
          <p className="mt-2 text-xs text-muted">
            No earlier versions yet. Regenerate or tweak this page to start a history.
          </p>
        )}
        {artifact ? (
          <p className="mt-2 text-[11px] text-muted">
            Current V{artifact.version} · {pluralize(historyDepth, "version")} stored. Previous
            version is available when history depth is greater than zero.
          </p>
        ) : null}
      </div>

      <div className="mt-4 border-t border-line pt-4">
        <Button
          ref={exportButtonRef}
          className="w-full"
          onClick={onOpenExport}
          aria-haspopup="dialog"
        >
          <FileDown className="h-4 w-4" aria-hidden="true" />
          Export deck
        </Button>
        <p className="mt-1.5 text-[11px] leading-snug text-muted">
          {designComplete
            ? "All pages have a current design. Review the scope before creating a file."
            : "Some pages are not designed yet. The export dialog lists the incomplete pages."}
        </p>
      </div>
    </section>
  );
}
