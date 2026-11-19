# Bound PPT · API Contracts (v1.1)

> Version: v1.1 · 2026-11-19 · Status: Draft · Owner: Backend / Frontend contract
> Requirements source: `docs/ppt-agent-prd.md` (PRD v1). Architecture source: `docs/ppt-agent-architecture.md` (v1.1, §9). Stack source: `docs/ppt-agent-tech-stack.md` (v2.1, §6). Data source: `docs/ppt-agent-data-model.md` (v1.2).
> This document owns the HTTP command/query surface, request/response DTOs, SSE event contracts, error envelope, and compatibility rules. It does not own product behavior, persistence, or UI layout. On a conflict, the PRD wins behavior, the architecture wins state semantics, and this document is corrected.

---

## 1. Document control

| Field | Value |
| --- | --- |
| Document / version / date | Bound PPT API Contracts / v1 / 2026-11-19 |
| Status / owner / audience | Draft / Backend + Frontend / engineering, QA, security |
| Precedence | PRD (behavior and acceptance) > Architecture (state, ownership, consistency) > Tech stack (implementation) > this document (wire contract) > FLOW/UX (evidence for UI states) |
| Scope | REST JSON commands/queries, SSE stream, upload/download handshakes, error envelope, enum/DTO vocabulary, compatibility rules |
| Out of scope | Prompt payloads, provider APIs, internal service interfaces, database columns (see data model), UI component structure (see frontend design) |
| Contract generation | Pydantic v2 models → FastAPI OpenAPI → `openapi-typescript`; shared artifact schemas → JSON Schema → TypeScript. CI fails on generated diffs [TECH §5.5] |

**Normative language.** MUST / MUST NOT / SHOULD follow PRD §8.1. `[TBD-*]` marks a decision owned elsewhere and is not permission to invent a value.

### 1.1 Terms used on the wire

| Term | Meaning |
| --- | --- |
| **Command** | An intention-named mutation (`POST`/`PUT`/`PATCH`/`DELETE`). Carries an idempotency key and, for project-scoped work, an expected project version. |
| **Query** | A side-effect-free read (`GET`). Never mutates state, never creates a job. |
| **Event** | A content-free notice in the per-project stream. Durable events are replayable; ephemeral deltas are not. |
| **Snapshot** | A consistent project read at a known event sequence. Primary reconnect contract [ARCH AD-10]. |
| **Cursor** | The last applied per-project event `sequence`. Opaque to the client except for ordering. |
| **Projection** | Server-derived stage/page/stale status. The client renders it; it never writes it [ARCH §8.7]. |
| **Content** | Topic, material text, digest text, profile text, outline text, page bodies, export files. Never appears in events/logs. |
| **Metadata** | IDs, kinds, statuses, counts, buckets, domains, timings, costs. Safe in events and telemetry [ARCH §7.5]. |

---

## 2. Transport and conventions

### 2.1 Base path and origin

- Base path: `/api`. Production serves the SPA and API from the same origin; the browser treats cookies and SSE as same-origin [TECH §5.1].
- Development: Vite proxies `/api` to `http://127.0.0.1:8000` [TECH §5.1].
- No CORS headers in M1. A cross-origin deployment requires an explicit security review and a CORS contract change.
- All request and response bodies are UTF-8 JSON (`application/json`) unless stated otherwise.
- SSE responses are `text/event-stream`.
- File downloads redirect to a short-lived signed object URL; raw object keys are never returned [TECH §8.3].

### 2.2 Versioning

- The URL is unversioned in M1 because the SPA and API ship together and the pilot has one deployment [TECH §3.1].
- Additive changes (new optional fields, new event types, new enum values) do not bump a version. Clients MUST ignore unknown fields and unknown event types.
- Breaking changes (field removal/rename, semantic change to an existing command, changed error category for the same code) require a new `/api/v2` prefix or an explicit contract migration approved by both owners.
- `schemaVersion` is carried on SSE events and artifact bodies; it advances independently of the project's optimistic `version` [DATA §11].
- A future deprecation uses `Deprecation` and `Sunset` headers. No deprecations exist in M1.

### 2.3 Naming and serialization

- Wire fields are **camelCase**; database columns are snake_case. Pydantic models use camelCase aliases at the API boundary only.
- IDs are UUIDv7 strings (lowercase, hyphenated). The client treats them as opaque `string`.
- Timestamps are ISO 8601 UTC with milliseconds and a `Z` suffix (`2026-11-19T08:15:30.123Z`).
- Durations are integer milliseconds; sizes are integer bytes; percentages are numbers `0..100` with at most one decimal.
- Enums are uppercase strings. Clients MUST handle an unknown enum value without crashing (render a neutral fallback and refetch the snapshot).
- Money and unit prices are not exposed in M1 user-facing APIs. Internal ledger values are decimal strings (`numeric`), never floats [DATA §6.8].
- `null` is used only where the field is explicitly nullable. Omitted and `null` are not interchangeable; a command that omits a required field is `validation`.

### 2.4 Required headers

| Header | Direction | Required on | Semantics |
| --- | --- | --- | --- |
| `Cookie: bound_session=<opaque>` | request | Every authenticated route | HttpOnly, `Secure` in production, `SameSite=Lax`, `Path=/` [TECH §6.4]. |
| `Idempotency-Key` | request | Every command (`POST`/`PUT`/`PATCH`/`DELETE`) except `POST /api/auth/login` and `POST /api/auth/logout` | Client-generated UUID per logical intent. Retries reuse the same value. A different body with the same key is `validation`. |
| `X-Expected-Version` | request | Every project-scoped command | The `project.version` the client last observed. Mismatch returns `conflict` and never applies the command. |
| `X-Request-Id` | request | Optional | Client correlation ID. Echoed as `meta.requestId`; the server generates one when absent. |
| `Idempotent-Replay` | response | When a duplicate key replays a stored result | `true`. No new job, artifact, event, or charge. |
| `Retry-After` | response | `429` and `503` | Seconds before retry. |
| `ETag` | response | `GET .../artifacts/{kind}` | The artifact `contentDigest`. Supports `If-None-Match` → `304`. |
| `Cache-Control` | response | All API and SSE responses | `no-store`. Project data is never cached by a shared proxy. |
| `Last-Event-ID` | request | SSE fallback | Accepted only when the `cursor` query parameter is absent [TECH §6.3]. |

Missing `Idempotency-Key` or `X-Expected-Version` on a required command is `validation` (`error.validation.missing_header`), not a silent default.

### 2.5 Command rules

1. A command is admitted only after authentication, project-scope authorization, rate-limit admission, schema validation, idempotency lookup, and optimistic-version check [ARCH §5.1].
2. A command that changes authoritative state writes the state change, the `domain_event`, and any `job` row in one transaction [TECH §7.2]. The response is returned after commit.
3. A command that starts asynchronous work returns the handle (`jobId` or `exportId`) and `202 Accepted`; the client MUST NOT treat acceptance as completion.
4. A command that can be satisfied synchronously returns `200 OK`.
5. A command MUST NOT be retried automatically by the client after a `4xx` except `409 conflict` (refetch, then retry as a new intent) and `429`/`503` (same key, after `Retry-After`).
6. Content-bearing commands (topic, paste text, tweak instruction) MUST NOT echo the content in error details or logs [PRD NFR-PRIV-3].

### 2.6 Success envelope

Every JSON response except health, SSE, and file download uses:

```json
{
  "ok": true,
  "data": {},
  "meta": {
    "requestId": "01J...",
    "traceId": "4bf92f3577b34da6a3ce929d0e0e4736",
    "serverTime": "2026-11-19T08:15:30.123Z",
    "projectVersion": 12,
    "sequence": 43,
    "idempotentReplay": false
  }
}
```

- `data` is the resource or command result defined below.
- `meta.projectVersion` is present when the response concerns a project; it is the authoritative version after the operation.
- `meta.sequence` is present when the response reflects a committed event; it is the stream cursor at that point.
- `meta.idempotentReplay` is present and `true` only for a duplicate-key replay.
- `data` is never `null` on success. A command with no payload returns `{}`.

### 2.7 Error envelope

```json
{
  "ok": false,
  "error": {
    "category": "conflict",
    "retryable": true,
    "messageKey": "error.conflict.stale_version",
    "details": { "currentVersion": 13 },
    "requestId": "01J...",
    "traceId": "4bf92f3577b34da6a3ce929d0e0e4736",
    "retryAfterMs": null
  }
}
```

Rules:

- `category` is one of the architecture taxonomy values [ARCH §9.3]. `messageKey` is a stable, namespaced key resolved by the client's message catalog; the server never sends user-facing prose.
- `details` is a small machine-readable object. It MUST NOT contain topic, material text, file names, full URLs, prompts, page bodies, or PII. IDs, counts, field names, enum values, and booleans are allowed.
- `retryable` tells the client whether the same intent can succeed without user correction. It is not a retry command.
- `requestId` and `traceId` are always present and match server logs.
- A request-schema failure uses `400` or FastAPI's `422` with `category: "validation"`; both are safe to treat as validation by the client.
- Authentication failure is HTTP `401` with `category: "forbidden"` and `messageKey: "error.auth.session_required"`. Authorization failure is `403`.
- An idempotency-key reuse with a different payload is `422` / `error.validation.idempotency_key_reused`; the server does not execute the new payload.

| Category | HTTP | Retryable | Typical client action |
| --- | --- | --- | --- |
| `validation` | 400 / 422 | No | Focus the offending field; fix input. |
| `gate_violation` | 409 | No | Complete the prerequisite stage or action. |
| `forbidden` | 401 / 403 | No | Sign in, request access, or switch project. |
| `not_found` | 404 | No | Refetch snapshot; recreate if deleted. |
| `conflict` | 409 | Yes after reconcile | Refetch snapshot/version; re-issue with the new version. |
| `rate_limited` | 429 | Yes, after `Retry-After` | Wait, then retry with the same idempotency key. |
| `provider_timeout` | 504 | Yes, bounded | Retry page/job; other work continues. |
| `provider_unavailable` | 503 | Yes/queued | Retry or use a degraded scope; no fake success. |
| `parse_failure` | 422 | No auto-repeat | Replace the material or paste the body text. |
| `export_validation_failure` | 422 | Conditional | Repair the named page, retry, or choose another format. |
| `quota_exceeded` | 402 (M2) | No | Upgrade/wait; editing and export remain available. |
| `internal` | 500 | Yes once | Retry; if it persists, contact support with IDs. |

### 2.8 Concurrency and idempotency

- `X-Expected-Version` compares against `project.version`. A successful command increments it exactly once. Job completion and artifact commit also increment it because they change the observable projection.
- A duplicate `Idempotency-Key` within the retention window returns the original status, `data`, and `meta` with `idempotentReplay: true`; it MUST NOT create a second job or ledger row [DATA §7.5].
- A duplicate command that targets an already-active operation (for example a second regenerate for the same page) returns the existing job with `200` and `meta.idempotentReplay: true` when the intent matches; otherwise `409 gate_violation` / `error.gate.page_write_in_progress` [PRD FR-6.9, FR-7.4].
- Idempotency-key retention is `[TBD-TECH · backend, before pilot]` (architecture AQ-11). The API does not expose the window.
- Structural commands (outline edit/move/insert/delete, style change) are server-serialized. The server response wins; the client replaces any optimistic ordering.

### 2.9 Pagination and caps

M1 lists are bounded by product caps and are returned whole:

- materials per project: configured cap (prototype 6 is a demo value) [PRD FR-1.7];
- pages per deck: configured cap [PRD NFR-SCALE-2];
- styles: the active built-in catalog (four in M1);
- history per page/kind: bounded by `PAGE_HISTORY_MAX_DEPTH` [DATA §9.3].

No offset pagination exists. If a future list can exceed its cap, it MUST use keyset pagination on `(createdAt, id)` and add explicit `nextCursor`/`hasMore` fields in a new contract version [DATA §10].

---

## 3. Shared vocabulary

### 3.1 Enums

| Enum | Values | Notes |
| --- | --- | --- |
| `ProjectMode` | `FULLY_AUTOMATIC`, `EXPERT_COPILOT` | Default `FULLY_AUTOMATIC` [PRD FR-1.13]. Mode is fixed for the project in M1. |
| `ProjectStatus` | `ACTIVE`, `DELETING`, `DELETED` | `DELETED` is only observable through a tombstone/404. |
| `Stage` | `INTAKE`, `RESEARCH`, `OUTLINE`, `PLAN`, `STYLE`, `DESIGN` | Export is an action inside `DESIGN`, not a stage. |
| `StageStatus` | `LOCKED`, `AVAILABLE`, `IN_PROGRESS`, `COMPLETE`, `STALE`, `ERROR` | Server-derived [DATA §8.2]. |
| `PageType` | `COVER`, `TOC`, `BODY`, `END` | Cover/TOC/end are created at outline v1 and are not deletable [PRD FR-3.2]. |
| `ArtifactKind` | `PLAN`, `DESIGN` | History is per page and kind. |
| `PageStatus` | `PENDING`, `PLANNING`, `DESIGNING`, `DONE`, `STALE`, `ERROR` | `PLANNING` appears only on `plan.status`; `DESIGNING` only on `design.status`. Precedence: error > active job > stale > done > pending [ARCH §8.3]. |
| `MaterialKind` | `PASTE`, `FILE`, `URL` | |
| `MaterialStatus` | `PENDING`, `INGESTING`, `DIGESTED`, `FAILED`, `REMOVED` | `FAILED` means "not digested"; it is isolated to that material [PRD FR-1.9]. |
| `SourceOrigin` | `PROVIDED`, `WEB` | Two source-panel groups [PRD FR-2.15]. |
| `SourceType` | `PASTE`, `FILE`, `URL`, `WEB_RESULT`, `INTERVIEW_ANSWER` | |
| `GapStatus` | `SUGGESTED`, `SELECTED`, `REJECTED` | |
| `JobType` | `INGEST`, `DIGEST`, `SEARCH`, `GAP_SUGGEST`, `PROFILE`, `OUTLINE`, `PLAN_PAGE`, `DESIGN_PAGE`, `EXPORT`, `DELETE_PROJECT` | `SEARCH` is the durable targeted-gap-search job; it is an additive enum value and requires the corresponding data-model enum extension (`[DATA §6.6]`, migration). |
| `JobState` | `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED`, `EXPIRED` | `CANCELLED` never becomes success [PRD FR-7.5]. |
| `ExportFormat` | `PPTX`, `HTML`, `PDF` | |
| `ExportState` | `QUEUED`, `VALIDATING`, `COMPOSING`, `PACKAGING`, `SUCCEEDED`, `FAILED`, `CANCELLED` | Success requires a real artifact [PRD FR-6.16]. |
| `StyleScope` | `BUILTIN`, `ACCOUNT`, `ORGANIZATION` | M1 uses `BUILTIN`; account/organization are M2/M3 [DATA §6.4]. |
| `LicenseStatus` | `CLEARED`, `SUBSTITUTION_REQUIRED`, `UNKNOWN`, `BLOCKED` | Export gate [PRD FR-6.17]. |

### 3.2 Shared object shapes

```ts
type Uuid = string;
type IsoDateTime = string; // 2026-11-19T08:15:30.123Z
type MessageKey = string;  // error.gate.profile_dirty

interface PageError {
  code: string;            // stable machine code, e.g. provider_timeout
  category: string;        // architecture error category
  messageKey: MessageKey;
  retryable: boolean;
  pageId?: Uuid;
}

interface ArtifactStatus {
  status: PageStatus;
  artifactVersionId?: Uuid;
  version?: number;        // per page/kind, starts at 1
  historyDepth?: number;
  canUndo?: boolean;
  error?: PageError;
}

interface ActiveJobRef {
  jobId: Uuid;
  type: JobType;
  state: JobState;
  pageId?: Uuid;
}
```

### 3.3 Project, stage, and snapshot

```ts
interface ProjectDTO {
  id: Uuid;
  name: string;
  topic: string;
  mode: ProjectMode;
  status: ProjectStatus;
  stage: Stage;
  version: number;
  epoch: number;
  createdAt: IsoDateTime;
  updatedAt: IsoDateTime;
}

interface StageStateDTO {
  stage: Stage;
  status: StageStatus;
  reachable: boolean;
  staleReasons: string[];       // content-free codes, e.g. profile_version_changed
  blockers: StageBlockerDTO[];  // why a gate is closed
  advanceToken?: string;        // present only when auto-advance is eligible
  advanceTokenExpiresAt?: IsoDateTime;
}

interface StageBlockerDTO {
  code: string;                 // profile_dirty, plan_incomplete, style_unconfirmed...
  messageKey: MessageKey;
  stage?: Stage;
}

interface ProjectSnapshotDTO {
  project: ProjectDTO;
  stages: StageStateDTO[];
  pointers: {
    profileVersionId: Uuid | null;
    outlineVersionId: Uuid | null;
    styleSelectionId: Uuid | null;
  };
  counts: {
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
  };
  profileDirty: boolean;
  materialLimit: number;
  styleSelection: {
    styleKey: string;
    styleVersion: number;
    confirmed: boolean;
    confirmedAt: IsoDateTime | null;
  } | null;
  activeJobs: ActiveJobRef[];
  latestExportId: Uuid | null;
  sequence: number;             // event sequence represented by this snapshot
  schemaVersion: number;
  serverTime: IsoDateTime;
}
```

`ProjectSnapshotDTO` never contains material text, source summaries, profile prose, outline titles, or page bodies. The client loads content-bearing stage resources separately [ARCH §9.2].

### 3.4 Materials and sources

```ts
interface MaterialDTO {
  id: Uuid;
  kind: MaterialKind;
  status: MaterialStatus;
  displayName: string;
  mimeType: string | null;
  sizeBytes: number;
  pageCount: number | null;
  domain: string | null;
  error?: PageError;            // parse_failure/url fetch failure
  createdAt: IsoDateTime;
  updatedAt: IsoDateTime;
  activeJob?: ActiveJobRef;     // ingest job while INGESTING
}

interface MaterialListDTO {
  materials: MaterialDTO[];
  limit: number;
  remaining: number;
}

interface SourceItemDTO {
  id: Uuid;
  origin: SourceOrigin;
  sourceType: SourceType;
  title: string;
  summary: string;
  domain: string | null;
  rank: number;
  materialId: Uuid | null;
  gapSuggestionId: Uuid | null;
}

interface SourcePanelDTO {
  materials: {
    count: number;
    status: "empty" | "loading" | "ready";
    items: SourceItemDTO[];
    digest?: MaterialDigestDTO[];   // present on GET /research only
  };
  web: {
    count: number;
    status: "empty" | "loading" | "ready";
    items: SourceItemDTO[];
    skipped: boolean;               // "not needed" or no selected gaps
    cap: number;
  };
}
```

Full URLs and raw object keys are never returned. `displayName`, `title`, and `summary` are content-bearing and appear only in authorized queries, never in SSE events [DATA §9.1].

### 3.5 Research and profile

```ts
interface QuestionOptionDTO { key: string; label: string; }

interface QuestionDTO {
  key: string;                  // stable identity, e.g. audience
  position: number;
  prompt: string;
  options: QuestionOptionDTO[];
  answer: {
    optionKey: string;
    revision: number;
    answeredAt: IsoDateTime;
  } | null;
}

interface MaterialDigestDTO {
  materialId: Uuid;
  displayName: string;
  status: "PENDING" | "READY" | "FAILED";
  extractedCharCount: number | null;
  lengthBucket: string | null;  // short/medium/long
  summaryPreview: string | null; // authorized query only
}

interface GapSuggestionDTO {
  id: Uuid;
  label: string;
  reason: string;
  recommended: boolean;
  status: GapStatus;
}

interface GapDecisionDTO {
  decidedAt: IsoDateTime;
  selectedSuggestionIds: Uuid[];
  webSkipped: boolean;
}

interface GapStateDTO {
  batch: number;
  suggestions: GapSuggestionDTO[];
  decision: GapDecisionDTO | null;
}

interface GapSearchOutcomeDTO {
  gapSuggestionId: Uuid;
  queryIndex: number;
  outcome: "PENDING" | "RESULTS" | "ZERO_RESULTS" | "FAILED";
  resultCount: number;
  errorCode: string | null;     // stable code only; no query text
}

interface ProfileDTO {
  profileVersionId: Uuid;
  version: number;
  audience: string;
  goal: string;
  styleMood: string;
  pageCount: number;
  materialsSummary: {
    materialIds: Uuid[];
    materialCount: number;
    strategy: "material_first" | "web_only";
  };
  webScope: {
    selectedGapSuggestionIds: Uuid[];
    webSkipped: boolean;
    sourceCount: number;
  };
  contentStrategy: string;
  sourceRefs: Uuid[];
  createdAt: IsoDateTime;
}

interface ResearchStateDTO {
  stage: Stage;
  stageStatus: StageStatus;
  profileDirty: boolean;
  questions: QuestionDTO[];
  digest: {
    status: "NONE" | "PENDING" | "PARTIAL" | "READY";
    items: MaterialDigestDTO[];
  };
  gaps: GapStateDTO | null;
  gapSearches: GapSearchOutcomeDTO[];   // one row per selected gap; zero-result is explicit
  sources: SourcePanelDTO;
  profile: ProfileDTO | null;
  counts: {
    questionsTotal: number;
    questionsAnswered: number;
    materialsSelected: number;
    selectedGaps: number;
  };
  activeJobs: ActiveJobRef[];
}
```

### 3.6 Outline

```ts
interface OutlineSectionDTO {
  sectionKey: string;
  title: string;
  position: number;
}

interface OutlinePageDTO {
  pageId: Uuid;
  position: number;
  pageType: PageType;
  sectionKey: string;
  title: string;
  keyPoints: string[];
  deletable: boolean;           // false for COVER/TOC/END
}

interface OutlineDTO {
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
    deviationWarning: boolean;  // |deviation| > 2
  };
  stageStatus: StageStatus;
}
```

### 3.7 Pages and artifacts

```ts
interface PageSummaryDTO {
  pageId: Uuid;
  position: number;
  pageType: PageType;
  sectionKey: string;
  sectionTitle: string;
  title: string;
  plan: ArtifactStatus;
  design: ArtifactStatus;
  activeJob: ActiveJobRef | null;
}

interface PageListDTO {
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

interface ArtifactChromeDTO {
  pageNumber: number;
  deckOrder: number;
  title: string;                // outline page title; re-rendered on title edit
  sectionLabel: string | null;
  chromeVersion: string;
}

interface ArtifactSourceRefDTO {
  sourceItemId: Uuid;
  title: string;
  origin: SourceOrigin;
  role: "primary_fact" | "supporting" | "interview";
}

interface ArtifactDTO {
  artifactVersionId: Uuid;
  pageId: Uuid;
  kind: ArtifactKind;
  version: number;
  contentDigest: string;
  inputFingerprint: string;
  schemaVersion: number;
  body: PlanBodyV1 | DesignBodyV1;
  chrome: ArtifactChromeDTO;
  sourceRefs: ArtifactSourceRefDTO[];
  history: {
    depth: number;
    canUndo: boolean;
    currentPointerVersion: number;
  };
  status: PageStatus;
  createdAt: IsoDateTime;
}

interface HistoryEntryDTO {
  artifactVersionId: Uuid;
  version: number;
  reason: "REGENERATE" | "TWEAK" | "REPLAN" | "STYLE_CHANGE" | "MANUAL";
  createdAt: IsoDateTime;
  isCurrent: boolean;
  undone: boolean;
}

interface PageHistoryDTO {
  pageId: Uuid;
  kind: ArtifactKind;
  depth: number;
  canUndo: boolean;
  entries: HistoryEntryDTO[];
}
```

#### 3.7.1 Artifact body schemas

The plan/design body is the shared content model rendered by React and by the export pipeline [TECH §12.1]. This contract fixes the top-level keys; the block-level schema is owned by `shared/schemas/plan-body.schema.json` and `shared/schemas/design-body.schema.json`, validated in CI.

```ts
interface CanvasV1 { width: 1280; height: 720; } // fixed 16:9 reference

type LayoutIdV1 = "single" | "two_col" | "three_col" | "hero" | "async" | "mix";

interface PlanBlockV1 {
  id: string;
  slot: string;                 // layout slot key from shared/layouts
  role: "headline" | "subhead" | "body" | "bullet_list" | "metric" | "quote"
      | "image" | "chart" | "table" | "callout" | "footer";
  text?: string;
  items?: string[];
  assetRef?: string;            // assetId resolved through GET .../assets/{assetId}
  emphasis?: "primary" | "secondary" | "muted";
  span?: { col: number; row: number };
}

interface PlanBodyV1 {
  schemaVersion: 1;
  canvas: CanvasV1;
  layoutId: LayoutIdV1;
  density: "low" | "medium" | "high";
  blocks: PlanBlockV1[];
  meta: {
    title: string;              // the body's own headline, not the outline/chrome title
    keyPointsUsed: string[];
  };
}

interface DesignBlockV1 extends PlanBlockV1 {
  style: {
    textStyle: string;          // token key, not a raw font string
    colorRole: string;          // token key, not a raw hex value
    align?: "left" | "center" | "right";
  };
}

interface DesignBodyV1 {
  schemaVersion: 1;
  canvas: CanvasV1;
  layoutId: LayoutIdV1;
  density: "low" | "medium" | "high";
  style: {
    styleKey: string;
    styleVersion: number;
    tokens: Record<string, string | number>; // resolved token subset used by the page
  };
  blocks: DesignBlockV1[];
  assets: Array<{
    assetId: string;
    kind: "image" | "icon" | "chart";
    width: number;
    height: number;
    licenseStatus: LicenseStatus;
  }>;
  meta: { title: string };      // body headline; the chrome title still comes from the outline
}
```

Chrome (page number, section label, deck order) is **not** inside the design body. It is returned as `ArtifactChromeDTO` and applied deterministically at render time, so a title/order change never requires a model job [ARCH AD-12].

### 3.8 Style

```ts
interface StyleDTO {
  styleKey: string;
  name: string;
  version: number;
  scope: StyleScope;
  description: string;
  palette: {
    primary: string;
    secondary: string;
    accent: string;
    background: string;
    surface: string;
    text: string;
  };
  previewUrl: string;           // short-lived authorized URL
  licenseStatus: LicenseStatus;
  useCase: string;
}

interface StyleSelectionDTO {
  styleSelectionId: Uuid;
  styleKey: string;
  styleVersion: number;
  confirmed: boolean;
  confirmedAt: IsoDateTime | null;
  rememberPreference: boolean;
  createdAt: IsoDateTime;
}
```

`previewUrl` is a signed, short-lived URL. It MUST NOT be logged or reused across tenants.

### 3.9 Jobs and exports

```ts
interface JobDTO {
  jobId: Uuid;
  projectId: Uuid;
  type: JobType;
  state: JobState;
  stage: Stage;
  pageId: Uuid | null;
  attemptCount: number;
  maxAttempts: number;
  cancelRequested: boolean;
  queuedAt: IsoDateTime;
  startedAt: IsoDateTime | null;
  completedAt: IsoDateTime | null;
  deadlineAt: IsoDateTime | null;
  error: PageError | null;
  progress: { phase: string; current: number; total: number } | null;
}

interface ExportValidationCheckDTO {
  code: string;                 // fonts_missing, asset_out_of_bounds, empty_page...
  status: "PASS" | "FAIL" | "WARN" | "SKIP";
  pageIds: Uuid[];
}

interface ExportArtifactDTO {
  artifactId: Uuid;
  fileName: string;             // safe display name; no server path
  mimeType: string;
  byteSize: number;
  checksum: string;             // sha256
  createdAt: IsoDateTime;
  expiresAt: IsoDateTime;
  downloadPath: string;         // /api/exports/{exportId}/download
}

interface ExportDTO {
  exportId: Uuid;
  projectId: Uuid;
  format: ExportFormat;
  state: ExportState;
  deckSnapshot: {
    pageCount: number;
    styleKey: string;
    renderedCount: number;
    excludedPageIds: Uuid[];
  };
  progress: { phase: string; pagesTotal: number; pagesRendered: number; percent: number };
  validation: {
    passed: boolean;
    checks: ExportValidationCheckDTO[];
    failedChecks: ExportValidationCheckDTO[];
  } | null;
  artifact: ExportArtifactDTO | null;
  substitutionReport: {
    substitutions: Array<{ from: string; to: string; reason: string }>;
  } | null;
  error: PageError | null;
  createdAt: IsoDateTime;
  startedAt: IsoDateTime | null;
  completedAt: IsoDateTime | null;
}
```

### 3.10 Stale propagation and stage advance

```ts
interface StaleSummaryDTO {
  changed: boolean;
  cause: "OUTLINE_EDIT" | "OUTLINE_MOVE" | "OUTLINE_INSERT" | "OUTLINE_DELETE"
       | "OUTLINE_CONFIRM" | "PROFILE_UPDATE" | "STYLE_CHANGE" | "PAGE_REPLAN"
       | "PAGE_TWEAK" | "UNDO" | "MATERIAL_REMOVED" | "MATERIAL_ADDED";
  affected: { plan: Uuid[]; design: Uuid[] };
  rerun: { plan: number; design: number };
  cascadeRatio: number | null;
  projectVersion: number;
}

interface AdvanceResultDTO {
  project: ProjectDTO;
  stages: StageStateDTO[];
  advanced: boolean;
  fromStage: Stage;
  toStage: Stage;
}
```

---

## 4. Endpoint catalog

All project routes require an authenticated session and project-scope authorization. `{projectId}` is a UUID the client obtained from `POST /api/projects`; guessing another project's ID returns `404` or `403` without revealing existence.

### 4.1 Session, configuration, and notices

| # | Method | Path | Purpose | Refs |
| --- | --- | --- | --- | --- |
| A1 | POST | `/api/auth/login` | Pilot sign-in with email/password | TECH §6.4 |
| A2 | POST | `/api/auth/logout` | Revoke the current session | TECH §6.4 |
| A3 | GET | `/api/auth/me` | Current user/account | TECH §6.4 |
| A4 | GET | `/api/config` | Client-safe limits, supported types, formats | PRD FR-1.7/1.8, NFR-SCALE-2 |
| A5 | GET | `/api/policy/notices` | Data-handling notice and consent state | PRD FR-1.12, NFR-PRIV-4 |
| A6 | POST | `/api/policy/consent` | Record notice acceptance | PRD FR-1.12, NFR-PRIV-4 |

**A1 `POST /api/auth/login`**
Request: `{ "email": string, "password": string }`. No idempotency key.
Response `200`: `{ "user": UserDTO }` and `Set-Cookie: bound_session=...`.
Errors: `401 forbidden` `error.auth.invalid_credentials`; `429 rate_limited`.
The response never indicates whether the email exists beyond the generic credential error.

**A2 `POST /api/auth/logout`**
Response `200`: `{ "loggedOut": true }` and an expired cookie. Idempotent.

**A3 `GET /api/auth/me`**
Response `200`: `{ "user": UserDTO, "account": AccountDTO | null }`.
`AccountDTO` is `{ id, name, plan, billingStatus? }`; M1 may return a pilot account placeholder [ARCH AD-14].

**A4 `GET /api/config`**
Authenticated; no project scope. Returns only non-secret client configuration:

```ts
interface ClientConfigDTO {
  materialLimit: number;
  pageLimit: number;
  uploadMaxBytes: number;
  supportedFileTypes: Array<{
    extension: string;          // ".pdf"
    mimeType: string;
    maxBytes: number;
    maxPages: number | null;
  }>;
  searchCapPerProject: number;
  exportFormats: ExportFormat[];
  deckCanvas: { width: 1280; height: 720 };
  questionCatalogVersion: string;
  styleCatalogVersion: string;
}
```

Response `200`: `{ "config": ClientConfigDTO }`.
This is the only pre-project source for the Home material count/limit and the supported-type list; the UI MUST NOT hard-code the prototype's six-item demo limit [PRD FR-1.7/1.8]. Values come from versioned configuration, not client code.

**A5 `GET /api/policy/notices`**
Response `200`:

```json
{
  "notices": [
    {
      "type": "DATA_NOTICE",
      "version": "2026-11-01",
      "title": "How we handle your materials",
      "body": "…",
      "requiresConsent": true,
      "acceptedAt": null
    }
  ]
}
```

The notice MUST be shown before the first material is added [PRD FR-1.12, NFR-PRIV-4]. `body` is product/legal content, not user content.

**A6 `POST /api/policy/consent`** — `Idempotency-Key` required.
Request: `{ "noticeType": "DATA_NOTICE", "version": "2026-11-01" }`.
Response `200`: `{ "acceptedAt": "2026-11-19T08:00:00.000Z", "version": "2026-11-01" }`.
The server records a `policy_record` with the authenticated user and version. Re-posting the same version is idempotent. An unknown/stale version returns `422 validation` `error.validation.notice_version_unknown`.
Material-add and upload-intent/finalize commands return `409 gate_violation` `error.gate.consent_required` when the required notice has not been accepted. The web-only `research/start` path has no material to upload and therefore no separate consent gate.

### 4.2 Projects

| # | Method | Path | Purpose | Refs |
| --- | --- | --- | --- | --- |
| P1 | POST | `/api/projects` | Create a project | PRD FR-1.1, FR-8.1 |
| P2 | GET | `/api/projects/{projectId}/snapshot` | Reconnect/read projection | PRD FR-7.9; ARCH AD-10 |
| P3 | PATCH | `/api/projects/{projectId}` | Rename / change topic before research | PRD FR-8.1 |
| P4 | POST | `/api/projects/{projectId}/restart` | Reset to intake | PRD FR-7.8 |
| P5 | DELETE | `/api/projects/{projectId}` | Delete project and content | PRD FR-8.2 |

**P1 `POST /api/projects`** — `Idempotency-Key` required; no `X-Expected-Version`.
Request:

```json
{ "topic": "Dify company introduction", "name": "Dify company introduction", "mode": "FULLY_AUTOMATIC" }
```

`topic` is required and non-empty after trimming. `name` defaults to `topic`. `mode` defaults to `FULLY_AUTOMATIC`.
Response `201`: `{ "project": ProjectDTO, "snapshot": ProjectSnapshotDTO }`.
Errors: `validation` `error.validation.empty_topic`; `rate_limited`.
A duplicate key returns the same project.

**P2 `GET /api/projects/{projectId}/snapshot`**
Response `200`: `ProjectSnapshotDTO` with `meta.projectVersion` and `meta.sequence`.
This is the primary reconnect read. It contains no content.

**P3 `PATCH /api/projects/{projectId}`** — `X-Expected-Version` + `Idempotency-Key`.
Request: `{ "name"?: string, "topic"?: string }`.
`name` may change at any stage. `topic` may change only while `stage=INTAKE`; after research has started it returns `409 gate_violation` `error.gate.topic_locked` (restart to change the topic) [ARCH §9.1 assumption].
Response `200`: `{ "project": ProjectDTO }`.

**P4 `POST /api/projects/{projectId}/restart`** — `X-Expected-Version` + `Idempotency-Key`.
Request: `{ "confirm": true }`; `confirm` MUST be `true`.
Response `202`: `{ "project": ProjectDTO, "snapshot": ProjectSnapshotDTO, "cancelledJobIds": Uuid[] }`.
Effects: cancel active jobs, increment `epoch`, reset stage/pointers, tombstone prior artifacts under retention [ARCH §6.10]. Idempotent while `DELETING`/after restart.

**P5 `DELETE /api/projects/{projectId}`** — `X-Expected-Version` + `Idempotency-Key`.
Response `202`: `{ "projectId": Uuid, "status": "DELETING", "jobId": Uuid }`.
The project is inaccessible while deleting. Deletion is asynchronous; a later `GET` returns `404 not_found`. The ledger remains pseudonymous [PRD FR-8.2].

### 4.3 Materials

| # | Method | Path | Purpose | Refs |
| --- | --- | --- | --- | --- |
| M1 | GET | `/api/projects/{projectId}/materials` | List current chips and cap | PRD FR-1.6/1.7 |
| M2 | POST | `/api/projects/{projectId}/materials/paste` | Add pasted text | PRD FR-1.3 |
| M3 | POST | `/api/projects/{projectId}/materials/url` | Add a URL | PRD FR-1.5 |
| M4 | POST | `/api/projects/{projectId}/materials/upload-url` | Presign a file upload | TECH §8.3 |
| M5 | POST | `/api/projects/{projectId}/materials/{materialId}/finalize` | Confirm upload and enqueue ingestion | TECH §8.3 |
| M6 | DELETE | `/api/projects/{projectId}/materials/{materialId}` | Remove a material | PRD FR-1.6 |

All material commands require `X-Expected-Version` and `Idempotency-Key`.

**M1 `GET .../materials`**
Response `200`: `MaterialListDTO`.

**M2 `POST .../materials/paste`**
Request: `{ "text": string, "displayName"?: string }`.
`text` is non-empty after trimming and within the configured character cap. `displayName` defaults to a short client label ("Pasted text") and is content-bearing. The server never logs either field.
Response `202`: `{ "material": MaterialDTO, "jobId": Uuid }`.
Errors: `validation` `error.validation.empty_paste`; `gate_violation` `error.gate.material_limit`; `gate_violation` `error.gate.material_locked` when the project is past RESEARCH (restart required; see §4.3.1); `gate_violation` `error.gate.consent_required` before the data notice is accepted.

**M3 `POST .../materials/url`**
Request: `{ "url": string, "displayName"?: string }`.
The server normalizes a missing scheme to `https://`, validates scheme/host, applies SSRF rules, and rejects private/link-local/metadata targets [TECH §11.2].
Response `202`: `{ "material": MaterialDTO, "jobId": Uuid }`.
Errors: `validation` `error.validation.invalid_url`; `parse_failure` `error.parse.url_unreachable` (recorded on the material, not returned as a request failure when the job starts successfully); `gate_violation` `error.gate.material_limit`; `gate_violation` `error.gate.material_locked`; `gate_violation` `error.gate.consent_required`.

**M4 `POST .../materials/upload-url`**
Request: `{ "fileName": string, "mimeType": string, "sizeBytes": integer }`.
The server validates extension/MIME/size policy, the data-notice consent, and project quota before signing.
Response `200`:

```json
{
  "materialId": "…",
  "upload": {
    "url": "https://storage.example/presigned…",
    "method": "PUT",
    "headers": { "Content-Type": "application/pdf" },
    "expiresAt": "2026-11-19T08:20:30.123Z"
  }
}
```

The material exists as `PENDING` with no content until finalize. Errors: `validation` `error.validation.unsupported_type` / `error.validation.file_too_large`; `gate_violation` `error.gate.material_locked`; `gate_violation` `error.gate.consent_required`; `gate_violation` `error.gate.material_limit`.
The browser uploads directly to storage and MUST NOT send bytes through the API process.

**M5 `POST .../materials/{materialId}/finalize`**
Request: `{}`.
The server HEADs the object, verifies actual size/type, then enqueues `INGEST`.
Response `202`: `{ "material": MaterialDTO, "jobId": Uuid }`.
Errors: `validation` `error.validation.upload_missing`; `parse_failure` `error.parse.type_mismatch`.

**M6 `DELETE .../materials/{materialId}`** — `X-Expected-Version` + `Idempotency-Key`.
Response `200`: `{ "materialId": Uuid, "removed": true, "stale": StaleSummaryDTO | null }`.
Removing before research deletes content and restores capacity. Removing after research retires the material, cancels its ingestion, and marks dependent profile/outline/plan/design stale; the client MUST re-research or restart. The post-research interaction is `[TBD-UX · product, M1]` (architecture AQ-12).

#### 4.3.1 Material mutation gate

Adding or removing a material while `stage` is `OUTLINE`, `PLAN`, `STYLE`, or `DESIGN` returns `409 gate_violation` `error.gate.material_locked` with `details.restartRequired: true`. This keeps the M1 profile/gap decision immutable and avoids an undefined re-research flow [PRD FR-2.21; ARCH AQ-12]. The client offers restart.

### 4.4 Research and interview

| # | Method | Path | Purpose | Refs |
| --- | --- | --- | --- | --- |
| R1 | POST | `/api/projects/{projectId}/research/start` | Enter research | PRD FR-1.2, FR-2.1 |
| R2 | GET | `/api/projects/{projectId}/research` | Full research/persona state | PRD FR-2.3–2.15 |
| R3 | PUT | `/api/projects/{projectId}/research/answers/{questionKey}` | Answer/edit one question | PRD FR-2.3/2.4 |
| R4 | POST | `/api/projects/{projectId}/research/gaps/decisions` | Record gap decisions | PRD FR-2.6/2.7/2.21 |
| R5 | POST | `/api/projects/{projectId}/research/profile` | Create/refresh the profile | PRD FR-2.12–2.14 |
| R6 | GET | `/api/projects/{projectId}/sources` | Source panel only | PRD FR-2.15 |

All commands require `X-Expected-Version` and `Idempotency-Key`.

**R1 `POST .../research/start`**
Request: `{}`.
Response `202`: `{ "stage": "RESEARCH", "stageStatus": StageStatus, "jobIds": Uuid[] }`.
With materials, enqueues one ingestion/digest chain per material; without materials, starts the web-only research plan [PRD FR-1.2, FR-2.9]. Idempotent: a second call returns the active state. There is no separate consent gate here: a material cannot exist unless consent was accepted at intake, and the web-only path uploads nothing [PRD FR-1.12; NFR-PRIV-4].

**R2 `GET .../research`**
Response `200`: `ResearchStateDTO`. Question options and prompts are content-bearing and returned only to an authorized project member.

**R3 `PUT .../research/answers/{questionKey}`**
Request: `{ "optionKey": string }`.
The answer is overwritten for that question identity; `revision` increments. It never creates a second answer [PRD FR-2.4].
Response `200`:

```json
{
  "question": { "key": "audience", "optionKey": "exec", "revision": 2, "answeredAt": "…" },
  "profileDirty": true,
  "stale": null
}
```

`profileDirty` becomes `true` only when a profile already exists. Editing an answer after the outline exists also unconfirms the outline only after `POST /research/profile` commits a new profile version [PRD FR-2.14].
Errors: `validation` `error.validation.unknown_question` / `error.validation.unknown_option`; `gate_violation` `error.gate.research_not_active`.

**R4 `POST .../research/gaps/decisions`**
Request:

```json
{ "selectedSuggestionIds": ["…"], "webSkipped": false }
```

`webSkipped: true` requires an empty selection and represents "Not needed — just use my materials" [PRD FR-2.7]. `selectedSuggestionIds` must be a subset of the current batch. A decision is immutable after a profile version exists [PRD FR-2.21].
Response `202`:

```json
{
  "gaps": { "batch": 1, "suggestions": [], "decision": { "decidedAt": "…", "selectedSuggestionIds": ["…"], "webSkipped": false } },
  "searchJobIds": ["…"],
  "gapSearches": [
    { "gapSuggestionId": "…", "queryIndex": 1, "outcome": "PENDING", "resultCount": 0, "errorCode": null }
  ],
  "webSkipped": false
}
```

One `SEARCH` job runs per selected gap. Each outcome resolves to `RESULTS`, `ZERO_RESULTS`, or `FAILED` and is reported by `gapSearchCompleted`; zero results are explicit and never silently skipped [PRD FR-2.10]. When `webSkipped` is `true`, both lists are empty.
Errors: `gate_violation` `error.gate.gaps_already_decided`; `validation` `error.validation.gap_selection_invalid`; `gate_violation` `error.gate.digest_incomplete`.

**R5 `POST .../research/profile`**
Request: `{}` (no free-text profile body; the profile is generated from answers, materials, gaps, and sources).
Response `200`: `{ "profile": ProfileDTO, "profileDirty": false, "outlineUnconfirmed": boolean, "stale": StaleSummaryDTO | null }`.
Requires all four answers and, when materials exist, a gap decision. A first call creates v1; a call while clean returns the current profile (idempotent); a call while dirty creates a new version, clears dirty, and unconfirms any outline [PRD FR-2.13/2.14, FR-3.14].
Errors: `gate_violation` `error.gate.answers_incomplete` / `error.gate.gaps_undecided`; `provider_unavailable` (the job may be enqueued instead; see §5).

**R6 `GET .../sources`**
Response `200`: `SourcePanelDTO`. Materials and web groups are separate; the materials group is `empty` and hidden when no materials exist [PRD FR-2.15].

### 4.5 Outline

| # | Method | Path | Purpose | Refs |
| --- | --- | --- | --- | --- |
| O1 | POST | `/api/projects/{projectId}/outline/generate` | Generate/regenerate the outline | PRD FR-3.1–3.3 |
| O2 | GET | `/api/projects/{projectId}/outline` | Current outline | PRD FR-3.3/3.9 |
| O3 | POST | `/api/projects/{projectId}/outline/confirm` | Lock structure | PRD FR-3.10 |
| O4 | PATCH | `/api/projects/{projectId}/outline/pages/{pageId}` | Edit title | PRD FR-3.4 |
| O5 | POST | `/api/projects/{projectId}/outline/pages` | Insert a body page | PRD FR-3.6/3.15 |
| O6 | DELETE | `/api/projects/{projectId}/outline/pages/{pageId}` | Delete a body page | PRD FR-3.2/3.6 |
| O7 | POST | `/api/projects/{projectId}/outline/pages/{pageId}/move` | Reorder / cross-section move | PRD FR-3.5/3.7/3.8 |
| O8 | POST | `/api/projects/{projectId}/stages/advance` | Auto-advance validation | PRD FR-3.11, FR-4.10 |

All commands require `X-Expected-Version` and `Idempotency-Key`.

**O1 `POST .../outline/generate`**
Request: `{}`.
Response `202`: `{ "jobId": Uuid, "outlineVersionId": null }`.
Requires a current, clean profile. Streams `outlineDelta` (ephemeral) and commits an `outlineDone` artifact [ARCH §6.3]. A second call while the outline job is active returns the active job (`200`, replay semantics).

**O2 `GET .../outline`**
Response `200`: `OutlineDTO`. If no outline exists yet, returns `200` with `outlineVersionId: null`? No — the contract returns `404 not_found` `error.not_found.outline` and the client renders its empty state. `GET /snapshot` is the source for "not generated yet".
Errors: `not_found`.

**O3 `POST .../outline/confirm`**
Request: `{}`.
Response `200`: `{ "outline": OutlineDTO, "stage": StageStateDTO, "snapshot": ProjectSnapshotDTO }`.
Requires a current outline and fully identified pages. It does not start plan generation [PRD FR-3.10].
Errors: `gate_violation` `error.gate.outline_missing` / `error.gate.outline_page_identity`; `conflict`.

**O4 `PATCH .../outline/pages/{pageId}`**
Request: `{ "title": string }`.
Response `200`: `{ "outline": OutlineDTO, "stale": StaleSummaryDTO }`.
Title edit invalidates **design only**; plan stays current and the header re-renders from chrome [PRD §8.9.1 R1; ARCH AD-12].
Errors: `validation` `error.validation.empty_title`; `not_found`; `conflict`.

**O5 `POST .../outline/pages`**
Request:

```json
{ "sectionKey": "part-1", "afterPageId": "…", "title": "New page", "keyPoints": ["…"] }
```

`afterPageId` is optional; when absent the page is appended to the section. A new stable page ID is created. Response `200`: `{ "outline": OutlineDTO, "pageId": Uuid, "stale": StaleSummaryDTO }`.
A section-level insert uses the section's last page as `afterPageId` [PRD FR-3.15].
Errors: `validation` `error.validation.unknown_section`; `gate_violation` `error.gate.outline_missing`. Inserting after confirmation is allowed: the outline becomes unconfirmed and must be reconfirmed before Plan/Design (see §4.5.1).

**O6 `DELETE .../outline/pages/{pageId}`**
Response `200`: `{ "outline": OutlineDTO, "stale": StaleSummaryDTO }`.
Deleting a body page retires its ID and tombstones plan/design/history. COVER/TOC/END return `409 gate_violation` `error.gate.fixed_page_not_deletable` [PRD FR-3.2/3.6].
The UI may offer a confirmation/toast; the API has no soft-delete undo in M1 (P1 FR-3.13).

**O7 `POST .../outline/pages/{pageId}/move`**
Request (one of the two forms):

```json
{ "toSectionKey": "part-2", "beforePageId": "…" }
{ "toSectionKey": "part-1", "toPosition": 3 }
```

`beforePageId` and `toPosition` are mutually exclusive. Dropping on a note means "insert before it" [PRD FR-3.7]. A move within the same section invalidates design only; a cross-section move invalidates plan and design [PRD §8.9.1 R2/R3].
Response `200`: `{ "outline": OutlineDTO, "stale": StaleSummaryDTO }`.

**O8 `POST .../stages/advance`**
Request:

```json
{ "fromStage": "OUTLINE", "advanceToken": "…" }
```

`advanceToken` is issued by the server in `StageStateDTO` when the countdown is eligible and expires after 30 seconds. The client runs the visible 3-second countdown; the server validates mode, gate eligibility, unchanged stage version, and token freshness [ARCH AD-9; PRD FR-3.11].
Response `200`: `AdvanceResultDTO`.
Errors: `gate_violation` `error.gate.auto_advance_ineligible` / `error.gate.token_expired`; `conflict` `error.conflict.stage_changed`.

#### 4.5.1 Outline edits after confirmation

M1 permits outline edits after confirmation to keep the expert-copilot flow usable; any edit sets `confirmed=false` on the current outline version and applies the stale matrix, so Plan/Design cannot run until the user reconfirms [PRD FR-2.14, FR-3.14]. The response's `outline.confirmed` is `false`. The UI shows the reconfirmation prompt. If product later decides to lock confirmed outlines, the command returns `gate_violation` `error.gate.outline_confirmed_locked`; this is a `[TBD-BIZ · product]` decision, not a silent client rule.

### 4.6 Pages and artifacts

| # | Method | Path | Purpose | Refs |
| --- | --- | --- | --- | --- |
| PG1 | GET | `/api/projects/{projectId}/pages` | Page list with statuses | PRD FR-4.2, FR-6.1 |
| PG2 | GET | `/api/projects/{projectId}/pages/{pageId}/artifacts/{kind}` | Current plan/design body | PRD FR-6.1 |
| PG3 | GET | `/api/projects/{projectId}/pages/{pageId}/history` | Per-page history | PRD FR-6.5, FR-7.7 |
| PG4 | GET | `/api/projects/{projectId}/assets/{assetId}` | Authorized image/icon content for a page | PRD FR-6.12/6.17; ARCH §12 |

**PG1 `GET .../pages?kind=plan|design`** — `kind` is optional; both statuses are always returned.
Response `200`: `PageListDTO`.
Statuses are server-derived; the client never computes them from timers [ARCH §8.3]. A page can be `DONE` while its stage is `STALE` because only some pages are affected.

**PG2 `GET .../pages/{pageId}/artifacts/{kind}`** — `kind` ∈ `plan|design`.
Response `200`: `ArtifactDTO` with `ETag: "<contentDigest>"`.
If the page has no current artifact, returns `404 not_found` `error.not_found.artifact`; the client shows a skeleton/pending state from the page list.
The server authorizes project scope before reading object content; the response body is the artifact JSON, not a signed URL [ARCH §12].

**PG3 `GET .../pages/{pageId}/history?kind=design`**
Response `200`: `PageHistoryDTO` with at most the configured depth. Entries are ordered newest first; `undone` marks popped rows retained for audit.

**PG4 `GET .../assets/{assetId}`**
Authorized binary/redirect endpoint for an image, icon, or chart referenced by `PlanBlockV1.assetRef` or `DesignBodyV1.assets[].assetId`.
Response: `302 Location: <short-lived signed URL>` for the original asset, or the binary itself with its content type. The endpoint authorizes project scope and verifies that the asset is referenced by one of the project's current or historical artifacts; an unknown/unreferenced asset returns `404 not_found` `error.not_found.asset`.
The client uses this path directly as an `<img>`/renderer source; signed URLs are never embedded in the artifact body, so a cached artifact cannot carry an expired URL. Assets with `licenseStatus` `BLOCKED` are not served for export; the UI shows the substitution/block state.

### 4.7 Plan draft

| # | Method | Path | Purpose | Refs |
| --- | --- | --- | --- | --- |
| PL1 | POST | `/api/projects/{projectId}/plan/generate` | Fan out plan jobs | PRD FR-4.1/4.9 |
| PL2 | POST | `/api/projects/{projectId}/pages/{pageId}/plan/regenerate` | Re-plan one page | PRD FR-4.5 |
| PL3 | POST | `/api/projects/{projectId}/pages/{pageId}/plan/tweak` | Tweak one page | PRD FR-4.6 |
| PL4 | POST | `/api/projects/{projectId}/pages/{pageId}/retry` | Retry a failed page | PRD FR-4.8 |
| PL5 | POST | `/api/projects/{projectId}/pages/{pageId}/undo` | Restore previous version | PRD FR-6.5, FR-7.7 |

All commands require `X-Expected-Version` and `Idempotency-Key`, plus the plan stage gate.

**PL1 `POST .../plan/generate`**
Request: `{}`.
Response `202`:

```json
{ "jobs": [{ "pageId": "…", "jobId": "…" }], "skippedPageIds": ["…"], "counts": { "required": 12, "scheduled": 10, "reused": 2 } }
```

Requires a confirmed outline. Pages whose inputs/fingerprint already match an existing plan are installed by pointer with zero jobs [PRD FR-4.9, NFR-COST-4].
Errors: `gate_violation` `error.gate.outline_unconfirmed`; `conflict`.

**PL2 `POST .../pages/{pageId}/plan/regenerate`**
Request: `{}`.
Response `202`: `{ "jobId": Uuid, "pageId": Uuid }`.
One page only; design for that page becomes stale [PRD FR-4.5/4.7]. A second request while the page has an active write returns `409 gate_violation` `error.gate.page_write_in_progress` (or the active job when the intent key matches).

**PL3 `POST .../pages/{pageId}/plan/tweak`**
Request: `{ "instruction": string }`.
`instruction` is non-empty, trimmed, and capped; empty returns `422 validation` `error.validation.empty_instruction` before any job is created [PRD FR-4.6].
Response `202`: `{ "jobId": Uuid, "pageId": Uuid }`.
The instruction is content; it is stored as a restricted object reference (`instruction_ref`), never in the job payload, events, or logs [DATA §6.6].

**PL4 `POST .../pages/{pageId}/retry`**
Request: `{ "kind": "plan" | "design" }`.
Response `202`: `{ "jobId": Uuid, "pageId": Uuid }`.
Retry creates a new attempt (or a new operation key where required) with no duplicate history or charge [PRD FR-4.8, NFR-REL-3].

**PL5 `POST .../pages/{pageId}/undo`**
Request: `{ "kind": "plan" | "design" }`.
Response `200`: `{ "artifact": ArtifactDTO, "history": PageHistoryDTO, "stale": StaleSummaryDTO | null }`.
Undo is a pointer move: no job, no model call, no new artifact [PRD FR-6.5]. Undoing a plan makes that page's design stale; undoing a design does not change plan.
Errors: `gate_violation` `error.gate.nothing_to_undo`.

### 4.8 Style selection

| # | Method | Path | Purpose | Refs |
| --- | --- | --- | --- | --- |
| S1 | GET | `/api/styles` | Active style catalog | PRD FR-5.1 |
| S2 | GET | `/api/styles/{styleKey}` | One style with tokens/preview | PRD FR-5.1 |
| S3 | PUT | `/api/projects/{projectId}/style` | Record a selection | PRD FR-5.3 |
| S4 | POST | `/api/projects/{projectId}/style/confirm` | Confirm and unlock design | PRD FR-5.3/5.6 |

**S1 `GET /api/styles`**
Response `200`: `{ "styles": StyleDTO[] }`; four built-in cards in M1 [PRD FR-5.1].
No project version required.

**S2 `GET /api/styles/{styleKey}?version=1`**
Response `200`: `StyleDTO` with resolved tokens and a signed preview URL. A missing/inactive version returns `404`.

**S3 `PUT .../style`** — `X-Expected-Version` + `Idempotency-Key`.
Request: `{ "styleKey": string, "styleVersion": number, "rememberPreference": boolean }`.
Response `200`: `{ "styleSelection": StyleSelectionDTO }`.
Selecting a style does not start generation [PRD FR-5.3]. Changing style after design exists marks all design stale, plan unchanged [PRD FR-5.5].
`rememberPreference` is project-scoped in M1 and account-scoped in M2 [PRD FR-5.4; ARCH §14].
Errors: `gate_violation` `error.gate.plan_incomplete`; `validation` `error.validation.unknown_style`; `conflict`.

**S4 `POST .../style/confirm`**
Request: `{}`.
Response `200`: `{ "styleSelection": StyleSelectionDTO, "stage": StageStateDTO, "stale": StaleSummaryDTO | null }`.
Confirmation unlocks design. In fully automatic mode, style is a pause point; it never auto-confirms [PRD §7.4].
Errors: `gate_violation` `error.gate.style_not_selected` / `error.gate.plan_incomplete`; `conflict`.

### 4.9 Design draft

| # | Method | Path | Purpose | Refs |
| --- | --- | --- | --- | --- |
| D1 | POST | `/api/projects/{projectId}/design/generate` | Fan out design jobs | PRD FR-6.2 |
| D2 | POST | `/api/projects/{projectId}/pages/{pageId}/design/regenerate` | New variant for one page | PRD FR-6.4/6.6 |
| D3 | POST | `/api/projects/{projectId}/pages/{pageId}/design/tweak` | Tweak one page | PRD FR-6.7 |

All require `X-Expected-Version` + `Idempotency-Key`.

**D1 `POST .../design/generate`**
Request: `{}`.
Response `202`: same shape as PL1 with `jobs`, `skippedPageIds`, `counts`.
Requires a confirmed style selection. One job per page; completed pages are inspectable while later pages run [PRD FR-6.2/6.3]. Pages whose plan/style inputs match an existing design are reused with zero jobs [NFR-COST-4].

**D2 `POST .../pages/{pageId}/design/regenerate`**
Request: `{}`.
Response `202`: `{ "jobId": Uuid, "pageId": Uuid }`.
A single-layout page (COVER/TOC/END or a layout with one variant) returns `409 gate_violation` `error.gate.single_layout_use_tweak`; the UI prompts for a tweak instead and MUST NOT fake a variant increment [PRD FR-6.6].
Success pushes the previous current onto history and installs the new version [ARCH §6.6].

**D3 `POST .../pages/{pageId}/design/tweak`**
Request: `{ "instruction": string }`.
Empty/whitespace returns `422 validation` `error.validation.empty_instruction`. Response `202`: `{ "jobId": Uuid, "pageId": Uuid }`.
On success the previous current is pushed to history; a failed tweak leaves current/history unchanged [PRD FR-6.7].

### 4.10 Jobs

| # | Method | Path | Purpose | Refs |
| --- | --- | --- | --- | --- |
| J1 | GET | `/api/projects/{projectId}/jobs/{jobId}` | Poll one job | PRD FR-7.5/7.6 |
| J2 | POST | `/api/projects/{projectId}/jobs/{jobId}/cancel` | Cancel queued/running work | PRD FR-7.5 |

**J1 `GET .../jobs/{jobId}`**
Response `200`: `JobDTO`. The client normally relies on SSE; polling is the fallback after a stream gap.

**J2 `POST .../jobs/{jobId}/cancel`** — `X-Expected-Version` + `Idempotency-Key`.
Response `200`: `{ "job": JobDTO }`.
Cancellation is cooperative; a late result is fenced and discarded. A terminal job returns its terminal state; cancelling a succeeded job is not an error (`200`, no effect) [ARCH §6.9].

### 4.11 Export

| # | Method | Path | Purpose | Refs |
| --- | --- | --- | --- | --- |
| E1 | POST | `/api/projects/{projectId}/exports` | Start an export | PRD FR-6.10 |
| E2 | GET | `/api/projects/{projectId}/exports/{exportId}` | Export status/report | PRD FR-6.14–6.16 |
| E3 | GET | `/api/exports/{exportId}/download` | Download the artifact | PRD FR-6.16 |

**E1 `POST .../exports`** — `X-Expected-Version` + `Idempotency-Key`.
Request: `{ "format": "PPTX" | "HTML" | "PDF" }`.
Response `202`: `{ "export": ExportDTO }`.
The server freezes a deck snapshot (ordered page IDs, current design versions, style, format, render completeness) at request time [PRD FR-6.19/6.21]. Re-export after an edit takes a fresh snapshot; a stale cached file is never served.
Errors: `gate_violation` `error.gate.design_incomplete`; `export_validation_failure` is normally reported asynchronously via `exportFailed`, not as the create response; `rate_limited`.

**E2 `GET .../exports/{exportId}`**
Response `200`: `ExportDTO`. `state=SUCCEEDED` always includes a non-null `artifact`; otherwise it is null [PRD FR-6.16].
Validation failure has `state=FAILED`, `error.category=export_validation_failure`, and `validation.failedChecks` naming page IDs/reason codes. The modal stays open and offers Retry / Try another format [PRD FR-6.15].

**E3 `GET /api/exports/{exportId}/download`**
Authorized, tenant-scoped. On success returns `302 Location: <short-lived signed URL>`; the signed URL is never returned in JSON. On failure returns the standard JSON error envelope.
Errors: `not_found` `error.not_found.export`; `gate_violation` `error.gate.export_not_ready`; `forbidden`.
No `Cache-Control: public`; the redirect is `no-store`.

### 4.12 SSE stream

**EV1 `GET /api/projects/{projectId}/events?cursor={sequence}`**

Headers: `Accept: text/event-stream`, optional `Last-Event-ID` fallback [TECH §6.3].
Response headers:

```
Content-Type: text/event-stream
Cache-Control: no-store
Connection: keep-alive
X-Accel-Buffering: no
```

Behavior:

1. If no valid cursor is supplied, send a `snapshot` frame first.
2. If the cursor is older than the retained window, send `resync` (with a new snapshot frame or a `snapshotAvailable` hint), then continue from the new snapshot sequence.
3. Replay durable `domain_event` rows in `sequence` order, then stream live committed events. The endpoint subscribes before reading the durable replay and dedupes live events by `sequence` [TECH §6.3].
4. Send a `heartbeat` frame every 15 seconds. The proxy/load-balancer idle timeout MUST exceed this.
5. Ephemeral deltas (`outlineDelta`) are sent as `ephemeral` frames and are never replayed or persisted. A client that misses them reloads the committed outline [ARCH §9.2].
6. A slow subscriber whose bounded queue fills is disconnected with `resync`; the client reconnects from its last applied durable sequence.

Frame formats:

```
event: snapshot
id: 42
data: {"snapshot": ProjectSnapshotDTO, "sequence": 42}

event: domain
id: 43
data: {"eventId":"…","sequence":43,"projectId":"…","type":"pageJobDone","schemaVersion":1,"occurredAt":"2026-11-19T08:15:30.123Z","payload":{…}}

event: ephemeral
data: {"type":"outlineDelta","jobId":"…","chunkIndex":7,"delta":{…}}

event: heartbeat
data: {"serverTime":"2026-11-19T08:15:45.123Z"}

event: resync
data: {"reason":"cursor_expired","snapshotAvailable":true,"latestSequence":1024}
```

- `id` is the durable sequence. Ephemeral frames have no `id` and are not valid cursors.
- The client persists the last applied durable `sequence` and sends it as `cursor` on reconnect.
- A `resync` frame is never followed by a silent gap; the client MUST reload the snapshot before applying later events.
- Event payloads carry IDs, counts, statuses, buckets, domains, timings, and costs only. Content (topic, titles, summaries, profile prose, page bodies) is fetched through queries [ARCH §9.2; PRD NFR-PRIV-3].

### 4.13 Health

| Method | Path | Response |
| --- | --- | --- |
| GET | `/api/health` | `200 {"status":"ok"}` — liveness; no dependency checks. |
| GET | `/api/health/ready` | `200 {"status":"ready","checks":{"database":"ok","migrations":"ok","objectStore":"ok","runner":"ok"}}` or `503` with the failing check. |

Health responses do not use the success envelope. Readiness fails during shutdown so the load balancer drains before the process exits [TECH §13.5].

---

## 5. Asynchronous work and response semantics

Some commands need a model call before they can return a domain result (for example a profile refresh or a synchronous resolve). The contract is:

- If the work is fast and bounded, the API may perform it inside the request and return `200` with the result; the request still carries an idempotency key.
- Otherwise the API enqueues a durable job, returns `202` with the job handle, and the client waits for `profileReady` / `pageJobDone` / `exportDone`.
- The API MUST NOT hold a request open for an unbounded model call.
- Accepted work is never reported as complete. A `202` response means "the server owns this intent and will report the outcome through a job/event" [ARCH §10 "no fake success"].
- If the provider is unavailable at admission, the API may return `503 provider_unavailable` without creating a job, or enqueue and let the job retry; it MUST NOT return a fabricated result.
- A job handle is pollable via J1 and observable via EV1. Polling and streaming may be mixed; the client dedupes by job ID and event ID.

---

## 6. SSE event catalog

All durable events share the envelope in §4.12. Payloads below are content-free unless explicitly marked **ephemeral**. `projectVersion` is included when the event reflects a version bump.

| Type | Group | Durable | Payload fields | Refs |
| --- | --- | --- | --- | --- |
| `projectCreated` | Project | Yes | `mode`, `stage`, `projectVersion` | PRD FR-1.13 |
| `materialStatusChanged` | Materials | Yes | `materialId`, `kind`, `status`, `errorCode?`, `pageCountBucket?`, `projectVersion` | PRD FR-1.9/1.10 |
| `sourceAdded` | Materials/research | Yes | `sourceItemId`, `origin`, `sourceType`, `domain`, `rank`, `materialId?`, `gapSuggestionId?` | PRD FR-2.15 |
| `digestReady` | Research | Yes | `materialId`, `status`, `lengthBucket`, `extractedCharBucket` | PRD FR-2.5 |
| `questionAsked` | Research | Yes | `questionKey`, `position`, `optionKeys` | PRD FR-2.3 |
| `answerRecorded` | Research | Yes | `questionKey`, `optionKey`, `revision`, `profileDirty` | PRD FR-2.4 |
| `gapSuggested` | Research | Yes | `batch`, `count`, `recommendedCount`, `suggestionIds` | PRD FR-2.6 |
| `gapDecided` | Research | Yes | `batch`, `selectedCount`, `suggestedCount`, `webSkipped` | PRD FR-2.7/2.8 |
| `gapSearchCompleted` | Research | Yes | `gapSuggestionId`, `queryIndex`, `outcome`, `resultCount`, `errorCode?` | PRD FR-2.8–2.10 |
| `profileReady` | Research | Yes | `profileVersion`, `profileVersionId`, `materialsCount`, `webSourceCount`, `webSkipped`, `projectVersion` | PRD FR-2.12 |
| `profileUpdated` | Research | Yes | `profileVersion`, `profileVersionId`, `outlineUnconfirmed`, `projectVersion` | PRD FR-2.14 |
| `outlineDelta` | Outline | **No (ephemeral)** | `jobId`, `chunkIndex`, `delta` (schema-shaped partial outline) | PRD FR-3.1 |
| `outlineDone` | Outline | Yes | `outlineVersionId`, `version`, `pageCount`, `sectionCount`, `deviation`, `projectVersion` | PRD FR-3.2/3.9 |
| `stageStateChanged` | Projection | Yes | `stage`, `status`, `previousStatus`, `reachable`, `staleReasons`, `projectVersion` | ARCH §8.1/§9.2 |
| `staleChanged` | Projection | Yes | `fromStage`, `cause`, `affectedPageIds`, `affectedPages`, `rerunPages`, `cascadeRatio`, `projectVersion` | PRD FR-3.12, FR-7.3 |
| `pageJobStarted` | Page jobs | Yes | `jobId`, `stage`, `pageId`, `pageType`, `kind`, `modelTier?` | PRD FR-4.2, FR-6.2 |
| `pageJobDone` | Page jobs | Yes | `jobId`, `pageId`, `kind`, `artifactVersionId`, `version`, `historyDepth`, `projectVersion` | PRD FR-4.2, FR-6.4 |
| `pageJobFailed` | Page jobs | Yes | `jobId`, `pageId`, `kind`, `errorCode`, `errorCategory`, `retryable` | PRD FR-4.8 |
| `historyPopped` | Page history | Yes | `pageId`, `kind`, `restoredArtifactVersionId`, `version`, `historyDepth`, `projectVersion` | PRD FR-6.5; DATA §7.2 |
| `jobQueued` | Jobs | Yes | `jobId`, `jobType`, `pageId?`, `waitMs?` | PRD FR-7.5 |
| `jobCancelled` | Jobs | Yes | `jobId`, `jobType`, `pageId?`, `reason?` | PRD FR-7.5 |
| `jobResumed` | Jobs | Yes | `jobId`, `jobType`, `pageId?`, `attemptCount` | PRD FR-7.5 |
| `exportProgress` | Export | Yes | `exportId`, `format`, `phase`, `pagesRendered`, `pagesTotal`, `percent` | PRD FR-6.10 |
| `exportDone` | Export | Yes | `exportId`, `format`, `artifactId`, `byteSize`, `checksum`, `expiresAt` | PRD FR-6.16 |
| `exportFailed` | Export | Yes | `exportId`, `format`, `errorCode`, `failedPageIds`, `validationResult` | PRD FR-6.15 |

Rules:

- `stageStateChanged` is an additive projection notice; it carries no new truth beyond the server-derived `project_stage_state`. A client that ignores it still converges by invalidating the snapshot on any event with a newer `projectVersion`.
- `gapSuggested` carries IDs and counts only; the client refetches `GET /research` to render labels and reasons. This keeps the durable log content-free.
- `gapSearchCompleted.outcome` is `RESULTS`, `ZERO_RESULTS`, or `FAILED`; `ZERO_RESULTS` is a recorded outcome, not an absence of an event [PRD FR-2.10].
- `outlineDelta` is the only event type that carries content, and it is ephemeral, authorized, and never persisted [ARCH §9.2]. `cardDelta` and `messageDelta` mentioned in [TECH §6.3] and [PRD §11.2] are telemetry/analytics names, not M1 SSE contract types; plan/design progress is observed through `pageJobStarted` / `pageJobDone` and the artifact query. There is no `jobFailed` stream type: non-page failures surface as `stageStateChanged` plus `GET /jobs/{jobId}`, and page failures use `pageJobFailed`.
- `exportDone` is emitted only after the artifact exists, has non-zero size, and a scoped download reference resolves [PRD FR-6.16].
- Unknown event types MUST be ignored without breaking the stream. Unknown payload fields MUST be ignored.
- Event `schemaVersion` is per type; a breaking payload change increments it and requires a client update. Additive fields do not.
- This catalog extends the architecture's event groups [ARCH §9.2] with `gapSearchCompleted` (search outcome), `stageStateChanged` (stage projection), and `historyPopped` (undo pointer change). They are notices over existing server truth, not new authoritative state.

---

## 7. Error code catalog (initial)

Codes are stable; `messageKey` is the UI lookup. This is a starter set, not an exhaustive enumeration of provider-specific causes.

| `messageKey` | Category | HTTP | Meaning |
| --- | --- | --- | --- |
| `error.auth.session_required` | forbidden | 401 | No/expired session. |
| `error.auth.invalid_credentials` | forbidden | 401 | Generic login failure. |
| `error.validation.missing_header` | validation | 400 | `Idempotency-Key` or `X-Expected-Version` absent. |
| `error.validation.empty_topic` | validation | 422 | Topic empty after trimming. |
| `error.validation.empty_paste` | validation | 422 | Paste text empty. |
| `error.validation.invalid_url` | validation | 422 | URL invalid after normalization. |
| `error.validation.unsupported_type` | validation | 422 | File type not supported. |
| `error.validation.file_too_large` | validation | 422 | File exceeds the configured cap. |
| `error.validation.upload_missing` | validation | 422 | Finalize attempted before the object exists. |
| `error.validation.unknown_question` | validation | 422 | Question key not in the current catalog. |
| `error.validation.unknown_option` | validation | 422 | Option not in the question snapshot. |
| `error.validation.gap_selection_invalid` | validation | 422 | Selected gap IDs are not in the current batch, or `webSkipped` conflicts with a non-empty selection. |
| `error.validation.empty_title` | validation | 422 | Outline title empty. |
| `error.validation.unknown_section` | validation | 422 | Section key not in the current outline. |
| `error.validation.unknown_style` | validation | 422 | Style key/version is not active. |
| `error.validation.empty_instruction` | validation | 422 | Tweak instruction empty. |
| `error.validation.notice_version_unknown` | validation | 422 | Consent references a notice version that is not current. |
| `error.validation.idempotency_key_reused` | validation | 422 | Same key, different payload. |
| `error.gate.topic_locked` | gate_violation | 409 | Topic change after intake; restart required. |
| `error.gate.material_locked` | gate_violation | 409 | Material change after research; restart required. |
| `error.gate.material_limit` | gate_violation | 409 | Material cap reached. |
| `error.gate.consent_required` | gate_violation | 409 | Data notice not accepted before material intake. |
| `error.gate.research_not_active` | gate_violation | 409 | Answer submitted outside research. |
| `error.gate.digest_incomplete` | gate_violation | 409 | Gap decision before all selected material digests resolve. |
| `error.gate.answers_incomplete` | gate_violation | 409 | Profile requested before four answers. |
| `error.gate.gaps_undecided` | gate_violation | 409 | Profile requested before gap decision. |
| `error.gate.gaps_already_decided` | gate_violation | 409 | Gap decision is immutable after profile. |
| `error.gate.profile_dirty` | gate_violation | 409 | Outline blocked until the profile is refreshed. |
| `error.gate.outline_missing` | gate_violation | 409 | Plan/confirm without an outline. |
| `error.gate.outline_unconfirmed` | gate_violation | 409 | Plan/design before outline confirmation. |
| `error.gate.outline_page_identity` | gate_violation | 409 | A page lacks a stable identity. |
| `error.gate.fixed_page_not_deletable` | gate_violation | 409 | COVER/TOC/END delete attempt. |
| `error.gate.plan_incomplete` | gate_violation | 409 | Style selection/confirmation before all plan pages are current. |
| `error.gate.style_not_selected` | gate_violation | 409 | Design before style selection. |
| `error.gate.style_unconfirmed` | gate_violation | 409 | Design before style confirmation. |
| `error.gate.design_incomplete` | gate_violation | 409 | Export before every page has a current design. |
| `error.gate.page_write_in_progress` | gate_violation | 409 | Concurrent page write. |
| `error.gate.single_layout_use_tweak` | gate_violation | 409 | Regenerate on a single-layout page. |
| `error.gate.nothing_to_undo` | gate_violation | 409 | History stack empty. |
| `error.gate.export_not_ready` | gate_violation | 409 | Download before success. |
| `error.gate.auto_advance_ineligible` | gate_violation | 409 | Expert mode or gate not eligible. |
| `error.gate.token_expired` | gate_violation | 409 | Advance token expired. |
| `error.conflict.stale_version` | conflict | 409 | Project version mismatch. |
| `error.conflict.stage_changed` | conflict | 409 | Stage changed during countdown. |
| `error.not_found.project` | not_found | 404 | Unknown/deleted project. |
| `error.not_found.outline` | not_found | 404 | No outline yet. |
| `error.not_found.artifact` | not_found | 404 | No current plan/design. |
| `error.not_found.asset` | not_found | 404 | Unknown or unreferenced asset. |
| `error.not_found.export` | not_found | 404 | Unknown export. |
| `error.rate.limited` | rate_limited | 429 | Admission rejected; see `Retry-After`. |
| `error.provider.timeout` | provider_timeout | 504 | Bounded retry allowed. |
| `error.provider.unavailable` | provider_unavailable | 503 | Degrade or retry. |
| `error.parse.url_unreachable` | parse_failure | 422 | URL fetch failure; paste-body suggestion. |
| `error.parse.type_mismatch` | parse_failure | 422 | Sniffed type differs from extension. |
| `error.export.validation_failed` | export_validation_failure | 422 | Pre-export checks failed. |
| `error.quota.exceeded` | quota_exceeded | 402 | M2 only. |
| `error.internal.unexpected` | internal | 500 | Retry once; report IDs. |

Retired keys: `error.gate.research_finished` and `error.gate.outline_locked` appeared in earlier drafts. They MUST NOT be emitted; the canonical keys are `error.gate.material_locked` and `error.not_found.outline`. Keeping the retired names here prevents a client catalog from reintroducing them.

---

## 8. Examples

### 8.1 Create a project and start research

```http
POST /api/projects
Content-Type: application/json
Idempotency-Key: 018f3f0e-8a1b-7c2d-9e3f-4a5b6c7d8e9f

{ "topic": "Dify company introduction", "mode": "FULLY_AUTOMATIC" }
```

```json
{
  "ok": true,
  "data": {
    "project": {
      "id": "018f3f10-1111-7aaa-8bbb-ccccdddd0001",
      "name": "Dify company introduction",
      "topic": "Dify company introduction",
      "mode": "FULLY_AUTOMATIC",
      "status": "ACTIVE",
      "stage": "INTAKE",
      "version": 1,
      "epoch": 1,
      "createdAt": "2026-11-19T08:00:00.000Z",
      "updatedAt": "2026-11-19T08:00:00.000Z"
    },
    "snapshot": { "project": { "…": "…" }, "stages": [], "counts": { "…": "…" } }
  },
  "meta": { "requestId": "…", "traceId": "…", "serverTime": "2026-11-19T08:00:00.010Z", "projectVersion": 1, "sequence": 1 }
}
```

### 8.2 Conflict on a stale version

```http
PATCH /api/projects/018f.../outline/pages/018f...
X-Expected-Version: 11
Idempotency-Key: 018f...
```

```json
{
  "ok": false,
  "error": {
    "category": "conflict",
    "retryable": true,
    "messageKey": "error.conflict.stale_version",
    "details": { "currentVersion": 13 },
    "requestId": "…",
    "traceId": "…",
    "retryAfterMs": null
  }
}
```

The client refetches the outline/snapshot, rebases the title edit if it is still valid, and re-issues with version 13 and a new idempotency key.

### 8.3 SSE reconnect

```
GET /api/projects/018f.../events?cursor=42
Accept: text/event-stream
```

```
event: domain
id: 43
data: {"eventId":"…","sequence":43,"projectId":"018f…","type":"pageJobDone","schemaVersion":1,"occurredAt":"2026-11-19T08:15:30.123Z","payload":{"jobId":"…","pageId":"…","kind":"PLAN","artifactVersionId":"…","version":1,"historyDepth":0,"projectVersion":14}}

event: heartbeat
data: {"serverTime":"2026-11-19T08:15:45.123Z"}
```

The client applies event 43, invalidates the page-list/artifact queries it names, and stores 43 as the new cursor.

---

## 9. Compatibility, generation, and CI gates

| Gate | Rule |
| --- | --- |
| OpenAPI | FastAPI generates `/openapi.json`; `npm run gen:api` writes `frontend/src/api/schema.d.ts`; CI fails if the committed file differs [TECH §5.5]. |
| Shared schemas | Pydantic event/artifact models export JSON Schema to `shared/schemas/`; `npm run gen:shared` generates TypeScript; CI fails on diff. |
| Unknown fields | Clients ignore unknown response fields and unknown event types. Servers never depend on client-supplied unknown fields. |
| Enum additions | Server may add enum values; client renders a neutral fallback for unknown values and refetches. Removing/renaming a value is breaking. |
| Event versioning | Additive payload fields do not bump `schemaVersion`. Removing/renaming/retyping a field does, and requires a coordinated client release. |
| Command compatibility | A command's required fields may be added only with a default or a new endpoint; existing required fields may not be removed. |
| Error keys | `messageKey` values are stable. A renamed key is a breaking change. |
| Contract tests | Pydantic/OpenAPI tests cover every command/query; MSW fixtures in the frontend use the generated types [TECH §15]. |

### 9.1 Traceability

| Contract area | Requirement groups |
| --- | --- |
| Auth/session/config/consent | PRD FR-1.12, NFR-SEC-1/3, NFR-PRIV-4, TECH §6.4 |
| Projects/snapshot | PRD FR-1.1, FR-7.8/7.9, FR-8.1/8.2 |
| Materials/sources | PRD FR-1.3–1.12, FR-2.15 |
| Research/profile | PRD FR-2.1–2.21 |
| Outline | PRD FR-3.1–3.15 |
| Pages/artifacts/history/assets | PRD FR-4.1–4.11, FR-6.1–6.9, FR-6.12/6.17, FR-7.7 |
| Style | PRD FR-5.1–5.6 |
| Design/export | PRD FR-6.2–6.21 |
| Jobs/cancel | PRD FR-7.5/7.6, NFR-REL-3/4 |
| SSE/reconnect | PRD FR-7.9, NFR-PERF-3, ARCH AD-10 |
| Stale/advance | PRD FR-3.11/3.12, FR-7.3, NFR-COST-3, ARCH AD-9 |
| Errors/privacy | PRD §8.9.2, NFR-PRIV-3, ARCH §9.3 |

---

## 10. Open contract questions

| ID | Question | Owner / stage |
| --- | --- | --- |
| API-Q1 | Material add/remove after research: restart-only (this contract) vs re-search (FR-2.18). | Product + backend · before M1 |
| API-Q2 | Outline edits after confirmation: allow + reconfirm (this contract) vs lock until explicit reopen. | Product + UX · before M1 |
| API-Q3 | Partial export policy: whether `ExportDTO.deckSnapshot.excludedPageIds` may be non-empty on success. | Product + UX · M1 (PRD-03) |
| API-Q4 | Idempotency-key retention window and client key format. | Backend · before pilot (ARCH AQ-11) |
| API-Q5 | Event-log retention / full-resync threshold, which determines how often `resync` occurs. | Ops + architecture · before pilot (ARCH AQ-3) |
| API-Q6 | Exact shared artifact body schema and layout vocabulary versioning. | Backend + design · before plan implementation |
| API-Q7 | Whether `POST /research/profile` performs model work synchronously or enqueues a `PROFILE` job in all cases. | Backend · before implementation |
| API-Q8 | Browser support for streaming `fetch`/`ReadableStream` and SSE reconnect. | Frontend · before M1 (PRD-06) |

---

## 11. Change log

| Version | Date | Change |
| --- | --- | --- |
| v1.1 | 2026-11-19 | Reconciliation pass: added `SEARCH` job type, `GET /api/config`, policy notice/consent endpoints, asset content endpoint, `gapSearchCompleted`, snapshot `styleSelection`, research `gapSearches`, `UNDO` stale cause, and missing error keys; removed stale `research_finished`/`outline_locked` references. |
| v1 | 2026-11-19 | Initial wire contract: conventions, envelopes, enums, DTOs, 51 endpoints, SSE event catalog, error catalog, examples, compatibility/CI gates, traceability, open questions. |
