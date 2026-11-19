import { useState, type RefObject } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { qk } from "@/api/keys";
import type { NoticeDTO } from "@/api/types";
import { Button } from "@/components/ui/button";
import { ErrorCard, Skeleton } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/primitives";
import { cn, uuid } from "@/lib/utils";
import { errorInfo, type ErrorInfo } from "./errors";
import { acceptPolicyNotice } from "./policy";
import { noticeGate } from "./validation";

export interface DataNoticeProps {
  notices: NoticeDTO[] | undefined;
  loading: boolean;
  error: unknown;
  onRetry: () => void;
  containerRef?: RefObject<HTMLDivElement | null>;
  compact?: boolean;
  disabled?: boolean;
}

/**
 * Consent gate for the data-handling notice. Materials cannot be added until
 * every required notice is accepted; the web-only start path does not need it.
 */
export function DataNotice({
  notices,
  loading,
  error,
  onRetry,
  containerRef,
  compact = false,
  disabled = false,
}: DataNoticeProps) {
  const queryClient = useQueryClient();
  const [accepting, setAccepting] = useState(false);
  const [acceptError, setAcceptError] = useState<ErrorInfo | null>(null);

  const gate = noticeGate(notices);
  if (!loading && !error && gate.required.length === 0) return null;

  const accept = async () => {
    if (gate.unaccepted.length === 0) return;
    setAccepting(true);
    setAcceptError(null);
    try {
      let acceptedAt = new Date().toISOString();
      for (const notice of gate.unaccepted) {
        const result = await acceptPolicyNotice(notice, uuid());
        acceptedAt = result.acceptedAt;
      }
      const acceptedKeys = new Set(gate.unaccepted.map((notice) => `${notice.type}@${notice.version}`));
      queryClient.setQueryData<NoticeDTO[]>(qk.notices, (previous) =>
        previous?.map((notice) =>
          acceptedKeys.has(`${notice.type}@${notice.version}`) && !notice.acceptedAt
            ? { ...notice, acceptedAt }
            : notice,
        ),
      );
      await queryClient.invalidateQueries({ queryKey: qk.notices });
    } catch (err) {
      setAcceptError(errorInfo(err));
    } finally {
      setAccepting(false);
    }
  };

  if (loading) {
    return (
      <div ref={containerRef} tabIndex={-1} className="outline-none">
        <div className="rounded-2xl border border-line bg-white p-4" aria-busy="true">
          <p className="sr-only">Loading the data-handling notice</p>
          <Skeleton className="h-4 w-48" />
          <Skeleton className="mt-3 h-3 w-full" />
          <Skeleton className="mt-2 h-3 w-4/5" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div ref={containerRef} tabIndex={-1} className="outline-none">
        <ErrorCard
          message="The data-handling notice could not be loaded. Materials stay disabled until it is available."
          reference={errorInfo(error).reference}
          onRetry={onRetry}
        />
      </div>
    );
  }

  if (gate.unaccepted.length === 0) {
    return (
      <div
        ref={containerRef}
        tabIndex={-1}
        className="flex items-center gap-2 rounded-xl border border-line bg-surface-2 px-3 py-2 text-xs text-muted outline-none"
      >
        <ShieldCheck className="h-4 w-4 shrink-0 text-ok" aria-hidden="true" />
        <span>
          Data notice accepted
          {gate.required[0]?.version ? ` (version ${gate.required[0].version})` : ""}. Materials are used only for
          this deck.
        </span>
      </div>
    );
  }

  return (
    <div ref={containerRef} tabIndex={-1} className="outline-none">
      <section
        aria-labelledby="data-notice-title"
        className={cn(
          "rounded-2xl border border-amber-200 bg-warn-soft/70 p-4",
          compact ? "text-sm" : "p-5",
        )}
      >
        <div className="flex items-start gap-3">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-white text-warn shadow-sm">
            <ShieldCheck className="h-5 w-5" aria-hidden="true" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 id="data-notice-title" className="text-sm font-semibold text-ink">
                Before you add materials
              </h2>
              <Badge tone="warn">Required</Badge>
            </div>
            <div className="mt-2 space-y-3">
              {gate.unaccepted.map((notice) => (
                <div key={`${notice.type}@${notice.version}`}>
                  <p className="text-sm font-medium text-ink">{notice.title}</p>
                  <p className="mt-1 whitespace-pre-line text-sm leading-relaxed text-muted">{notice.body}</p>
                </div>
              ))}
            </div>
            {acceptError ? (
              <p role="alert" className="mt-3 rounded-lg border border-red-200 bg-danger-soft px-3 py-2 text-sm text-danger">
                {acceptError.message}
                {acceptError.reference ? (
                  <span className="mono mt-1 block text-xs">Reference: {acceptError.reference}</span>
                ) : null}
              </p>
            ) : null}
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Button type="button" size="sm" onClick={() => void accept()} disabled={accepting || disabled}>
                {accepting ? "Recording acceptance…" : "Accept data notice"}
              </Button>
              <p className="text-xs text-muted">
                Required only for materials. A web-only project can start without adding any.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
