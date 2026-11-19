import { ApiError } from "@/api/client";

/** A `422 validation` response; the UI renders the message inline. */
export function isValidationError(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    (error.httpStatus === 422 || error.category === "validation")
  );
}

/** A `409 gate_violation` response; it needs a different user action, not a refresh. */
export function isGateViolation(error: unknown, messageKey?: string): boolean {
  if (!(error instanceof ApiError)) return false;
  if (messageKey) return error.messageKey === messageKey;
  return error.category === "gate_violation";
}

export function requestReference(error: unknown): string | undefined {
  if (!(error instanceof ApiError)) return undefined;
  return error.requestId || error.traceId || undefined;
}
