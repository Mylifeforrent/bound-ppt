import type { QueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ApiError } from "@/api/client";
import { qk } from "@/api/keys";
import { errorText, messageFor } from "@/lib/messages";

export interface ErrorInfo {
  message: string;
  reference?: string;
}

/** Resolve a server `messageKey` (or a network/unknown failure) into display copy. */
export function errorInfo(error: unknown): ErrorInfo {
  if (error instanceof ApiError) {
    return {
      message: messageFor(error.messageKey),
      reference: error.requestId || error.traceId || undefined,
    };
  }
  return { message: errorText(error) };
}

export function isHttpConflict(error: unknown): boolean {
  return error instanceof ApiError && error.httpStatus === 409;
}

export function isConflictError(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    (error.category === "conflict" || error.messageKey.startsWith("error.conflict."))
  );
}

export function isGateViolation(error: unknown): boolean {
  return error instanceof ApiError && error.category === "gate_violation";
}

export interface ReportOptions {
  queryClient: QueryClient;
  projectId?: string;
  /**
   * `409` always refreshes the snapshot. The toast is non-destructive: local
   * drafts and selections stay on screen so the user never loses input.
   */
  toastOnConflict?: boolean;
}

export function reportCommandError(error: unknown, options: ReportOptions): ErrorInfo {
  const info = errorInfo(error);
  const conflict = isHttpConflict(error);
  if (conflict && options.projectId) {
    void options.queryClient.invalidateQueries({ queryKey: qk.snapshot(options.projectId) });
  }
  if (conflict && options.toastOnConflict !== false) {
    toast.error(info.message, info.reference ? { description: `Reference: ${info.reference}` } : undefined);
  }
  return info;
}

export function toastCommandError(error: unknown, options: ReportOptions): ErrorInfo {
  const info = reportCommandError(error, { ...options, toastOnConflict: false });
  toast.error(info.message, info.reference ? { description: `Reference: ${info.reference}` } : undefined);
  return info;
}
