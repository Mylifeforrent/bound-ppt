# Bound PPT · Frontend Design (v1.1)

> Version: v1.1 · 2026-11-19 · Status: Draft · Owner: Frontend
> Requirements source: `docs/ppt-agent-prd.md` (v1). State/precedence source: `docs/ppt-agent-architecture.md` (v1.1). Stack source: `docs/ppt-agent-tech-stack.md` (v2.1). Wire source: `docs/ppt-agent-api-contracts.md` (v1.1). Interaction source: `docs/ppt-agent-interaction-flow.md` (v3).
> This document owns the SPA structure, client state split, API/SSE client, renderer integration, screen behavior, accessibility, responsiveness, performance, and frontend testing. It does not own product behavior, wire shapes, server state, or visual design tokens. Endpoint paths, DTO field names, enum values, SSE event names, and error `messageKey` values in this document are quoted from the wire contract and are normative only as references.

---

## 1. Document control

### 1.1 Metadata

| Field | Value |
| --- | --- |
| Document / version / date | Bound PPT Frontend Design / v1 / 2026-11-19 |
| Status / owner / audience | Draft / Frontend / engineering, design, QA, security review |
| Precedence | PRD (behavior, acceptance) > Architecture (state ownership, consistency) > Tech stack (implementation choices) > API contracts (wire shapes) > this document (UI implementation). |
| Scope | React SPA structure, routing, client state, API/SSE consumption, deck rendering, screen behavior, accessibility, responsive rules, frontend performance, error surfaces, frontend test plan |
| Out of scope | Product behavior and gates, server state semantics, OpenAPI generation internals, visual brand design, prompt/model behavior, export file generation, browser support freeze (PRD-06), PPTX fidelity bar (PRD-07) |
| Wire authority | On any conflict between this document and `docs/ppt-agent-api-contracts.md`, the API document wins for paths, DTO fields, enums, headers, SSE names, and `messageKey` values; the conflict is logged in §18 and this document is corrected. |

**Normative language.** MUST / MUST NOT / DEFAULT follow [PRD §8.1] and [PRD §1.4]. `[TBD-*]` marks a decision owned elsewhere and is not permission to invent a value. `[ASSUMPTION]` marks a frontend premise that requires validation.

### 1.2 Terms

| Term | Meaning |
| --- | --- |
| **Server state** | Anything the API owns: project, stage, status, stale flags, job state, history, page artifacts, export state [ARCH §8.7]. |
| **View state** | Client-only UI state that is never sent as project state: selection, pin, modals, countdown, drafts. |
| **Intent** | One logical user command with a stable `Idempotency-Key` reused across retries of that same intent [API §2.8]. |
| **Snapshot** | `ProjectSnapshotDTO` plus `meta.projectVersion` and `meta.sequence`; the reconnect and seeding read [API §2.6, §4.2 P2]. |
| **Cursor** | Last applied durable SSE `sequence`, sent as `?cursor=` on reconnect [API §4.12]. |
| **Reachability** | Server-derived `StageStateDTO.reachable`; the only source for route guards [API §3.3]. |
| **Advance token** | `StageStateDTO.advanceToken` issued by the server for a validated auto-advance window [API §4.5 O8]. |
| **App tokens** | Shell color/type/spacing tokens (Tailwind/shadcn). |
| **Deck theme** | `shared/themes/*.json` and `DesignBodyV1.style.tokens`; deck content, never the app theme [TECH §5.2]. |
| **Pinned page** | Client-only page lock during generation; never changes scheduling [PRD FR-6.3]. |
| **Rerun-on-entry** | Calling the stage's generate command once when entering a stale stage; server computes the incremental scope [PRD FR-7.3]. |

---

## 2. Scope and decision summary

### 2.1 Frontend decisions

| ID | Decision | Rationale / constraint |
| --- | --- | --- |
| FE-1 | React 19 + TypeScript 5.x `strict` + Vite SPA. No SSR, no Next.js, no server components. | Frozen client stack [TECH §3.1]. |
| FE-2 | React Router owns all client routes; production uses an SPA fallback that never swallows `/api/*`. | [TECH §5.1]. |
| FE-3 | Tailwind CSS 4 + shadcn/ui source components on Radix primitives; Lucide inline SVG icons; no emoji as structural icons. | [TECH §5.2; FLOW §5]. |
| FE-4 | TanStack Query owns all server state, caching, invalidation, and mutation lifecycles. | [TECH §5.3]. |
| FE-5 | Zustand owns local view state only. It MUST NOT store stage, status, stale, history, job, or export truth. | [ARCH AD-1; TECH §5.3]. |
| FE-6 | React Hook Form + Zod own form state and client validation; schemas reuse generated types where possible. | [TECH §3.1]. |
| FE-7 | dnd-kit (pointer, touch, keyboard sensors) for sticky-note ordering; keyboard alternatives are always present. | [PRD FR-3.8; TECH §5.4]. |
| FE-8 | Motion for transitions and fly-in; `useReducedMotion` is a hard gate, never decorative-only. | [PRD FR-7.12]. |
| FE-9 | Sonner for transient notifications; a toast is never the only signal for a required state. | [TECH §5.4]. |
| FE-10 | API/SSE types come from `openapi-typescript` (`src/api/schema.d.ts`) and generated shared-schema types; hand-written interfaces are limited to UI-only shapes. | [API §9; TECH §5.5]. |
| FE-11 | The client is a projection. Stage, reachability, status, stale, history, job, and export state are rendered from the API and SSE events, never computed from timers or local flags. | [ARCH §8.7; PRD FR-7.9]. |
| FE-12 | SSE is consumed with `fetch` + `ReadableStream`, not native `EventSource`; the client sends `cursor`, aborts on unmount, and is MSW-interceptable. | [TECH §6.3]. |
| FE-13 | Same-origin deployment: HttpOnly session cookie, no bearer token in JavaScript, no CORS, SSE same-origin. | [TECH §6.4; API §2.1]. |
| FE-14 | Export formats are exactly `PPTX`, `HTML`, `PDF`. No SVG, image, or ZIP export option exists. | [API §3.1; PRD CR-6]. |
| FE-15 | The only client-owned timing is the 3-second outline countdown; the advance is server-validated with `advanceToken`. | [ARCH AD-9/§8.8; PRD FR-3.11]. |
| FE-16 | M1 style memory is project-scoped through `PUT /api/projects/{projectId}/style` with `rememberPreference`; `localStorage` is not an M1 store. | [API §4.8 S3; ARCH §14; PRD FR-5.4]. |

### 2.2 Not decided here

| Item | Owner / stage |
| --- | --- |
| Browser support matrix | `[TBD-FE · frontend, before M1]` (PRD-06, API-Q8) |
| PPTX fidelity acceptance wording shown in the export modal | `[TBD-BIZ · product + engineering, before M1]` (PRD-07) |
| Material default cap and pre-project limit exposure | `[TBD-UX · design, visual design stage]` / `[TBD-BE · backend, before M1]` |
| Partial export policy | `[TBD-UX · product, M1]` (PRD-03, API-Q3) |
| UI locale | `[TBD-BIZ · product, M1]` (PRD-05); the client uses one message catalog and no runtime i18n framework in M1 |
| Deck asset content delivery | `GET /api/projects/{projectId}/assets/{assetId}` (`302` signed, authorized); never a signed URL inside the artifact body [API §4.6 PG4] |

---

## 3. Runtime and routing

### 3.1 Routes

| Route | Screen | Guard |
| --- | --- | --- |
| `/` | Home / new project (intake form) | Authenticated; no project required. |
| `/login` | Sign-in | Unauthenticated only; authenticated users are redirected to `/`. |
| `/projects/:projectId` | Stage dispatcher; redirects to the route of the current server stage (`INTAKE` → intake) | Snapshot loaded. |
| `/projects/:projectId/intake` | Material intake; editable at `INTAKE`, read-only with a restart affordance afterwards | Always reachable [PRD §7.3]. |
| `/projects/:projectId/research` | Research + interview | `RESEARCH` reachable. |
| `/projects/:projectId/outline` | Outline | `OUTLINE` reachable. |
| `/projects/:projectId/plan` | Plan draft | `PLAN` reachable. |
| `/projects/:projectId/style` | Style selection | `STYLE` reachable. |
| `/projects/:projectId/design` | Design draft + export modal | `DESIGN` reachable. |
| `*` | Not-found screen with a link to `/` | None. |

The URL never encodes stage truth. A route is a requested view; the snapshot decides whether it is reachable. Back navigation within a project is allowed to any reachable earlier stage [PRD §7.3].

### 3.2 Bootstrap sequence

1. `GET /api/auth/me`. `401` (`error.auth.session_required`) redirects to `/login?returnTo=<route>`; network failure shows a retry screen, not a login redirect.
2. If the route contains `:projectId`, `GET /api/projects/{projectId}/snapshot`. Seed `['project', id, 'snapshot']` with the response and keep `meta.projectVersion` and `meta.sequence` as the version/cursor baseline.
3. If the route is `/projects/:projectId`, replace the URL with the current stage's route (`INTAKE` → `/projects/:projectId/intake`). Never auto-enter a stage the server has not marked reachable.
4. If the requested stage is not reachable, replace with the deepest reachable stage and show an inline notice resolved from the first `StageStateDTO.blockers[].messageKey` (for example `error.gate.profile_dirty`). No locked screen is shown.
5. Start the SSE subscription from `snapshot.sequence` (§7). The stream starts only after the snapshot is committed to the cache, so a replayed event cannot race a stale snapshot.
6. On `projectId` change, abort the stream, clear project-scoped queries and stores, then repeat steps 2–5.

A refresh or a new tab repeats this sequence; there is no client-side project persistence layer [TECH §5.1].

### 3.3 Deep links and redirects

| Situation | Behavior |
| --- | --- |
| Deep link to a reachable earlier stage | Render it; the stage is not forced forward. |
| Deep link to an unreachable future stage | `replace` to the deepest reachable stage; banner names the blocker `messageKey`. |
| Deep link to a project the session cannot access | `404 error.not_found.project` renders the not-found screen; a `403` renders access denied; neither response reveals whether the project exists [API §4]. |
| Project at `INTAKE` | `/projects/:projectId` redirects to `/projects/:projectId/intake`; stage routes redirect there. |
| Intake after research | The intake route is reachable but read-only; edit actions are disabled with a restart affordance, and the API still enforces `409 error.gate.material_locked` / `409 error.gate.topic_locked`. |
| Restart completes (`202`) | Seed the returned snapshot, clear all project queries, navigate to `/projects/:projectId/intake`. |
| Project deleted (`202`) | Abort the stream, clear all project queries, navigate to `/`; deletion is asynchronous, so no success beyond "Deletion requested" [API §4.2 P5]. |
| `401` on any request | Clear the query cache, abort the stream, redirect to `/login?returnTo=...`. |
| `403` | Access-denied screen; no retry loop. |

### 3.4 Static build and development

| Concern | Rule |
| --- | --- |
| Build | `npm run build` emits `frontend/dist`; assets are content-hashed and immutable; `index.html` is `no-store`. |
| SPA fallback | Production serves `index.html` for non-`/api` paths; `/api/*` and `/api/health*` are never swallowed [TECH §5.1; API §4.13]. |
| Dev proxy | Vite proxies `/api` to `http://127.0.0.1:8000`; SSE must not be buffered by the proxy [API §2.1]. |
| Cookies | `fetch` uses `credentials: "same-origin"`; no Authorization header; no token in JS or storage [TECH §6.4]. |
| Code splitting | One route-level chunk per stage feature; the deck renderer and export modal are separate chunks (§14). |
| Error boundary | A route-level React error boundary renders a content-free failure card with a reference ID and a reload action. |

---

## 4. Directory layout

```
frontend/src/
  api/                 client.ts, errors.ts, keys.ts, endpoints/*.ts, schema.d.ts (generated)
  pages/               HomePage, LoginPage, ResearchPage, OutlinePage, PlanPage, StylePage, DesignPage, NotFoundPage
  features/
    intake/            topic form, mode selector, material composer, upload queue
    research/          conversation, question cards, digest, gaps, profile card, source panel
    outline/           sticky board, note, section, insert/move/delete, countdown bar
    plan/              page list, wireframe canvas, progress, tweak panel
    style/             style gallery, style card, palette, remember preference
    design/            workbench, thumbnail rail, canvas, page actions, history
    export/            export dialog, format picker, scope summary, progress, failure
  render/              deck renderer: canvas, layouts, blocks, chrome, thumbnails, themes
  components/ui/       shadcn/ui source components
  hooks/               useProjectStream, useStageNavigation, useCountdown, useArtifactQuery, useIdempotentMutation
  stores/              Zustand view stores: selection, modal, countdown, drafts, panels
  lib/                 messages.ts, format.ts, ids.ts, analytics.ts, clamp.ts
  styles/              tailwind.css, app-tokens.css, deck-theme.css
  test/                MSW handlers, fixtures, render helpers
```

| Folder | Owns | Import rules |
| --- | --- | --- |
| `api/` | HTTP wrapper, generated types, query keys, endpoint functions | MUST NOT import React, stores, pages, or features. |
| `pages/` | Route composition, page-level loading/error shells | MAY import features and render; MUST NOT contain deck layout CSS. |
| `features/*` | One stage's components, hooks, and forms | MAY import `api`, `render`, `components/ui`, `hooks`, `lib`; MUST NOT import another feature's internals. |
| `render/` | Deck body → DOM; layout registry, block registry, chrome, canvas scaling | MUST depend only on generated body types, shared layout/theme JSON, and `lib`; MUST NOT call the API or read stores. |
| `components/ui/` | App primitives | No project or stage knowledge. |
| `hooks/` | Cross-feature client behavior (stream, countdown, navigation) | MAY import `api`, `stores`, `lib`; MUST NOT import feature internals. |
| `stores/` | View state slices | No API calls, no server truth. |
| `lib/` | Pure utilities, message catalog | No React, no API calls. |
| `styles/` | App tokens, global CSS, deck theme scoping | Deck theme selectors are scoped under `.deck-root` only. |

Enforced with ESLint `import/no-restricted-paths` in CI; a violating import fails the build.

---

## 5. State architecture

### 5.1 Four state classes

| Class | Owner | Rules |
| --- | --- | --- |
| Server state | TanStack Query | Keyed by project and resource; seeded by snapshot/mutation responses; updated by event invalidation/merge. It is the only render source for stage, status, stale, history, and counts. |
| Local view state | Zustand | Selection, pin, modals, panel state, countdown, drafts, focus. Namespaced by `projectId` and reset on project change or `epoch` change. |
| Form state | React Hook Form + Zod | Field values and client messages; submit maps to one intent and one idempotency key. |
| Ephemeral stream state | `useProjectStream` reducer | Partial outline notes and connection state only. Never persisted, never treated as a committed artifact, discarded on `outlineDone`, resync, stage exit, or unmount [ARCH §9.2]. |

DEFAULT: server responses replace local state; optimistic UI is limited to title drafts, reorder preview, chip add/remove, and selection highlight [ARCH §8.7; TECH §5.3].

### 5.2 Query key registry

| Key | Endpoint | Primary consumers |
| --- | --- | --- |
| `['auth','me']` | `GET /api/auth/me` | App shell, login redirect. |
| `['project', id, 'snapshot']` | `GET /api/projects/{projectId}/snapshot` | Shell, all stage guards, counts, mode badge, restart/delete dialogs. |
| `['project', id, 'materials']` | `GET /api/projects/{projectId}/materials` | Intake material list (after project creation). |
| `['project', id, 'research']` | `GET /api/projects/{projectId}/research` | Research conversation, questions, digest, gaps, profile, counts. The embedded `sources` field is ignored by the conversation model. |
| `['project', id, 'sources']` | `GET /api/projects/{projectId}/sources` | Source panel only; isolated so source arrivals do not re-render the conversation. |
| `['project', id, 'outline']` | `GET /api/projects/{projectId}/outline` | Outline board, counts, deviation, confirmation state. |
| `['project', id, 'pages']` | `GET /api/projects/{projectId}/pages` | Plan page list, design thumbnails, progress, statuses. |
| `['project', id, 'page', pageId, 'artifact', kind]` | `GET /api/projects/{projectId}/pages/{pageId}/artifacts/{kind}` | Plan canvas (`kind="plan"`), design canvas (`kind="design"`). |
| `['project', id, 'history', pageId, kind]` | `GET /api/projects/{projectId}/pages/{pageId}/history?kind={kind}` | Design "Previous version" availability and variant counts. |
| `['project', id, 'job', jobId]` | `GET /api/projects/{projectId}/jobs/{jobId}` | Fallback polling after a stream gap; cancellation dialog state. |
| `['project', id, 'export', exportId]` | `GET /api/projects/{projectId}/exports/{exportId}` | Export modal status, validation, artifact. |
| `['styles']` | `GET /api/styles` | Style gallery. |
| `['style', styleKey, version]` | `GET /api/styles/{styleKey}?version={version}` | Preview refresh when a signed `previewUrl` expires; pinned-version resolution. |
| `['config']` | `GET /api/config` | Pre-project material limit, supported types, formats, canvas; fetched once per session. |
| `['policy', 'notices']` | `GET /api/policy/notices` | Data-handling notice and consent state; gates material intake. |

Query defaults: no `placeholderData` for project truth; the snapshot response is used as `initialData` for its own key; artifacts use `structuralSharing` off (immutable bodies); every key includes `projectId` so switching projects cannot show another project's data.

### 5.3 Event → cache action map

`Merge` means patching only the named fields of a cached DTO from event metadata; it is a server-authored patch, not a computation. `Invalidate` marks the key stale and refetches it if mounted. Unknown event types are ignored [API §6].

| Event | Action | Targets | Notes |
| --- | --- | --- | --- |
| `projectCreated` | No-op | — | Creation is consumed from the `201` response and snapshot. |
| `materialStatusChanged` | Invalidate | `materials`, `research` | Adds per-material status/error; content is refetched. |
| `sourceAdded` | Invalidate | `sources` | Metadata only; titles/summaries require the query [API §6]. |
| `digestReady` | Invalidate | `research`, `sources` | Digest card and material group. |
| `questionAsked` | Invalidate | `research` | Prompt/options are content; never derived from the event. |
| `answerRecorded` | Merge | `research` (`questions[key].answer`, `profileDirty`) | Cross-tab answer convergence without a refetch. |
| `gapSuggested` | Invalidate | `research` | Labels/reasons are content-bearing. |
| `gapDecided` | Invalidate | `research` | Decision state. |
| `gapSearchCompleted` | Invalidate | `research`, `sources` | Per-gap `RESULTS`/`ZERO_RESULTS`/`FAILED`; no query text in the event. |
| `profileReady` | Invalidate | `research`, `snapshot` | Pointer and `profileDirty`. |
| `profileUpdated` | Invalidate | `research`, `snapshot`, `outline`, `pages` | Outline may become unconfirmed; plan/design may be stale. |
| `outlineDelta` | Ephemeral | Stream reducer only | No query cache; discarded on `outlineDone`/resync. |
| `outlineDone` | Invalidate | `outline`, `pages`, `snapshot` | Replaces the ephemeral board with the committed outline. |
| `stageStateChanged` | Invalidate | `snapshot` | Cheapest convergence; protects nav/gates. |
| `staleChanged` | Invalidate | `snapshot`, `pages` | Stage amber dot and page stale statuses. |
| `pageJobStarted` | Merge | `pages` (`plan.status`/`design.status` = `PLANNING`/`DESIGNING`) | `activeJob` is not synthesized; page actions also gate on status. |
| `pageJobDone` | Merge + invalidate | Merge `pages` status/version/historyDepth; invalidate `page artifact`, `history`, `snapshot` | Snapshot invalidation is debounced 250 ms trailing during a deck fan-out. |
| `pageJobFailed` | Invalidate | `pages`, `snapshot` | Full `PageError.messageKey` is only authoritative in the query. |
| `historyPopped` | Invalidate | `page artifact`, `history` | Undo from another tab or the same tab converges. |
| `jobQueued` | No-op | — | Page status will move on `pageJobStarted`. |
| `jobCancelled` | Invalidate | `pages`, `snapshot`, `job` | Status returns to a stable state; cancellation is never success. |
| `jobResumed` | No-op | — | Page remains in its active status. |
| `exportProgress` | Merge | `export.progress` (`phase`, `pagesRendered`, `pagesTotal`, `percent`) | No state promotion; only `exportDone`/`exportFailed` change state. |
| `exportDone` | Invalidate | `export` | `artifact`/`fileName`/`downloadPath` are only in `ExportDTO`; no success toast before it resolves. |
| `exportFailed` | Invalidate | `export` | `validation.failedChecks` and `error.messageKey` come from the query. |

Stream control frames: `snapshot` replaces every project-scoped cache with the framed snapshot and resets the cursor; `resync` invalidates the snapshot and every mounted project query, then resubscribes from the new sequence; `heartbeat` resets the liveness timer only [API §4.12].

### 5.4 Zustand slices

| Slice | Shape | Reset |
| --- | --- | --- |
| `selection` | `selectedPageId`, `pinnedPageId`, `lastDesignPageId` | Project change; page removal selects the nearest page. |
| `modals` | `restartOpen`, `deleteOpen`, `exportOpen`, `confirmPageDeleteId`, `changeMaterialsOpen` | Route change, Esc, successful action. |
| `countdown` | `stage`, `token`, `tokenExpiresAt`, `deadlineAt`, `remainingMs`, `paused`, `pauseReason` | Any outline mutation, navigation, `outlineDone` replay, token expiry, unmount. |
| `drafts` | `outlineTitle[pageId]`, `planTweak[pageId]`, `designTweak[pageId]`, `topic`, `materialComposer` | Successful save, discard, route change. |
| `panels` | research source panel collapsed, source group expanded, nav mobile open, zoom mode | Project change. |
| `styleDraft` | `selectedStyleKey`, `rememberPreference` | Successful `PUT /api/projects/{projectId}/style`, stage exit. |
| `exportUi` | `format`, `lastExportId`, `openedFromPageId` | Modal close. |

MUST NOT be stored: stage, stage status, reachability, stale flags, page status, history depth, job state, export state, counts, `project.version`. These are read from queries and events [ARCH AD-1; PRD FR-7.9].

### 5.5 Form schemas and messages

| Form | Schema | Client message key | Server key mapped |
| --- | --- | --- | --- |
| Topic | `topic: string.trim().min(1).max(TBD-BE)`; `mode: ProjectMode` | `ui.form.topic_required` | `error.validation.empty_topic` |
| Paste material | `text: string.trim().min(1)`; `displayName?: string` | `ui.form.paste_required` | `error.validation.empty_paste` |
| URL material | `url: string` normalized to `https://`; `new URL()` must parse | `ui.form.url_invalid` | `error.validation.invalid_url` |
| Answer | `optionKey: string` from the current question options | `ui.form.answer_required` | `error.validation.unknown_option` |
| Gap decision | `selectedSuggestionIds: string[]`; `webSkipped: boolean`; `webSkipped=true` requires an empty selection | `ui.form.gap_web_skip_conflict` | `error.validation.gap_selection_invalid` |
| Outline title | `title: string.trim().min(1)` | `ui.form.title_required` | `error.validation.empty_title` |
| Insert page | `sectionKey: string`; `title: string.trim().min(1)`; `keyPoints: string[]` | `ui.form.title_required` | `error.validation.unknown_section` |
| Tweak | `instruction: string.trim().min(1)` | `ui.form.instruction_required` | `error.validation.empty_instruction` |
| Style | `styleKey: string`; `styleVersion: number`; `rememberPreference: boolean` | `ui.form.style_required` | `error.gate.style_not_selected` |
| Export | `format: PPTX or HTML or PDF` | `ui.form.format_required` | `error.gate.design_incomplete` |

Client keys use the `ui.*` namespace so they never collide with the stable server `error.*` namespace. When a server `messageKey` is present it wins over the client message; the catalog resolves both.

---

## 6. API client

### 6.1 Request pipeline

1. Build the URL from `/api/...`; add `Content-Type: application/json` for bodies.
2. Add `X-Request-Id` (client UUID) for correlation.
3. Add `Idempotency-Key` on every command (`POST`/`PUT`/`PATCH`/`DELETE`) except `POST /api/auth/login` and `POST /api/auth/logout`.
4. Add `X-Expected-Version` on project-scoped commands from the latest observed `project.version`.
5. `fetch` with `credentials: "same-origin"` and an `AbortSignal`; parse JSON once.
6. `ok: true` → return `data` plus `meta` to the caller; commands update the version baseline from `meta.projectVersion`.
7. `ok: false` → normalize to `AppError` and throw; never render the envelope `details` object raw.

### 6.2 Envelope and `AppError`

`data` is never null on success; a no-payload command returns `{}` [API §2.6]. `AppError` is a UI-only type:

```ts
type AppError = {
  category: string; retryable: boolean; messageKey: string;
  details: Record<string, unknown>; requestId: string; traceId: string;
  retryAfterMs: number | null; httpStatus: number;
};
```

Unknown enum values and unknown fields render a neutral fallback and refetch the snapshot; they MUST NOT crash a screen [API §2.2/§2.3]. `messageKey` is resolved by `src/lib/messages.ts`; a missing key renders a generic message plus the key and a copy-reference action. The server never sends prose [API §2.7].

### 6.3 Idempotency and version baseline

| Concern | Rule |
| --- | --- |
| Key generation | A client-generated UUID: `crypto.randomUUID()` (UUID v4) is the default; a UUIDv7 helper is acceptable when sortable keys are preferred. IDs are opaque to the server. |
| Intent identity | Key stored in memory with an intent descriptor `(method, path, targetId, canonicalPayloadHash)`. |
| Retry/timeout/`429`/`503` | Reuse the same key and the same body. No new job or charge on replay [API §2.8]. |
| User correction | A changed field produces a new intent and a new key. |
| `409 conflict` rebase | Refetch, rebase, then re-issue as a new intent with a new key [API §8.2]. |
| `422 error.validation.idempotency_key_reused` | Bug signal: regenerate the key, surface a content-free error, and report the `requestId`. |
| Version source | `meta.projectVersion` from the latest snapshot or command response; never `+1` locally. |
| Missing version | `POST /api/projects` and auth commands carry no `X-Expected-Version` [API §4.2 P1]. |
| Non-project commands | `GET /api/styles` and `POST /api/auth/*` carry no version/idempotency key where the contract exempts them. |

### 6.4 Conflict and retry policy

| Response | Client action |
| --- | --- |
| Network error / `5xx` on a query | Automatic retry with jittered backoff (max 2), then an inline retry card. |
| `429` / `503` on a command | Wait for `Retry-After` (`retryAfterMs`), then retry once with the same key; generation commands show a "busy" state instead of an automatic retry. |
| `409 conflict` (`error.conflict.stale_version`, `error.conflict.stage_changed`) | Refetch the snapshot and the affected query; rebase a title edit if still valid; prompt before re-issuing destructive intents (`DELETE` page, move, style change). |
| `409 gate_violation` | No retry. Resolve `messageKey` to a banner/toast and refetch the snapshot. |
| Other `4xx` | No automatic retry [API §2.5]. |
| Generation / export commands | Never auto-retried; the user retries explicitly or relies on server jobs. |
| Unmount | Abort the request; the mutation result is not replayed automatically. |
| Tab close | No queued writes; only committed server state survives [ARCH §8.9]. |

### 6.5 Upload and download

**Upload** (file material): `POST /api/projects/{projectId}/materials/upload-url` → browser `PUT` to `upload.url` with exactly `upload.headers` and `method` (`PUT`) → `POST /api/projects/{projectId}/materials/{materialId}/finalize`. The presigned PUT uses `XMLHttpRequest` solely to expose upload progress; no API credentials or cookies are attached to the storage request. File bytes never pass through the API process [API §4.3 M4/M5]. On expiry (`upload.expiresAt`) or failure, request a new upload URL; a `PENDING` material can be removed with `DELETE /api/projects/{projectId}/materials/{materialId}`.

**Download**: offered only when `ExportDTO.state="SUCCEEDED"` and `artifact` is non-null. The button navigates to `artifact.downloadPath` (`/api/exports/{exportId}/download`), which returns `302` to a short-lived signed URL [API §4.11 E3]. The signed URL is never fetched by JS, copied to analytics, or logged. A failed navigation after a successful state is treated as a content-free error with a re-check action.

**Artifacts**: `GET /api/projects/{projectId}/pages/{pageId}/artifacts/{kind}` sends `If-None-Match: "<contentDigest>"`; `304` keeps the cached body, which is safe because artifact bodies are immutable per version [API §2.4/§4.6]. `404 error.not_found.artifact` for a pending page is rendered as a skeleton, not an error.

### 6.6 Response → cache seeding

| Command | Status | Cache action |
| --- | --- | --- |
| `POST /api/projects` | `201` | Seed `snapshot` and `project` from the response. |
| `POST /api/projects/{projectId}/restart` | `202` | Seed `snapshot`/`project`; clear every other project query and the stream; this `202` already contains the reset snapshot [API §4.2 P4]. |
| `POST /api/projects/{projectId}/research/start` | `202` | Response has `stage`/`stageStatus`/`jobIds` but no snapshot: invalidate `snapshot`, await it, then navigate. |
| `PUT /api/projects/{projectId}/research/answers/{questionKey}` | `200` | Merge the returned `question`, `profileDirty`, and `stale` into `research`; invalidate `snapshot` only when `stale` is non-null. |
| `POST /api/projects/{projectId}/research/gaps/decisions` | `202` | Invalidate `research`; the job IDs are not completion. |
| `POST /api/projects/{projectId}/research/profile` | `200` | Invalidate `research` and `snapshot`; `outlineUnconfirmed`/`stale` drive the banners. |
| `POST /api/projects/{projectId}/outline/confirm` | `200` | Seed `outline`, `stage`, and `snapshot` from the response. |
| Outline `PATCH`/`POST`/`DELETE`/`move` | `200` | Replace `outline` from the response; invalidate `snapshot` and `pages` when `stale` is non-null. |
| `POST /api/projects/{projectId}/stages/advance` | `200` | Apply `project`/`stages` to the cached snapshot, invalidate `snapshot` for counts, then navigate. |
| `PUT /api/projects/{projectId}/style` | `200` | Merge `styleSelection` into the cached snapshot (the snapshot carries `styleKey`/`styleVersion`/`confirmed`), so a refresh restores the selection. |
| `POST /api/projects/{projectId}/style/confirm` | `200` | Merge `styleSelection` and `stage`; invalidate `snapshot`; `stale` drives the design marker. |
| `POST /api/projects/{projectId}/plan/generate`, `POST /api/projects/{projectId}/design/generate` | `202` | Invalidate `pages` and `snapshot`; the `202` is acceptance, not completion. |
| `POST /api/projects/{projectId}/pages/{pageId}/plan/regenerate`, `POST /api/projects/{projectId}/pages/{pageId}/plan/tweak`, `POST /api/projects/{projectId}/pages/{pageId}/retry`, `POST /api/projects/{projectId}/pages/{pageId}/design/regenerate`, `POST /api/projects/{projectId}/pages/{pageId}/design/tweak` | `202` | Invalidate `pages`; the artifact is refetched on `pageJobDone`. |
| `POST /api/projects/{projectId}/pages/{pageId}/undo` | `200` | Seed the returned `artifact` and `history`; invalidate `pages` when `stale` is non-null. |
| `POST /api/projects/{projectId}/exports` | `202` | Seed `['project', id, 'export', exportId]` with the returned `ExportDTO`; progress arrives by event. |

---

## 7. SSE hook

### 7.1 Connection contract

`useProjectStream(projectId, initialCursor)` opens `GET /api/projects/{projectId}/events?cursor={sequence}` with `Accept: text/event-stream`, `credentials: "same-origin"`, and an `AbortController`. It parses frames from the byte stream with `TextDecoder`, splitting on `\n\n` and reading `event:`, `id:`, and `data:` lines. Comment lines (`:`) and `event: heartbeat` both count as liveness. It does not use `EventSource` (no abort, no cursor header, no MSW interception) [TECH §6.3].

The client does not set `Last-Event-ID`; the server accepts it only when `cursor` is absent, which is reserved for proxies and a future native client [API §2.4/§4.12].

### 7.2 State machine

| State | Entry | Exit |
| --- | --- | --- |
| `idle` | No project, route `/` or `/login` | Project id present → `connecting`. |
| `connecting` | `fetch` started, no frame yet | First `snapshot`/`domain`/`heartbeat` → `live`; failure → `reconnecting`; `401` → `closed`. |
| `live` | Frames arriving; heartbeat timer running | Stream error, abort, 45 s without any frame → `reconnecting`; `resync` → `resyncing`; unmount → `closed`. |
| `reconnecting` | Backoff scheduled (base 500 ms, factor 1.8, cap 15 s, full jitter) | Attempt starts → `connecting`; user logout → `closed`. |
| `resyncing` | `resync` frame received | Snapshot refetch completes; resume from new `sequence` → `connecting`; failure → retry card. |
| `closed` | Unmounted, logged out, project deleted | Terminal for the hook instance. |

The shell shows a `role="status"` connection banner only for `reconnecting`/`resyncing`; a healthy stream is silent.

### 7.3 Cursor, dedupe, and recovery

- Cursor is the last applied durable `sequence`; it is kept in a ref and mirrored to `sessionStorage` (`bound:cursor:<projectId>`) as a refresh fallback. Once a snapshot loads, `snapshot.sequence` MUST replace the stored cursor.
- Durable events are applied only when `sequence > appliedSequence`; an eventId LRU (200 entries) guards replays. Out-of-order older events are dropped.
- Ephemeral frames have no `id` and never move the cursor [API §4.12]. `outlineDelta` is deduped by `(jobId, chunkIndex)`; a chunk-index jump marks the streamed board as incomplete, and the board is replaced by the committed outline on `outlineDone`.
- `resync` MUST NOT be followed by applying queued events; the client refetches the snapshot, resets project queries, and resumes from the framed `latestSequence`. If `snapshotAvailable` is false, the stage shows a blocking retry card.
- Subscription lifecycle: subscribe after the snapshot; abort on route leave, project change, logout, and unmount. Background jobs continue server-side; returning re-reads the snapshot [PRD FR-7.5].
- Multi-tab: each tab owns its own stream and cursor. Every tab receives the same events and converges through invalidation. The countdown is local to each tab; a losing tab's advance returns `409 error.gate.auto_advance_ineligible` or `409 error.conflict.stage_changed`, and that tab stops and refetches (§10). No leader election is used in M1 `[ASSUMPTION · frontend, before M1]`.

### 7.4 Ephemeral outline delta

The reducer appends parsed partial notes, keyed by a client-generated `deltaId` plus the server `chunkIndex`; it never writes to TanStack Query, never persists, and is cleared on `outlineDone`, `resync`, resubscription, any outline mutation, or stage exit. If `outlineDelta` never arrives or arrives with a chunk gap (a missed ephemeral window or a reconnect), the board renders from `GET /api/projects/{projectId}/outline`, which is the durable source [ARCH §9.2]. Ephemeral frames are ignored for any stage other than OUTLINE. An unknown ephemeral `type` is ignored without breaking the stream; the contract defines only `outlineDelta` [API §6].

---

## 8. Rendering architecture

### 8.1 Canvas and scaling

The deck canvas is a fixed `1280×720` reference (`CanvasV1`) inside an `aspect-ratio: 16/9` wrapper. The stage renders at 1280×720 with `transform: scale(var(--deck-scale))` and `transform-origin: top left`; a `ResizeObserver` computes `--deck-scale = min(w/1280, h/720)`. Transform scaling is used instead of zoom or font resizing so slot geometry and measured overflow are identical at every viewport. CSS `cqi` units are not used for deck content; they cannot be shared with the Python renderer.

### 8.2 Shared model and layout registry

`shared/layouts/*.json` owns slot keys, geometry, and capacity; `shared/themes/*.json` owns palette, fonts, and text styles. Both are versioned and read by React and Python [TECH §12.1]. `layoutId` maps to a component:

| `layoutId` | Component | Notes |
| --- | --- | --- |
| `single` | `SingleLayout` | One full-bleed slot family; typically used by COVER/TOC/END compositions. |
| `two_col` | `TwoColLayout` | Two primary columns with optional sidebar slot. |
| `three_col` | `ThreeColLayout` | Three columns; card capacity from the layout JSON. |
| `hero` | `HeroLayout` | Top hero slot plus supporting row. |
| `async` | `AsyncLayout` | Asymmetric primary + secondary grid. |
| `mix` | `MixLayout` | Mixed spans using `span.col`/`span.row`. |

Block rendering is registry-driven by `role`: `headline`, `subhead`, `body`, `bullet_list`, `metric`, `quote`, `image`, `chart`, `table`, `callout`, `footer` [API §3.7.1]. A block's `slot` must exist in the layout; an unknown role or slot renders a neutral labeled placeholder and is reported, never dropped silently.

### 8.3 Plan wireframe vs design renderer

| Aspect | Plan renderer | Design renderer |
| --- | --- | --- |
| Input | `PlanBodyV1` | `DesignBodyV1` |
| Style | Grayscale, dashed card outlines, role labels explaining "what goes here" | Applies `style.textStyle`, `style.colorRole`, `align`, and resolved `body.style.tokens` |
| Assets | Labeled placeholder boxes | Image/chart blocks via resolved asset references (`GET .../assets/{assetId}`) |
| Purpose | Layout only; no theme | Style-applied preview |
| Shared | Slot geometry, block roles, canvas, chrome overlay | Same |

Both renderers are memoized per `(artifactVersionId, chromeVersion)` so a chrome-only change (title/order) never re-runs body layout [ARCH AD-12].

### 8.4 Chrome overlay

`ArtifactChromeDTO` (`pageNumber`, `deckOrder`, `title`, `sectionLabel`, `chromeVersion`) is rendered as a deterministic overlay, not as part of the body. `chromeVersion` is part of the render memo key and the thumbnail cache key; a title edit or reorder changes chrome without a model job [API §3.7; ARCH AD-12]. The overlay owns the page number, title, section label, and deck order indicators.

### 8.5 Thumbnails and offscreen rendering

Thumbnails render the same design component at thumbnail scale inside `pointer-events: none` wrappers. The thumbnail bitmap is live DOM, not a raster; the interactive element is the surrounding button, which carries the accessible name. Thumbnail rendering is deferred with `content-visibility: auto` and capped to the visible range when the deck exceeds 40 pages `[TBD-FE · measure before pilot]`.

An offscreen mount (`position: fixed; visibility: hidden; pointer-events: none` at 1280×720) is used only for advisory overflow measurement and font-settling before a page is marked "measured". It never blocks rendering and never replaces server validation.

### 8.6 Overflow, assets, fonts, sanitization

- Text overflow: the server's export validation is authoritative [PRD FR-6.14]. The client MAY show a non-blocking "may overflow" warning when `scrollHeight > clientHeight` on the 1280×720 mount; it MUST NOT truncate content silently or claim export validity.
- Assets: `DesignBodyV1.assets[]` exposes `assetId`, dimensions, and `licenseStatus`; `PlanBlockV1.assetRef` is the same ID. The renderer resolves it through `GET /api/projects/{projectId}/assets/{assetId}` (`302` to a short-lived signed URL, authorized and project-scoped) [API §4.6 PG4]. The path, not the signed URL, is cached with the artifact, so an expired URL cannot be baked into an immutable body. Images load lazily and decode before paint; a failed load renders a labeled neutral placeholder, never a broken-image icon. `licenseStatus` is advisory in the UI; the export gate is server-side.
- Fonts: deck fonts are bundled licensed families declared by the theme; they are loaded with `document.fonts.load` before measurement. No runtime font fetch from an external origin (CSP). App UI fonts are a separate stack.
- Sanitization: React text nodes only. `dangerouslySetInnerHTML` MUST NOT be used for any user, material, web, model, or server content. The design body is structured JSON, never HTML or markdown. Source titles/domains are rendered as text; a URL is never turned into a clickable link from free content.
- App tokens vs deck themes: `.deck-root` scopes deck CSS variables from the body/theme; app Tailwind tokens never leak into the deck, and deck palette values never style chrome or UI. The two systems are not interchangeable [TECH §5.2].

---

## 9. Screens

### 9.1 Global shell

| Aspect | Design |
| --- | --- |
| Route | All authenticated routes; the stage area only under `/projects/:projectId/*`. |
| Data queries | `['auth','me']`, `['project', id, 'snapshot']`. |
| Local state | Mobile nav open, restart/delete dialogs, stream status, stage-nav focus. |
| Primary components | `AppShell`, `SkipLink`, `TopBar`, `ModeBadge`, `StageNav`, `StageSelect` (≤920), `StreamStatus`, `RestartDialog`, `DeleteProjectDialog`, `Toaster`. |
| User actions | Navigate to a reachable stage; open restart; open delete; log out; open the data-handling notice. |
| Loading / empty / error | Auth skeleton; `401` → login; snapshot `404` → not-found; snapshot network error → retry card; stream `reconnecting`/`resyncing` banner. |
| Events consumed | `stageStateChanged`, `staleChanged`; all events drive the stream status dot. |
| Gating rules | Items come from `snapshot.stages`; enabled only when `reachable`; current item `aria-current="step"`; stale item has an amber dot plus `aria-label="needs rerun"`; no stage is computed locally. |
| Keyboard / a11y | Skip link is the first focusable element; nav is a list of links; `StageSelect` has a label; Esc closes dialogs; restart dialog focuses Cancel by default [PRD FR-7.8]; mode badge is text, not color-only. |
| Responsive | ≥1180 full nav and project name; 921–1180 condensed spacing; ≤920 native `<select>` with equivalent reachability and stale text [PRD FR-7.14]; ≤480 brand text trimmed, project name truncates with a title attribute. |

Restart is `POST /api/projects/{projectId}/restart` with `{ "confirm": true }`; `202` returns `project`, `snapshot`, `cancelledJobIds`. The dialog states that active jobs are cancelled and that prior artifacts are tombstoned per retention. Delete is `DELETE /api/projects/{projectId}`; `202` means deletion requested, not complete [API §4.2]. The project name is displayed; editing it is not exposed in M1 because project rename is deferred [PRD FR-8.3].

### 9.2 Home / material intake

| Aspect | Design |
| --- | --- |
| Route | `/` (new project) and `/projects/:projectId/intake` (existing project). |
| Data queries | New project: `config`, `policy/notices`. Existing intake: `snapshot`, `materials`, `config`, `policy/notices`. |
| Local state | Topic draft, mode draft, material drafts (paste text, URL, `File` objects), per-chip upload progress, failed-chip list. |
| Primary components | `TopicField`, `ScenarioChips`, `ModeSelector`, `MaterialComposer` (paste/file/URL tabs), `MaterialChip`, `UploadProgress`, `DataNotice`, `StartButton`. |
| User actions | Enter topic; pick a scenario chip (fills the topic, never submits); choose mode; add/remove material chips; start. |
| Loading / empty / error | Empty material slot is valid and selects the web-only path; topic error is inline and focuses the field; URL error is inline and preserves input; upload failure is per chip with Retry/Remove; submit shows a progress state; command errors are toasts with a reference ID. |
| Events consumed | `materialStatusChanged`, `jobQueued` on the existing-intake route; `projectCreated` is a no-op. |
| Gating rules | Topic non-empty after trimming; mode default `FULLY_AUTOMATIC`; the required data notice must be accepted before the first material is added, via `POST /api/policy/consent`; adding a material before a project exists is a local draft, and the project is created on Start; once past `INTAKE`, the route is read-only, add/remove/topic controls are disabled, and a "Change materials" action opens the restart confirmation backed by the `error.gate.material_locked` gate [API §4.3.1]. |
| Keyboard / a11y | `Cmd/Ctrl+Enter` submits the paste composer; mode is a radiogroup with arrow keys [PRD FR-1.13]; chips have remove buttons with names; drag-and-drop has a picker alternative; the data notice is a labeled region. |
| Responsive | ≥1180 centered hero with the material slot beside or below the topic; ≤1180 single column; ≤720 full-width controls; ≤480 chips wrap and scenario chips are trimmed to two [PRD §8.9.4]. |

Home flow (server-authoritative): the form holds drafts; on Start it validates the topic and calls `POST /api/projects` (`Idempotency-Key`, no `X-Expected-Version`). The `201` response seeds the snapshot. If no materials were drafted it calls `POST /api/projects/{projectId}/research/start` (`202`), invalidates and awaits the snapshot, then navigates to research. If materials exist, it commits them one by one (paste: `POST /api/projects/{projectId}/materials/paste`, URL: `POST /api/projects/{projectId}/materials/url`, file: `POST /api/projects/{projectId}/materials/upload-url` → PUT → `POST /api/projects/{projectId}/materials/{materialId}/finalize`), shows per-chip progress, and only then calls research/start. A failed material does not block the others [PRD FR-1.9]. Refresh during commit loses only uncommitted drafts; committed materials reload from the API `[ASSUMPTION · frontend, before M1]`. Abandoning the form before Start creates nothing.

Material count and limit: `GET /api/config` supplies `materialLimit`, `uploadMaxBytes`, and `supportedFileTypes`, so the Home screen shows `N / limit` and the supported-type list before a project exists [API §4.1 A4; PRD FR-1.7/1.8]. A multi-file selection over the remaining quota adds the remaining files and explains what was skipped; there is no silent drop [PRD FR-1.7]. The server still enforces the cap and returns `409 error.gate.material_limit`. The data-handling notice from `GET /api/policy/notices` MUST appear before the first material is added; acceptance is recorded by `POST /api/policy/consent`, and the server returns `409 error.gate.consent_required` until then [API §4.1 A5/A6; PRD FR-1.12; NFR-PRIV-4].

Mode: default fully automatic; expert copilot changes only advance mechanics. Mid-project switching is not exposed [PRD FR-1.13, PRD-04].

### 9.3 Research + interview

| Aspect | Design |
| --- | --- |
| Route | `/projects/:projectId/research`. |
| Data queries | `snapshot`, `research`, `sources`. |
| Local state | Follow-scroll enabled, `editingQuestionKey`, gap selection set, profile edit mode, pending answer intent. |
| Primary components | `Conversation` (`role="log"`), `MilestoneStatus` (`role="status"`), `MaterialToolCard`, `QuestionCard`, `DigestCard`, `GapCard`, `ProfileCard`, `SourcePanel`. |
| User actions | Answer the current question; edit an answered question; confirm gaps or "not needed"; generate/update the profile; go to outline; open the change-materials dialog. |
| Loading / empty / error | Conversation skeleton; digest `PENDING` skeleton; per-material failure card with a message key and Remove/Replace; `gapSearches[].outcome=ZERO_RESULTS` keeps the gap and says "not found" with continue/adjust, `FAILED` shows a retryable gap card, and `PENDING` shows a skeleton [PRD FR-2.10]; profile provider failure shows a retry card; `profileDirty` banner; source group `empty`/`loading`/`ready` from `SourcePanelDTO` with `materials.count`/`web.count`. |
| Events consumed | `questionAsked`, `answerRecorded`, `digestReady`, `gapSuggested`, `gapDecided`, `gapSearchCompleted`, `profileReady`, `profileUpdated`, `materialStatusChanged`, `sourceAdded`, `jobQueued`, `jobCancelled`. |
| Gating rules | Only the current unanswered question is interactive; answers use `PUT /api/projects/{projectId}/research/answers/{questionKey}` and overwrite the same identity (no count increment); `recommended` gap suggestions are pre-checked on first render, "Not needed — just use my materials" clears every other selection and submits `selectedSuggestionIds: []` with `webSkipped: true`, and `webSkipped=true` requires an empty selection; profile generation requires all answers and, with materials, a decision; the outline entry is disabled when `profileDirty` or the profile is missing, using `StageStateDTO.blockers` message keys, never a local flag. |
| Keyboard / a11y | Options are a radiogroup (roving tabindex per PRD-23) selectable with Space/Enter; gaps are native checkboxes; conversation is `role="log"` with `aria-live="off"`; milestones are announced only through the `role="status"` region; skeletons are `aria-busy`; answer edit returns focus to the question. |
| Responsive | ≥1180 two columns with an independent conversation scroll; ≤1180 source panel moves below; ≤720 single column, conversation scrolls with the page [PRD FR-2.22]; ≤480 cards stack and the sources panel is collapsed by default. |

Answering is sequential: `questionAsked` for the next position appears only after the current answer is recorded; the client renders from `research.questions[].position` and never invents a question. Edit mode reopens the option list and saves through the same `PUT`; `revision` updates from the response, and `profileDirty` comes from the response and the event merge. The profile card shows audience, goal, style mood, page count, materials summary, web scope, and content strategy from `ProfileDTO`; "Update profile" calls `POST /api/projects/{projectId}/research/profile` (`200`); `outlineUnconfirmed=true` adds a reconfirmation banner on the outline screen. Gap confirmation is immutable after a profile exists [PRD FR-2.21]; changing it in M1 requires restart, so the source panel and gap card are read-only and a "Change materials / gaps" action opens the restart explanation (§9.2, §11).

Missing content is never fabricated: a source row without a title/summary is not rendered; a skeleton is shown instead [PRD FR-2.15]. The material group is hidden when no materials exist; the web group shows `skipped` when the user chose "not needed".

### 9.4 Outline

| Aspect | Design |
| --- | --- |
| Route | `/projects/:projectId/outline`. |
| Data queries | `snapshot`, `outline`. |
| Local state | `editingPageId` + title draft, drag state, pending move target, countdown (§10), delete-confirm page id. |
| Primary components | `StickyBoard`, `SectionGroup`, `StickyNote`, `SectionInsertButton`, `OutlineStats`, `ReconfirmBanner`, `CountdownBar`. |
| User actions | Inline title edit (Enter saves); move up/down; insert after a page or at a section end; delete a body page; drag or keyboard reorder; confirm/reconfirm; continue to plan. |
| Loading / empty / error | `outlineDelta` notes fly in one by one; `GET` `404 error.not_found.outline` renders a "Generate outline" empty state; generation failure renders an error card with Retry (`POST /api/projects/{projectId}/outline/generate`); edit conflict refetches and rebases; fixed pages have no delete action. |
| Events consumed | `outlineDelta` (ephemeral), `outlineDone`, `stageStateChanged`, `staleChanged`, `jobQueued`, `jobCancelled`. |
| Gating rules | Title edit → `PATCH /api/projects/{projectId}/outline/pages/{pageId}`; move → `POST /api/projects/{projectId}/outline/pages/{pageId}/move` with `{toSectionKey,toPosition}` or `{toSectionKey,beforePageId}`; insert → `POST /api/projects/{projectId}/outline/pages`; delete → `DELETE /api/projects/{projectId}/outline/pages/{pageId}`; every structural command returns a new outline and `stale`; any edit after confirmation returns `confirmed=false` and the UI MUST show reconfirmation before plan/design can run [API §4.5.1; PRD FR-3.14]. |
| Keyboard / a11y | `Alt+↑/↓` within the section, `Shift+Alt+←/→` to the end of an adjacent section, `Enter` saves a title; focus stays on the moved note; buttons mirror every keyboard action; delete confirmation is a dialog with Cancel focused by default. |
| Responsive | ≥1180 multi-column sticky board with fixed cover/TOC/end notes; ≤920 nav select; ≤720 two-column board with page scroll; ≤480 one column; section insert buttons remain 44px touch targets. |

Notes show page number, title, and key points; cover/TOC/END are fixed-position notes with `deletable=false` and no delete affordance [PRD FR-3.2]. Counts come from `OutlineDTO.counts`: `N pages · M sections`; `deviationWarning` (from `|deviation| > 2`) renders a non-blocking warning and never blocks confirmation [PRD FR-3.9]. Dropping on a note means "insert before it" [PRD FR-3.7]. Section-level insertion uses the section's last page as `afterPageId` [API §4.5 O5]. The reconfirmation banner appears whenever `outline.confirmed=false` and explains that plan/design are blocked until the outline is confirmed; the primary action calls `POST /api/projects/{projectId}/outline/confirm`.

Stale explanation: the banner is built from `StageStateDTO.staleReasons` and `blockers[].messageKey`; both are content-free codes. Known reason codes get a catalog entry, unknown codes are shown as a generic "Needs rerun" with the code, and no cause is invented.

### 9.5 Plan draft

| Aspect | Design |
| --- | --- |
| Route | `/projects/:projectId/plan`. |
| Data queries | `snapshot`, `pages`, `['project', id, 'page', pageId, 'artifact', 'plan']`. |
| Local state | `selectedPageId` (default: first page without a current plan), tweak draft per page, pending retry page. |
| Primary components | `PlanPageList`, `PageStatusBadge`, `PlanProgress`, `WireframeCanvas`, `TweakPanel`, `RetryButton`, `ConfirmBar`. |
| User actions | Switch pages; re-plan the current page; tweak the current page; retry a failed page; confirm to continue. |
| Loading / empty / error | Pending page renders a skeleton (`aria-busy`), not a finished-looking wireframe; `404 error.not_found.artifact` is a skeleton; per-page error shows `PageError.messageKey` + Retry; empty tweak shows an inline error; concurrent write returns `409 error.gate.page_write_in_progress` and disables actions. |
| Events consumed | `pageJobStarted`, `pageJobDone`, `pageJobFailed`, `staleChanged`, `stageStateChanged`, `jobCancelled`. |
| Gating rules | Confirm is enabled only when every page is `DONE` and none is `ERROR` (`PageListDTO.counts`/snapshot counts) and the server has not returned a gate error; re-plan/tweak/retry are disabled for the selected page while `plan.status` is `PLANNING` or `design.status` is `DESIGNING`; confirm in expert mode navigates to style, in fully automatic mode advances per §10 when the server offers a token. |
| Keyboard / a11y | Page list is a list of buttons with `aria-current` on the selected page; status is text + icon + `aria-label` (pending, planning, done, stale, error), never color alone; the canvas is `role="img"` with a page-level label; progress uses `role="progressbar"` + `aria-valuenow`; tweak submits on Enter with the field error announced. |
| Responsive | ≥1180 left list + main canvas; 921–1180 list narrows; ≤920 nav select; ≤720 page list becomes a horizontal strip and the canvas is 680px wide with horizontal scrolling [PRD §8.9.4]; ≤480 actions collapse below the canvas. |

Re-plan is `POST /api/projects/{projectId}/pages/{pageId}/plan/regenerate` (`202`, `jobId`, `pageId`); tweak is `POST /api/projects/{projectId}/pages/{pageId}/plan/tweak` (`202`) with a non-empty `instruction`; retry is `POST /api/projects/{projectId}/pages/{pageId}/retry` with `{ "kind": "plan" }` (`202`). The page list groups pages by `PageSummaryDTO.sectionKey`/`sectionTitle` in outline order. Every `202` means accepted, not done; the page status changes on `pageJobStarted`/`pageJobDone` [API §5]. Re-plan/tweak mark that page's design stale server-side; the design stage shows the marker on entry [PRD FR-4.7]. A page in `error` keeps the confirm gate closed until retry succeeds [PRD FR-4.8].

### 9.6 Style selection

| Aspect | Design |
| --- | --- |
| Route | `/projects/:projectId/style`. |
| Data queries | `snapshot` (restores `styleSelection`), `styles`; `['style', styleKey, version]` only to refresh an expired preview or resolve the saved version. |
| Local state | `selectedStyleKey`, `rememberPreference` draft, focused card index. |
| Primary components | `StyleGallery`, `StyleCard` (preview, palette, use case), `RememberPreference`, `ConfirmBar`. |
| User actions | Select one style; toggle remember; confirm and enter design. |
| Loading / empty / error | Four skeleton cards; preview image failure shows a neutral placeholder, never wrong colors; catalog failure shows a retry card; `previewUrl` expiry triggers a detail refetch; confirm error shows the message key. |
| Events consumed | `stageStateChanged`, `staleChanged` (style changes invalidate design elsewhere), `jobQueued`. |
| Gating rules | Single-select radiogroup with `aria-checked`; confirm is disabled until a selection exists; the server also enforces `409 error.gate.style_not_selected`; selection alone never starts generation [PRD FR-5.3]; a style change after design exists marks all design stale and never changes plan [PRD FR-5.5]. |
| Keyboard / a11y | Arrow keys move and select within the radiogroup (roving tabindex per PRD-23); Space/Enter selects; the gallery is labeled; each card has an accessible description including the use case; the selected state is announced. |
| Responsive | ≥1180 four cards in a row; 921–1180 two by two; ≤720 one column; ≤480 previews shorten and palette dots remain. |

Confirm is two commands in order: `PUT /api/projects/{projectId}/style` with `{styleKey, styleVersion, rememberPreference}` (`200` → `StyleSelectionDTO`), then `POST /api/projects/{projectId}/style/confirm` (`200` → `styleSelection`, `stage`, `stale`). If the user only toggles `rememberPreference`, the `PUT` is re-issued with the same `styleKey`/`styleVersion`. After a refresh, the selected card is restored from `snapshot.styleSelection`; if `confirmed=false` the confirm control is enabled with that selection, and if `confirmed=true` the user is already cleared to enter design. A selection returned by `PUT`/`confirm` updates the snapshot cache so the restored state matches without a refetch. `rememberPreference` is project-scoped in M1; it is stored on the selection, not in `localStorage` [API §3.3/§4.8; PRD FR-5.4]. M1 does not carry a preference across projects [ARCH §14].

### 9.7 Design draft

| Aspect | Design |
| --- | --- |
| Route | `/projects/:projectId/design`. |
| Data queries | `snapshot`, `pages`, `['project', id, 'page', pageId, 'artifact', 'design']`, `['project', id, 'history', pageId, 'design']`. |
| Local state | `selectedPageId`, `pinnedPageId`, tweak draft per page, zoom/fit preference (`[TBD-UX · PRD-24]`), export modal state. |
| Primary components | `DesignWorkbench`, `ThumbnailRail`, `DesignCanvas`, `PageActions`, `HistoryCount`, `TweakPanel`, `SingleLayoutNotice`, `ExportDialog`. |
| User actions | Page through thumbnails/arrows; pin a page; regenerate; restore the previous version; tweak; open export. |
| Loading / empty / error | Pending/designing page renders a skeleton and `aria-busy`; artifact `404` is a skeleton; error page shows `messageKey` + Retry (`{kind:"design"}`); regenerating a single-layout page returns `409 error.gate.single_layout_use_tweak` and opens the tweak prompt; concurrent writes show "please wait"; export is disabled with an explanation while design is incomplete. |
| Events consumed | `pageJobStarted`, `pageJobDone`, `pageJobFailed`, `historyPopped`, `staleChanged`, `stageStateChanged`, `exportProgress`, `exportDone`, `exportFailed`, `jobCancelled`. |
| Gating rules | Regenerate/tweak/history are scoped to the current page and disabled while that page has `activeJob` or an active status; export requires every page to have a current design (`error.gate.design_incomplete` otherwise); no "regenerate deck" action exists [PRD FR-6.8]; generation never steals the selected page [PRD FR-6.3]. |
| Keyboard / a11y | `←`/`→` change pages when the canvas or rail has focus; the canvas is `role="img"` with a page-number/title/status label; thumbnail images are `aria-hidden`, but each thumbnail button has an accessible name and is keyboard reachable (clarifies [FLOW §7.2]); generation progress uses `role="progressbar"`; errors are announced. |
| Responsive | ≥1180 three columns (rail, canvas, actions); 921–1180 rail collapses; ≤1180 order becomes canvas → actions → thumbnails [PRD §8.9.4]; ≤720 thumbnails are a horizontal strip and the canvas is 680px with horizontal scrolling; ≤480 the action panel stacks below the canvas. |

Regenerate is `POST /api/projects/{projectId}/pages/{pageId}/design/regenerate` (`202`); a `202` is acceptance only. The thumbnail rail groups pages by `sectionKey`/`sectionTitle` in outline order and shows per-page status. Previous version is `POST /api/projects/{projectId}/pages/{pageId}/undo` with `{ "kind": "design" }` (`200` → `artifact`, `history`, `stale`); it is disabled when `history.canUndo` is false, and there is no redo in M1 [PRD FR-6.5; ARCH §8.5]. Tweak is `POST /api/projects/{projectId}/pages/{pageId}/design/tweak` (`202`); a failed tweak leaves current/history unchanged server-side. Variant and history counts come from `ArtifactDTO.version` and `ArtifactDTO.history.depth`, never from local counters. Selecting a thumbnail sets `pinnedPageId`; remaining pages continue server-side [PRD FR-6.3].

### 9.8 Export modal

| Aspect | Design |
| --- | --- |
| Route | Dialog over `/projects/:projectId/design`; not a route in M1. |
| Data queries | `snapshot`, `pages`, `['project', id, 'export', exportId]` after creation. |
| Local state | `format` (default `PPTX`), `lastExportId`, dialog open. |
| Primary components | `ExportDialog` (Radix Dialog), `FormatPicker`, `ScopeSummary`, `ExportProgress`, `ExportFailure`, `DownloadAction`. |
| User actions | Choose PPTX/HTML/PDF; start export; retry; try another format; download; close. |
| Loading / empty / error | Scope summary from the current snapshot/pages before creation; after creation from `ExportDTO.deckSnapshot`; progress phases from `exportProgress`; failure keeps the modal open with reason, Retry, and Try another format [PRD FR-6.15]; no success state without `artifact`. |
| Events consumed | `exportProgress`, `exportDone`, `exportFailed`. |
| Gating rules | Formats are exactly `PPTX`, `HTML`, `PDF`, PPTX marked recommended; start is disabled when design is incomplete; the server also enforces `error.gate.design_incomplete`; incomplete/excluded pages must be named when the server reports them (PRD-03 policy pending). |
| Keyboard / a11y | Dialog `role="dialog"` with `aria-modal`, focus trap, Esc close, focus restored to the export trigger; format is a radiogroup with arrow keys; progress is `role="progressbar"` with `aria-valuenow`; completion and failure are announced through a status region. |
| Responsive | ≥1180 centered 560px dialog; ≤720 full-width sheet; ≤480 format rows stack with the recommended label retained. |

Start is `POST /api/projects/{projectId}/exports` with `{ "format": ... }` (`202` → `ExportDTO`) and a new idempotency key per export intent. A retry after `exportFailed` is a new intent with a new key; "Try another format" creates a new export with a different `format`. Progress merges the event fields; the state changes only when the export query reflects `SUCCEEDED`/`FAILED`. `exportDone` alone is not permission to show success: the UI waits for `artifact` (fileName, byteSize, downloadPath) from `GET /api/projects/{projectId}/exports/{exportId}` [PRD FR-6.16]. Failure renders `failedChecks` page IDs as chips that navigate to the named pages. The modal MUST NOT close on failure and MUST NOT show a success toast before the artifact exists.

---

## 10. Auto-advance design

| Rule | Design |
| --- | --- |
| Ownership | The client owns the visible 3-second countdown; the server validates the advance with `advanceToken` and stage version [ARCH AD-9/§8.8; PRD FR-3.11]. There is no server timer in M1. |
| Eligibility | `project.mode="FULLY_AUTOMATIC"`, the current stage is OUTLINE, `StageStateDTO.advanceToken` is present, and `advanceTokenExpiresAt` is later than now + 3 s + 1 s margin. If any condition fails, no countdown is shown. |
| Start | Only after `outlineDone` (durable) and the committed outline is in cache. Never after an ephemeral delta. |
| Tick | `remainingMs` is derived from `performance.now()` against `deadlineAt` (not decremented per tick), so background-tab throttling cannot extend or skip the countdown. |
| Pause | Pause button; entering title edit mode; any outline mutation; any structural command; `document.visibilitychange` to hidden; focus inside an input/editable area at zero. Pause is sticky and announced once through the status region. |
| Auto-pause on edit | Pause immediately, not after the save. If the outline version changes, the countdown is cancelled permanently for that version. |
| At zero | If focus is in an input/editable area, pause instead of navigating. Otherwise call `POST /api/projects/{projectId}/stages/advance` with `{ "fromStage": "OUTLINE", "advanceToken": token }`. |
| Success | `200 AdvanceResultDTO`; apply `project` and `stages` to the cached snapshot, invalidate `snapshot` in the background for counts, then `navigate('/projects/:projectId/plan', { replace: true })`. |
| Failure | `409 error.gate.auto_advance_ineligible`, `409 error.gate.token_expired`, `409 error.conflict.stage_changed`: stop, refetch the snapshot, show the message key, and offer an explicit "Confirm outline" action. No silent retry and no second automatic attempt. |
| Token hygiene | A token is never reused after a pause caused by an edit, after navigation, or after expiry. A new token is only accepted from a fresh `StageStateDTO`. |
| Route transition | The countdown is cleared before navigation; the target route still passes the reachability guard, so a stale advance cannot bypass a gate. |
| Reconnect | On reconnect the outline remains unconfirmed; the countdown restarts only if the stage is visible, the token is fresh, and no edit is in progress. A background tab never advances. |
| Plan → Style | Fully automatic mode advances after all plan pages are done and none is in error, using the same validated advance path when the server offers a token; no 3-second countdown is specified for this transition [PRD §7.4]. `[TBD-UX · design, M1]` whether a visible countdown is added. |
| Multi-tab | Each tab counts down; the first successful advance wins. A losing tab receives `409` or `stageStateChanged`, stops, and refetches. It never steals navigation from an in-progress edit; a banner offers "Go to Plan". |

Pause copy MUST explain why (user pause, editing, hidden tab), and the countdown MUST NOT steal focus [PRD FR-3.11; UX §3.2].

---

## 11. Stale rerun and undo UI

| Concern | Design |
| --- | --- |
| Markers | Stage nav amber dot + `aria-label="needs rerun"` from `StageStateDTO.status="STALE"`; page badges from `PageSummaryDTO.plan/design.status="STALE"`; the explanation uses `staleReasons`/`blockers[].messageKey` codes. |
| Rerun-on-entry | Outline: if no outline exists and the profile is clean, `POST /api/projects/{projectId}/outline/generate` once; if the outline is unconfirmed, show reconfirmation and do NOT regenerate automatically. Plan: `POST /api/projects/{projectId}/plan/generate` once when stale/missing plan pages exist. Design: `POST /api/projects/{projectId}/design/generate` once when stale/missing design pages exist. Style: never auto-runs generation. |
| Guard | At most one rerun-on-entry per stage per `projectVersion`; no loop after an error; a page `ERROR` surfaces Retry instead of another automatic call. |
| Scope honesty | The generate response reports `jobs`, `skippedPageIds`, and `counts` (`required`, `scheduled`, `reused`); the UI shows the actual scope and never claims a full rerun when pages were reused [PRD NFR-COST-3/4]. |
| Per-page previous version | Design only; `POST /api/projects/{projectId}/pages/{pageId}/undo` with `{ "kind": "design" }`; the button is disabled when `history.canUndo=false`; the server returns the restored artifact and history. No redo in M1 [ARCH AQ-4]. |
| Plan undo | The API supports `kind="plan"`, but no M1 requirement exposes it; the UI does not show plan undo `[TBD-UX · product, post-M1]`. |
| Optimistic behavior | None for stale/history/current. No local history decrement, no local current swap, no amber-dot removal before the server response. |
| Disabled states | Page actions are disabled during an active job and while a mutation is in flight for that page; a second click cannot create a second history entry [PRD FR-7.4]. |
| Material changes after research | Restart-only in M1. The API returns `409 error.gate.material_locked` with `details.restartRequired: true` [API §4.3.1]; the confirmation flow explains that research, profile, outline, and downstream artifacts are reset and offers Restart (default focus Cancel). |

---

## 12. Accessibility

### 12.1 Semantics

| Element | Contract |
| --- | --- |
| Conversation | `role="log"`, `aria-live="off"`; milestones announced through a separate `role="status"` region [PRD FR-7.11]. |
| Stage nav | Current stage `aria-current="step"`; stale item has `aria-label` including "needs rerun"; disabled items are `aria-disabled` and not focusable. |
| Question options | `role="radio"` / native inputs with `aria-checked`; gaps are native checkboxes. |
| Style gallery | `role="radiogroup"` with `aria-checked` per card. |
| Canvas | `role="img"` plus `aria-label` with page number, title, and status; thumbnails expose named buttons while their images are `aria-hidden`. |
| Generation / skeletons | Container `aria-busy="true"`; skeletons are not announced as content. |
| Progress | `role="progressbar"`, `aria-valuenow`, `aria-valuemin`, `aria-valuemax`, and a text label for export and plan/design progress. |
| Modals | `role="dialog"`, `aria-modal="true"`, labeled by title, focus trap, Esc close, focus restore to the trigger [PRD FR-6.11]. |
| Status not by color | Every status includes text and an icon; amber dots always carry an accessible label. |

### 12.2 Keyboard matrix

| Area | Key | Behavior |
| --- | --- | --- |
| Global | `Tab` / `Shift+Tab` | Visual order; cycles within a modal. |
| Global | `Esc` | Closes the open modal; focus returns to the trigger. |
| Home mode | `←` / `→` / `↑` / `↓` | Switches fully automatic / expert copilot when the mode radiogroup has focus [PRD FR-1.13]. |
| Intake paste | `Cmd/Ctrl+Enter` | Submits the paste composer. |
| Interview | `Tab` + `Space` / `Enter` | Selects an option; gaps are toggled individually, then confirmed. |
| Sticky notes | `Alt+↑/↓` | Moves within the section; boundary action is disabled. |
| Sticky notes | `Shift+Alt+←/→` | Moves to the end of an adjacent section. |
| Sticky notes | `Enter` | Saves an inline title edit. |
| Style | `←` / `→` / `↑` / `↓` | Moves and selects style cards. |
| Design | `←` / `→` | Previous/next page when the canvas or rail has focus. |
| Export modal | `Tab` / `Shift+Tab` / `Esc` | Focus trap, close, focus restore. |

No core action is pointer-only [PRD FR-7.10]. Roving tabindex for radio groups is M1 hardening tracked by PRD-23; until it lands, `Tab` + `Space`/`Enter` remains the guaranteed path.

### 12.3 Focus, contrast, motion

- On stage change, focus moves to the stage `h1`; on a route with an inline blocker banner, focus stays on the heading and the banner is announced, not focused.
- Focus ring is 2px brand color with a 2px offset and is visible on every interactive element, including dark deck chrome overlays.
- Body and secondary text meet at least 4.5:1; disabled states remain distinguishable without color alone [PRD NFR-ACC-2].
- `prefers-reduced-motion: reduce` sets animation/transition durations near zero, disables note fly-in, and renders streamed outline text immediately; no information exists only in animation [PRD FR-7.12].
- Toasts are supplementary; Sonner is configured with `aria-live="polite"` and never used for a required state that has no persistent surface.

---

## 13. Responsive design

| Stage | ≥1180 (1440/1180) | 921–1180 | ≤920 (920) | ≤720 (720) | ≤480 (390) |
| --- | --- | --- | --- | --- | --- |
| Shell | Top nav, full project name, mode badge | Condensed nav spacing | Nav becomes native `<select>` with reachability + stale text | Same | Brand trims; project name truncates |
| Home | Centered hero, material slot beside topic | Material slot below topic | Single column | Full-width controls; canvas none | Two scenario chips; chips wrap |
| Research | Conversation + source panel | Source panel below conversation | Panel collapsed below | Single column, page scroll | Cards stack; panel collapsed by default |
| Outline | Multi-column board | Denser board | Nav select | Two-column board, page scroll | One column |
| Plan | Page list + canvas | Narrow list | Nav select | Page list horizontal strip; canvas 680px with horizontal scroll | Actions below canvas |
| Style | Four cards in a row | Two by two | Two by two | One column | Shortened previews |
| Design | Three columns | Rail collapses; canvas → actions → thumbnails | Nav select | Thumbnail strip; canvas 680px scroll | Actions stack below canvas |

Rules: vertical page scroll is allowed at every breakpoint except inside an explicitly scrollable canvas container; no page-level horizontal scroll is introduced except the 680px canvas container at ≤720 [PRD FR-7.15]. Deck content scales by transform, so text does not reflow at breakpoints. Table-like content never uses horizontal scrolling as the only access path.

---

## 14. Performance

| Concern | Rule |
| --- | --- |
| Streaming outline | Ephemeral deltas are batched with `requestAnimationFrame`; at most one React commit per frame; partial notes are appended to a local reducer, not to TanStack Query. |
| Query freshness | `snapshot` 0 ms (invalidated by events); `research` 5 s; `sources` 2 s; `outline` 5 s; `pages` 1 s; artifacts `Infinity` (immutable per version, `If-None-Match`); `history` 30 s; `styles` 5 min; export 0 ms while the modal is open. |
| GC | Project queries `gcTime` 10 min; cleared on project switch/logout. |
| Memoized page render | `DeckPage` is memoized on `(artifactVersionId, chromeVersion, styleVersion)`; thumbnails share the same component and memo. |
| Virtualization | Page/thumbnail lists virtualize above 40 pages; below that, `content-visibility: auto` per thumbnail. Deck size is capped server-side [PRD NFR-SCALE-2]. |
| Code splitting | Route-level lazy loading for each stage; `render/`, `ExportDialog`, and dnd-kit are separate chunks; the shell ships without the deck renderer. |
| Images and fonts | Style previews lazy-load below the fold; deck fonts load once per style; no external font/image requests at render time. |
| Interaction during streaming | Inputs remain interactive; the countdown pauses on focus; the stream never blocks typing or navigation. |
| Layout stability | Fixed 1280×720 stage, transform scaling, `ResizeObserver` writes only CSS variables; no per-frame measurement; offscreen measurement runs only when a page settles. |
| Route transitions | Keep the previous snapshot for the shell; do not keep a stale artifact painted as current — show a dimmed stale badge until the new query resolves. |

---

## 15. Error handling and UX

### 15.1 Surfaces

| Surface | Use | Examples |
| --- | --- | --- |
| Inline field | Correctable input errors | `error.validation.empty_topic`, `error.validation.invalid_url`, `error.validation.empty_title`, `error.validation.empty_instruction`, `error.validation.unsupported_type`, `error.validation.file_too_large` |
| Inline card / banner | Blocking gate or recoverable resource state | `error.gate.profile_dirty`, `error.gate.outline_unconfirmed`, `error.gate.material_locked`, `error.gate.topic_locked`, `error.gate.style_not_selected`, `error.gate.style_unconfirmed`, `error.parse.url_unreachable`, `error.parse.type_mismatch` |
| Toast | Transient command result or supplemental notice | `error.rate.limited`, `error.gate.page_write_in_progress`, `error.conflict.stale_version`, `error.internal.unexpected` |
| Modal | Destructive confirmation and export failure | restart, delete, export failure with Retry / Try another format |
| Full-page redirect | Session and access | `error.auth.session_required`, `403` access denied, `error.not_found.project` |

### 15.2 Behavior

- Every error shows the resolved message plus a reference (`requestId` / `traceId`) with a copy action; `details` is never rendered raw.
- `error.conflict.stale_version` refetches the snapshot and affected query, then rebases once; a second conflict shows a "reload" action instead of looping.
- `error.gate.*` errors are not retried; the action that closes the gate is the primary button (for example "Update profile" or "Confirm outline").
- Provider errors (`error.provider.timeout`, `error.provider.unavailable`) render retry affordances for the affected page/export; other pages continue.
- Export failure keeps the modal open; Retry and Try another format are always both present; no success state without an artifact [PRD FR-6.15/6.16].
- The message catalog is keyed by `messageKey` and MUST cover every key in [API §7] plus endpoint-level keys used in §4 (for example `error.validation.gap_selection_invalid` and `error.validation.unknown_section`); a CI test compares the catalog against the generated contract fixtures and fails on a missing key.
- Correlation IDs are copy-only. The client never sends message content, topic, titles, URLs, file names, or request bodies to analytics; analytics receives route, stage enum, `messageKey`, category, and IDs only [PRD NFR-PRIV-3].
- Offline: the stream banner switches to `reconnecting`; queries fail with a retry card; mutations are not queued; server jobs continue and converge on reconnect [PRD FR-7.5].
- `401`: clear all caches and stores, abort the stream, redirect to `/login?returnTo=<current route>`.
- A `404` on a project means deleted or inaccessible; show a content-free not-found screen without revealing existence.

---

## 16. Security and privacy

| Control | Client rule |
| --- | --- |
| Session | HttpOnly `bound_session` cookie; never readable by JS; no token in storage; `credentials: "same-origin"` [TECH §6.4]. |
| CSRF | Same-origin SPA; the server checks origin on mutating routes; the client adds no custom auth headers [TECH §14]. |
| Provider keys | No model, search, storage, or provider key exists in the bundle; no client-side model call [TECH §10.3; PRD NFR-SEC-3]. |
| HTML injection | No `dangerouslySetInnerHTML`; no `innerHTML`; all content renders as text nodes; URLs are not linkified from free content [TECH §12.2]. |
| CSP | Nonce-based strict CSP, `connect-src` limited to the app/API and required telemetry; no `unsafe-eval` in production [TECH §14]. |
| Signed URLs | `previewUrl`, presigned upload URLs, and download redirects are never logged, never put in analytics, and never rendered as text. |
| Analytics | No content fields; IDs only; no full URLs, file names, emails, or deck text [PRD NFR-PRIV-3]. |
| Error reporting | No request bodies; no content in Sentry/telemetry breadcrumbs; correlation IDs only. |
| Dependencies | No unaudited runtime package; lockfile committed; `npm ci` in CI. |

---

## 17. Testing

| Layer | Tooling | Coverage |
| --- | --- | --- |
| Unit | Vitest | Reducers (stream, countdown), key builders, error normalization, message catalog, upload state machine, format/scope summaries. |
| Component | Vitest + React Testing Library | Topic validation, mode radiogroup, question flow, gap "not needed", outline keyboard moves, plan gate, style confirm gating, regenerate/history disabled states, export failure. |
| API/SSE mocks | MSW with fixtures typed from generated types | Snapshot, all event types, `snapshot`/`resync`/`heartbeat` frames, 401/404/409/429/503, `304` artifact. No test calls a real provider [TECH §5.6]. |
| E2E | Playwright | Six-stage happy path; stale rerun; design undo; reconnect/resync; export failure + retry; keyboard-only run; responsive 1440/1180/920/720/390; multi-tab advance conflict. |
| Accessibility | axe-core + Playwright, manual screen-reader audit | WCAG 2.2 AA baseline; keyboard matrix; live regions; focus trap/restore; contrast [PRD NFR-ACC-1–6]. |
| Visual | Playwright screenshots | Plan wireframes, design pages, style cards, export modal at the five viewports [TECH §15]. |
| Motion | Playwright with `reducedMotion: "reduce"` | No fly-in, immediate text, no information loss. |
| Contract drift | CI diff on `schema.d.ts` and shared-schema types | Fails when generated output differs from committed output [API §9; TECH §5.5]. |

MSW handlers are generated from the wire types, so a renamed field or event fails the typecheck before it fails a test. Tests MUST NOT assert on server prose; they assert on `messageKey` and rendered catalog text.

---

## 18. Open questions and conflicts

| ID | Question / conflict | Frontend handling / owner |
| --- | --- | --- |
| API-Q1 | Material add/remove after research: restart-only vs re-search | UI assumes restart-only in M1 and implements the `error.gate.material_locked` restart flow [API §4.3.1]. Product + backend · before M1. |
| API-Q2 | Outline edits after confirmation: allow + reconfirm vs lock | UI assumes allow + reconfirm and renders `confirmed=false` as a reconfirmation gate [API §4.5.1]. Product + UX · before M1. |
| API-Q3 | Partial export policy / excluded pages | Modal blocks success on `error.gate.design_incomplete` until decided; excluded pages are named when the server reports them. Product + UX · M1. |
| API-Q4 | Idempotency-key retention and client key format | Client uses `crypto.randomUUID()` per intent and reuses it on retry. Backend · before pilot. |
| API-Q5 | Event-log retention / resync threshold | The stream handles `resync` generically; no retention assumption is coded. Ops + architecture · before pilot. |
| API-Q6 | Exact artifact body schema / layout vocabulary versioning | The renderer is blocked on the shared JSON Schema contract; unknown slots/roles render a neutral placeholder and are reported. Backend + design · before plan implementation. |
| API-Q7 | `POST /api/projects/{projectId}/research/profile` synchronous vs job | The UI accepts `200` with a profile or `202` plus `profileReady`; both paths render the same skeleton. Backend · before implementation. |
| API-Q8 / PRD-06 | Streaming `fetch`/`ReadableStream` support and browser matrix | The hook assumes `ReadableStream`; a fallback to polling `GET /api/projects/{projectId}/snapshot` is required if the matrix excludes a browser. `[TBD-FE · frontend, before M1]` |
| PRD-07 | PPTX fidelity bar and PowerPoint versions | No client behavior changes; export copy must not promise a fidelity level before the bar is set. `[TBD-BIZ · product + engineering, before M1]` |
| TBD-FE-1 | Re-search after profile (FR-2.18) | M1 uses the restart fallback; the "change gaps" entry is not shown as a re-search flow. `[TBD-FE · frontend, before M1]` |
| FE-Q1 | Asset content endpoint | Resolved: `GET /api/projects/{projectId}/assets/{assetId}` (`302` signed, authorized) is used directly by the renderer; signed URLs are never stored in the artifact body [API §4.6 PG4]. |
| FE-Q2 | Pre-project config endpoint | Resolved: `GET /api/config` supplies `materialLimit`, supported types, upload cap, formats, and canvas before project creation [API §4.1 A4]. |
| FE-Q3 | Consent/notice endpoint | Resolved: `GET /api/policy/notices` + `POST /api/policy/consent`; material add/upload returns `error.gate.consent_required` until accepted. The web-only start path has no upload and no separate gate [API §4.1 A5/A6]. |
| FE-Q4 | Zero-search-results signal | Resolved: `ResearchStateDTO.gapSearches[]` and durable `gapSearchCompleted` carry `RESULTS`/`ZERO_RESULTS`/`FAILED` per selected gap [API §3.5/§6]. |
| FE-Q5 | Stale `error.gate.research_finished` key | Resolved: the API contract uses `error.gate.material_locked`; the stale key was removed from the endpoint text and catalog. |
| FE-Q6 | `cardDelta` vs `outlineDelta` | Resolved: `cardDelta`/`messageDelta` are telemetry names, not SSE contract types; plan/design progress uses `pageJobStarted`/`pageJobDone` and the artifact query [API §6]. |
| FE-Q7 | Plan → Style auto-advance has no countdown in [PRD §7.4] | Implemented as an immediate validated advance; a visible countdown is `[TBD-UX · design, M1]`. |
| FE-Q8 | Thumbnails are described as `aria-hidden` but are interactive | Resolution: thumbnail images are decorative; the surrounding buttons are named and focusable. `[TBD-UX · design, M1]` |
| FE-Q9 | Outline rerun-on-entry vs reconfirmation | The UI never regenerates an unconfirmed outline automatically; it shows reconfirmation. If product wants regeneration, `[TBD-UX · product, M1]`. |
| FE-Q10 | Style selection restoration | Resolved: `ProjectSnapshotDTO.styleSelection` carries `styleKey`, `styleVersion`, `confirmed`, and `confirmedAt`, so the style screen restores the selection after refresh [API §3.3]. |

---

## 19. Traceability

| Screen / feature | Requirements | API endpoints / events |
| --- | --- | --- |
| Shell, routing, guards | FR-7.1, FR-7.2, FR-7.9, FR-7.14, NFR-ACC-4 | `GET /api/auth/me`, `GET /api/projects/{projectId}/snapshot`, `POST /api/projects/{projectId}/restart`, `DELETE /api/projects/{projectId}`; `stageStateChanged`, `staleChanged` |
| Home / intake | FR-1.1–1.14, FR-8.1, NFR-PRIV-4 | `GET /api/config`, `GET /api/policy/notices`, `POST /api/policy/consent`, `POST /api/projects`, `GET /api/projects/{projectId}/materials`, `POST /api/projects/{projectId}/materials/paste`, `POST /api/projects/{projectId}/materials/url`, `POST /api/projects/{projectId}/materials/upload-url`, `POST /api/projects/{projectId}/materials/{materialId}/finalize`, `DELETE /api/projects/{projectId}/materials/{materialId}`, `POST /api/projects/{projectId}/research/start`; `materialStatusChanged`, `jobQueued` |
| Research | FR-2.1–2.22, NFR-ACC-5 | `GET /api/projects/{projectId}/research`, `GET /api/projects/{projectId}/sources`, `PUT /api/projects/{projectId}/research/answers/{questionKey}`, `POST /api/projects/{projectId}/research/gaps/decisions`, `POST /api/projects/{projectId}/research/profile`; `questionAsked`, `answerRecorded`, `digestReady`, `gapSuggested`, `gapDecided`, `gapSearchCompleted`, `profileReady`, `profileUpdated`, `sourceAdded` |
| Outline | FR-3.1–3.15, FR-7.8, NFR-COST-3 | `GET /api/projects/{projectId}/outline`, `POST /api/projects/{projectId}/outline/generate`, `POST /api/projects/{projectId}/outline/confirm`, `PATCH /api/projects/{projectId}/outline/pages/{pageId}`, `POST /api/projects/{projectId}/outline/pages`, `DELETE /api/projects/{projectId}/outline/pages/{pageId}`, `POST /api/projects/{projectId}/outline/pages/{pageId}/move`, `POST /api/projects/{projectId}/stages/advance`; `outlineDelta`, `outlineDone` |
| Plan | FR-4.1–4.11, FR-7.16 | `GET /api/projects/{projectId}/pages`, `GET /api/projects/{projectId}/pages/{pageId}/artifacts/plan`, `POST /api/projects/{projectId}/plan/generate`, `POST /api/projects/{projectId}/pages/{pageId}/plan/regenerate`, `POST /api/projects/{projectId}/pages/{pageId}/plan/tweak`, `POST /api/projects/{projectId}/pages/{pageId}/retry`; `pageJobStarted`, `pageJobDone`, `pageJobFailed` |
| Style | FR-5.1–5.6, NFR-ACC-2 | `GET /api/styles`, `GET /api/styles/{styleKey}`, `PUT /api/projects/{projectId}/style`, `POST /api/projects/{projectId}/style/confirm` |
| Design | FR-6.1–6.9, FR-7.4, FR-7.7, NFR-REL-3 | `GET /api/projects/{projectId}/pages/{pageId}/artifacts/design`, `GET /api/projects/{projectId}/pages/{pageId}/history`, `GET /api/projects/{projectId}/assets/{assetId}`, `POST /api/projects/{projectId}/design/generate`, `POST /api/projects/{projectId}/pages/{pageId}/design/regenerate`, `POST /api/projects/{projectId}/pages/{pageId}/design/tweak`, `POST /api/projects/{projectId}/pages/{pageId}/undo`; `historyPopped`, `jobCancelled` |
| Export | FR-6.10–6.21, NFR-COMPAT-4/5 | `POST /api/projects/{projectId}/exports`, `GET /api/projects/{projectId}/exports/{exportId}`, `GET /api/exports/{exportId}/download`; `exportProgress`, `exportDone`, `exportFailed` |
| Auto-advance | FR-3.10/3.11, FR-4.10, ARCH AD-9 | `POST /api/projects/{projectId}/stages/advance`; `stageStateChanged` |
| Reconnect / streaming | FR-7.5, FR-7.9, NFR-REL-4, NFR-PERF-3 | `GET /api/projects/{projectId}/events?cursor={sequence}`, `GET /api/projects/{projectId}/snapshot`; all durable events |
| Accessibility / responsive | NFR-ACC-1–6, NFR-COMPAT-2/3 | No endpoint; client behavior only |

---

## 20. Change log

| Version | Date | Change |
| --- | --- | --- |
| v1.1 | 2026-11-19 | Reconciled with API contract v1.1: added `GET /api/config`, policy notice/consent, asset content endpoint, `gapSearchCompleted`, snapshot `styleSelection`, and resolved FE-Q1–Q6/Q10. |
| v1 | 2026-11-19 | Initial frontend design: React 19/Vite SPA decisions, routing and bootstrap, directory and import rules, four-class state model with query-key registry and full event-to-cache map, API client with idempotency/version/retry/upload/download rules, `fetch` SSE hook with reconnect/resync/dedupe, shared-model renderer and chrome overlay, eight screen contracts, client-owned countdown with server-validated advance, stale/undo UI, accessibility and keyboard matrix, responsive rules, performance budget, error surfaces, security/privacy, test plan, open questions, and traceability. |
