import {
  AlertCircle,
  Clipboard,
  FileText,
  Link2,
  RotateCw,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/primitives";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/controls";
import { formatBytes } from "@/lib/utils";
import { messageFor } from "@/lib/messages";
import type { IntakeEntry } from "./types";
import { entryStatusLabel } from "./useMaterialIntake";

const KIND_LABEL: Record<IntakeEntry["kind"], string> = {
  PASTE: "Pasted text",
  FILE: "File",
  URL: "Web link",
};

function entryTypeLabel(entry: IntakeEntry): string {
  if (entry.kind === "FILE") {
    const extension = entry.displayName.includes(".")
      ? entry.displayName.slice(entry.displayName.lastIndexOf(".") + 1).toUpperCase()
      : "File";
    return `${KIND_LABEL.FILE} · ${extension}`;
  }
  if (entry.kind === "URL") {
    return entry.domain ? `${KIND_LABEL.URL} · ${entry.domain}` : KIND_LABEL.URL;
  }
  return KIND_LABEL.PASTE;
}

function KindIcon({ kind }: { kind: IntakeEntry["kind"] }) {
  const Icon = kind === "FILE" ? FileText : kind === "URL" ? Link2 : Clipboard;
  return <Icon className="h-4 w-4" aria-hidden="true" />;
}

function statusTone(status: IntakeEntry["status"]): "neutral" | "brand" | "ok" | "warn" | "danger" {
  switch (status) {
    case "DIGESTED":
      return "ok";
    case "FAILED":
      return "danger";
    case "UPLOADING":
    case "PENDING":
    case "INGESTING":
      return "warn";
    case "DRAFT":
      return "neutral";
    default:
      return "neutral";
  }
}

export interface MaterialChipsProps {
  entries: IntakeEntry[];
  onRemove: (key: string) => void;
  onRetry: (key: string) => void;
  retryEnabled?: boolean;
  readOnly?: boolean;
  disabled?: boolean;
  emptyText?: string;
}

export function MaterialChips({
  entries,
  onRemove,
  onRetry,
  retryEnabled = true,
  readOnly = false,
  disabled = false,
  emptyText = "No materials added yet. The agent will research the web only.",
}: MaterialChipsProps) {
  if (entries.length === 0) {
    return (
      <p className="rounded-xl border border-dashed border-line-strong bg-surface-2 px-3 py-3 text-sm text-muted">
        {emptyText}
      </p>
    );
  }

  return (
    <ul className="space-y-2" aria-label="Materials">
      {entries.map((entry) => {
        const failed = entry.status === "FAILED";
        const showProgress = entry.status === "UPLOADING";
        // A local entry that is mid-submit has no server id yet; removing it
        // here would leave an orphaned server row, so wait for the response.
        const midSubmit =
          !entry.fromServer &&
          !entry.materialId &&
          (entry.status === "UPLOADING" || entry.status === "PENDING");
        const controlsDisabled = disabled || entry.removing || midSubmit;
        return (
          <li
            key={entry.key}
            className="rounded-xl border border-line bg-white p-3 shadow-[var(--sh-1)]"
            data-material-key={entry.key}
          >
            <div className="flex items-start gap-2.5">
              <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-surface-2 text-muted">
                <KindIcon kind={entry.kind} />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="min-w-0 truncate text-sm font-semibold text-ink" title={entry.displayName}>
                    {entry.displayName}
                  </p>
                  <Badge tone={statusTone(entry.status)}>{entryStatusLabel(entry)}</Badge>
                </div>
                <p className="mt-0.5 text-xs text-muted">
                  {entryTypeLabel(entry)}
                  {entry.sizeBytes !== null ? ` · ${formatBytes(entry.sizeBytes)}` : ""}
                  {entry.fromServer ? " · Saved" : ""}
                </p>
                {showProgress ? (
                  <div className="mt-2">
                    <Progress
                      value={entry.progress ?? 0}
                      label={`Uploading ${entry.displayName}`}
                    />
                    <p className="mt-1 text-[11px] text-muted">
                      {entry.progress === null ? "Uploading…" : `${entry.progress}% uploaded`}
                    </p>
                  </div>
                ) : null}
                {entry.error ? (
                  <div className="mt-2 rounded-lg border border-red-200 bg-danger-soft px-2.5 py-2 text-xs text-danger">
                    <p className="flex items-start gap-1.5">
                      <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                      <span>{messageFor(entry.error.messageKey)}</span>
                    </p>
                    {entry.error.requestId ? (
                      <p className="mono mt-1 text-[11px] text-danger/80">Reference: {entry.error.requestId}</p>
                    ) : null}
                  </div>
                ) : null}
              </div>
              <div className="flex shrink-0 items-center gap-1">
                {failed && retryEnabled && entry.retryable && !entry.fromServer ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => onRetry(entry.key)}
                    disabled={controlsDisabled}
                    aria-label={`Retry ${entry.displayName}`}
                  >
                    <RotateCw className="h-3.5 w-3.5" aria-hidden="true" />
                    Retry
                  </Button>
                ) : null}
                {!readOnly ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => onRemove(entry.key)}
                    disabled={controlsDisabled}
                    aria-label={`Remove ${entry.displayName}`}
                    title={
                      midSubmit
                        ? "Wait for this material to finish adding before removing it"
                        : `Remove ${entry.displayName}`
                    }
                  >
                    <X className="h-4 w-4" aria-hidden="true" />
                  </Button>
                ) : null}
              </div>
            </div>
            {entry.removing ? <p className="mt-2 text-xs text-muted">Removing…</p> : null}
          </li>
        );
      })}
    </ul>
  );
}
