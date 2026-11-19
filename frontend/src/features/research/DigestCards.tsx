import { AlertCircle, CheckCircle2, FileSearch, Loader2 } from "lucide-react";
import type { MaterialDigestDTO } from "@/api/types";
import { Badge, Card } from "@/components/ui/primitives";
import { Skeleton } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

function statusTone(status: MaterialDigestDTO["status"]): "ok" | "warn" | "danger" {
  return status === "READY" ? "ok" : status === "FAILED" ? "danger" : "warn";
}

function statusLabel(status: MaterialDigestDTO["status"]): string {
  return status === "READY" ? "Ready" : status === "FAILED" ? "Failed" : "Pending";
}

function lengthBucketLabel(bucket: string | null): string | null {
  if (!bucket) return null;
  return bucket.charAt(0).toUpperCase() + bucket.slice(1);
}

export function MaterialDigestCard({ item }: { item: MaterialDigestDTO }) {
  const pending = item.status === "PENDING";
  const failed = item.status === "FAILED";
  const bucket = lengthBucketLabel(item.lengthBucket);
  return (
    <Card
      className={cn("p-4", failed && "border-red-200 bg-danger-soft/40")}
      aria-busy={pending}
      data-material-digest={item.materialId}
    >
      <div className="flex items-start gap-3">
        <span
          className={cn(
            "grid h-8 w-8 shrink-0 place-items-center rounded-lg",
            failed ? "bg-white text-danger" : "bg-surface-2 text-brand-strong",
          )}
        >
          {pending ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          ) : failed ? (
            <AlertCircle className="h-4 w-4" aria-hidden="true" />
          ) : (
            <FileSearch className="h-4 w-4" aria-hidden="true" />
          )}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="min-w-0 truncate text-sm font-semibold text-ink" title={item.displayName}>
              {item.displayName}
            </p>
            <Badge tone={statusTone(item.status)}>{statusLabel(item.status)}</Badge>
          </div>
          {pending ? (
            <div className="mt-2 space-y-1.5">
              <p className="text-xs text-muted">Reading this material…</p>
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-3/4" />
            </div>
          ) : failed ? (
            <p className="mt-1 text-sm text-danger">
              This material could not be read and was not digested. Other materials continue normally. Restart the
              project if you need to replace it.
            </p>
          ) : (
            <>
              <p className="mt-1 text-xs text-muted">
                {item.extractedCharCount !== null
                  ? `${item.extractedCharCount.toLocaleString()} characters extracted`
                  : "Content extracted"}
                {bucket ? ` · ${bucket}` : ""}
              </p>
              {item.summaryPreview ? (
                <p className="mt-2 rounded-lg bg-surface-2 px-2.5 py-2 text-sm leading-relaxed text-ink-2">
                  {item.summaryPreview}
                </p>
              ) : null}
            </>
          )}
        </div>
      </div>
    </Card>
  );
}

export function DigestSummaryCard({ items }: { items: MaterialDigestDTO[] }) {
  const ready = items.filter((item) => item.status === "READY");
  if (ready.length === 0) return null;
  return (
    <Card className="border-green-200 bg-ok-soft/40 p-4">
      <div className="flex items-start gap-3">
        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-white text-ok">
          <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
        </span>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-ink">
            Material digestion complete · {ready.length} {ready.length === 1 ? "material" : "materials"} ready
          </p>
          <p className="mt-1 text-sm text-muted">
            I extracted the content below. Your materials take priority over web supplements when the two disagree.
          </p>
          <ul className="mt-2 space-y-1.5">
            {ready.map((item) => (
              <li key={item.materialId} className="text-sm text-ink-2">
                <span className="font-medium">{item.displayName}</span>
                {item.summaryPreview ? <span className="text-muted"> — {item.summaryPreview}</span> : null}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </Card>
  );
}
