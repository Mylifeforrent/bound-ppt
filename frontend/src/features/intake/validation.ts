import type { ClientConfigDTO, NoticeDTO } from "@/api/types";

export interface FileCheck {
  ok: boolean;
  errorKey?: string;
  maxBytes?: number;
}

/** Add the default scheme and return a normalized public URL, or null when invalid. */
export function normalizeUrl(input: string): string | null {
  const trimmed = input.trim();
  if (!trimmed) return null;
  const candidate = /^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//.test(trimmed) ? trimmed : `https://${trimmed}`;
  try {
    const url = new URL(candidate);
    if (url.protocol !== "http:" && url.protocol !== "https:") return null;
    if (!url.hostname) return null;
    if (!url.hostname.includes(".") && url.hostname !== "localhost") return null;
    return url.toString();
  } catch {
    return null;
  }
}

export function urlDisplayName(normalized: string): string {
  try {
    const url = new URL(normalized);
    const path = url.pathname === "/" ? "" : url.pathname;
    return `${url.hostname}${path}`;
  } catch {
    return normalized;
  }
}

export function fileExtension(fileName: string): string {
  const index = fileName.lastIndexOf(".");
  return index >= 0 ? fileName.slice(index).toLowerCase() : "";
}

/** Validate extension/size against the versioned client configuration. */
export function checkFile(
  file: File,
  supportedFileTypes?: ClientConfigDTO["supportedFileTypes"],
  uploadMaxBytes?: number,
): FileCheck {
  const extension = fileExtension(file.name);
  if (supportedFileTypes && supportedFileTypes.length > 0) {
    const rule = supportedFileTypes.find(
      (entry) =>
        entry.extension.toLowerCase() === extension ||
        (Boolean(file.type) && entry.mimeType.toLowerCase() === file.type.toLowerCase()),
    );
    if (!rule) return { ok: false, errorKey: "error.validation.unsupported_type" };
    if (rule.maxBytes > 0 && file.size > rule.maxBytes) {
      return { ok: false, errorKey: "error.validation.file_too_large", maxBytes: rule.maxBytes };
    }
    return { ok: true, maxBytes: rule.maxBytes };
  }
  if (uploadMaxBytes && file.size > uploadMaxBytes) {
    return { ok: false, errorKey: "error.validation.file_too_large", maxBytes: uploadMaxBytes };
  }
  return { ok: true, maxBytes: uploadMaxBytes };
}

export function acceptedTypesLabel(config: ClientConfigDTO | undefined): string | undefined {
  if (!config?.supportedFileTypes.length) return undefined;
  return config.supportedFileTypes.map((entry) => entry.extension).join(", ");
}

export function maxFileBytes(config: ClientConfigDTO | undefined): number | undefined {
  if (!config) return undefined;
  const perType = config.supportedFileTypes.map((entry) => entry.maxBytes).filter((value) => value > 0);
  if (perType.length > 0) return Math.max(...perType);
  return config.uploadMaxBytes;
}

export interface NoticeGate {
  required: NoticeDTO[];
  unaccepted: NoticeDTO[];
  blocked: boolean;
}

export function noticeGate(notices: NoticeDTO[] | undefined): NoticeGate {
  const required = (notices ?? []).filter((notice) => notice.requiresConsent);
  const unaccepted = required.filter((notice) => !notice.acceptedAt);
  return { required, unaccepted, blocked: unaccepted.length > 0 };
}

export function textSizeBytes(text: string): number {
  try {
    return new TextEncoder().encode(text).length;
  } catch {
    return text.length;
  }
}
