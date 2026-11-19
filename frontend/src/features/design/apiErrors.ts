import { ApiError } from "@/api/client";
import { errorText } from "@/lib/messages";

/**
 * `error.conflict.*` is a retryable stale-version style conflict. A `409`
 * gate violation (`error.gate.*`) is deliberately not a conflict: it needs a
 * different user action, not a refresh-and-retry.
 */
export function isApiConflict(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    (error.category === "conflict" ||
      (error.httpStatus === 409 && error.messageKey.startsWith("error.conflict.")))
  );
}

export function isApiNotFound(error: unknown): boolean {
  return error instanceof ApiError && (error.httpStatus === 404 || error.category === "not_found");
}

export function isApiValidation(error: unknown): boolean {
  return error instanceof ApiError && (error.httpStatus === 422 || error.category === "validation");
}

export function isGateViolation(error: unknown, messageKey?: string): boolean {
  if (!(error instanceof ApiError)) return false;
  if (messageKey) return error.messageKey === messageKey;
  return error.category === "gate_violation";
}

export function commandErrorText(error: unknown): string {
  return errorText(error);
}
