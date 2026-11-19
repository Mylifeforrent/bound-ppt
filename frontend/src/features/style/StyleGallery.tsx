import { useCallback, useRef, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, CheckCircle2, Loader2, Lock, Palette, Save } from "lucide-react";
import type { ProjectSnapshotDTO, StyleDTO } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/primitives";
import { Checkbox } from "@/components/ui/controls";
import { EmptyState, ErrorCard, Skeleton } from "@/components/ui/dialog";
import { errorText } from "@/lib/messages";
import { cn } from "@/lib/utils";
import { StyleCard } from "./StyleCard";
import { useStyleSelection } from "./useStyleSelection";

export function StyleGallery({
  projectId,
  snapshot,
}: {
  projectId: string;
  snapshot: ProjectSnapshotDTO;
}) {
  const state = useStyleSelection({ projectId, snapshot });
  const groupRef = useRef<HTMLDivElement>(null);

  const focusCard = useCallback((index: number) => {
    window.requestAnimationFrame(() => {
      const element = groupRef.current?.querySelector<HTMLElement>(
        `[data-style-index="${index}"]`,
      );
      element?.focus();
    });
  }, []);

  const handleCardKeyDown = useCallback(
    (event: KeyboardEvent<HTMLDivElement>, index: number) => {
      if (state.styles.length === 0) return;
      const key = event.key;
      let next = index;
      if (key === "ArrowRight" || key === "ArrowDown") {
        next = (index + 1) % state.styles.length;
      } else if (key === "ArrowLeft" || key === "ArrowUp") {
        next = (index - 1 + state.styles.length) % state.styles.length;
      } else if (key === "Home") {
        next = 0;
      } else if (key === "End") {
        next = state.styles.length - 1;
      } else if (key === " " || key === "Enter") {
        event.preventDefault();
        state.selectStyle(state.styles[index]);
        return;
      } else {
        return;
      }
      event.preventDefault();
      state.selectStyle(state.styles[next]);
      focusCard(next);
    },
    [focusCard, state],
  );

  if (state.stylesQuery.isLoading) {
    return <StyleGallerySkeleton />;
  }

  if (state.stylesQuery.isError) {
    return (
      <ErrorCard
        message={errorText(state.stylesQuery.error) || "The style catalog could not be loaded."}
        reference={
          state.stylesQuery.error &&
          typeof state.stylesQuery.error === "object" &&
          "requestId" in state.stylesQuery.error
            ? (state.stylesQuery.error as { requestId?: string }).requestId
            : undefined
        }
        onRetry={() => void state.stylesQuery.refetch()}
      />
    );
  }

  if (state.styles.length === 0) {
    return (
      <EmptyState
        title="No styles are available"
        description="The style catalog is empty. Retry loading it; the server catalog is the only source of style tokens."
        action={
          <Button variant="secondary" size="sm" onClick={() => void state.stylesQuery.refetch()}>
            Retry style catalog
          </Button>
        }
      />
    );
  }

  const selectedExists = state.styles.some((style) => style.styleKey === state.selectedKey);
  const busy = state.saving || state.confirming;

  return (
    <div className="min-w-0">
      <div className="sr-only" role="status" aria-live="polite">
        {state.confirming
          ? "Confirming the style and opening the design draft."
          : state.saving
            ? "Saving the style selection."
            : state.confirmed
              ? "Style confirmed."
              : ""}
      </div>

      <section aria-labelledby="style-gallery-title" className="app-card p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 id="style-gallery-title" className="text-lg font-semibold text-ink">
              Choose the deck style
            </h2>
            <p className="mt-1 max-w-2xl text-sm text-muted">
              Every card is a real page rendered from the style's tokens. Select one, optionally
              remember it for this project, then confirm to open the design draft.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            {state.lastUsed ? (
              <Badge tone={state.lastUsed.confirmed ? "ok" : "brand"}>
                <Palette className="h-3 w-3" aria-hidden="true" />
                Last used: {state.lastUsedStyle?.name ?? state.lastUsed.styleKey}
                {state.lastUsed.confirmed ? " · confirmed" : ""}
              </Badge>
            ) : (
              <Badge tone="neutral">No style recorded yet</Badge>
            )}
            {state.selectedStyle ? (
              <Badge tone="brand">Selected: {state.selectedStyle.name}</Badge>
            ) : null}
          </div>
        </div>

        {state.blockers.length > 0 ? (
          <div
            role="alert"
            className="mt-3 rounded-xl border border-amber-200 bg-warn-soft p-3"
          >
            <p className="flex items-center gap-2 text-sm font-semibold text-ink">
              <Lock className="h-4 w-4 shrink-0 text-warn" aria-hidden="true" />
              Style selection is blocked
            </p>
            <ul className="mt-1.5 space-y-1.5">
              {state.blockers.map((blocker) => (
                <li key={`${blocker.code}-${blocker.message}`} className="text-xs text-muted">
                  {blocker.message}
                  {blocker.href && blocker.action ? (
                    <>
                      {" "}
                      <Link to={blocker.href} className="font-semibold text-warn underline">
                        {blocker.action}
                      </Link>
                    </>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <div
          ref={groupRef}
          role="radiogroup"
          aria-label="Deck style"
          aria-busy={state.saving || state.confirming}
          aria-describedby="style-gallery-hint"
          className="mt-4 grid grid-cols-1 gap-3 min-[921px]:grid-cols-2 min-[1180px]:grid-cols-4"
        >
          {state.styles.map((style, index) => (
            <StyleCard
              key={style.styleKey}
              style={style}
              index={index}
              selected={state.selectedKey === style.styleKey}
              lastUsed={state.lastUsed?.styleKey === style.styleKey}
              confirmed={state.lastUsed?.styleKey === style.styleKey && state.lastUsed.confirmed}
              focusable={
                state.selectedKey === style.styleKey || (!selectedExists && index === 0)
              }
              disabled={state.confirming}
              onSelect={state.selectStyle}
              onKeyDown={handleCardKeyDown}
            />
          ))}
        </div>
        <p id="style-gallery-hint" className="mt-2 text-[11px] text-muted">
          Arrow keys move and select. Space or Enter selects the focused card. The selection is saved
          on the server before design generation starts.
        </p>

        {state.selectionError ? (
          <div
            role="alert"
            className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-red-200 bg-danger-soft px-3 py-2 text-xs text-danger"
          >
            <span>{state.selectionError}</span>
            {state.selectedStyle ? (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => state.selectStyle(state.selectedStyle as StyleDTO)}
                disabled={busy}
              >
                <Save className="h-3.5 w-3.5" aria-hidden="true" />
                Retry saving selection
              </Button>
            ) : null}
          </div>
        ) : null}

        <div className="mt-4 flex flex-col gap-3 border-t border-line pt-4 sm:flex-row sm:items-start sm:justify-between">
          <label
            htmlFor="style-remember-preference"
            className="flex max-w-xl cursor-pointer items-start gap-2.5"
          >
            <Checkbox
              id="style-remember-preference"
              checked={state.remember}
              onCheckedChange={(checked) => state.toggleRemember(checked === true)}
              disabled={busy}
              aria-describedby="style-remember-hint"
            />
            <span>
              <span className="block text-sm font-medium text-ink">Remember my preference</span>
              <span id="style-remember-hint" className="mt-0.5 block text-[11px] leading-snug text-muted">
                Stored on this project's style selection. Selecting the style again restores it
                after a refresh.
              </span>
            </span>
          </label>
          <div className="flex flex-wrap items-center gap-2">
            {state.saving ? (
              <span className="flex items-center gap-1.5 text-xs font-medium text-brand-strong">
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                Saving selection…
              </span>
            ) : state.selectedKey && state.savedKey === state.selectedKey ? (
              <span className="flex items-center gap-1.5 text-xs font-medium text-ok">
                <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                Selection saved
              </span>
            ) : null}
            {state.confirmed ? (
              <Button
                onClick={state.openDesign}
                disabled={state.confirming || state.planIncomplete || state.blockers.length > 0}
              >
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
                Open design draft
              </Button>
            ) : (
              <Button
                onClick={state.confirm}
                disabled={!state.canConfirm}
                aria-describedby="style-confirm-hint"
              >
                {state.confirming ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <ArrowRight className="h-4 w-4" aria-hidden="true" />
                )}
                Confirm style and open design draft
              </Button>
            )}
          </div>
        </div>
        <p id="style-confirm-hint" className="mt-2 text-[11px] leading-snug text-muted">
          {state.confirmed
            ? "This style is confirmed for the project. Selecting another style records a new, unconfirmed choice."
            : !state.selectedStyle
              ? "Confirm is disabled until a style is selected."
              : state.planIncomplete
                ? "The plan draft must be complete before a style can be confirmed."
                : state.blockers.length > 0
                  ? "Resolve the blocker above before confirming the style."
                  : "Confirming unlocks design generation. Confirming again is required after a style change."}
        </p>

        {state.confirmError ? (
          <div
            role="alert"
            className="mt-3 rounded-xl border border-red-200 bg-danger-soft px-3 py-2 text-xs text-danger"
          >
            <p className="font-semibold">The style could not be confirmed.</p>
            <p className="mt-0.5 leading-snug">{state.confirmError}</p>
          </div>
        ) : null}

        {state.hasExistingDesign ? (
          <p className="mt-3 rounded-xl border border-amber-200 bg-warn-soft px-3 py-2 text-[11px] leading-snug text-warn">
            Design pages already exist for this project. Changing the style marks all design pages as
            needing rerun on the server; the outline and plan draft stay unchanged.
          </p>
        ) : null}
      </section>
    </div>
  );
}

function StyleGallerySkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading style catalog">
      <div className="app-card p-5">
        <Skeleton className="h-5 w-52" />
        <Skeleton className="mt-2 h-3 w-2/3" />
        <div className="mt-4 grid grid-cols-1 gap-3 min-[921px]:grid-cols-2 min-[1180px]:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className={cn("rounded-2xl border border-line p-3")}>
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="mt-2 aspect-video w-full" />
              <Skeleton className="mt-2.5 h-3 w-full" />
              <Skeleton className="mt-1.5 h-3 w-4/5" />
              <div className="mt-3 flex gap-1.5 border-t border-line pt-2.5">
                {Array.from({ length: 6 }).map((__, swatch) => (
                  <Skeleton key={swatch} className="h-5 w-5 rounded-full" />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
