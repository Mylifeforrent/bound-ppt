import { AlertCircle, FileText, Globe2, RefreshCw } from "lucide-react";
import type { SourceItemDTO, SourcePanelDTO } from "@/api/types";
import { Badge, Card } from "@/components/ui/primitives";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { errorInfo } from "@/features/intake/errors";

const SKELETON_ROWS = 3;

function validItems(items: SourceItemDTO[]): SourceItemDTO[] {
  return items.filter((item) => Boolean(item.title?.trim()) && Boolean(item.summary?.trim()));
}

function SourceRow({ item }: { item: SourceItemDTO }) {
  const isMaterial = item.origin === "PROVIDED";
  return (
    <li className="rounded-xl border border-line bg-white p-3">
      <div className="flex flex-wrap items-center gap-1.5">
        <Badge tone={isMaterial ? "brand" : "neutral"}>{isMaterial ? "Material" : "Web"}</Badge>
        <span className="text-[11px] uppercase tracking-[0.08em] text-faint">{item.sourceType}</span>
        {item.domain ? <span className="mono text-[11px] text-faint">{item.domain}</span> : null}
      </div>
      <p className="mt-1.5 text-sm font-semibold text-ink">{item.title}</p>
      <p className="mt-1 line-clamp-3 text-xs leading-relaxed text-muted">{item.summary}</p>
    </li>
  );
}

function GroupSkeleton({ label }: { label: string }) {
  return (
    <div className="space-y-2" aria-busy="true">
      <p className="sr-only">{label}</p>
      {Array.from({ length: SKELETON_ROWS }).map((_, index) => (
        <div key={index} className="rounded-xl border border-line bg-surface-2 p-3">
          <Skeleton className="h-4 w-20" />
          <Skeleton className="mt-2 h-3.5 w-3/4" />
          <Skeleton className="mt-2 h-3 w-full" />
        </div>
      ))}
    </div>
  );
}

export interface SourcePanelProps {
  panel: SourcePanelDTO;
  materialsExist: boolean;
  loading: boolean;
  fetching?: boolean;
  materialsPending?: boolean;
  error?: unknown;
  onRetry: () => void;
}

export function SourcePanel({
  panel,
  materialsExist,
  loading,
  fetching,
  materialsPending,
  error,
  onRetry,
}: SourcePanelProps) {
  const materialItems = validItems(panel.materials.items);
  const webItems = validItems(panel.web.items);
  const materialsLoading = loading || (materialsPending ?? panel.materials.status === "loading");
  const webLoading = loading || panel.web.status === "loading";
  const reference = error ? errorInfo(error).reference : undefined;

  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-ink">Content sources</h2>
        {fetching ? (
          <span className="flex items-center gap-1 text-[11px] text-muted">
            <RefreshCw className="h-3 w-3 animate-spin" aria-hidden="true" />
            Updating…
          </span>
        ) : null}
      </div>

      {error ? (
        <div
          role="alert"
          className="mt-3 rounded-lg border border-red-200 bg-danger-soft px-2.5 py-2 text-xs text-danger"
        >
          <p className="flex items-start gap-1.5">
            <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <span>Sources could not be refreshed. Showing the last state that loaded.</span>
          </p>
          {reference ? <p className="mono mt-1 text-[11px] text-danger/80">Reference: {reference}</p> : null}
          <Button type="button" variant="ghost" size="sm" className="mt-1 h-7 px-2 text-xs" onClick={onRetry}>
            Retry
          </Button>
        </div>
      ) : null}

      {materialsExist ? (
        <section className="mt-4" aria-labelledby="sources-materials-title">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h3 id="sources-materials-title" className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.08em] text-muted">
              <FileText className="h-3.5 w-3.5" aria-hidden="true" />
              Your materials
            </h3>
            <Badge tone="brand">{panel.materials.count}</Badge>
          </div>
          {materialsLoading ? (
            <GroupSkeleton label="Loading your material sources" />
          ) : materialItems.length > 0 ? (
            <ul className="space-y-2">
              {materialItems.map((item) => (
                <SourceRow key={item.id} item={item} />
              ))}
            </ul>
          ) : (
            <p className={cn("rounded-xl border border-dashed border-line-strong bg-surface-2 px-3 py-2 text-xs text-muted")}>
              Materials are saved, but no extracted passages are available yet.
            </p>
          )}
        </section>
      ) : null}

      <section className="mt-4" aria-labelledby="sources-web-title">
        <div className="mb-2 flex items-center justify-between gap-2">
          <h3 id="sources-web-title" className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.08em] text-muted">
            <Globe2 className="h-3.5 w-3.5" aria-hidden="true" />
            Web supplements
          </h3>
          <div className="flex items-center gap-1">
            {panel.web.cap > 0 ? <span className="text-[11px] text-faint">cap {panel.web.cap}</span> : null}
            <Badge tone="neutral">{panel.web.count}</Badge>
          </div>
        </div>
        {panel.web.skipped ? (
          <p className="rounded-xl border border-line bg-surface-2 px-3 py-2 text-xs text-muted">
            Web search was skipped. The deck uses your materials only and the profile records no web supplements.
          </p>
        ) : webLoading ? (
          <GroupSkeleton label="Loading web supplement sources" />
        ) : webItems.length > 0 ? (
          <ul className="space-y-2">
            {webItems.map((item) => (
              <SourceRow key={item.id} item={item} />
            ))}
          </ul>
        ) : (
          <p className="rounded-xl border border-dashed border-line-strong bg-surface-2 px-3 py-2 text-xs text-muted">
            {materialsExist
              ? "No web supplements yet. Targeted gap searches appear here as they run."
              : "No web sources yet. The default web research starts at the intake step."}
          </p>
        )}
      </section>
    </Card>
  );
}
