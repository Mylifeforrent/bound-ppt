import type { MaterialKind, MaterialStatus } from "@/api/types";

export type IntakeEntryStatus = "DRAFT" | "UPLOADING" | MaterialStatus;

export interface IntakeEntryError {
  messageKey: string;
  requestId?: string;
  retryable: boolean;
}

export interface IntakeEntry {
  key: string;
  materialId?: string;
  kind: MaterialKind;
  displayName: string;
  sizeBytes: number | null;
  status: IntakeEntryStatus;
  progress: number | null;
  error: IntakeEntryError | null;
  fromServer: boolean;
  retryable: boolean;
  removing: boolean;
  domain?: string | null;
}

export interface SkippedFile {
  name: string;
  errorKey: string;
}

export interface AddMaterialsResult {
  ok: boolean;
  errorKey?: string;
  added?: number;
  skipped?: SkippedFile[];
}

export interface CommitResult {
  committed: number;
  failed: number;
}
