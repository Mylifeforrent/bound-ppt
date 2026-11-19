import { AlertTriangle, Loader2, RefreshCw } from "lucide-react";
import type { ProfileDTO } from "@/api/types";
import { Badge, Card } from "@/components/ui/primitives";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

function materialsStrategy(profile: ProfileDTO): string {
  const summary = profile.materialsSummary;
  if (summary.strategy === "material_first") {
    return `${summary.materialCount} first-party ${
      summary.materialCount === 1 ? "material" : "materials"
    } lead the content. Web supplements fill only the confirmed gaps.`;
  }
  return "No first-party materials. The deck is built from web research.";
}

function webScope(profile: ProfileDTO): string {
  const scope = profile.webScope;
  if (scope.webSkipped) return "No web supplements — materials only.";
  if (profile.materialsSummary.strategy === "web_only") {
    return `Default web research · ${scope.sourceCount} ${scope.sourceCount === 1 ? "source" : "sources"}.`;
  }
  return `${scope.selectedGapSuggestionIds.length} targeted ${
    scope.selectedGapSuggestionIds.length === 1 ? "gap" : "gaps"
  } searched · ${scope.sourceCount} ${scope.sourceCount === 1 ? "source" : "sources"}.`;
}

function ProfileRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-0.5 sm:grid-cols-[140px_minmax(0,1fr)] sm:gap-3">
      <dt className="text-xs font-semibold uppercase tracking-[0.08em] text-muted">{label}</dt>
      <dd className="text-sm text-ink-2">{children}</dd>
    </div>
  );
}

export interface ProfileCardProps {
  profile: ProfileDTO;
  dirty: boolean;
  pending: boolean;
  error?: { message: string; reference?: string } | null;
  onUpdate: () => void;
}

export function ProfileCard({ profile, dirty, pending, error, onUpdate }: ProfileCardProps) {
  return (
    <Card className={cn("p-4", dirty && "border-amber-300")}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold text-ink">Requirements profile</h2>
            <Badge tone="brand">v{profile.version}</Badge>
            {dirty ? <Badge tone="warn">Needs update</Badge> : <Badge tone="ok">Aligned</Badge>}
          </div>
          <p className="mt-1 text-sm text-muted">
            Generated from your four answers, materials, and gap decisions. This profile constrains the outline.
          </p>
        </div>
        {dirty ? (
          <Button type="button" size="sm" onClick={onUpdate} disabled={pending}>
            {pending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
            )}
            {pending ? "Updating…" : "Update profile"}
          </Button>
        ) : null}
      </div>

      {dirty ? (
        <p className="mt-3 flex items-start gap-1.5 rounded-lg border border-amber-200 bg-warn-soft px-2.5 py-2 text-xs text-warn">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          Answers changed after this profile was generated. Outline generation is blocked until the profile is updated.
        </p>
      ) : null}

      <dl className="mt-4 space-y-3">
        <ProfileRow label="Audience">{profile.audience}</ProfileRow>
        <ProfileRow label="Goal">{profile.goal}</ProfileRow>
        <ProfileRow label="Page count">{profile.pageCount} pages</ProfileRow>
        <ProfileRow label="Style / mood">{profile.styleMood}</ProfileRow>
        <ProfileRow label="Materials">{materialsStrategy(profile)}</ProfileRow>
        <ProfileRow label="Web scope">{webScope(profile)}</ProfileRow>
        <ProfileRow label="Content strategy">{profile.contentStrategy}</ProfileRow>
      </dl>

      {profile.materialsSummary.strategy === "material_first" ? (
        <p className="mt-3 rounded-lg bg-surface-2 px-2.5 py-2 text-xs text-muted">
          Source priority: your materials, then organization assets, then web supplements. Conflicting web facts never
          override first-party material.
        </p>
      ) : null}

      {error ? (
        <div role="alert" className="mt-3 rounded-lg border border-red-200 bg-danger-soft px-2.5 py-2 text-xs text-danger">
          <p>{error.message}</p>
          {error.reference ? <p className="mono mt-1 text-[11px] text-danger/80">Reference: {error.reference}</p> : null}
        </div>
      ) : null}
    </Card>
  );
}
