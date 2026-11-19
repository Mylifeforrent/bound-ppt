import { useCallback, useEffect, useRef, useState } from "react";

export type CountdownStatus = "idle" | "running" | "paused" | "done";

export interface UseCountdownOptions {
  /** Total countdown length. Defaults to 3000 ms (outline auto-advance). */
  durationMs?: number;
  /** When false the countdown stops and resets to idle. */
  enabled: boolean;
  /** Called once when the countdown reaches zero and canComplete returns true. */
  onComplete: () => void;
  /**
   * Evaluated at zero. Returning false pauses the countdown instead of
   * completing (used to avoid navigating while focus is in an editable field).
   */
  canComplete?: () => boolean;
}

export interface CountdownControls {
  status: CountdownStatus;
  remainingMs: number;
  remainingSeconds: number;
  pauseReason: string | null;
  pause: (reason?: string) => void;
  resume: () => void;
  restart: () => void;
  cancel: () => void;
}

/**
 * A visible, pausable countdown owned by the client.
 *
 * The remaining time is derived from `performance.now()` against a deadline,
 * so background-tab throttling cannot extend or skip the countdown. Pausing
 * with the tab hidden is sticky: returning to the tab does not auto-resume.
 */
export function useCountdown({
  durationMs = 3000,
  enabled,
  onComplete,
  canComplete,
}: UseCountdownOptions): CountdownControls {
  const [status, setStatus] = useState<CountdownStatus>("idle");
  const [remainingMs, setRemainingMs] = useState(durationMs);
  const [pauseReason, setPauseReason] = useState<string | null>(null);

  const deadlineRef = useRef<number | null>(null);
  const remainingRef = useRef(durationMs);
  const completedRef = useRef(false);
  const enabledRef = useRef(enabled);
  const statusRef = useRef<CountdownStatus>("idle");
  const startedRef = useRef(false);
  const onCompleteRef = useRef(onComplete);
  const canCompleteRef = useRef(canComplete);

  enabledRef.current = enabled;
  statusRef.current = status;
  onCompleteRef.current = onComplete;
  canCompleteRef.current = canComplete;

  const finish = useCallback(() => {
    deadlineRef.current = null;
    remainingRef.current = 0;
    setRemainingMs(0);
    if (completedRef.current) return;
    if (canCompleteRef.current && !canCompleteRef.current()) {
      setStatus("paused");
      setPauseReason("focus");
      return;
    }
    completedRef.current = true;
    setStatus("done");
    setPauseReason(null);
    onCompleteRef.current();
  }, []);

  const tick = useCallback(() => {
    const deadline = deadlineRef.current;
    if (deadline === null) return;
    const remaining = deadline - performance.now();
    if (remaining <= 0) {
      finish();
      return;
    }
    remainingRef.current = remaining;
    setRemainingMs(remaining);
  }, [finish]);

  const startFrom = useCallback((ms: number) => {
    if (document.visibilityState === "hidden") {
      deadlineRef.current = null;
      remainingRef.current = ms;
      completedRef.current = false;
      setRemainingMs(ms);
      setPauseReason("hidden");
      setStatus("paused");
      return;
    }
    deadlineRef.current = performance.now() + ms;
    remainingRef.current = ms;
    completedRef.current = false;
    setRemainingMs(ms);
    setPauseReason(null);
    setStatus("running");
  }, []);

  useEffect(() => {
    if (!enabled) {
      deadlineRef.current = null;
      remainingRef.current = durationMs;
      completedRef.current = false;
      startedRef.current = false;
      setStatus("idle");
      setRemainingMs(durationMs);
      setPauseReason(null);
      return;
    }
    if (!startedRef.current) {
      startedRef.current = true;
      startFrom(durationMs);
    }
  }, [enabled, durationMs, startFrom]);

  useEffect(() => {
    if (status !== "running") return;
    const timer = window.setInterval(tick, 100);
    return () => window.clearInterval(timer);
  }, [status, tick]);

  const pause = useCallback((reason = "user") => {
    const deadline = deadlineRef.current;
    if (deadline !== null) {
      remainingRef.current = Math.max(0, deadline - performance.now());
      setRemainingMs(remainingRef.current);
    }
    deadlineRef.current = null;
    if (statusRef.current === "done") return;
    setPauseReason(reason);
    setStatus("paused");
  }, []);

  const resume = useCallback(() => {
    if (!enabledRef.current || statusRef.current === "done") return;
    deadlineRef.current = performance.now() + Math.max(0, remainingRef.current);
    completedRef.current = false;
    setPauseReason(null);
    setStatus("running");
  }, []);

  const restart = useCallback(() => {
    if (!enabledRef.current) return;
    startFrom(durationMs);
  }, [durationMs, startFrom]);

  const cancel = useCallback(() => {
    deadlineRef.current = null;
    remainingRef.current = durationMs;
    completedRef.current = false;
    startedRef.current = false;
    setStatus("idle");
    setRemainingMs(durationMs);
    setPauseReason(null);
  }, [durationMs]);

  useEffect(() => {
    const onVisibilityChange = () => {
      if (document.visibilityState === "hidden" && statusRef.current === "running") {
        pause("hidden");
      }
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => document.removeEventListener("visibilitychange", onVisibilityChange);
  }, [pause]);

  return {
    status,
    remainingMs,
    remainingSeconds: Math.max(0, Math.ceil(remainingMs / 1000)),
    pauseReason,
    pause,
    resume,
    restart,
    cancel,
  };
}

/** True when focus is inside a text field or editable region. */
export function isEditableFocus(): boolean {
  const element = document.activeElement;
  if (!(element instanceof HTMLElement)) return false;
  if (element.isContentEditable) return true;
  const tag = element.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  return element.getAttribute("role") === "textbox";
}
