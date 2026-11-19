import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  AlertTriangle,
  CheckCircle2,
  Code2,
  FileText,
  Loader2,
  Presentation,
  RefreshCw,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import { api } from "@/api/client";
import { qk } from "@/api/keys";
import type {
  ExportDTO,
  ExportFormat,
  ExportValidationCheckDTO,
  PageListDTO,
  ProjectSnapshotDTO,
  StyleDTO,
} from "@/api/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/primitives";
import { Progress, RadioGroup, RadioGroupItem } from "@/components/ui/controls";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { useSnapshot } from "@/hooks/useProjectData";
import { errorText, messageFor } from "@/lib/messages";
import { cn, formatBytes, pluralize, uuid } from "@/lib/utils";
import { isApiConflict, isApiValidation } from "@/features/design/apiErrors";
import {
  designStatusInfo,
  formatPercent,
  formatTimestamp,
} from "@/features/design/designStatus";

const FORMATS: Array<{
  value: ExportFormat;
  title: string;
  description: string;
  Icon: LucideIcon;
  recommended?: boolean;
}> = [
  {
    value: "PPTX",
    title: "PowerPoint (PPTX)",
    description: "Editable slides composed from the deck's SVG pages.",
    Icon: Presentation,
    recommended: true,
  },
  {
    value: "HTML",
    title: "HTML deck",
    description: "A self-contained web presentation for sharing or presenting.",
    Icon: Code2,
  },
  {
    value: "PDF",
    title: "PDF",
    description: "Fixed-layout 16:9 pages for review and printing.",
    Icon: FileText,
  },
];

const STATE_LABEL: Record<string, string> = {
  QUEUED: "Queued",
  VALIDATING: "Validating pages",
  COMPOSING: "Composing slides",
  PACKAGING: "Packaging the file",
  SUCCEEDED: "Completed",
  FAILED: "Failed",
  CANCELLED: "Cancelled",
};

const CHECK_LABEL: Record<string, string> = {
  fonts_missing: "Missing font",
  asset_out_of_bounds: "Asset outside the canvas",
  empty_page: "Empty page",
  render_incomplete: "Incomplete render",
};

export function ExportDialog({
  open,
  onOpenChange,
  projectId,
  snapshot,
  pages,
  onSelectPage,
  returnFocusRef,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  snapshot: ProjectSnapshotDTO;
  pages?: PageListDTO;
  onSelectPage: (pageId: string) => void;
  returnFocusRef: React.RefObject<HTMLButtonElement | null>;
}) {
  const queryClient = useQueryClient();
  const [format, setFormat] = useState<ExportFormat>("PPTX");
  const [activeExportId, setActiveExportId] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const firstFormatRef = useRef<HTMLButtonElement>(null);
  const lastStateRef = useRef<string | null>(null);

  const snapshotQuery = useSnapshot(projectId);
  const currentSnapshot = snapshotQuery.data ?? snapshot;
  const pagesQuery = useQuery({
    queryKey: qk.pages(projectId),
    queryFn: async () => (await api<PageListDTO>(`/api/projects/${projectId}/pages`)).data,
    enabled: open,
    staleTime: 1_000,
  });
  const currentPages = pagesQuery.data ?? pages;
  const stylesQuery = useQuery({
    queryKey: qk.styles,
    queryFn: async () => (await api<{ styles: StyleDTO[] }>("/api/styles")).data.styles,
    enabled: open,
    staleTime: 5 * 60_000,
    retry: 1,
  });

  const exportQuery = useQuery({
    queryKey: qk.exportJob(projectId, activeExportId ?? "none"),
    queryFn: async () =>
      (await api<ExportDTO>(`/api/projects/${projectId}/exports/${activeExportId}`)).data,
    enabled: open && Boolean(activeExportId),
    staleTime: 0,
    retry: 1,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 1_000;
      if (data.state === "FAILED" || data.state === "CANCELLED") return false;
      if (data.state === "SUCCEEDED" && data.artifact && data.artifact.byteSize > 0) return false;
      return 1_000;
    },
  });
  const exportData = exportQuery.data;

  const createMutation = useMutation({
    mutationFn: async (requestedFormat: ExportFormat) =>
      (
        await api<{ export: ExportDTO }>(`/api/projects/${projectId}/exports`, {
          method: "POST",
          body: { format: requestedFormat },
          expectedVersion: currentSnapshot.project.version,
          idempotencyKey: uuid(),
        })
      ).data.export,
    onMutate: () => setCreateError(null),
    onSuccess: (created) => {
      queryClient.setQueryData(qk.exportJob(projectId, created.exportId), created);
      setActiveExportId(created.exportId);
      setCreateError(null);
      setAnnouncement(`Export queued for ${created.format}.`);
      void queryClient.invalidateQueries({ queryKey: qk.snapshot(projectId) });
    },
    onError: (error) => {
      setCreateError(errorText(error));
      if (isApiConflict(error)) {
        void queryClient.invalidateQueries({ queryKey: qk.snapshot(projectId) });
        void queryClient.invalidateQueries({ queryKey: qk.pages(projectId) });
        toast.error(errorText(error));
      } else if (isApiValidation(error)) {
        void queryClient.invalidateQueries({ queryKey: qk.pages(projectId) });
      }
    },
  });

  useEffect(() => {
    if (open) return;
    setFormat("PPTX");
    setActiveExportId(null);
    setCreateError(null);
    setAnnouncement("");
    lastStateRef.current = null;
  }, [open]);

  useEffect(() => {
    if (!exportData) return;
    if (lastStateRef.current === exportData.state) return;
    lastStateRef.current = exportData.state;
    if (exportData.state === "SUCCEEDED") {
      setAnnouncement(
        exportData.artifact && exportData.artifact.byteSize > 0
          ? "Export complete. The file is ready to download."
          : "The export finished, but the downloadable file is not available yet.",
      );
    } else if (exportData.state === "FAILED" || exportData.state === "CANCELLED") {
      setAnnouncement("Export failed. Review the reason, then retry or try another format.");
    } else {
      setAnnouncement(`${STATE_LABEL[exportData.state] ?? "Export"} in progress.`);
    }
  }, [exportData]);

  const styleSelection = currentSnapshot.styleSelection;
  const styleKey = styleSelection?.styleKey ?? "";
  const styleVersion = styleSelection?.styleVersion;
  const styleConfirmed = styleSelection?.confirmed === true;
  const styleName = stylesQuery.data?.find((style) => style.styleKey === styleKey)?.name;
  const pageCount = currentPages?.counts.total ?? currentSnapshot.counts.pages;
  const designTotal =
    currentPages?.counts.total ??
    (currentSnapshot.counts.designTotal || currentSnapshot.counts.pages);
  const designDone = currentPages?.counts.designDone ?? currentSnapshot.counts.designDone;
  const incompletePages =
    currentPages?.pages.filter((page) => page.design.status !== "DONE") ?? [];
  const hasPageList = Boolean(currentPages?.pages.length);
  const complete = hasPageList
    ? incompletePages.length === 0
    : pageCount > 0 && designTotal > 0 && designDone >= designTotal;
  const canStart =
    complete && styleConfirmed && Boolean(styleKey) && !createMutation.isPending && open;

  const artifact =
    exportData?.state === "SUCCEEDED" &&
    exportData.artifact &&
    exportData.artifact.byteSize > 0
      ? exportData.artifact
      : null;
  const succeeded = Boolean(artifact);
  const failed = exportData?.state === "FAILED" || exportData?.state === "CANCELLED";
  const exporting = Boolean(activeExportId) && !succeeded && !failed;
  const progressPercent = formatPercent(exportData?.progress.percent ?? 0);
  const failedChecks: ExportValidationCheckDTO[] =
    exportData?.validation?.failedChecks ?? [];
  const excludedPageIds = exportData?.deckSnapshot.excludedPageIds ?? [];
  const failureReason = exportData?.error
    ? messageFor(exportData.error.messageKey)
    : failedChecks.length > 0
      ? "Pre-export validation failed. Review the affected pages and checks below."
      : "The export stopped before a file was produced.";

  const resetToPicker = () => {
    const currentIndex = FORMATS.findIndex((option) => option.value === format);
    const nextFormat = FORMATS[(currentIndex + 1) % FORMATS.length]?.value ?? "PPTX";
    setFormat(nextFormat);
    setActiveExportId(null);
    setCreateError(null);
    setAnnouncement("Choose a format to start a new export.");
    lastStateRef.current = null;
    window.setTimeout(
      () => document.getElementById(`export-format-${nextFormat}`)?.focus(),
      0,
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        aria-modal="true"
        className="max-[721px]:w-[calc(100vw-20px)] max-[721px]:max-h-[92vh]"
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          firstFormatRef.current?.focus();
        }}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          returnFocusRef.current?.focus();
        }}
      >
        <DialogTitle>Export deck</DialogTitle>
        <DialogDescription>
          Review the page count, style, and rendered completeness before creating a file. Export
          starts only when every page has a current design.
        </DialogDescription>

        <div role="status" aria-live="polite" className="sr-only">
          {announcement}
        </div>

        {!activeExportId && !succeeded ? (
          <div className="mt-4">
            <ExportScope
              pageCount={pageCount}
              designDone={designDone}
              designTotal={designTotal}
              styleName={styleName}
              styleKey={styleKey}
              styleVersion={styleVersion}
              styleConfirmed={styleConfirmed}
              complete={complete}
              incompletePages={incompletePages}
              pages={currentPages}
              onSelectPage={onSelectPage}
            />

            <div className="mt-5">
              <p className="mb-2 text-sm font-medium text-ink-2">Format</p>
              <RadioGroup
                value={format}
                onValueChange={(value) => {
                  setFormat(value as ExportFormat);
                  setCreateError(null);
                }}
                aria-label="Export format"
                className="space-y-2"
              >
                {FORMATS.map((option, index) => {
                  const selected = format === option.value;
                  return (
                    <label
                      key={option.value}
                      className={cn(
                        "flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition-colors",
                        selected
                          ? "border-brand bg-brand-soft/50 ring-1 ring-brand/30"
                          : "border-line bg-white hover:bg-surface-2",
                      )}
                    >
                      <RadioGroupItem
                        ref={index === 0 ? firstFormatRef : undefined}
                        value={option.value}
                        id={`export-format-${option.value}`}
                        className="mt-0.5"
                      />
                      <span className="min-w-0 flex-1">
                        <span className="flex flex-wrap items-center gap-2">
                          <option.Icon className="h-4 w-4 text-brand" aria-hidden="true" />
                          <span className="text-sm font-semibold text-ink">{option.title}</span>
                          {option.recommended ? <Badge tone="brand">Recommended</Badge> : null}
                        </span>
                        <span className="mt-0.5 block text-xs text-muted">{option.description}</span>
                      </span>
                    </label>
                  );
                })}
              </RadioGroup>
            </div>

            {createError ? (
              <p
                role="alert"
                className="mt-3 rounded-xl border border-red-200 bg-danger-soft px-3 py-2 text-xs text-danger"
              >
                {createError}
              </p>
            ) : null}

            <div className="mt-5 flex flex-wrap items-center justify-between gap-2">
              <Button variant="secondary" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button
                onClick={() => createMutation.mutate(format)}
                disabled={!canStart}
                aria-describedby="export-start-note"
              >
                {createMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                ) : null}
                {createMutation.isPending ? "Starting export…" : `Export ${format}`}
              </Button>
            </div>
            <p id="export-start-note" className="mt-2 text-[11px] leading-snug text-muted">
              {complete
                ? "A deck snapshot is frozen at request time. Re-export after edits to include them."
                : "Finish every page before exporting. The incomplete pages are listed above."}
            </p>
          </div>
        ) : null}

        {exporting ? (
          <div className="mt-4" aria-busy="true">
            <div className="rounded-xl border border-line bg-surface-2 p-4">
              <div className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin text-brand" aria-hidden="true" />
                <p className="text-sm font-semibold text-ink">
                  {exportData?.state === "SUCCEEDED"
                    ? "Finalizing the downloadable file…"
                    : `${STATE_LABEL[exportData?.state ?? ""] ?? "Exporting"}…`}
                </p>
                <span className="ml-auto text-xs font-medium tabular-nums text-muted">
                  {progressPercent}%
                </span>
              </div>
              <Progress value={progressPercent} label="Export progress" className="mt-3" />
              <p className="mt-2 text-xs text-muted">
                {exportData
                  ? `${exportData.progress.pagesRendered} of ${exportData.progress.pagesTotal} pages rendered`
                  : "The export is being queued. Progress updates every second."}
              </p>
            </div>
            {exportData?.state === "SUCCEEDED" && !artifact ? (
              <p role="status" className="mt-3 text-xs text-warn">
                The export finished but the file reference is not available yet. Waiting for the
                server to finalize it.
              </p>
            ) : null}
            {exportQuery.isError ? (
              <div
                role="alert"
                className="mt-3 rounded-xl border border-red-200 bg-danger-soft p-3 text-xs text-danger"
              >
                <p className="font-medium">Export status could not be refreshed.</p>
                <p className="mt-0.5">{errorText(exportQuery.error)}</p>
                <Button
                  variant="secondary"
                  size="sm"
                  className="mt-2"
                  onClick={() => void exportQuery.refetch()}
                >
                  <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                  Retry status
                </Button>
              </div>
            ) : null}
            <div className="mt-4 flex justify-end">
              <Button variant="secondary" onClick={() => onOpenChange(false)}>
                Close
              </Button>
            </div>
          </div>
        ) : null}

        {failed && exportData ? (
          <div className="mt-4">
            <div role="alert" className="rounded-xl border border-red-200 bg-danger-soft p-4">
              <div className="flex items-start gap-2">
                <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-danger" aria-hidden="true" />
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-danger">
                    {exportData.state === "CANCELLED" ? "Export cancelled" : "Export failed"}
                  </p>
                  <p className="mt-1 text-xs leading-snug text-danger">{failureReason}</p>
                </div>
              </div>
              {failedChecks.length > 0 ? (
                <ul className="mt-3 space-y-2">
                  {failedChecks.map((check, index) => (
                    <li
                      key={`${check.code}-${index}`}
                      className="rounded-lg border border-red-200 bg-white/70 p-2.5"
                    >
                      <p className="text-xs font-semibold text-danger">
                        {CHECK_LABEL[check.code] ?? check.code}
                      </p>
                      {check.pageIds.length > 0 ? (
                        <PageLinkList
                          pageIds={check.pageIds}
                          pages={currentPages}
                          onSelectPage={onSelectPage}
                        />
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : null}
              {excludedPageIds.length > 0 ? (
                <div className="mt-3">
                  <p className="text-xs font-semibold text-warn">
                    Pages excluded from this export ({excludedPageIds.length})
                  </p>
                  <PageLinkList
                    pageIds={excludedPageIds}
                    pages={currentPages}
                    onSelectPage={onSelectPage}
                  />
                </div>
              ) : null}
            </div>
            {createError ? (
              <p
                role="alert"
                className="mt-3 rounded-xl border border-red-200 bg-danger-soft px-3 py-2 text-xs text-danger"
              >
                {createError}
              </p>
            ) : null}
            <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
              <Button variant="secondary" onClick={() => onOpenChange(false)}>
                Close
              </Button>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="secondary"
                  onClick={resetToPicker}
                  disabled={createMutation.isPending}
                >
                  Try another format
                </Button>
                <Button
                  onClick={() => createMutation.mutate(exportData.format)}
                  disabled={createMutation.isPending}
                >
                  {createMutation.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <RefreshCw className="h-4 w-4" aria-hidden="true" />
                  )}
                  Retry export
                </Button>
              </div>
            </div>
            <p className="mt-2 text-[11px] text-muted">
              Retry starts a new export intent with a fresh idempotency key. The modal stays open
              until a file exists.
            </p>
          </div>
        ) : null}

        {succeeded && artifact ? (
          <div className="mt-4">
            <div
              role="status"
              className="flex items-start gap-2 rounded-xl border border-green-200 bg-ok-soft p-4"
            >
              <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-ok" aria-hidden="true" />
              <div>
                <p className="text-sm font-semibold text-ok">Export complete</p>
                <p className="mt-0.5 text-xs text-ok/90">
                  The file was produced by the server and is ready to download.
                </p>
              </div>
            </div>
            <dl className="mt-4 grid grid-cols-2 gap-2 text-xs">
              <div className="col-span-2 rounded-lg border border-line bg-surface-2 px-3 py-2">
                <dt className="text-[10px] uppercase tracking-wide text-faint">File</dt>
                <dd className="mt-0.5 break-all font-semibold text-ink">{artifact.fileName}</dd>
              </div>
              <div className="rounded-lg border border-line bg-surface-2 px-3 py-2">
                <dt className="text-[10px] uppercase tracking-wide text-faint">Size</dt>
                <dd className="mt-0.5 font-semibold tabular-nums text-ink">
                  {formatBytes(artifact.byteSize)}
                </dd>
              </div>
              <div className="rounded-lg border border-line bg-surface-2 px-3 py-2">
                <dt className="text-[10px] uppercase tracking-wide text-faint">Created</dt>
                <dd className="mt-0.5 font-semibold text-ink">
                  {formatTimestamp(artifact.createdAt)}
                </dd>
              </div>
              <div className="col-span-2 rounded-lg border border-line bg-surface-2 px-3 py-2">
                <dt className="text-[10px] uppercase tracking-wide text-faint">Checksum (sha256)</dt>
                <dd className="mono mt-0.5 break-all text-[11px] text-ink-2">
                  {artifact.checksum}
                </dd>
              </div>
            </dl>
            {exportData?.substitutionReport?.substitutions.length ? (
              <div className="mt-3 rounded-xl border border-amber-200 bg-warn-soft p-3">
                <p className="text-xs font-semibold text-warn">Font or asset substitutions</p>
                <ul className="mt-1 space-y-1">
                  {exportData.substitutionReport.substitutions.map((substitution, index) => (
                    <li key={`${substitution.from}-${index}`} className="text-[11px] text-warn">
                      {substitution.from} → {substitution.to} ({substitution.reason})
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {excludedPageIds.length > 0 ? (
              <div className="mt-3 rounded-xl border border-amber-200 bg-warn-soft p-3">
                <p className="text-xs font-semibold text-warn">
                  Pages excluded from this export ({excludedPageIds.length})
                </p>
                <PageLinkList
                  pageIds={excludedPageIds}
                  pages={currentPages}
                  onSelectPage={onSelectPage}
                />
              </div>
            ) : null}
            <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
              <Button variant="secondary" onClick={() => onOpenChange(false)}>
                Close
              </Button>
              <Button asChild>
                <a href={artifact.downloadPath} download>
                  Download {artifact.fileName}
                </a>
              </Button>
            </div>
            <p className="mt-2 text-[11px] text-muted">
              The download route authorizes the request and redirects to a short-lived file URL.
            </p>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function ExportScope({
  pageCount,
  designDone,
  designTotal,
  styleName,
  styleKey,
  styleVersion,
  styleConfirmed,
  complete,
  incompletePages,
  pages,
  onSelectPage,
}: {
  pageCount: number;
  designDone: number;
  designTotal: number;
  styleName: string | undefined;
  styleKey: string;
  styleVersion: number | undefined;
  styleConfirmed: boolean;
  complete: boolean;
  incompletePages: PageListDTO["pages"];
  pages: PageListDTO | undefined;
  onSelectPage: (pageId: string) => void;
}) {
  return (
    <div className="rounded-xl border border-line bg-surface-2 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-ink">Export scope</h3>
        <Badge tone={complete ? "ok" : "warn"}>
          {complete ? (
            <>
              <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
              All pages ready
            </>
          ) : (
            <>
              <AlertTriangle className="h-3 w-3" aria-hidden="true" />
              Incomplete deck
            </>
          )}
        </Badge>
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div className="rounded-lg border border-line bg-white px-2.5 py-1.5">
          <dt className="text-[10px] uppercase tracking-wide text-faint">Pages</dt>
          <dd className="mt-0.5 font-semibold tabular-nums text-ink">{pageCount}</dd>
        </div>
        <div className="rounded-lg border border-line bg-white px-2.5 py-1.5">
          <dt className="text-[10px] uppercase tracking-wide text-faint">Rendered</dt>
          <dd className="mt-0.5 font-semibold tabular-nums text-ink">
            {designDone} / {designTotal}
          </dd>
        </div>
        <div className="col-span-2 rounded-lg border border-line bg-white px-2.5 py-1.5">
          <dt className="text-[10px] uppercase tracking-wide text-faint">Style</dt>
          <dd className="mt-0.5 font-semibold text-ink">
            {styleKey ? (
              <>
                {styleName ?? styleKey}
                <span className="font-normal text-muted">
                  {" "}
                  ({styleKey}
                  {styleVersion !== undefined ? ` v${styleVersion}` : ""}) ·{" "}
                  {styleConfirmed ? "confirmed" : "not confirmed"}
                </span>
              </>
            ) : (
              "Not selected"
            )}
          </dd>
        </div>
      </dl>
      {incompletePages.length > 0 ? (
        <div className="mt-3 rounded-lg border border-amber-200 bg-warn-soft p-3">
          <p className="text-xs font-semibold text-warn">
            {pluralize(incompletePages.length, "page")} not ready:
          </p>
          <ul className="mt-1.5 space-y-1">
            {incompletePages.map((page) => {
              const index = pages?.pages.findIndex((candidate) => candidate.pageId === page.pageId) ?? -1;
              const info = designStatusInfo(page.design.status);
              return (
                <li key={page.pageId}>
                  <button
                    type="button"
                    onClick={() => onSelectPage(page.pageId)}
                    className="inline-flex w-full items-center gap-1.5 rounded-md text-left text-[11px] text-warn hover:underline"
                  >
                    <span className="truncate">
                      {index >= 0 ? `Page ${index + 1}: ` : ""}
                      {page.title}
                    </span>
                    <span className="shrink-0 text-warn/80">— {info.label}</span>
                  </button>
                </li>
              );
            })}
          </ul>
          <p className="mt-1.5 text-[11px] text-warn/80">
            The server rejects an export until every page has a current design. Open a page to
            retry or tweak it.
          </p>
        </div>
      ) : null}
      {!complete && incompletePages.length === 0 ? (
        <p className="mt-3 rounded-lg border border-amber-200 bg-warn-soft px-3 py-2 text-[11px] text-warn">
          The page list is still loading. Incomplete page names will appear here before an export
          can start.
        </p>
      ) : null}
    </div>
  );
}

function PageLinkList({
  pageIds,
  pages,
  onSelectPage,
}: {
  pageIds: string[];
  pages: PageListDTO | undefined;
  onSelectPage: (pageId: string) => void;
}) {
  const resolved = useMemo(() => {
    if (!pages) return [];
    return pageIds
      .map((pageId) => {
        const index = pages.pages.findIndex((page) => page.pageId === pageId);
        return index >= 0 ? { page: pages.pages[index], index } : null;
      })
      .filter((entry): entry is { page: PageListDTO["pages"][number]; index: number } =>
        Boolean(entry),
      );
  }, [pageIds, pages]);

  if (resolved.length === 0) {
    return (
      <p className="mt-1 text-[11px] text-muted">
        {pageIds.length > 0
          ? `${pluralize(pageIds.length, "page")} affected — ${
              pages ? "not in the current deck list" : "the page list is still loading"
            }.`
          : ""}
      </p>
    );
  }

  return (
    <div className="mt-1.5 flex flex-wrap gap-1.5">
      {resolved.map(({ page, index }) => (
        <button
          key={page.pageId}
          type="button"
          onClick={() => onSelectPage(page.pageId)}
          className="rounded-full border border-line-strong bg-white px-2 py-0.5 text-[11px] font-medium text-ink-2 hover:bg-surface-2"
        >
          Page {index + 1}: {page.title}
        </button>
      ))}
    </div>
  );
}
