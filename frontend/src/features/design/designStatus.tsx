import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  Loader2,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

export type StatusTone = "neutral" | "brand" | "ok" | "warn" | "danger";

export interface DesignStatusInfo {
  label: string;
  /** Screen-reader friendly description used in canvas/thumbnail labels. */
  description: string;
  tone: StatusTone;
  Icon: LucideIcon;
  spin: boolean;
}

const STATUS: Record<string, DesignStatusInfo> = {
  PENDING: {
    label: "Pending",
    description: "not designed yet",
    tone: "neutral",
    Icon: CircleDashed,
    spin: false,
  },
  DESIGNING: {
    label: "Generating",
    description: "generating",
    tone: "brand",
    Icon: Loader2,
    spin: true,
  },
  DONE: {
    label: "Done",
    description: "designed",
    tone: "ok",
    Icon: CheckCircle2,
    spin: false,
  },
  STALE: {
    label: "Needs rerun",
    description: "needs rerun",
    tone: "warn",
    Icon: AlertTriangle,
    spin: false,
  },
  ERROR: {
    label: "Error",
    description: "design failed",
    tone: "danger",
    Icon: XCircle,
    spin: false,
  },
};

function titleCase(value: string): string {
  return value
    .toLowerCase()
    .split(/[\s_-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function designStatusInfo(status: string | null | undefined): DesignStatusInfo {
  if (!status) {
    return {
      label: "Unknown",
      description: "status unavailable",
      tone: "neutral",
      Icon: CircleDashed,
      spin: false,
    };
  }
  return (
    STATUS[status] ?? {
      label: titleCase(status) || status,
      description: titleCase(status) || "status unavailable",
      tone: "neutral",
      Icon: CircleDashed,
      spin: false,
    }
  );
}

export function StatusIcon({
  status,
  className,
}: {
  status: string | null | undefined;
  className?: string;
}) {
  const info = designStatusInfo(status);
  return (
    <info.Icon
      aria-hidden="true"
      className={cn("h-3.5 w-3.5 shrink-0", info.spin && "animate-spin", className)}
    />
  );
}

export function pageTypeLabel(pageType: string | null | undefined): string {
  switch (pageType) {
    case "COVER":
      return "Cover";
    case "TOC":
      return "Contents";
    case "END":
      return "Closing";
    case "BODY":
      return "Body";
    default:
      return pageType ? titleCase(pageType) : "Page";
  }
}

export function historyReasonLabel(reason: string | null | undefined): string {
  switch (reason) {
    case "REGENERATE":
      return "Regenerated";
    case "TWEAK":
      return "Tweaked";
    case "REPLAN":
      return "Re-planned";
    case "STYLE_CHANGE":
      return "Style change";
    case "MANUAL":
      return "Manual edit";
    default:
      return reason ? titleCase(reason) : "Earlier version";
  }
}

export function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function formatPercent(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, Math.round(value)));
}
