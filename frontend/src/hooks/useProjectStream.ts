import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { qk } from "@/api/keys";
import type { DomainEventEnvelope, OutlineDeltaPayload, ProjectSnapshotDTO } from "@/api/types";
import { useStreamStore } from "@/stores/view";

interface Options {
  projectId: string | undefined;
  initialCursor: number | undefined;
  enabled?: boolean;
}

const EPHEMERAL_DEDUPE = 200;

export function useProjectStream({ projectId, initialCursor, enabled = true }: Options) {
  const queryClient = useQueryClient();
  const setStatus = useStreamStore((s) => s.setStatus);
  const applyOutlineDelta = useStreamStore((s) => s.applyOutlineDelta);
  const clearOutlineDelta = useStreamStore((s) => s.clearOutlineDelta);
  const cursorRef = useRef<number>(0);
  const appliedRef = useRef<Set<number>>(new Set());
  const chunkRef = useRef<Set<string>>(new Set());
  const abortRef = useRef<AbortController | null>(null);
  const timerRef = useRef<number | null>(null);
  const stopRef = useRef(false);
  const attemptRef = useRef(0);
  const snapshotDebounce = useRef<number | null>(null);

  useEffect(() => {
    if (initialCursor !== undefined && initialCursor !== null) {
      cursorRef.current = initialCursor;
    }
  }, [initialCursor]);

  useEffect(() => {
    if (!projectId || !enabled) {
      setStatus("idle");
      return;
    }
    stopRef.current = false;
    appliedRef.current.clear();
    chunkRef.current.clear();

    const invalidateSnapshot = () => {
      if (snapshotDebounce.current) window.clearTimeout(snapshotDebounce.current);
      snapshotDebounce.current = window.setTimeout(() => {
        void queryClient.invalidateQueries({ queryKey: qk.snapshot(projectId) });
      }, 250);
    };

    const invalidate = (key: readonly unknown[]) => {
      void queryClient.invalidateQueries({ queryKey: key });
    };

    const handleDomain = (envelope: DomainEventEnvelope) => {
      if (envelope.sequence <= cursorRef.current || appliedRef.current.has(envelope.sequence)) return;
      appliedRef.current.add(envelope.sequence);
      cursorRef.current = envelope.sequence;
      try {
        sessionStorage.setItem(`bound:cursor:${projectId}`, String(envelope.sequence));
      } catch {
        /* storage may be unavailable */
      }
      switch (envelope.type) {
        case "projectCreated":
          break;
        case "materialStatusChanged":
          invalidate(qk.materials(projectId));
          invalidate(qk.research(projectId));
          break;
        case "sourceAdded":
          invalidate(qk.sources(projectId));
          break;
        case "digestReady":
          invalidate(qk.research(projectId));
          invalidate(qk.sources(projectId));
          break;
        case "questionAsked":
        case "answerRecorded":
        case "gapSuggested":
        case "gapDecided":
        case "gapSearchCompleted":
        case "profileReady":
          invalidate(qk.research(projectId));
          if (envelope.type === "profileReady") invalidateSnapshot();
          break;
        case "profileUpdated":
          invalidate(qk.research(projectId));
          invalidate(qk.outline(projectId));
          invalidate(qk.pages(projectId));
          invalidateSnapshot();
          break;
        case "outlineDone":
          clearOutlineDelta(projectId);
          invalidate(qk.outline(projectId));
          invalidate(qk.pages(projectId));
          invalidateSnapshot();
          break;
        case "stageStateChanged":
          invalidateSnapshot();
          break;
        case "staleChanged":
          invalidateSnapshot();
          invalidate(qk.pages(projectId));
          break;
        case "pageJobStarted":
          invalidate(qk.pages(projectId));
          break;
        case "pageJobDone": {
          const payload = envelope.payload as { pageId?: string; kind?: string };
          if (payload.pageId && payload.kind) {
            const kind = payload.kind.toLowerCase() as "plan" | "design";
            invalidate(qk.artifact(projectId, payload.pageId, kind));
            invalidate(qk.history(projectId, payload.pageId, kind));
          }
          invalidate(qk.pages(projectId));
          invalidateSnapshot();
          break;
        }
        case "pageJobFailed":
          invalidate(qk.pages(projectId));
          invalidateSnapshot();
          break;
        case "historyPopped": {
          const payload = envelope.payload as { pageId?: string; kind?: string };
          if (payload.pageId && payload.kind) {
            const kind = payload.kind.toLowerCase() as "plan" | "design";
            invalidate(qk.artifact(projectId, payload.pageId, kind));
            invalidate(qk.history(projectId, payload.pageId, kind));
          }
          break;
        }
        case "jobQueued":
          break;
        case "jobCancelled":
          invalidate(qk.pages(projectId));
          invalidateSnapshot();
          break;
        case "jobResumed":
          break;
        case "exportProgress":
        case "exportDone":
        case "exportFailed": {
          const payload = envelope.payload as { exportId?: string };
          if (payload.exportId) invalidate(qk.exportJob(projectId, payload.exportId));
          if (envelope.type !== "exportProgress") invalidateSnapshot();
          break;
        }
        default:
          // Unknown event types are ignored by design.
          break;
      }
    };

    const connect = async () => {
      if (stopRef.current) return;
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      setStatus(attemptRef.current === 0 ? "connecting" : "reconnecting");
      try {
        const response = await fetch(
          `/api/projects/${projectId}/events?cursor=${cursorRef.current ?? 0}`,
          {
            headers: { Accept: "text/event-stream" },
            credentials: "same-origin",
            signal: controller.signal,
          },
        );
        if (response.status === 401) {
          window.dispatchEvent(new CustomEvent("bound:unauthorized"));
          setStatus("closed");
          return;
        }
        if (!response.ok || !response.body) throw new Error("stream failed");
        attemptRef.current = 0;
        setStatus("live");
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (!stopRef.current) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          let index = buffer.indexOf("\n\n");
          while (index >= 0) {
            const raw = buffer.slice(0, index);
            buffer = buffer.slice(index + 2);
            parseFrame(raw);
            index = buffer.indexOf("\n\n");
          }
        }
        throw new Error("stream ended");
      } catch {
        if (stopRef.current || controller.signal.aborted) return;
        setStatus("reconnecting");
        const delay = Math.min(15000, 500 * 1.8 ** attemptRef.current) * (0.5 + Math.random() * 0.5);
        attemptRef.current += 1;
        timerRef.current = window.setTimeout(connect, delay);
      }
    };

    const parseFrame = (raw: string) => {
      let eventName = "message";
      let data = "";
      for (const line of raw.split("\n")) {
        if (line.startsWith(":")) continue;
        if (line.startsWith("event:")) eventName = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) return;
      let parsed: any;
      try {
        parsed = JSON.parse(data);
      } catch {
        return;
      }
      if (eventName === "snapshot") {
        const snapshot = parsed.snapshot as ProjectSnapshotDTO;
        const sequence = Number(parsed.sequence ?? snapshot.sequence ?? 0);
        cursorRef.current = sequence;
        queryClient.setQueryData(qk.snapshot(projectId), snapshot);
        void queryClient.invalidateQueries({
          predicate: (query) => query.queryKey[0] === "project" && query.queryKey[1] === projectId && query.queryKey[2] !== "snapshot",
        });
        setStatus("live");
      } else if (eventName === "domain") {
        handleDomain(parsed as DomainEventEnvelope);
      } else if (eventName === "ephemeral") {
        if (parsed.type === "outlineDelta") {
          const payload = parsed as OutlineDeltaPayload;
          const key = `${payload.jobId}:${payload.chunkIndex}`;
          if (!chunkRef.current.has(key)) {
            if (chunkRef.current.size > EPHEMERAL_DEDUPE) chunkRef.current.clear();
            chunkRef.current.add(key);
            applyOutlineDelta(projectId, payload);
          }
        }
      } else if (eventName === "heartbeat") {
        if (!stopRef.current) setStatus("live");
      } else if (eventName === "resync") {
        setStatus("resyncing");
        cursorRef.current = Number(parsed.latestSequence ?? 0);
        void queryClient.invalidateQueries({
          predicate: (query) => query.queryKey[0] === "project" && query.queryKey[1] === projectId,
        });
      }
    };

    void connect();

    return () => {
      stopRef.current = true;
      abortRef.current?.abort();
      if (timerRef.current) window.clearTimeout(timerRef.current);
      if (snapshotDebounce.current) window.clearTimeout(snapshotDebounce.current);
      setStatus("closed");
    };
  }, [projectId, enabled, queryClient, setStatus, applyOutlineDelta, clearOutlineDelta]);
}
