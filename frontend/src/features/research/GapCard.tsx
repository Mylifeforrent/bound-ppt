import { useEffect, useId, useState } from "react";
import { CheckCircle2, Globe2, Loader2, Sparkles } from "lucide-react";
import type { GapStateDTO } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/controls";
import { Badge, Card } from "@/components/ui/primitives";
import type { ErrorInfo } from "@/features/intake/errors";
import type { GapDecisionInput } from "./api";

export interface GapCardProps {
  gaps: GapStateDTO;
  /** Withdraws the controls after a decision (decisions are immutable in M1). */
  readOnly?: boolean;
  pending: boolean;
  error?: ErrorInfo | null;
  onConfirm: (input: GapDecisionInput) => void;
}

export function GapCard({ gaps, readOnly = false, pending, error, onConfirm }: GapCardProps) {
  const baseId = useId();
  const decision = gaps.decision;
  const locked = readOnly || Boolean(decision);
  const [selected, setSelected] = useState<Set<string>>(
    () =>
      new Set(
        decision?.selectedSuggestionIds ??
          gaps.suggestions.filter((suggestion) => suggestion.recommended).map((suggestion) => suggestion.id),
      ),
  );
  const [skipWeb, setSkipWeb] = useState(Boolean(decision?.webSkipped));
  const [initializedBatch, setInitializedBatch] = useState<number | null>(decision ? gaps.batch : null);

  useEffect(() => {
    if (decision) {
      setSelected(new Set(decision.selectedSuggestionIds));
      setSkipWeb(decision.webSkipped);
      setInitializedBatch(gaps.batch);
      return;
    }
    if (initializedBatch !== gaps.batch) {
      setSelected(new Set(gaps.suggestions.filter((suggestion) => suggestion.recommended).map((suggestion) => suggestion.id)));
      setSkipWeb(false);
      setInitializedBatch(gaps.batch);
    }
  }, [decision, gaps.batch, gaps.suggestions, initializedBatch]);

  const toggle = (id: string) => {
    if (locked || pending) return;
    setSelected((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
    setSkipWeb(false);
  };

  const chooseSkip = () => {
    if (locked || pending) return;
    setSelected(new Set());
    setSkipWeb(true);
  };

  const selectedSuggestionIds = gaps.suggestions
    .filter((suggestion) => selected.has(suggestion.id))
    .map((suggestion) => suggestion.id);

  if (gaps.suggestions.length === 0) return null;

  if (locked) {
    const chosen = gaps.suggestions.filter((suggestion) =>
      decision?.selectedSuggestionIds.includes(suggestion.id),
    );
    return (
      <Card className="p-4" data-gap-batch={gaps.batch}>
        <div className="flex items-start gap-3">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-ok-soft text-ok">
            <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-ink">Gap plan recorded</p>
            {decision?.webSkipped ? (
              <p className="mt-1 text-sm text-muted">
                No web supplements. The profile uses only your materials — “Not needed, just use my materials.”
              </p>
            ) : (
              <>
                <p className="mt-1 text-sm text-muted">
                  {chosen.length} targeted {chosen.length === 1 ? "search" : "searches"} selected for the profile.
                </p>
                <ul className="mt-1.5 space-y-1 text-sm text-ink-2">
                  {chosen.map((suggestion) => (
                    <li key={suggestion.id} className="flex items-start gap-1.5">
                      <Globe2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted" aria-hidden="true" />
                      <span>{suggestion.label}</span>
                    </li>
                  ))}
                </ul>
              </>
            )}
            <p className="mt-2 text-xs text-faint">
              Gap decisions are locked once recorded; changing them requires restarting research.
            </p>
          </div>
        </div>
      </Card>
    );
  }

  const noSelection = selectedSuggestionIds.length === 0 && !skipWeb;

  return (
    <Card className="border-brand/40 p-4" data-gap-batch={gaps.batch}>
      <div className="flex items-start gap-3">
        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-brand-soft text-brand-strong">
          <Sparkles className="h-4 w-4" aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-ink">Suggested content gaps</p>
            <Badge tone="brand">Agent suggestions</Badge>
          </div>
          <p className="mt-1 text-sm text-muted">
            Your materials come first. I can add these targeted web supplements where the deck would otherwise rely on
            assumptions. Recommended items are pre-checked.
          </p>

          <ul className="mt-3 space-y-2">
            {gaps.suggestions.map((suggestion) => {
              const checked = selected.has(suggestion.id) && !skipWeb;
              const labelId = `${baseId}-${suggestion.id}`;
              return (
                <li
                  key={suggestion.id}
                  className="flex items-start gap-2.5 rounded-xl border border-line bg-white px-3 py-2"
                >
                  <Checkbox
                    id={labelId}
                    checked={checked}
                    onCheckedChange={() => toggle(suggestion.id)}
                    disabled={pending}
                    aria-describedby={`${labelId}-reason`}
                    className="mt-0.5"
                  />
                  <label htmlFor={labelId} className="min-w-0 flex-1 cursor-pointer">
                    <span className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-medium text-ink">{suggestion.label}</span>
                      {suggestion.recommended ? <Badge tone="warn">Recommended</Badge> : null}
                    </span>
                    <span id={`${labelId}-reason`} className="mt-0.5 block text-xs text-muted">
                      {suggestion.reason}
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>

          <div className="mt-3 flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              variant={skipWeb ? "subtle" : "secondary"}
              aria-pressed={skipWeb}
              onClick={chooseSkip}
              disabled={pending}
            >
              Not needed — just use my materials
            </Button>
            <Button
              type="button"
              size="sm"
              onClick={() =>
                onConfirm(
                  skipWeb
                    ? { selectedSuggestionIds: [], webSkipped: true }
                    : { selectedSuggestionIds, webSkipped: false },
                )
              }
              disabled={pending || (noSelection && !skipWeb)}
            >
              {pending ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : null}
              {pending ? "Recording decision…" : "Confirm gaps"}
            </Button>
          </div>

          {skipWeb ? (
            <p className="mt-2 rounded-lg border border-line bg-surface-2 px-2.5 py-2 text-xs text-ink-2">
              Web search will be skipped. Confirm the decision to record “materials only”.
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="ml-2 h-6 px-2 text-xs"
                onClick={() => setSkipWeb(false)}
                disabled={pending}
              >
                Undo
              </Button>
            </p>
          ) : null}
          {noSelection ? <p className="mt-2 text-xs text-muted">Select at least one gap, or choose “Not needed”.</p> : null}

          {error ? (
            <div role="alert" className="mt-3 rounded-lg border border-red-200 bg-danger-soft px-2.5 py-2 text-xs text-danger">
              <p>{error.message}</p>
              {error.reference ? <p className="mono mt-1 text-[11px] text-danger/80">Reference: {error.reference}</p> : null}
            </div>
          ) : null}
        </div>
      </div>
    </Card>
  );
}
