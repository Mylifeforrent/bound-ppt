import type { KeyboardEvent } from "react";
import type { PageSummaryDTO } from "@/api/types";
import { cn, pluralize } from "@/lib/utils";
import { StatusIcon, planStatusInfo, type StatusTone } from "./planStatus";

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

export function PlanPageList({
  pages,
  selectedPageId,
  onSelect,
  onKeyDown,
}: {
  pages: PageSummaryDTO[];
  selectedPageId: string | null;
  onSelect: (pageId: string) => void;
  onKeyDown: (event: KeyboardEvent<HTMLElement>) => void;
}) {
  const groups = groupBySection(pages);
  const indexByPageId = new Map(pages.map((page, index) => [page.pageId, index]));

  return (
    <aside
      aria-label="Plan pages"
      onKeyDown={onKeyDown}
      className="app-card min-w-0 p-3 min-[1180px]:sticky min-[1180px]:top-[88px] min-[1180px]:max-h-[calc(100vh-112px)] min-[1180px]:overflow-y-auto"
    >
      <div className="mb-2 flex items-center justify-between gap-2 px-1">
        <h2 className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">Pages</h2>
        <span className="text-[11px] font-medium tabular-nums text-muted">{pages.length}</span>
      </div>
      <nav
        aria-label="Plan pages grouped by section"
        className="flex min-w-0 flex-col gap-4 max-[721px]:flex-row max-[721px]:items-start max-[721px]:gap-3 max-[721px]:overflow-x-auto max-[721px]:pb-1"
      >
        {groups.map((group) => (
          <section key={group.key} className="min-w-0 max-[721px]:shrink-0" aria-label={group.title}>
            <h3 className="mb-1.5 flex items-center gap-1 px-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-faint">
              <span className="truncate">{group.title}</span>
              <span className="shrink-0 tabular-nums">({group.pages.length})</span>
            </h3>
            <ol className="flex flex-col gap-1.5 max-[721px]:flex-row">
              {group.pages.map((page) => {
                const index = indexByPageId.get(page.pageId) ?? 0;
                const selected = page.pageId === selectedPageId;
                const info = planStatusInfo(page.plan.status);
                return (
                  <li key={page.pageId} className="min-w-0 max-[721px]:w-[188px]">
                    <button
                      type="button"
                      onClick={() => onSelect(page.pageId)}
                      aria-current={selected ? "page" : undefined}
                      aria-label={`Page ${index + 1} of ${pages.length}: ${page.title}. Plan status: ${
                        info.label
                      } (${page.plan.status}).${selected ? " Current page." : ""}`}
                      className={cn(
                        "flex w-full items-start gap-2 rounded-xl border px-2.5 py-2 text-left transition-colors",
                        selected
                          ? "border-brand bg-brand-soft/60 ring-1 ring-brand/30"
                          : "border-line bg-white hover:bg-surface-2",
                      )}
                    >
                      <span className="mono shrink-0 pt-0.5 text-[10px] font-semibold tabular-nums text-muted">
                        {index + 1}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="line-clamp-2 block text-[11px] font-semibold leading-snug text-ink">
                          {page.title}
                        </span>
                        <span
                          className={cn(
                            "mt-1 flex items-center gap-1 text-[10px] font-medium",
                            TONE_TEXT[info.tone],
                          )}
                        >
                          <StatusIcon status={page.plan.status} className="h-3 w-3" />
                          {info.label}
                        </span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ol>
          </section>
        ))}
      </nav>
      <p className="mt-3 border-t border-line px-1 pt-2 text-[11px] text-muted max-[721px]:hidden">
        {pluralize(pages.length, "page")} grouped by outline section. Use ← → to change pages.
      </p>
    </aside>
  );
}
