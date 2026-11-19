import { AlertCircle, CheckCircle2, Loader2, Search, SearchX } from "lucide-react";
import type { GapSearchOutcomeDTO, GapStateDTO } from "@/api/types";
import { Badge, Card } from "@/components/ui/primitives";
import { Skeleton } from "@/components/ui/dialog";

export interface GapSearchListProps {
  gaps: GapStateDTO;
  outcomes: GapSearchOutcomeDTO[];
}

function outcomeCopy(outcome: GapSearchOutcomeDTO["outcome"], resultCount: number): string {
  switch (outcome) {
    case "RESULTS":
      return `${resultCount} ${resultCount === 1 ? "source" : "sources"} found and added to the Web supplements.`;
    case "ZERO_RESULTS":
      return "Nothing was found for this gap. You can continue; the profile records the missing supplement explicitly.";
    case "FAILED":
      return "The search failed for this gap. You can continue with the other sources, or restart research to retry.";
    case "PENDING":
    default:
      return "Searching the web for this gap…";
  }
}

export function GapSearchList({ gaps, outcomes }: GapSearchListProps) {
  const decision = gaps.decision;
  if (!decision) return null;

  const suggestionLabels = new Map(gaps.suggestions.map((suggestion) => [suggestion.id, suggestion.label]));
  const selectedCount = decision.selectedSuggestionIds.length;

  if (decision.webSkipped) {
    return (
      <Card className="p-4">
        <div className="flex items-start gap-3">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-surface-2 text-muted">
            <SearchX className="h-4 w-4" aria-hidden="true" />
          </span>
          <div>
            <p className="text-sm font-semibold text-ink">Web search skipped</p>
            <p className="mt-1 text-sm text-muted">
              “Not needed — just use my materials” was recorded. No web searches run and the profile’s Web row stays
              empty.
            </p>
          </div>
        </div>
      </Card>
    );
  }

  if (selectedCount === 0) return null;

  const pending = outcomes.some((outcome) => outcome.outcome === "PENDING");
  const resolved = outcomes.filter((outcome) => outcome.outcome !== "PENDING").length;
  const zero = outcomes.filter((outcome) => outcome.outcome === "ZERO_RESULTS").length;
  const failed = outcomes.filter((outcome) => outcome.outcome === "FAILED").length;

  return (
    <Card className="p-4" aria-busy={pending}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold text-ink">Targeted gap searches</p>
        <Badge tone={pending ? "warn" : "neutral"}>
          {resolved} / {outcomes.length || selectedCount} resolved
        </Badge>
      </div>

      {outcomes.length === 0 ? (
        <div className="mt-3 space-y-2" aria-busy="true">
          {Array.from({ length: selectedCount }).map((_, index) => (
            <div key={index} className="rounded-xl border border-line bg-surface-2 p-3">
              <p className="sr-only">Starting a targeted gap search</p>
              <Skeleton className="h-3.5 w-48" />
              <Skeleton className="mt-2 h-3 w-full" />
            </div>
          ))}
        </div>
      ) : (
        <ul className="mt-3 space-y-2">
          {outcomes.map((outcome) => {
            const label = suggestionLabels.get(outcome.gapSuggestionId) ?? "Selected gap";
            const isPending = outcome.outcome === "PENDING";
            const isZero = outcome.outcome === "ZERO_RESULTS";
            const isFailed = outcome.outcome === "FAILED";
            const Icon = isPending ? Loader2 : isFailed || isZero ? AlertCircle : CheckCircle2;
            return (
              <li
                key={`${outcome.gapSuggestionId}-${outcome.queryIndex}`}
                className="rounded-xl border border-line bg-white p-3"
              >
                <div className="flex items-start gap-2.5">
                  <span
                    className={`mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg ${
                      isFailed || isZero ? "bg-warn-soft text-warn" : "bg-surface-2 text-brand-strong"
                    }`}
                  >
                    <Icon
                      className={isPending ? "h-3.5 w-3.5 animate-spin" : "h-3.5 w-3.5"}
                      aria-hidden="true"
                    />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-medium text-ink">{label}</p>
                      {outcome.queryIndex > 0 ? (
                        <span className="text-[11px] text-faint">Query {outcome.queryIndex}</span>
                      ) : null}
                      {isZero ? <Badge tone="warn">Zero results</Badge> : null}
                      {isFailed ? <Badge tone="danger">Failed</Badge> : null}
                      {outcome.outcome === "RESULTS" ? <Badge tone="ok">Results</Badge> : null}
                    </div>
                    <p className="mt-0.5 text-xs text-muted">{outcomeCopy(outcome.outcome, outcome.resultCount)}</p>
                    {outcome.errorCode ? (
                      <p className="mono mt-1 text-[11px] text-faint">Code: {outcome.errorCode}</p>
                    ) : null}
                    {isPending ? <Skeleton className="mt-2 h-2 w-2/3" /> : null}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {!pending && (zero > 0 || failed > 0) ? (
        <p className="mt-3 rounded-lg border border-amber-200 bg-warn-soft px-2.5 py-2 text-xs text-warn">
          {zero > 0 ? `${zero} ${zero === 1 ? "gap has" : "gaps have"} no web results. ` : ""}
          {failed > 0 ? `${failed} ${failed === 1 ? "search failed" : "searches failed"}. ` : ""}
          You can continue; missing supplements are recorded in the profile rather than silently invented.
        </p>
      ) : null}
      {!pending && zero === 0 && failed === 0 && outcomes.length > 0 ? (
        <p className="mt-3 flex items-center gap-1.5 text-xs text-ok">
          <Search className="h-3.5 w-3.5" aria-hidden="true" />
          All targeted searches completed.
        </p>
      ) : null}
    </Card>
  );
}
