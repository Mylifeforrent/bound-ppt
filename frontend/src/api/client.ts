import type { EnvelopeMeta } from "./types";

export class ApiError extends Error {
  category: string;
  retryable: boolean;
  messageKey: string;
  details: Record<string, unknown>;
  requestId: string;
  traceId: string;
  retryAfterMs: number | null;
  httpStatus: number;

  constructor(init: {
    category: string;
    retryable: boolean;
    messageKey: string;
    details?: Record<string, unknown>;
    requestId?: string;
    traceId?: string;
    retryAfterMs?: number | null;
    httpStatus: number;
  }) {
    super(init.messageKey);
    this.name = "ApiError";
    this.category = init.category;
    this.retryable = init.retryable;
    this.messageKey = init.messageKey;
    this.details = init.details ?? {};
    this.requestId = init.requestId ?? "";
    this.traceId = init.traceId ?? "";
    this.retryAfterMs = init.retryAfterMs ?? null;
    this.httpStatus = init.httpStatus;
  }
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  idempotencyKey?: string;
  expectedVersion?: number;
  signal?: AbortSignal;
  headers?: Record<string, string>;
  rawBody?: BodyInit;
}

export interface ApiResult<T> {
  data: T;
  meta: EnvelopeMeta;
}

const MUTATING = new Set(["POST", "PUT", "PATCH", "DELETE"]);

function newRequestId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export async function api<T = unknown>(path: string, options: RequestOptions = {}): Promise<ApiResult<T>> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = {
    Accept: "application/json",
    "X-Request-Id": newRequestId(),
    ...(options.headers ?? {}),
  };
  let body: BodyInit | undefined = options.rawBody;
  if (options.body !== undefined && !options.rawBody) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }
  if (MUTATING.has(method) && !path.startsWith("/api/auth/") && options.idempotencyKey !== "") {
    headers["Idempotency-Key"] = options.idempotencyKey ?? newRequestId();
  }
  if (options.expectedVersion !== undefined) {
    headers["X-Expected-Version"] = String(options.expectedVersion);
  }
  let response: Response;
  try {
    response = await fetch(path, {
      method,
      headers,
      body,
      credentials: "same-origin",
      signal: options.signal,
    });
  } catch (error) {
    if ((error as Error)?.name === "AbortError") throw error;
    throw new ApiError({
      category: "internal",
      retryable: true,
      messageKey: "error.network.unreachable",
      httpStatus: 0,
    });
  }
  if (response.status === 401) {
    window.dispatchEvent(new CustomEvent("bound:unauthorized"));
  }
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    if (response.ok) {
      return { data: (await response.text()) as T, meta: {} as EnvelopeMeta };
    }
    throw new ApiError({
      category: "internal",
      retryable: response.status >= 500,
      messageKey: "error.internal.unexpected",
      httpStatus: response.status,
    });
  }
  const payload = await response.json();
  if (!response.ok || payload?.ok === false) {
    const err = payload?.error ?? {};
    throw new ApiError({
      category: String(err.category ?? "internal"),
      retryable: Boolean(err.retryable),
      messageKey: String(err.messageKey ?? "error.internal.unexpected"),
      details: err.details ?? {},
      requestId: String(err.requestId ?? ""),
      traceId: String(err.traceId ?? ""),
      retryAfterMs: err.retryAfterMs ?? null,
      httpStatus: response.status,
    });
  }
  return { data: payload.data as T, meta: payload.meta as EnvelopeMeta };
}

export function uploadBinary(
  url: string,
  file: File,
  headers: Record<string, string>,
  method = "PUT",
  onProgress?: (percent: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(method, url, true);
    xhr.withCredentials = false;
    for (const [key, value] of Object.entries(headers)) {
      xhr.setRequestHeader(key, value);
    }
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress?.(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve();
      else reject(new ApiError({ category: "internal", retryable: true, messageKey: "ui.upload.failed", httpStatus: xhr.status }));
    };
    xhr.onerror = () =>
      reject(new ApiError({ category: "internal", retryable: true, messageKey: "ui.upload.failed", httpStatus: 0 }));
    xhr.send(file);
  });
}

export function downloadUrl(path: string): string {
  return path;
}
