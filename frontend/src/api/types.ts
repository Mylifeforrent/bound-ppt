export type Uuid = string;
export type IsoDateTime = string;

export interface EnvelopeMeta {
  requestId: string;
  traceId: string;
  serverTime: IsoDateTime;
  projectVersion?: number;
  sequence?: number;
  idempotentReplay?: boolean;
}

export interface PageError {
  code: string;
  category: string;
  messageKey: string;
  retryable: boolean;
  pageId?: Uuid;
}

export interface ArtifactStatus {
  status: string;
  artifactVersionId?: Uuid;
  version?: number;
  historyDepth?: number;
  canUndo?: boolean;
  error?: PageError;
}

export interface ActiveJobRef {
  jobId: Uuid;
  type: string;
  state: string;
  pageId?: Uuid;
}

export type ProjectMode = "FULLY_AUTOMATIC" | "EXPERT_COPILOT";
export type StageName = "INTAKE" | "RESEARCH" | "OUTLINE" | "PLAN" | "STYLE" | "DESIGN";
export type StageStatus = "LOCKED" | "AVAILABLE" | "IN_PROGRESS" | "COMPLETE" | "STALE" | "ERROR";
export type PageStatus = "PENDING" | "PLANNING" | "DESIGNING" | "DONE" | "STALE" | "ERROR";
export type MaterialKind = "PASTE" | "FILE" | "URL";
export type MaterialStatus = "PENDING" | "INGESTING" | "DIGESTED" | "FAILED" | "REMOVED";
export type ArtifactKind = "plan" | "design";
export type ExportFormat = "PPTX" | "HTML" | "PDF";
export type LayoutId = "single" | "two_col" | "three_col" | "hero" | "async" | "mix";

export interface UserDTO {
  id: Uuid;
  email: string;
  name: string | null;
  role: string;
}

export interface AccountDTO {
  id: Uuid;
  name: string | null;
  plan: string;
  billingStatus?: string | null;
}

export interface ClientConfigDTO {
  materialLimit: number;
  pageLimit: number;
  uploadMaxBytes: number;
  supportedFileTypes: Array<{ extension: string; mimeType: string; maxBytes: number; maxPages: number | null }>;
  searchCapPerProject: number;
  exportFormats: ExportFormat[];
  deckCanvas: { width: number; height: number };
  questionCatalogVersion: string;
  styleCatalogVersion: string;
}

export interface NoticeDTO {
  type: string;
  version: string;
  title: string;
  body: string;
  requiresConsent: boolean;
  acceptedAt: IsoDateTime | null;
}

export interface ProjectDTO {
  id: Uuid;
  name: string;
  topic: string;
  mode: ProjectMode;
  status: string;
  stage: StageName;
  version: number;
  epoch: number;
  createdAt: IsoDateTime;
  updatedAt: IsoDateTime;
}

export interface StageBlockerDTO {
  code: string;
  messageKey: string;
  stage?: StageName;
}

export interface StageStateDTO {
  stage: StageName;
  status: StageStatus;
  reachable: boolean;
  staleReasons: string[];
  blockers: StageBlockerDTO[];
  advanceToken?: string;
  advanceTokenExpiresAt?: IsoDateTime;
}

export interface SnapshotCountsDTO {
  materials: number;
  webSources: number;
  pages: number;
  sections: number;
  planDone: number;
  planTotal: number;
  designDone: number;
  designTotal: number;
  stalePages: number;
  errorPages: number;
}

export interface StyleSelectionSummaryDTO {
  styleKey: string;
  styleVersion: number;
  confirmed: boolean;
  confirmedAt: IsoDateTime | null;
}

export interface ProjectSnapshotDTO {
  project: ProjectDTO;
  stages: StageStateDTO[];
  pointers: {
    profileVersionId: Uuid | null;
    outlineVersionId: Uuid | null;
    styleSelectionId: Uuid | null;
  };
  counts: SnapshotCountsDTO;
  profileDirty: boolean;
  materialLimit: number;
  styleSelection: StyleSelectionSummaryDTO | null;
  activeJobs: ActiveJobRef[];
  latestExportId: Uuid | null;
  sequence: number;
  schemaVersion: number;
  serverTime: IsoDateTime;
}

export interface StaleSummaryDTO {
  changed: boolean;
  cause: string;
  affected: { plan: Uuid[]; design: Uuid[] };
  rerun: { plan: number; design: number };
  cascadeRatio: number | null;
  projectVersion: number;
}

export interface AdvanceResultDTO {
  project: ProjectDTO;
  stages: StageStateDTO[];
  advanced: boolean;
  fromStage: StageName;
  toStage: StageName;
}

export interface MaterialDTO {
  id: Uuid;
  kind: MaterialKind;
  status: MaterialStatus;
  displayName: string;
  mimeType: string | null;
  sizeBytes: number;
  pageCount: number | null;
  domain: string | null;
  error?: PageError;
  createdAt: IsoDateTime;
  updatedAt: IsoDateTime;
  activeJob?: ActiveJobRef;
}

export interface MaterialListDTO {
  materials: MaterialDTO[];
  limit: number;
  remaining: number;
}

export interface UploadUrlDTO {
  materialId: Uuid;
  upload: {
    url: string;
    method: string;
    headers: Record<string, string>;
    expiresAt: IsoDateTime;
  };
}

export interface SourceItemDTO {
  id: Uuid;
  origin: "PROVIDED" | "WEB";
  sourceType: string;
  title: string;
  summary: string;
  domain: string | null;
  rank: number;
  materialId: Uuid | null;
  gapSuggestionId: Uuid | null;
}

export interface MaterialDigestDTO {
  materialId: Uuid;
  displayName: string;
  status: "PENDING" | "READY" | "FAILED";
  extractedCharCount: number | null;
  lengthBucket: string | null;
  summaryPreview: string | null;
}

export interface SourcePanelDTO {
  materials: { count: number; status: "empty" | "loading" | "ready"; items: SourceItemDTO[]; digest?: MaterialDigestDTO[] };
  web: { count: number; status: "empty" | "loading" | "ready"; items: SourceItemDTO[]; skipped: boolean; cap: number };
}

export interface QuestionDTO {
  key: string;
  position: number;
  prompt: string;
  options: Array<{ key: string; label: string }>;
  answer: { optionKey: string; revision: number; answeredAt: IsoDateTime } | null;
}

export interface GapSuggestionDTO {
  id: Uuid;
  label: string;
  reason: string;
  recommended: boolean;
  status: "SUGGESTED" | "SELECTED" | "REJECTED";
}

export interface GapStateDTO {
  batch: number;
  suggestions: GapSuggestionDTO[];
  decision: {
    decidedAt: IsoDateTime;
    selectedSuggestionIds: Uuid[];
    webSkipped: boolean;
  } | null;
}

export interface GapSearchOutcomeDTO {
  gapSuggestionId: Uuid;
  queryIndex: number;
  outcome: "PENDING" | "RESULTS" | "ZERO_RESULTS" | "FAILED";
  resultCount: number;
  errorCode: string | null;
}

export interface ProfileDTO {
  profileVersionId: Uuid;
  version: number;
  audience: string;
  goal: string;
  styleMood: string;
  pageCount: number;
  materialsSummary: { materialIds: Uuid[]; materialCount: number; strategy: "material_first" | "web_only" };
  webScope: { selectedGapSuggestionIds: Uuid[]; webSkipped: boolean; sourceCount: number };
  contentStrategy: string;
  sourceRefs: Uuid[];
  createdAt: IsoDateTime;
}

export interface ResearchStateDTO {
  stage: StageName;
  stageStatus: StageStatus;
  profileDirty: boolean;
  questions: QuestionDTO[];
  digest: { status: "NONE" | "PENDING" | "PARTIAL" | "READY"; items: MaterialDigestDTO[] };
  gaps: GapStateDTO | null;
  gapSearches: GapSearchOutcomeDTO[];
  sources: SourcePanelDTO;
  profile: ProfileDTO | null;
  counts: { questionsTotal: number; questionsAnswered: number; materialsSelected: number; selectedGaps: number };
  activeJobs: ActiveJobRef[];
}

export interface OutlineSectionDTO {
  sectionKey: string;
  title: string;
  position: number;
}

export interface OutlinePageDTO {
  pageId: Uuid;
  position: number;
  pageType: "COVER" | "TOC" | "BODY" | "END";
  sectionKey: string;
  title: string;
  keyPoints: string[];
  deletable: boolean;
}

export interface OutlineDTO {
  outlineVersionId: Uuid;
  version: number;
  confirmed: boolean;
  confirmedAt: IsoDateTime | null;
  pages: OutlinePageDTO[];
  sections: OutlineSectionDTO[];
  counts: {
    pages: number;
    sections: number;
    bodyPages: number;
    agreedPageCount: number;
    deviation: number;
    deviationWarning: boolean;
  };
  stageStatus: StageStatus;
}

export interface PageSummaryDTO {
  pageId: Uuid;
  position: number;
  pageType: "COVER" | "TOC" | "BODY" | "END";
  sectionKey: string;
  sectionTitle: string;
  title: string;
  plan: ArtifactStatus;
  design: ArtifactStatus;
  activeJob: ActiveJobRef | null;
}

export interface PageListDTO {
  outlineVersionId: Uuid | null;
  projectVersion: number;
  counts: {
    total: number;
    planDone: number;
    planPending: number;
    planRunning: number;
    planStale: number;
    planError: number;
    designDone: number;
    designPending: number;
    designRunning: number;
    designStale: number;
    designError: number;
  };
  pages: PageSummaryDTO[];
}

export interface ArtifactChromeDTO {
  pageNumber: number;
  deckOrder: number;
  title: string;
  sectionLabel: string | null;
  chromeVersion: string;
}

export interface ArtifactSourceRefDTO {
  sourceItemId: Uuid;
  title: string;
  origin: string;
  role: string;
}

export interface PlanBlockV1 {
  id: string;
  slot: string;
  role: string;
  text?: string | null;
  items?: string[] | null;
  assetRef?: string | null;
  emphasis?: string | null;
  span?: { col: number; row: number } | null;
}

export interface PlanBodyV1 {
  schemaVersion: 1;
  canvas: { width: 1280; height: 720 };
  layoutId: LayoutId;
  density: "low" | "medium" | "high";
  blocks: PlanBlockV1[];
  meta: { title: string; keyPointsUsed?: string[]; [key: string]: unknown };
}

export interface DesignBlockV1 extends PlanBlockV1 {
  style: { textStyle: string; colorRole: string; align?: "left" | "center" | "right" };
}

export interface DesignBodyV1 {
  schemaVersion: 1;
  canvas: { width: 1280; height: 720 };
  layoutId: LayoutId;
  density: "low" | "medium" | "high";
  style: { styleKey: string; styleVersion: number; tokens: Record<string, string | number> };
  blocks: DesignBlockV1[];
  assets: Array<{ assetId: string; kind: string; width: number; height: number; licenseStatus: string }>;
  meta: { title: string; [key: string]: unknown };
}

export interface ArtifactDTO {
  artifactVersionId: Uuid;
  pageId: Uuid;
  kind: "PLAN" | "DESIGN";
  version: number;
  contentDigest: string;
  inputFingerprint: string;
  schemaVersion: number;
  body: PlanBodyV1 | DesignBodyV1;
  chrome: ArtifactChromeDTO;
  sourceRefs: ArtifactSourceRefDTO[];
  history: { depth: number; canUndo: boolean; currentPointerVersion: number };
  status: PageStatus;
  createdAt: IsoDateTime;
}

export interface HistoryEntryDTO {
  artifactVersionId: Uuid;
  version: number;
  reason: string;
  createdAt: IsoDateTime;
  isCurrent: boolean;
  undone: boolean;
}

export interface PageHistoryDTO {
  pageId: Uuid;
  kind: "PLAN" | "DESIGN";
  depth: number;
  canUndo: boolean;
  entries: HistoryEntryDTO[];
}

export interface StylePaletteDTO {
  primary: string;
  secondary: string;
  accent: string;
  background: string;
  surface: string;
  text: string;
}

export interface StyleDTO {
  styleKey: string;
  name: string;
  version: number;
  scope: string;
  description: string;
  palette: StylePaletteDTO;
  previewUrl: string;
  licenseStatus: string;
  useCase: string;
}

export interface StyleSelectionDTO {
  styleSelectionId: Uuid;
  styleKey: string;
  styleVersion: number;
  confirmed: boolean;
  confirmedAt: IsoDateTime | null;
  rememberPreference: boolean;
  createdAt: IsoDateTime;
}

export interface JobDTO {
  jobId: Uuid;
  projectId: Uuid;
  type: string;
  state: string;
  stage: StageName;
  pageId?: Uuid | null;
  attemptCount: number;
  maxAttempts: number;
  cancelRequested: boolean;
  queuedAt: IsoDateTime;
  startedAt?: IsoDateTime | null;
  completedAt?: IsoDateTime | null;
  deadlineAt?: IsoDateTime | null;
  error?: PageError | null;
  progress?: { phase: string; current: number; total: number } | null;
}

export interface ExportArtifactDTO {
  artifactId: Uuid;
  fileName: string;
  mimeType: string;
  byteSize: number;
  checksum: string;
  createdAt: IsoDateTime;
  expiresAt: IsoDateTime | null;
  downloadPath: string;
}

export interface ExportValidationCheckDTO {
  code: string;
  status: "PASS" | "FAIL" | "WARN" | "SKIP";
  pageIds: Uuid[];
}

export interface ExportDTO {
  exportId: Uuid;
  projectId: Uuid;
  format: ExportFormat;
  state: "QUEUED" | "VALIDATING" | "COMPOSING" | "PACKAGING" | "SUCCEEDED" | "FAILED" | "CANCELLED";
  deckSnapshot: { pageCount: number; styleKey: string; renderedCount: number; excludedPageIds: Uuid[] };
  progress: { phase: string; pagesTotal: number; pagesRendered: number; percent: number };
  validation: { passed: boolean; checks: ExportValidationCheckDTO[]; failedChecks: ExportValidationCheckDTO[] } | null;
  artifact: ExportArtifactDTO | null;
  substitutionReport: { substitutions: Array<{ from: string; to: string; reason: string }> } | null;
  error: PageError | null;
  createdAt: IsoDateTime;
  startedAt: IsoDateTime | null;
  completedAt: IsoDateTime | null;
}

export interface DomainEventEnvelope {
  eventId: Uuid;
  sequence: number;
  projectId: Uuid;
  type: string;
  schemaVersion: number;
  occurredAt: IsoDateTime;
  payload: Record<string, unknown>;
}

export interface OutlineDeltaPayload {
  jobId: Uuid;
  chunkIndex: number;
  delta: {
    sections?: OutlineSectionDTO[];
    pages?: Array<Partial<OutlinePageDTO> & { title?: string }>;
    done?: boolean;
  };
}
