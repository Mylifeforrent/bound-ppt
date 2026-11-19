import { Link } from "react-router-dom";
import { ArrowRight, Lock } from "lucide-react";
import type { DesignBlocker } from "./useDesignWorkbench";

export function DesignBlockerCard({ blockers }: { blockers: DesignBlocker[] }) {
  return (
    <section aria-label="Design draft blockers" className="app-card p-6">
      <div className="flex items-start gap-3">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-warn-soft text-warn">
          <Lock className="h-5 w-5" aria-hidden="true" />
        </span>
        <div>
          <h2 className="text-lg font-semibold text-ink">Design is not ready yet</h2>
          <p className="mt-1 max-w-2xl text-sm text-muted">
            The agent only generates design pages after the plan draft is complete and a style is
            confirmed. Finish the steps below, then return to this stage.
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
            The design stage is not reachable yet. Refresh the project state and retry.
          </li>
        ) : null}
      </ul>
    </section>
  );
}
