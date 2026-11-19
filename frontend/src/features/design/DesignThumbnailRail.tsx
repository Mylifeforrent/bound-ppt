import type { KeyboardEvent } from "react";
import { Pin } from "lucide-react";
import type { ArtifactDTO, DesignBodyV1, PageSummaryDTO } from "@/api/types";
import { DesignDeckPage, ScaledDeckCanvas } from "@/render/DeckRenderer";
import { Badge } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";
import {
  StatusIcon,
  designStatusInfo,
  type StatusTone,
} from "./designStatus";

const TONE_TEXT: Record<StatusTone, string> = {
  neutral: "text-muted",
  brand: "text-brand",
  ok: "text-ok",
  warn: "text-warn",
  danger: "text-danger",
};

function groupBySection(pages: PageSummaryDTO[]) {
  const groups: Array<{ key: string; title: string; pages: PageSummaryDTO[] }> = [];
  for (const page of pages) {
    let group = groups.find((candidate) => candidate.key === page.sectionKey);
    if (!group) {
      group = {
        key: page.sectionKey,
        title: page.sectionTitle || page.sectionKey,
        pages: [],
      };
      groups.push(group);
    }
    group.pages.push(page);
  }
  return groups;
}

export function DesignThumbnailRail({
  pages,
  selectedPageId,
  pinnedPageId,
  thumbnails,
  onSelect,
  onKeyDown,
}: {
  pages: PageSummaryDTO[];
  selectedPageId: string | null;
  pinnedPageId: string | null;
  thumbnails: Record<string, ArtifactDTO | undefined>;
  onSelect: (pageId: string) => void;
  onKeyDown: (event: KeyboardEvent<HTMLElement>) => void;
}) {
  const groups = groupBySection(pages);
  const indexByPageId = new Map(pages.map((page, index) => [page.pageId, index]));

  return (
    <aside
      aria-label="Deck pages"
      onKeyDown={onKeyDown}
      className="app-card min-w-0 p-3 min-[1180px]:sticky min-[1180px]:top-[88px] min-[1180px]:max-h-[calc(100vh-112px)] min-[1180px]:overflow-y-auto"
    >
      <div className="mb-2 flex items-center justify-between gap-2 px-1">
        <h2 className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">Pages</h2>
        <span className="text-[11px] font-medium tabular-nums text-muted">{pages.length}</span>
      </div>
      <nav
        aria-label="Design pages grouped by section"
        className="flex min-w-0 flex-col gap-4 max-[721px]:flex-row max-[721px]:items-start max-[721px]:gap-3 max-[721px]:overflow-x-auto max-[721px]:pb-1"
      >
        {groups.map((group) => (
          <section key={group.key} className="min-w-0 max-[721px]:shrink-0" aria-label={group.title}>
            <h3 className="mb-1.5 truncate px-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-faint">
              {group.title}
            </h3>
            <ol className="flex flex-col gap-2 max-[721px]:flex-row">
              {group.pages.map((page) => {
                const index = indexByPageId.get(page.pageId) ?? 0;
                const selected = page.pageId === selectedPageId;
                const pinned = page.pageId === pinnedPageId;
                const info = designStatusInfo(page.design.status);
                const artifact = thumbnails[page.pageId];
                return (
                  <li key={page.pageId} className="min-w-0 max-[721px]:w-[172px]">
                    <button
                      type="button"
                      onClick={() => onSelect(page.pageId)}
                      aria-current={selected ? "page" : undefined}
                      aria-label={`Page ${index + 1} of ${pages.length}: ${page.title}. ${
                        info.description
                      }.${selected ? " Current page." : ""}`}
                      className={cn(
                        "w-full rounded-xl border p-1.5 text-left transition-colors",
                        selected
                          ? "border-brand bg-brand-soft/60 ring-1 ring-brand/30"
                          : "border-line bg-white hover:bg-surface-2",
                      )}
                    >
                      <span className="block overflow-hidden rounded-lg" aria-hidden="true">
                        {artifact ? (
                          <span className="pointer-events-none block">
                            <ScaledDeckCanvas ariaLabel="">
                              <DesignDeckPage
                                body={artifact.body as DesignBodyV1}
                                chrome={artifact.chrome}
                              />
                            </ScaledDeckCanvas>
                          </span>
                        ) : (
                          <span
                            className={cn(
                              "grid aspect-video w-full place-items-center rounded-lg border border-dashed",
                              page.design.status === "ERROR"
                                ? "border-red-200 bg-danger-soft"
                                : page.design.status === "DESIGNING"
                                  ? "border-indigo-200 bg-brand-soft"
                                  : "border-line-strong bg-surface-2",
                            )}
                          >
                            <StatusIcon
                              status={page.design.status}
                              className={cn("h-4 w-4", TONE_TEXT[info.tone])}
                            />
                          </span>
                        )}
                      </span>
                      <span className="mt-1.5 flex items-start gap-1.5 px-0.5">
                        <span className="mono shrink-0 pt-0.5 text-[10px] font-semibold tabular-nums text-muted">
                          {index + 1}
                        </span>
                        <span className="line-clamp-2 min-w-0 flex-1 text-[11px] font-semibold leading-snug text-ink">
                          {page.title}
                        </span>
                        {pinned ? (
                          <Pin
                            aria-hidden="true"
                            className="h-3 w-3 shrink-0 text-brand"
                          />
                        ) : null}
                      </span>
                      <span
                        className={cn(
                          "mt-0.5 flex items-center gap-1 px-0.5 text-[10px] font-medium",
                          TONE_TEXT[info.tone],
                        )}
                      >
                        <StatusIcon status={page.design.status} className="h-3 w-3" />
                        {info.label}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ol>
          </section>
        ))}
      </nav>
      <div className="mt-3 border-t border-line px-1 pt-2 max-[721px]:hidden">
        <Badge tone="neutral" className="text-[10px]">
          Use ← → to change pages
        </Badge>
      </div>
    </aside>
  );
}
