import { useCallback, useMemo, useRef, useState } from "react";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { api, ApiError, uploadBinary } from "@/api/client";
import type { ClientConfigDTO, MaterialDTO, MaterialKind, MaterialStatus, UploadUrlDTO } from "@/api/types";
import { uuid } from "@/lib/utils";
import { applyProjectVersion, readProjectVersion } from "./projectVersion";
import type { AddMaterialsResult, CommitResult, IntakeEntry, IntakeEntryStatus, SkippedFile } from "./types";
import { checkFile, normalizeUrl, textSizeBytes, urlDisplayName } from "./validation";

interface LocalEntry {
  key: string;
  kind: MaterialKind;
  displayName: string;
  sizeBytes: number | null;
  status: IntakeEntryStatus;
  progress: number | null;
  error: IntakeEntry["error"];
  text?: string;
  url?: string;
  file?: File;
  materialId?: string;
}

export interface UseMaterialIntakeOptions {
  limit: number;
  noticeAccepted: boolean;
  serverMaterials?: MaterialDTO[];
  supportedFileTypes?: ClientConfigDTO["supportedFileTypes"];
  uploadMaxBytes?: number;
  /** Present for an existing project; absent while the Home form is still local. */
  projectId?: string;
  onChanged?: () => void | Promise<void>;
  onError?: (error: unknown) => void;
}

function toEntryStatus(status: MaterialStatus): IntakeEntryStatus {
  return status;
}

function apiErrorToEntryError(error: unknown): IntakeEntry["error"] {
  if (error instanceof ApiError) {
    return {
      messageKey: error.messageKey,
      requestId: error.requestId || error.traceId || undefined,
      retryable: error.retryable,
    };
  }
  return { messageKey: "error.internal.unexpected", retryable: true };
}

function serverStatusToEntry(material: MaterialDTO): IntakeEntryStatus {
  return toEntryStatus(material.status);
}

export function useMaterialIntake(options: UseMaterialIntakeOptions) {
  const {
    limit,
    noticeAccepted,
    serverMaterials = [],
    supportedFileTypes,
    uploadMaxBytes,
    projectId,
    onChanged,
    onError,
  } = options;
  const queryClient = useQueryClient();
  const [localEntries, setLocalEntries] = useState<LocalEntry[]>([]);
  const [removingKeys, setRemovingKeys] = useState<string[]>([]);
  const [activeCount, setActiveCount] = useState(0);
  const localRef = useRef<LocalEntry[]>([]);
  localRef.current = localEntries;
  const chainRef = useRef<Promise<void>>(Promise.resolve());

  const setLocal = useCallback((updater: (previous: LocalEntry[]) => LocalEntry[]) => {
    setLocalEntries((previous) => {
      const next = updater(previous);
      localRef.current = next;
      return next;
    });
  }, []);

  const updateLocal = useCallback(
    (key: string, patch: Partial<LocalEntry>) => {
      setLocal((previous) => previous.map((entry) => (entry.key === key ? { ...entry, ...patch } : entry)));
    },
    [setLocal],
  );

  const enqueue = useCallback((task: () => Promise<void>) => {
    setActiveCount((count) => count + 1);
    const run = chainRef.current.then(task, task).finally(() => {
      setActiveCount((count) => Math.max(0, count - 1));
    });
    chainRef.current = run.catch(() => undefined);
    return run;
  }, []);

  const serverIds = useMemo(() => new Set(serverMaterials.map((material) => material.id)), [serverMaterials]);

  const visibleLocal = useMemo(
    () => localEntries.filter((entry) => !entry.materialId || !serverIds.has(entry.materialId)),
    [localEntries, serverIds],
  );

  const entries = useMemo<IntakeEntry[]>(() => {
    const serverEntries: IntakeEntry[] = serverMaterials
      .filter((material) => material.status !== "REMOVED")
      .map((material) => {
        const key = `server-${material.id}`;
        return {
          key,
          materialId: material.id,
          kind: material.kind,
          displayName: material.displayName,
          sizeBytes: material.sizeBytes,
          status: serverStatusToEntry(material),
          progress: null,
          error: material.error
            ? {
                messageKey: material.error.messageKey,
                retryable: material.error.retryable,
              }
            : null,
          fromServer: true,
          retryable: false,
          removing: removingKeys.includes(key),
          domain: material.domain,
        };
      });
    const local: IntakeEntry[] = visibleLocal.map((entry) => ({
      key: entry.key,
      materialId: entry.materialId,
      kind: entry.kind,
      displayName: entry.displayName,
      sizeBytes: entry.sizeBytes,
      status: entry.status,
      progress: entry.progress,
      error: entry.error,
      fromServer: false,
      retryable: Boolean(entry.file || entry.text || entry.url),
      removing: removingKeys.includes(entry.key),
      domain: entry.url ? safeHost(entry.url) : null,
    }));
    return [...serverEntries, ...local];
  }, [serverMaterials, visibleLocal, removingKeys]);

  const count = entries.length;
  const remaining = Math.max(0, limit - count);
  const atLimit = limit > 0 && count >= limit;

  const markRemoving = useCallback((key: string, removing: boolean) => {
    setRemovingKeys((previous) =>
      removing ? (previous.includes(key) ? previous : [...previous, key]) : previous.filter((item) => item !== key),
    );
  }, []);

  const checkGate = useCallback(
    (needed: number): AddMaterialsResult | null => {
      if (!noticeAccepted) return { ok: false, errorKey: "error.gate.consent_required" };
      const activeCountNow = entries.length;
      if (limit > 0 && activeCountNow + needed > limit) {
        return { ok: false, errorKey: "error.gate.material_limit" };
      }
      return null;
    },
    [entries.length, limit, noticeAccepted],
  );

  const finishMaterial = useCallback(
    (key: string, material: MaterialDTO, version: number | undefined, pid?: string) => {
      const status = serverStatusToEntry(material);
      updateLocal(key, {
        materialId: material.id,
        displayName: material.displayName,
        sizeBytes: material.sizeBytes,
        status,
        progress: null,
        error: material.error
          ? { messageKey: material.error.messageKey, retryable: material.error.retryable }
          : null,
      });
      if (pid) applyProjectVersion(queryClient, pid, version);
    },
    [queryClient, updateLocal],
  );

  const submitEntry = useCallback(
    async (key: string, pid: string): Promise<boolean> => {
      const entry = localRef.current.find((item) => item.key === key);
      if (!entry) return false;
      try {
        if (entry.kind === "PASTE" && entry.text !== undefined) {
          updateLocal(key, { status: "PENDING", error: null, progress: null });
          const version = await readProjectVersion(pid, queryClient);
          const { data, meta } = await api<{ material: MaterialDTO; jobId: string }>(
            `/api/projects/${pid}/materials/paste`,
            {
              method: "POST",
              body: { text: entry.text },
              expectedVersion: version,
              idempotencyKey: uuid(),
            },
          );
          finishMaterial(key, data.material, meta.projectVersion, pid);
        } else if (entry.kind === "URL" && entry.url) {
          updateLocal(key, { status: "PENDING", error: null, progress: null });
          const version = await readProjectVersion(pid, queryClient);
          const { data, meta } = await api<{ material: MaterialDTO; jobId: string }>(
            `/api/projects/${pid}/materials/url`,
            {
              method: "POST",
              body: { url: entry.url },
              expectedVersion: version,
              idempotencyKey: uuid(),
            },
          );
          finishMaterial(key, data.material, meta.projectVersion, pid);
        } else if (entry.kind === "FILE" && entry.file) {
          updateLocal(key, { status: "UPLOADING", error: null, progress: 0 });
          const version = await readProjectVersion(pid, queryClient);
          const intent = await api<UploadUrlDTO>(`/api/projects/${pid}/materials/upload-url`, {
            method: "POST",
            body: {
              fileName: entry.file.name,
              mimeType: entry.file.type || "application/octet-stream",
              sizeBytes: entry.file.size,
            },
            expectedVersion: version,
            idempotencyKey: uuid(),
          });
          updateLocal(key, { materialId: intent.data.materialId, status: "UPLOADING", progress: 0 });
          applyProjectVersion(queryClient, pid, intent.meta.projectVersion);
          await uploadBinary(
            intent.data.upload.url,
            entry.file,
            intent.data.upload.headers,
            intent.data.upload.method,
            (progress) => updateLocal(key, { progress }),
          );
          updateLocal(key, { status: "PENDING", progress: 100 });
          const finalizeVersion = await readProjectVersion(pid, queryClient);
          const { data, meta } = await api<{ material: MaterialDTO; jobId: string }>(
            `/api/projects/${pid}/materials/${intent.data.materialId}/finalize`,
            {
              method: "POST",
              body: {},
              expectedVersion: finalizeVersion,
              idempotencyKey: uuid(),
            },
          );
          finishMaterial(key, data.material, meta.projectVersion, pid);
        } else {
          throw new ApiError({
            category: "internal",
            retryable: false,
            messageKey: "error.internal.unexpected",
            httpStatus: 500,
          });
        }
        await onChanged?.();
        return true;
      } catch (error) {
        updateLocal(key, { status: "FAILED", error: apiErrorToEntryError(error), progress: null });
        onError?.(error);
        return false;
      }
    },
    [finishMaterial, onChanged, onError, queryClient, updateLocal],
  );

  const cleanupFailedUpload = useCallback(
    async (key: string, pid: string) => {
      const entry = localRef.current.find((item) => item.key === key);
      if (!entry?.materialId) return;
      try {
        const version = await readProjectVersion(pid, queryClient);
        await api(`/api/projects/${pid}/materials/${entry.materialId}`, {
          method: "DELETE",
          expectedVersion: version,
          idempotencyKey: uuid(),
        });
        updateLocal(key, { materialId: undefined });
        applyProjectVersion(queryClient, pid, version);
      } catch {
        // Best effort: keep the material id so the failed placeholder can still be removed later.
      }
    },
    [queryClient, updateLocal],
  );

  const addPaste = useCallback(
    (text: string, displayName?: string): AddMaterialsResult => {
      const value = text.trim();
      if (!value) return { ok: false, errorKey: "ui.form.paste_required" };
      const blocked = checkGate(1);
      if (blocked) return blocked;
      const entry: LocalEntry = {
        key: uuid(),
        kind: "PASTE",
        displayName: displayName?.trim() || "Pasted text",
        sizeBytes: textSizeBytes(value),
        status: "DRAFT",
        progress: null,
        error: null,
        text: value,
      };
      setLocal((previous) => [...previous, entry]);
      if (projectId) void enqueue(() => submitEntry(entry.key, projectId).then(() => undefined));
      return { ok: true, added: 1 };
    },
    [checkGate, enqueue, projectId, setLocal, submitEntry],
  );

  const addUrl = useCallback(
    (url: string): AddMaterialsResult => {
      const normalized = normalizeUrl(url);
      if (!normalized) return { ok: false, errorKey: "ui.form.url_invalid" };
      const blocked = checkGate(1);
      if (blocked) return blocked;
      const entry: LocalEntry = {
        key: uuid(),
        kind: "URL",
        displayName: urlDisplayName(normalized),
        sizeBytes: null,
        status: "DRAFT",
        progress: null,
        error: null,
        url: normalized,
      };
      setLocal((previous) => [...previous, entry]);
      if (projectId) void enqueue(() => submitEntry(entry.key, projectId).then(() => undefined));
      return { ok: true, added: 1 };
    },
    [checkGate, enqueue, projectId, setLocal, submitEntry],
  );

  const addFiles = useCallback(
    (files: File[]): AddMaterialsResult => {
      const list = Array.from(files);
      if (list.length === 0) return { ok: true, added: 0 };
      const blocked = checkGate(1);
      if (blocked) return blocked;
      const capacity = Math.max(0, limit - entries.length);
      if (capacity === 0) return { ok: false, errorKey: "error.gate.material_limit" };
      const accepted: LocalEntry[] = [];
      const skipped: SkippedFile[] = [];
      for (const file of list) {
        if (accepted.length >= capacity) {
          skipped.push({ name: file.name, errorKey: "error.gate.material_limit" });
          continue;
        }
        const check = checkFile(file, supportedFileTypes, uploadMaxBytes);
        if (!check.ok) {
          skipped.push({ name: file.name, errorKey: check.errorKey ?? "error.validation.unsupported_type" });
          continue;
        }
        accepted.push({
          key: uuid(),
          kind: "FILE",
          displayName: file.name,
          sizeBytes: file.size,
          status: "DRAFT",
          progress: null,
          error: null,
          file,
        });
      }
      if (accepted.length > 0) {
        setLocal((previous) => [...previous, ...accepted]);
        if (projectId) {
          for (const entry of accepted) {
            void enqueue(() => submitEntry(entry.key, projectId).then(() => undefined));
          }
        }
      }
      return {
        ok: accepted.length > 0,
        added: accepted.length,
        skipped,
        errorKey: accepted.length === 0 ? skipped[0]?.errorKey : undefined,
      };
    },
    [checkGate, enqueue, entries.length, limit, projectId, setLocal, submitEntry, supportedFileTypes, uploadMaxBytes],
  );

  const remove = useCallback(
    (key: string) => {
      const entry = entries.find((item) => item.key === key);
      if (!entry) return;
      if (!entry.materialId) {
        setLocal((previous) => previous.filter((item) => item.key !== key));
        void onChanged?.();
        return;
      }
      const targetProject = projectId;
      if (!targetProject) {
        setLocal((previous) => previous.filter((item) => item.key !== key));
        void onChanged?.();
        return;
      }
      markRemoving(key, true);
      void enqueue(async () => {
        try {
          const version = await readProjectVersion(targetProject, queryClient);
          await api(`/api/projects/${targetProject}/materials/${entry.materialId}`, {
            method: "DELETE",
            expectedVersion: version,
            idempotencyKey: uuid(),
          });
          applyProjectVersion(queryClient, targetProject, version);
          setLocal((previous) => previous.filter((item) => item.key !== key));
          await onChanged?.();
        } catch (error) {
          onError?.(error);
        } finally {
          markRemoving(key, false);
        }
      });
    },
    [entries, enqueue, markRemoving, onChanged, onError, projectId, queryClient, setLocal],
  );

  const retry = useCallback(
    (key: string) => {
      const targetProject = projectId;
      if (!targetProject) return;
      void enqueue(async () => {
        await cleanupFailedUpload(key, targetProject);
        await submitEntry(key, targetProject);
      });
    },
    [cleanupFailedUpload, enqueue, projectId, submitEntry],
  );

  /** Commit every local draft sequentially; used by Home after project creation. */
  const commitAll = useCallback(
    async (targetProject: string): Promise<CommitResult> => {
      let committed = 0;
      let failed = 0;
      const pending = localRef.current.filter((entry) => !entry.materialId || entry.status === "FAILED");
      await enqueue(async () => {
        for (const snapshot of pending) {
          const current = localRef.current.find((entry) => entry.key === snapshot.key);
          if (!current) continue;
          if (current.materialId) {
            await cleanupFailedUpload(current.key, targetProject);
          }
          const ok = await submitEntry(current.key, targetProject);
          if (ok) committed += 1;
          else failed += 1;
        }
      });
      return { committed, failed };
    },
    [cleanupFailedUpload, enqueue, submitEntry],
  );

  return {
    entries,
    count,
    limit,
    remaining,
    atLimit,
    isBusy: activeCount > 0,
    addPaste,
    addUrl,
    addFiles,
    remove,
    retry,
    commitAll,
  };
}

export type MaterialIntakeController = ReturnType<typeof useMaterialIntake>;

function safeHost(url: string): string | null {
  try {
    return new URL(url).hostname;
  } catch {
    return null;
  }
}

/** Exposed for tests and status copy. */
export function entryStatusLabel(entry: IntakeEntry): string {
  switch (entry.status) {
    case "DRAFT":
      return "Draft";
    case "UPLOADING":
      return entry.progress !== null ? `Uploading ${entry.progress}%` : "Uploading";
    case "PENDING":
      return "Queued";
    case "INGESTING":
      return "Reading";
    case "DIGESTED":
      return "Ready";
    case "FAILED":
      return "Failed";
    case "REMOVED":
      return "Removed";
    default:
      return "Draft";
  }
}

export type { QueryClient };
