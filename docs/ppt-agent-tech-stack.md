# Bound PPT · Technology Stack (v2.1)

> Version: v2.1 · 2026-11-19 · Status: Draft · Owner: Tech Lead / Architecture
> Requirements source: `docs/ppt-agent-prd.md` (PRD v1).
> Architecture source: `docs/ppt-agent-architecture.md` (v1.1).
> Data model: `docs/ppt-agent-data-model.md` (physical schema, SQLAlchemy/Alembic, retention).
> Reference implementation: `yuyuanweb/ai-ppt-generator` (patterns only; no code is copied).
> Scope: implementation stack for M1 (paid-pilot readiness), with M2/M3 extension points. Resolves architecture deferred decisions **DD-1 … DD-20**.

v2 replaces the v1 Node.js/TypeScript stack. The product behavior, interaction flow, gates, and acceptance criteria are unchanged. The two binding implementation constraints are:

1. **Web is React + TypeScript; every server-side component is Python.**
2. **No Redis and no external message broker.** Async work uses an in-process `asyncio` queue; durability is carried by PostgreSQL job records plus reconciliation, not by the queue process.

This document chooses technologies; it does not change product behavior. A stack choice that would change a user-visible contract is raised as a `[CONFLICT]` in §19 and requires a PRD/architecture decision.

---

## 1. Document control

### 1.1 Metadata

| Field | Value |
| --- | --- |
| Document / version / date | Bound PPT Technology Stack / v2 / 2026-11-19 |
| Status / owner / audience | Draft / Tech lead + Architecture / engineering, product, QA, security, finance |
| Requirements source | PRD v1, especially FR-1–FR-8, §8.9 matrices, §11 instrumentation, NFRs |
| Architecture source | Architecture v1.1: AD-1–AD-14, components, runtime flows, state model, cost ledger, security boundaries, DD-1–DD-20 |
| Data model | `docs/ppt-agent-data-model.md` — PostgreSQL tables, SQLAlchemy 2.0 models, Alembic migrations, retention |
| Supersedes | v1 (Node.js/TypeScript end to end, Next.js, Graphile Worker, Prisma) |
| Review cadence | At M1, M2, M3 gates and before a vendor or major-version change |

### 1.2 Decision status vocabulary

| Status | Meaning |
| --- | --- |
| **Frozen for M1** | Implementation may start against this choice. Changing it requires a tech-lead decision and a migration/rollback note. |
| **Proposed vendor** | A default is named so the team can build; the final vendor/region remains `[TBD-INFRA]` or `[TBD-BIZ]` with the stated owner. |
| **Deferred** | No choice in this document; the listed owner decides before the stated stage. |
| `[TBD-BIZ]` / `[TBD-INFRA]` / `[TBD-BE]` / `[TBD-FE]` | Decision not yet made; owner and stage are stated. |

### 1.3 Constraints carried from the repository and the user

- **Server language:** Python 3.12+ (3.13 recommended). No Node.js service in the request path. Node is a build-time tool for the frontend and for the single-file viewer bundle.
- **Client language:** TypeScript 5.x `strict`, React 19.
- **Queue/broker:** no Redis, no Celery/ARQ/RabbitMQ/Kafka, no managed queue. An in-process `asyncio` queue is the only dispatch mechanism in M1. This is a hard constraint, not a default.
- **Process topology:** one application process for M1. The API, scheduler, workers, SSE bus, and rate limiter share one event loop. Horizontal scaling is a deliberate non-goal for M1 (§17.2).
- **Package management:** `uv` for Python (`pyproject.toml` + `uv.lock`); `npm` for the frontend. No pip hand-written requirements files, no poetry, no pnpm/yarn.
- **Secrets:** root `.env` for local development only; `.env.example` contains placeholders only. No secret in the repo, Docker image, client bundle, or logs.
- **No mock content on the paid path** `[PRD FR-7.18, FR-2.20]`.

### 1.4 What we borrow from the reference implementation

The reference project (`ai-ppt-generator`) is a FastAPI + LangChain/LangGraph + python-pptx + React SPA application. We borrow the following patterns because they are proven and fit this architecture:

| Pattern | Why it is adopted |
| --- | --- |
| Layered backend (`api` → `services` → `domain` → `render`) with adapters for LLM, ingestion, storage, images | Keeps the domain free of framework and provider code, matching AD-1/AD-6. |
| Per-page generation tasks with a bounded `asyncio.Semaphore` | Directly implements AD-5 (page failure isolation, inspect-while-generating) without a broker. |
| SSE with a snapshot-first frame, heartbeat, and terminal-event stop | Implements AD-10 (reconnect without silent gaps) without Redis pub/sub. |
| Shared `shared/layouts/*.json` and `shared/themes/*.json` read by both React and python-pptx | One design model, two renderers; prevents web/export drift. |
| `python-pptx` native text boxes, shapes, tables, charts, images; verify by reopening the file | Satisfies the editability acceptance test in FR-6.12 far better than an image-only page. |
| LangGraph “generate → validate → one repair round” single-page workflow | Structured self-correction without unbounded retries. |
| OpenAPI → TypeScript types | Removes frontend/backend contract drift. |
| FontTools glyph metrics for overflow detection, with error/warning tiers | Pre-export validation (FR-6.14) is real, not a timer. |

What we deliberately do **not** borrow:

| Reference choice | Our replacement | Reason |
| --- | --- | --- |
| ARQ + Redis queue and Redis pub/sub | In-process `asyncio` queue + PostgreSQL job rows + in-process event bus | Hard no-Redis constraint; pilot scale does not justify a broker. |
| JWT in `localStorage` | Opaque database session in an HttpOnly cookie | Revocable, no token in JavaScript, simpler CSRF story. |
| Synchronous PPTX export inside the request | Export in an isolated subprocess with validation | Keeps the event loop responsive and isolates Chromium/python-pptx memory. |
| Single hard-coded model provider | `ModelGateway` + LangChain provider adapters | Portability and vendor negotiation (AD-6, NFR-MAINT-2). |
| One process per deck with ad-hoc cancellation flag | Durable `job`/`job_attempt` rows with leases, fencing, deadlines, and cooperative cancellation | The architecture requires real job semantics, not a fire-and-forget task. |
| No durable draft/outline identity | Stable page identity + immutable outline versions | Required by AD-3/AD-11; the reference's simpler editor model is not sufficient for the six-stage flow. |

---

## 2. Scope and decision summary

### 2.1 What this document decides

- Python runtime, web framework, validation, ORM, migrations, database, queue/worker model, SSE transport, cache, auth, object storage.
- Model gateway, prompt execution, structured output, ingestion/URL/search adapters, rendering/export pipeline.
- React/Vite frontend, UI system, client state, API typing, testing.
- Module layout, process topology, CI/CD, deployment, observability.
- The resolution of DD-1 … DD-20 (§18).

### 2.2 What this document does not decide

- Model vendor, model quality tiers, and token budgets — `[TBD-BIZ · founder + tech lead, before development]` (DD-8).
- Search vendor — `[TBD-BIZ · founder + tech lead, before development]` (DD-9).
- Launch region, data residency, and subprocessors — `[TBD-BIZ · founder + legal, before paid pilot]` (BM-8).
- Price points, plans, billing provider, invoice/tax — `[TBD-BIZ · founder + finance + legal, M2]` (DD-15).
- Exact browser support matrix — `[TBD-FE · frontend, before M1]` (PRD-06).
- PPTX fidelity acceptance bar and PowerPoint version matrix — `[TBD-BIZ · product + engineering, before M1]` (PRD-07).
- Retention/deletion SLA and analytics consent — `[TBD-BIZ · legal, before paid pilot]` (PRD-08, BM-7).

### 2.3 Decision principles

| Principle | Consequence |
| --- | --- |
| **Python owns the server; React owns the client** | No cross-language server bridge. The only shared artifacts are JSON schemas, generated TypeScript types, and the `shared/` design vocabulary. |
| **Server-authoritative workflow** | The client never owns stage, gates, page status, stale truth, or history `[ARCH AD-1]`. |
| **Durability is a database property** | A committed `job` row plus an idempotent commit protocol is the durability boundary. The in-process queue is only dispatch. Losing the queue loses latency, never committed work. |
| **Single process at pilot scale** | One uvicorn worker, one event loop, one dispatch table. This removes the broker and makes SSE trivial; it is traded for availability and horizontal scale (§19.2). |
| **One design model, three outputs** | The design body JSON renders in React for web and offline HTML, is printed by Chromium for PDF, and is rebuilt as native shapes by `python-pptx` for editable PPTX. No divergent layout data. |
| **Contracts are generated, not retyped** | Pydantic models define the API; FastAPI emits OpenAPI; `openapi-typescript` emits the SPA types. Design JSON has a JSON Schema and a CI validation gate. |
| **No fake success** | A page is done only with a committed artifact; an export is done only with a downloadable package. The stack must make the fake path hard to build. |
| **Conservative dependencies** | Every runtime dependency is reviewed for maintenance, license, security, and exit cost. No unaudited package. |

### 2.4 Why React + Python

- **The document-AI and ingestion ecosystem is strongest in Python.** PDF layout, DOCX, XLSX, PPTX parsing, font metrics, and image processing all have mature Python libraries. The current architecture's adapter boundary lets parsing be first-class instead of a Node workaround.
- **The AI workflow ecosystem is strongest in Python.** LangChain/LangGraph, Pydantic structured output, and provider SDKs are first-class. The single-page self-correction loop is a Python graph, not a hand-rolled state machine.
- **React remains the best fit for the interaction-heavy client.** The six-stage flow (drag/sort sticky notes, streaming notes, BFCache-safe progress, undo, stale markers, responsive workbench) is a client application. Vite + React 19 keeps the client independent of a server-rendering framework.
- **A broker is not needed at pilot scale.** 5–10 design partners, tens of pages per deck, and bounded concurrency fit comfortably in one process. The reference proves the per-page semaphore pattern; PostgreSQL proves the durable record.
- **Trade-off accepted.** Python has no direct Satori-equivalent SVG renderer, so the fidelity path is Chromium plus native `python-pptx` shapes. CPU-heavy work runs in a bounded process pool or the export subprocess, never on the request path. If the export pipeline outgrows the application container, the subprocess can move to its own container without changing the domain (§12.6/§17.1).

---

## 3. Stack at a glance

### 3.1 Frozen for M1

| Layer | Choice | Why |
| --- | --- | --- |
| Server language | Python 3.12+ (3.13 recommended), type hints enforced | Ecosystem, asyncio maturity, Pydantic. |
| Server runtime | CPython + `uvicorn` (one worker) | One event loop owns the queue and SSE bus. |
| Python package manager | `uv` + `pyproject.toml` + `uv.lock` | Reproducible, fast, repository rule. |
| Web framework | FastAPI | Async, OpenAPI generation, dependency injection, SSE-friendly. |
| Validation/schemas | Pydantic v2 + `pydantic-settings` | One schema source for API, DB payloads, model output, and config. |
| ORM | SQLAlchemy 2.0 async + `asyncpg` | Mature typed models, transactions, `FOR UPDATE`, migrations. |
| Migrations | Alembic (autogenerate + hand-written SQL) | Partial indexes, check constraints, deferred FKs. |
| Database | PostgreSQL 16+ (17 default), managed | Transactional state, JSONB, partial indexes, event log, ledger. |
| IDs | UUIDv7 via the `uuid6` backport (or stdlib `uuid.uuid7()` once the runtime provides it) | Time-sortable application-generated IDs per data-model DM-10. |
| Queue | In-process `asyncio` `JobRunner` + authoritative `job` rows | No Redis; bounded concurrency; DB reconciliation. |
| Scheduler | `asyncio` tasks + periodic DB sweep | Per-page fan-out, retries, deadlines, cancellation. |
| SSE | FastAPI `StreamingResponse` + in-process `EventBus` + `domain_event` replay | One-way server→client, reconnect, no broker. |
| Cache | Process TTL/LRU + PostgreSQL projections | Rebuildable; never authoritative. |
| Rate limiting | In-process token buckets + PostgreSQL counters | Cheap routes in memory; expensive commands durable. |
| Object storage | S3-compatible API via `boto3`; MinIO locally; R2/S3 in production | Presigned uploads/downloads, private buckets. |
| Auth | Opaque DB session token in an HttpOnly cookie; `pwdlib[argon2]` | Revocable sessions, no token in JavaScript. |
| Model orchestration | LangChain (`langchain-core`, `langchain-openai`) + LangGraph | Provider-neutral chat models, structured output, explicit graphs. |
| Structured output | Pydantic models + `with_structured_output`; JSON-mode fallback + validation + one repair | Works across OpenAI-compatible providers. |
| Prompt registry | Versioned Python modules + `evals/` fixtures | Reviewable, traceable, no runtime prompt editing. |
| Search | Adapter interface; Tavily proposed default (`httpx`) | Replaceable; normalized result shape. |
| File parsing | `pdfplumber`/`pypdf`, `python-docx`, `openpyxl`, `python-pptx`, `markdown-it-py` | Per-type adapters; no macro execution. |
| URL extraction | `httpx` + `trafilatura` (fallback `readability-lxml`) | Readable text without a browser; SSRF guard. |
| MIME/type detection | `python-magic` (libmagic) + extension allowlist | Reject mismatches with a specific reason. |
| PPTX export | `python-pptx` native shapes/text/tables/charts/images | Editable Office output; no image-only pages. |
| PDF export | Playwright Chromium printing the same React viewer | 16:9 fidelity, real fonts, one renderer. |
| HTML export | Single-file React viewer bundle with embedded deck JSON and inlined assets | Offline, self-contained, same renderer. |
| Font handling | `fonttools` metrics/subsetting; licensed font registry | Overflow detection, substitution report, no silent unlicensed embedding. |
| Image processing | Pillow | Decode, resize, bounds, format validation. |
| HTML sanitization | `nh3` (or `bleach` if `nh3` is unavailable) | Safe user-derived text and offline HTML. |
| Logging | `structlog` JSON + redaction processors | Content-free structured logs. |
| Tracing/metrics | OpenTelemetry Python (FastAPI/SQLAlchemy/httpx instrumentation) + OTLP | End-to-end project/job/page traces. |
| Errors | Sentry Python SDK | Grouping, release tagging, PII scrubbing. |
| Testing | `pytest`, `pytest-asyncio`, `httpx` AsyncClient, Testcontainers, Playwright, Vitest, RTL, MSW, axe-core | Unit, integration, E2E, accessibility, export smoke. |
| Python lint/format | Ruff (lint + format), mypy | One style/type gate. |
| Frontend framework | React 19 + TypeScript 5.x + Vite | SPA, fast HMR, static build. |
| Router | React Router | Client routes; no server-side rendering requirement. |
| Styling/UI | Tailwind CSS 4 + shadcn/ui (Radix primitives) | Utility styling + accessible source-owned primitives. |
| Icons | Lucide React | Inline SVG; no emoji as structural icons. |
| Server state | TanStack Query | Caching, retries, invalidation, mutation states. |
| View state | Zustand | Selected page, pin, modal, countdown, drafts. Never authoritative project state. |
| Forms | React Hook Form + Zod | Typed forms; shared shape with generated types. |
| Drag and drop | dnd-kit | Accessible sortable sticky notes; keyboard sensor. |
| Motion | Motion (Framer Motion successor) + `useReducedMotion` | Fly-in/page transitions; reduced motion is a hard gate. |
| Toasts | Sonner | Accessible transient notifications. |
| API typing | `openapi-typescript` + JSON Schema → TypeScript for SSE/design payloads | No handwritten duplicate types. |
| Frontend lint/format | ESLint 9 flat config + `eslint-plugin-jsx-a11y` + Prettier; Oxlint optional as a fast pre-check | One style gate; accessibility rules included. |
| CI/CD | GitHub Actions + Docker + `alembic upgrade head` | Reproducible builds, migration gate, staging→prod promotion. |
| Deployment | One application container (API + in-process workers) + managed PostgreSQL + S3-compatible storage | No broker; vertically scaled for M1. |

### 3.2 Proposed vendors / deferred decisions

| Area | Proposed default | Remains |
| --- | --- | --- |
| PostgreSQL | Neon or Supabase (pooled + direct URLs, branching) | `[TBD-INFRA · tech lead, before pilot]` |
| Object storage | Cloudflare R2 (S3 API) | `[TBD-INFRA · tech lead, before pilot]`; AWS S3 for region/enterprise. |
| App hosting | Fly.io or Railway container | `[TBD-INFRA · tech lead, before pilot]`; the Docker image is portable. |
| Model provider | One OpenAI-compatible primary via `langchain-openai`; stage tiers | `[TBD-BIZ · founder + tech lead, before development]` (DD-8). |
| Search provider | Tavily | `[TBD-BIZ · founder + tech lead, before development]` (DD-9). |
| Observability | Grafana Cloud (OTLP) + Sentry | `[TBD-INFRA · tech lead, before pilot]`. |
| Malware scanning | Async scan/quarantine policy | `[TBD-INFRA · security, before pilot]`; type/size limits and sandboxed parsing are mandatory regardless. |
| Transactional email | Managed email provider for invite links/support | `[TBD-INFRA · tech lead, before pilot]`; no marketing email in M1. |
| Billing | Stripe (M2) | `[TBD-BIZ · founder + finance + legal, M2]`; no billing in M1. |

---

## 4. Runtime and repository layout

### 4.1 Processes

| Process | Runs | Responsibilities | Scaling |
| --- | --- | --- | --- |
| `api` | `uvicorn app.main:app` with **one worker** | UI static files (production), auth, command/query API, SSE, scheduler, in-process generation/ingestion workers | **Exactly one process in M1**; vertical scale only. |
| `export` | Short-lived subprocess spawned by the export job handler | Playwright Chromium + `python-pptx` assembly, validation, packaging | One at a time (configurable 1–2); isolated memory; crash does not kill the API. |
| PostgreSQL | Managed service | Metadata, job rows, events, ledger, projections | Primary + optional read replica; PITR. |
| Object storage | S3-compatible | Content, artifacts, exports | Lifecycle + versioning. |

**Hard invariants** (a violation is an incident, not a tuning choice):

1. The API runs with `workers=1`. Multiple uvicorn workers would create multiple in-memory queues and multiple SSE buses; a request could enqueue on one worker and stream from another.
2. CPU-heavy or blocking work never runs on the event loop. Parsing/metrics use `asyncio.to_thread` or a bounded thread/process pool; synchronous SDKs (`boto3`) run through `asyncio.to_thread`; export uses a subprocess.
3. A job's durable state lives in PostgreSQL before any in-memory dispatch happens. The queue is never the only record of a job.

### 4.2 Backend layout

```
backend/
  pyproject.toml / uv.lock
  alembic.ini
  alembic/                  # forward-only migrations
  app/
    main.py                 # FastAPI app factory + lifespan (runner start/stop)
    api/
      deps.py               # session, current user, project scope, idempotency
      v1/                   # projects, materials, research, outline, plan, design, export, events, auth
    core/                   # config, db, security, ids, clock, errors, logging, telemetry
    domain/                 # pure Python: content model, layouts, themes, geometry, validation,
                            # fingerprinting, stale matrix, outline/page/artifact rules
    models/                 # SQLAlchemy 2.0 declarative models
    schemas/                # Pydantic request/response/event/model-output schemas
    services/               # project, orchestrator, artifacts, research, ingestion, generation,
                            # export, events, metering, policy
    workflows/              # LangGraph graphs: outline, page, edit
    llm/                    # model gateway, provider adapters, prompts, structured-output client
    ingest/                 # file/URL adapters + registry + limits
    render/                 # design JSON → viewer HTML / PDF / PPTX; fonts; verify
    storage/                # S3/MinIO adapter, presigned URLs, local filesystem in tests
    worker/                 # JobRunner, handlers, retry/backoff, reconciliation, shutdown
    cli/                    # create-user, reconcile, rebuild-projections, export-openapi
  tests/
frontend/
  package.json / package-lock.json
  src/
    api/                    # request client, generated schema.d.ts
    pages/                  # route-level screens
    features/               # intake, research, outline, plan, style, design, export
    render/                 # React renderer for the shared design model
    components/ui/          # shadcn/ui source components
    hooks/                  # SSE, drag-sort, countdown, save queue
    stores/                 # Zustand view stores
  scripts/                  # OpenAPI/schema generation, viewer build
shared/
  layouts/*.json            # slot geometry + capacity, read by Python and React
  themes/*.json             # palette, fonts, text styles, read by Python and React
  schemas/*.json            # JSON Schema for design body/events (validation gate)
evals/                      # versioned prompt/eval fixtures (outside the request path)
infra/                      # Dockerfiles, compose, deployment manifests, runbooks
docs/
```

Layer rules (enforced by import-linter or a CI script):

- `app/api` may import `services`, `schemas`, `core`; never `models` directly for business logic.
- `app/services` may import `domain`, `models`, `storage`, `llm` interfaces; never FastAPI.
- `app/domain` must not import FastAPI, SQLAlchemy, LangChain, `httpx`, or `boto3`.
- `app/render` reads `shared/` and the design body; it must not call the model or mutate project state.
- `app/llm` exposes stage-level interfaces; provider-specific code stays inside an adapter.
- `frontend` never imports Python; contract types are generated.

### 4.3 Environment configuration

- Root `.env` for local development; `.env.example` committed with placeholders.
- `pydantic-settings` validates environment variables at boot; missing/malformed values fail fast.
- Secrets live in the platform secret store in staging/production.
- Required names (values not included): `DATABASE_URL`, `DIRECT_DATABASE_URL`, `SESSION_SECRET`, `APP_BASE_URL`, `S3_ENDPOINT`, `S3_REGION`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `MODEL_PROVIDER`, `MODEL_BASE_URL`, `MODEL_API_KEY`, `MODEL_ID`, `SEARCH_API_KEY`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `SENTRY_DSN`, `APP_ENV`.
- Only non-secret values may be exposed to the browser; provider/database/storage secrets are server-only.

---

## 5. Frontend stack (React + Vite SPA)

### 5.1 Rendering model

- The app is a client-side SPA built by Vite. React Router owns routes; there is no Next.js server component model.
- Production: FastAPI serves `frontend/dist` as static files with an SPA fallback (`/api/*` is never swallowed by the fallback). A reverse proxy may serve the static files instead; the API contract is unchanged.
- Development: Vite dev server proxies `/api` to `http://127.0.0.1:8000`, so cookies and SSE are same-origin in dev.
- Authoritative project data is always fetched from the API. The SPA does not cache project data in a service worker or local database.
- Navigating away from a generating project does not cancel the server job; returning re-reads the snapshot and resubscribes `[PRD FR-7.5]`.

### 5.2 Component and styling system

- Tailwind CSS 4 for layout/spacing; shadcn/ui source components for accessible primitives (dialog, radio group, checkbox, tabs, progress, toast).
- Radix primitives provide focus management; the app still implements the PRD's explicit focus/semantic contract: `role="log"`, `role="status"`, `aria-busy`, `aria-current="step"`, `aria-label="needs rerun"`, modal focus trap/restore, and focus-to-heading on stage change `[PRD FR-7.11]`.
- Design tokens (color, type, radius, shadow, motion) exist twice by design: Tailwind/shadcn tokens for the app shell, and `shared/themes/*.json` for deck content. The deck theme is content data, not the app theme; they must not be conflated.
- Icons are inline SVG from Lucide; no emoji as structural icons.
- `prefers-reduced-motion` disables fly-in/typewriter animation; content is immediately readable `[PRD FR-7.12]`.
- Contrast: body/secondary text meets 4.5:1; the focus ring is always visible `[PRD FR-7.13]`.

### 5.3 Client state split

| State | Owner | Examples |
| --- | --- | --- |
| Server state | TanStack Query + API | Project snapshot, page list, artifact metadata, job/export status, source panel. |
| Local view state | Zustand | Selected page, pinned page, open modal, countdown token, draft title/tweak text, stage-nav focus. |
| Form state | React Hook Form + Zod | Topic, material paste/URL, tweak instruction, profile edits. |
| Ephemeral stream state | SSE hook + local reducer | Partial outline notes, card deltas, progress ticks. Reconciled to authoritative snapshots. |

The client never writes stage, stale, page status, or history. Optimistic UI is limited to title drafts, reorder preview, chip add/remove, and selection highlight; the server response wins `[ARCH §8.7]`.

### 5.4 Key interactions and libraries

| Interaction | Implementation |
| --- | --- |
| Sticky-note drag/sort | dnd-kit sortable + keyboard sensor; cross-section drag; `Alt+↑/↓` and `Shift+Alt+←/→` custom handlers `[PRD FR-3.5–3.8]`. |
| Inline title edit | Native input with Enter-to-save; no drag activation while editing. |
| Stage navigation | React Router; completed stages clickable, future disabled, stale amber dot + `aria-label`; ≤920px native `<select>` `[PRD FR-7.2, FR-7.14]`. |
| Countdown | Client-owned 3-second countdown with Pause; edit/add/delete/sort cancels; at zero sends `advanceStage` with a countdown token; server validates `[ARCH AD-9; PRD FR-3.11]`. |
| Page paging | Thumbnail list + `←`/`→`; selecting during generation pins the current page; remaining pages continue server-side `[PRD FR-6.3]`. |
| Export modal | Radix Dialog focus trap; Esc closes; progress `role="progressbar"`; failure keeps the modal open `[PRD FR-6.11, FR-6.15]`. |
| Toasts | Sonner for non-blocking success/error/undo hints; never the only signal for a required state. |

### 5.5 Contract generation

- FastAPI emits `/openapi.json`; `npm run gen:api` runs `openapi-typescript` into `src/api/schema.d.ts`.
- SSE event models and the design body are Pydantic models; `python -m app.cli.export_schemas` writes JSON Schema to `shared/schemas/`, and `npm run gen:shared` generates TypeScript types.
- CI fails if generated files differ from the committed output. This replaces hand-maintained duplicate interfaces.

### 5.6 Frontend testing

- Vitest + React Testing Library for components and hooks.
- MSW for API/SSE fixtures; no test may call a real model or search provider.
- Playwright for the six-stage happy path, stale rerun, undo, reconnect, export failure, keyboard matrix, and responsive breakpoints.
- `@axe-core/playwright` + `eslint-plugin-jsx-a11y`; manual screen-reader audit before M1.
- Visual snapshots for plan wireframes, design pages, style cards, and the export modal at 1440/1180/920/720/390.

---

## 6. API, streaming, and auth

### 6.1 API style

- REST JSON command/query API implemented with FastAPI routers. No GraphQL, tRPC, or client-side database access in M1.
- Commands are intention-named writes; queries are side-effect-free reads `[ARCH §9]`.
- All request/response bodies are Pydantic models; FastAPI validates and documents them.
- Every mutating command carries:
  - `expectedVersion` (project optimistic concurrency),
  - `idempotencyKey` (intent key),
  - a discriminated `type` and typed `payload` (or a dedicated endpoint per command with the same envelope fields).
- Error envelope follows the architecture taxonomy: category, retryable, message key, safe details, correlation IDs; never echo user text `[PRD §8.9.2; ARCH §9.3]`.

Example command envelope:

```json
{
  "type": "editOutlinePage",
  "expectedVersion": 12,
  "idempotencyKey": "01J...",
  "payload": { "projectId": "…", "pageId": "…", "title": "…" }
}
```

Example error envelope:

```json
{
  "ok": false,
  "error": {
    "category": "conflict",
    "retryable": true,
    "messageKey": "error.conflict.stale_version",
    "details": { "currentVersion": 13 },
    "requestId": "…",
    "traceId": "…"
  }
}
```

### 6.2 Endpoint shape

| Area | Endpoint (illustrative) |
| --- | --- |
| Project | `POST /api/projects`, `GET /api/projects/:id/snapshot`, `POST /api/projects/:id/commands` |
| Materials | `POST /api/projects/:id/materials/upload-url`, `POST /api/projects/:id/materials`, `DELETE /api/projects/:id/materials/:materialId` |
| Pages | `GET /api/projects/:id/pages`, `GET /api/projects/:id/pages/:pageId/artifacts/:kind`, `GET /api/projects/:id/pages/:pageId/history` |
| Jobs/exports | `GET /api/projects/:id/jobs/:jobId`, `GET /api/projects/:id/exports/:exportId`, `GET /api/exports/:exportId/download` |
| Stream | `GET /api/projects/:id/events?cursor=...` (SSE) |
| Auth | `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me` |

The exact URL table is an implementation detail; the command/query names, version/idempotency rules, and event contracts are not.

### 6.3 SSE and reconnect

- SSE is served by the same process that runs the jobs. There is no cross-process fan-out in M1.
- Each connection sends:
  - a `snapshot` event at the current project sequence when the client has no valid cursor,
  - durable `domain_event` rows in sequence order from the requested cursor,
  - a heartbeat comment every 15 seconds,
  - a `resync` event when the cursor is older than retention.
- The client consumes the stream with `fetch` + `ReadableStream` rather than native `EventSource`: it sends the last received `sequence` as a `cursor` query parameter, aborts on unmount, and can be intercepted by MSW in tests. The server also accepts `Last-Event-ID` for compatibility with proxies or a native client.
- Within the retained window it replays; otherwise it reloads the project snapshot `[ARCH AD-10]`.
- Durability is the `domain_event` table, not the connection. A dropped connection loses no committed state `[PRD FR-7.9]`.
- The in-process `EventBus` fans out committed events to live subscribers. Subscriber queues are bounded; a slow subscriber is disconnected with `resync` rather than allowed to grow without bound.
- Ephemeral model-token deltas (`outlineDelta`, `cardDelta`) are batched by the worker (100–250 ms) and published to the `EventBus` only; they are **not** persisted in `domain_event`. If a client misses them, it reloads the committed outline/plan/design `[ARCH §9.2]`.
- SSE headers: `Content-Type: text/event-stream`, `Cache-Control: no-store`, `Connection: keep-alive`, `X-Accel-Buffering: no`; the load balancer idle timeout MUST exceed the heartbeat interval.

Event delivery sketch:

```python
# app/services/events.py
class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[UUID, set[asyncio.Queue[DomainEvent]]] = defaultdict(set)

    def subscribe(self, project_id: UUID) -> asyncio.Queue[DomainEvent]:
        queue: asyncio.Queue[DomainEvent] = asyncio.Queue(maxsize=256)
        self._subscribers[project_id].add(queue)
        return queue

    def publish(self, project_id: UUID, event: DomainEvent) -> None:
        for queue in list(self._subscribers.get(project_id, ())):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Slow consumer: drop it; the client will resync from the event log.
                self._subscribers[project_id].discard(queue)
```

The endpoint subscribes **before** reading the durable replay, then dedupes live events by `sequence`; this closes the gap between “read history” and “start listening”.

### 6.4 Auth

- Invite-only pilot onboarding in M1. No self-serve signup and no billing.
- **Opaque database sessions**: a 32-byte random token is sent in an HttpOnly cookie; only its SHA-256 hash is stored in `session`. Sessions are revocable by deleting the row.
- Pilot users have an email + password credential, hashed with Argon2 via `pwdlib[argon2]`. A CLI command (`python -m app.cli.create_user`) provisions accounts; there is no self-serve signup. M2 adds magic links/SSO through the policy boundary.
- Session cookie: `HttpOnly`, `Secure` in production, `SameSite=Lax`, `Path=/`. Mutating routes also verify the request origin.
- API routes authorize project scope on every command/query; the client cannot select another tenant by changing an ID `[PRD NFR-SEC-1]`.
- No provider or storage secret is ever exposed to the browser.
- The `auth_account` table is reserved for M2 OIDC/provider links; M1 does not use it.

### 6.5 Rate limiting

- Cheap routes use in-process token buckets keyed by user/session.
- Expensive commands (generation, export, search) also reserve a PostgreSQL counter row, so a restart does not reset a paid quota.
- A rejected request returns `429` with `Retry-After`; the client backs off and retries with the same idempotency key.

---

## 7. Domain and backend modules

### 7.1 Component mapping

| Architecture component | Implementation |
| --- | --- |
| Web client | `frontend/src` React SPA + shadcn/Radix UI |
| Edge/API | FastAPI routers + auth/authorization + idempotency + rate limiting |
| Stream gateway | SSE route + `EventBus` + `domain_event` replay |
| Project service | `app/services/project.py` + repositories |
| Workflow orchestrator | `app/services/orchestrator.py` — gates, stale derivation, affected scope, job planning |
| Artifact/version service | `app/services/artifacts.py` — immutable versions, pointers, history, lineage, commit |
| Style/asset registry | `app/services/styles.py` + `shared/themes` + license records |
| Ingestion service | `app/services/ingestion.py` + `app/ingest` adapters |
| Research service | `app/services/research.py` — digest, gaps, profile, search orchestration |
| Generation service | `app/services/generation.py` + `app/workflows` + `app/llm` |
| Model gateway | `app/llm/gateway.py` — LangChain adapters, timeout/retry, usage capture |
| Search adapter | `app/ingest/search.py` — normalized results, caps, zero/failure outcomes |
| Render/export service | `app/render` + `app/services/export.py` + export subprocess |
| Job scheduler/workers | `app/worker/runner.py` + handler registry |
| Event/telemetry/ledger | `app/services/events.py` + `app/services/metering.py` + `domain_event`/`usage_record` |
| Policy/identity/billing boundary | `app/services/policy.py` + session auth; billing M2 |
| Config/feature flags | `config_version` table + env; no runtime external flag vendor in M1 |

### 7.2 Transaction boundaries

- A command updates project state, appends `domain_event`, and inserts the `job` row in one PostgreSQL transaction. After commit, the API wakes the runner.
- Artifact commit follows data-model §7.1: validate fencing/epoch → insert version/lineage/source refs → push history → install pointer → complete job → emit event.
- Export never mutates project state, style selection, or page artifacts `[ARCH §5.4]`.
- Content is written to object storage before the metadata transaction; the pointer install is the commit point; an orphan sweeper removes unreferenced writes.

### 7.3 Error handling

- Domain errors are typed exceptions with stable codes mapped to the architecture taxonomy; no string matching in the UI.
- Retry ownership: adapters do bounded transient retries inside one attempt; the runner owns cross-attempt retry/backoff; the orchestrator owns user-initiated retry; the client only resubscribes and resends pending intent with the same idempotency key `[ARCH §10]`.
- A failure MUST leave current pointers and history unchanged; a late worker result is fenced if the head moved or the job was cancelled.
- Unexpected exceptions are logged with IDs only; the user sees a message key and a correlation ID.

---

## 8. Data and storage

### 8.1 PostgreSQL

- Managed PostgreSQL 16+ (default 17), with pooled application connections and a direct connection for migrations.
- SQLAlchemy 2.0 async with `asyncpg`; Alembic migrations are the only schema change mechanism.
- `DATABASE_URL` uses the pooler; `DIRECT_DATABASE_URL` is used only by `alembic upgrade head`.
- Connection limits are sized per process. With one API process at pilot scale: pool 10–20 total, plus one direct migration connection. Exact values are load-tested `[TBD-INFRA]`.
- Read replicas are optional; authoritative reads and all writes go to the primary.
- Migrations run as a release step with an advisory lock; application instances never auto-migrate on boot `[ARCH §13]`.

### 8.2 SQLAlchemy usage rules

- Repositories are the only layer that imports SQLAlchemy sessions for business reads/writes; domain services depend on repository protocols.
- Multi-step invariants use `async with session.begin()` with the smallest possible scope; no external provider call inside a database transaction.
- Money/units use `NUMERIC` mapped to `Decimal`; never `float` for ledger math.
- Raw SQL is allowed for queue polling/reconciliation, projection audits, partial-index-backed queries, and report aggregates; it must be parameterized.
- `select()` is explicit on hot paths; no accidental loading of large JSONB or content-bearing fields.
- `SELECT … FOR UPDATE` is used for job claim and artifact pointer install; never for long provider calls.

### 8.3 Object storage

- S3-compatible API via `boto3`, private buckets, server-side encryption, versioning where available. `boto3` is synchronous; every call runs through `asyncio.to_thread` so the event loop is never blocked on object storage.
- Upload flow:
  1. Client requests a presigned PUT with file name/type/size.
  2. Server validates metadata, project quota, and MIME/extension policy before signing.
  3. Client uploads directly to the bucket.
  4. Client finalizes; server HEADs the object, enforces actual size/type, then enqueues ingestion.
- Download flow: server authorizes project/tenant access, then returns a short-lived signed URL. Raw object keys never reach the browser `[PRD NFR-SEC-1]`.
- Key layout follows data-model §9.1; tenant prefix is mandatory.
- Lifecycle rules: expire export artifacts, abort incomplete multipart uploads, and archive/delete per retention policy.
- Local development uses MinIO (S3-compatible) via Docker Compose.

### 8.4 Cache

- M1 does not use Redis.
- In-process caches are allowed only for versioned, non-user-specific data (style definitions, config snapshots, layout/theme JSON) with a short TTL and a version key.
- `project_snapshot_cache` and `render_cache` are PostgreSQL tables; they are rebuildable and never authoritative.
- If SSE fan-out, rate limiting, or session throughput outgrows one process at M2, the transport/cache can change behind the same interfaces; it must not become the source of truth.

---

## 9. Async jobs (in-process queue)

### 9.1 Why an in-process queue

The architecture requires durable, resumable, cancellable, per-page jobs that survive navigation, refresh, and network loss `[ARCH AD-2; PRD FR-7.5; NFR-REL-3/4]`. It does **not** require a broker. At pilot scale, a single process can hold the dispatch queue and the SSE bus; PostgreSQL holds the durable job state. This removes Redis, one operational service, and the failure mode where the broker is up but the application cannot reach it.

What the queue provides:

- bounded concurrency and backpressure;
- per-project and per-page fairness;
- cooperative cancellation;
- retry scheduling with jittered backoff;
- wake-up latency measured in milliseconds.

What the queue does **not** provide (and where PostgreSQL takes over):

- surviving a process crash;
- cross-process or cross-instance delivery;
- guaranteed execution while the process is down.

### 9.2 Architecture

```
┌──────────────────────────── API process (uvicorn, workers=1) ────────────────────────────┐
│                                                                                          │
│  FastAPI request ──enqueue(transaction)──▶ PostgreSQL: job + domain_event + state        │
│        │                                                   │                             │
│        └──after commit──▶ JobRunner.wake(job_id) ──▶ asyncio.Queue (bounded)             │
│                                                                  │                       │
│                       ┌──────────────────────────────────────────┘                       │
│                       ▼                                                                  │
│  generation workers (N) ──claim/fence──▶ handler ──▶ service ──▶ artifact commit         │
│  export worker (1) ──▶ subprocess: Playwright + python-pptx ──▶ artifact commit          │
│                                                                                          │
│  EventBus ──▶ SSE subscribers (bounded per-project queues)                               │
│  Reconciler ──▶ startup + every 30s: re-wake queued jobs, requeue expired leases         │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

### 9.3 Job record is authoritative

The `job` and `job_attempt` tables (data-model §6.6) remain authoritative for state, attempts, deadline, cancellation, fencing, and history. No external queue row exists: the in-memory queue holds only `job_id` values, and the nullable `queue_job_id` column is reserved for a future transport (data-model §6.6).

Critical fields:

| Field | Use |
| --- | --- |
| `state` | `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED`, `EXPIRED`. |
| `active_operation_key` | Unique for active work; prevents duplicate page writes. Cleared on terminal state. |
| `attempt_count` / `max_attempts` | Cross-attempt retry accounting. |
| `deadline_at` | No execution after the deadline; visible timeout. |
| `cancel_requested_at` | Cooperative cancellation flag. |
| `lease_owner` / `lease_expires_at` | Which worker owns the attempt and when the lease expires. |
| `fencing_token` | Monotonic per claim; commit verifies it. |

### 9.4 Enqueue protocol

1. In one transaction: insert the `job` row (`state=QUEUED`, `active_operation_key=…`), append `domain_event(jobQueued)`, update the project/stage projection as needed.
2. Commit.
3. Call `runner.wake(job_id)`.
4. If the process crashes between 2 and 3, the startup/periodic reconciler finds the `QUEUED` row and wakes it.

`wake()` never blocks the request path: if the bounded queue is full, it returns and lets the reconciler pick the job up. The committed job is never lost because the queue was full.

```python
# app/worker/runner.py (shape, not final code)
class JobRunner:
    def __init__(self, *, handlers, generation_workers: int, export_workers: int) -> None:
        self._handlers = handlers
        self._queue: asyncio.Queue[UUID] = asyncio.Queue(maxsize=2048)
        self._queued: set[UUID] = set()  # pruned on dequeue/terminal state
        self._worker_count = generation_workers + export_workers
        self._generation = asyncio.Semaphore(generation_workers)
        self._export = asyncio.Semaphore(export_workers)
        self._project: dict[UUID, asyncio.Semaphore] = defaultdict(lambda: asyncio.Semaphore(2))
        self._stopping = asyncio.Event()

    def wake(self, job_id: UUID) -> None:
        if job_id in self._queued:
            return
        self._queued.add(job_id)
        try:
            self._queue.put_nowait(job_id)
        except asyncio.QueueFull:
            # Not an error: the DB reconciler will re-wake it.
            self._queued.discard(job_id)

    async def run(self) -> None:
        tasks = [asyncio.create_task(self._worker()) for _ in range(self._worker_count)]
        tasks.append(asyncio.create_task(self._reconcile_loop()))
        await self._stopping.wait()
        # Graceful shutdown: stop pulling, let running attempts finish or requeue them.
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
```

### 9.5 Claim, lease, and commit

Claim is a single conditional update; the returned `fencing_token` is passed to the handler and to every artifact commit:

```sql
UPDATE job
SET state = 'RUNNING',
    lease_owner = :worker_id,
    lease_expires_at = now() + interval '60 seconds',
    fencing_token = fencing_token + 1,
    attempt_count = attempt_count + 1
WHERE id = :job_id
  AND state = 'QUEUED'
  AND (deadline_at IS NULL OR deadline_at > now())
RETURNING fencing_token, attempt_count;
```

- In the same transaction as the claim, insert a `job_attempt` row with `attempt_no = attempt_count`, the returned `fencing_token`, and `state='RUNNING'`.
- A heartbeat task extends `lease_expires_at` every 15–20 seconds while the handler runs.
- Commit is conditional on `state='RUNNING'` and the same `fencing_token`; a late result whose token does not match is discarded.
- The artifact commit, the `job_attempt` close (state, ended_at, usage fields), and `job.state='SUCCEEDED'` happen in one transaction, so a succeeded job always has its artifact and a failed job never installed a pointer.
- On terminal state, `active_operation_key` is cleared to free the page's write slot.
- `job_attempt` records provider/model/tokens/latency/cost per attempt, even for failed attempts.

### 9.6 Retry, backoff, cancellation

- Retryable failure: close the attempt row as `FAILED`, set `state=QUEUED`, and schedule `wake(job_id)` after a jittered exponential delay (in-memory timer). `attempt_count` was already incremented at claim.
- Permanent failure or attempts exhausted: close the attempt row and set `state=FAILED`; emit `pageJobFailed`/`jobFailed` with a stable error code.
- A process restart loses in-memory retry timers; the reconciler re-wakes `QUEUED` jobs immediately. This may shorten a backoff window but never duplicates a committed artifact.
- Cancellation is cooperative: `cancel_requested_at` is checked at task checkpoints (before a model call, between pages, before packaging). A cancelled job never installs a result; a late result is fenced. The in-flight page is allowed to finish rather than being killed mid-write, to avoid wasted provider spend and half-states.
- A job past `deadline_at` becomes `EXPIRED`; it is not executed.

### 9.7 Concurrency and fairness

- **Global generation slots** (default 4) bound concurrent model-heavy page jobs.
- **Per-project slots** (default 2) prevent one project from monopolizing the process.
- **Per-page single writer** is enforced by `active_operation_key`; a second `regeneratePage` returns the active job, not a duplicate.
- **Export slot** (default 1) is separate; export runs in a subprocess with a memory cap.
- **Ingestion slots** (default 2) are separate from generation so a large upload does not starve page generation.
- Queue order is priority, then `created_at`; retries do not jump ahead of user-initiated work indefinitely.

### 9.8 Reconciliation and shutdown

On startup and every 30 seconds:

1. Re-wake `QUEUED` jobs not currently in the in-memory set (bounded batch, ordered by priority/created_at).
2. Requeue `RUNNING` jobs whose `lease_expires_at < now()` and whose process is not alive (single-process M1 makes this unambiguous).
3. Mark `QUEUED` jobs past `deadline_at` as `EXPIRED`.
4. Verify that `SUCCEEDED` jobs have artifacts and that pointers resolve; log a content-free audit event on mismatch.

On graceful shutdown (`lifespan`):

1. Stop accepting new commands (readiness fails first).
2. Stop pulling new jobs.
3. Give running handlers a grace window (e.g., 30 s) to finish.
4. Requeue unfinished attempts (`state=QUEUED`, release lease) so the next start re-runs them.
5. Close the DB pool and flush telemetry.

### 9.9 Failure matrix

| Failure | Effect | Recovery |
| --- | --- | --- |
| Handler raises a retryable error | Page/job stays `QUEUED` | Jittered backoff; attempt metered; no pointer installed. |
| Handler raises a permanent error | Page `error`; other pages continue | User retries the page; no duplicate history/charge. |
| Process crash / OOM / deploy | In-flight attempt lost; queue memory lost | Job rows survive; startup reconciler re-wakes `QUEUED` and expires leases; fencing prevents duplicate commit. |
| Queue full | Wake skipped | Reconciler wakes the committed job; request path never blocks. |
| DB unavailable | No new jobs, no commits | API returns a retryable error; in-memory work cannot commit and is requeued later. |
| Export subprocess crashes | One export fails | Parent marks `exportFailed` with a reason; retry re-spawns; no success without a file. |
| Slow SSE subscriber | Queue fills | Subscriber is dropped with `resync`; client reloads snapshot. |
| Duplicate command (double click) | Idempotency key returns the active job | No second job, no double charge `[PRD NFR-REL-3]`. |

**What is lost on a process restart:** unwritten in-memory progress, ephemeral token deltas, and retry timers. **What is never lost:** committed project state, job records, artifacts, pointers, history, events, and ledger rows. The product can always resume from the last committed artifact.

### 9.10 Task registry

| Task | Job type | Runs | Notes |
| --- | --- | --- | --- |
| `ingest-material` | `INGEST` | Parse/fetch/normalize one material | One material failure does not fail others; bounded thread/process pool. |
| `digest-material` | `DIGEST` | Produce per-material digest | Structured output + validation. |
| `search-gaps` | `SEARCH` | Run one targeted query per selected gap | Bounded by source/search caps; zero result and failure are recorded outcomes. |
| `suggest-gaps` | `GAP_SUGGEST` | Judge sufficiency, propose three gaps | Runs after selected digests. |
| `build-profile` | `PROFILE` | Produce/refresh requirements profile | Requires four answers; dirty gate is orchestrator-owned. |
| `generate-outline` | `OUTLINE` | Stream outline deltas, validate, commit outline version | Committed outline is the artifact; deltas are ephemeral. |
| `plan-page` | `PLAN_PAGE` | Plan one page | Per-page job, bounded concurrency. |
| `design-page` | `DESIGN_PAGE` | Design one page | Reads plan version + style token version. |
| `export-deck` | `EXPORT` | Validate, render, package, checksum | Separate slot/subprocess. |
| `delete-project` | `DELETE_PROJECT` | Cancel, delete content, tombstone, verify | Idempotent sweeper. |

### 9.11 Upgrade path (M2+)

The `JobRunner` and `EventBus` are interfaces, not assumptions spread across services. If M2 needs multiple processes or instances:

- Replace the dispatch with a PostgreSQL queue (`SELECT … FOR UPDATE SKIP LOCKED`) or a managed broker behind the same interface; keep the `job` table authoritative.
- Replace `EventBus` fan-out with PostgreSQL `LISTEN/NOTIFY` or Redis; keep `domain_event` as the replay source.
- Move export to its own deployment; the subprocess contract already isolates it.

None of these changes the domain, API, or UX contracts.

---

## 10. AI model gateway

### 10.1 Provider abstraction

- `app/llm/gateway.py` exposes stage-level methods (`digest`, `gaps`, `profile`, `outline`, `plan_page`, `design_page`, `tweak`) and never leaks a provider SDK to the domain.
- LangChain `BaseChatModel` adapters: `langchain-openai` for OpenAI-compatible providers (OpenAI, DeepSeek, Qwen, etc.). The base URL, model ID, and key are configuration, not code `[ARCH AD-6]`.
- Structured output uses Pydantic models with `with_structured_output`. If the provider does not support JSON Schema mode, the adapter falls back to JSON mode with an explicit schema in the prompt, then validates with Pydantic.
- Invalid output is a failed attempt, never a confirmed artifact. A bounded repair round (one) is allowed; it is metered and recorded.
- Streaming uses LangChain's `astream`; the worker batches deltas and publishes them to the `EventBus`. Only the final validated result is written as an artifact.

### 10.2 Workflows

- **Outline graph:** trim/select source sections → generate structured outline → validate page count, layout IDs, source refs → one repair → return candidate.
- **Page graph:** trim the page's sources → generate a structured draft → geometry fit (width then height) → validate structure/richness → one repair → return candidate. The graph is compiled once and reused; each page runs it independently.
- **Edit graph:** bind edit tools to a page snapshot; the model proposes structured operations; the domain applies them with bounds checks; validation runs before commit.
- The graph is not a substitute for the orchestrator: it produces a candidate; the artifact service commits; the job runner schedules.

### 10.3 Routing policy

- Stage-level `generation_profile` rows select provider/model/params/prompt version/output schema.
- Default intent (not a vendor commitment): economy tier for digest/gap suggestions/plan; quality tier for outline/design; tweak inherits the design tier. Final model selection is `[TBD-BIZ · founder + tech lead, before development]`.
- A provider failover may be configured, but a fallback result must pass the same structured validation and quality bar; a cheap fallback must not silently lower quality `[ARCH AQ-14]`.
- No client-side model calls; no provider key in the browser.

### 10.4 Prompt management

- Prompts live in `app/llm/prompts/` as versioned Python modules with explicit `PROMPT_VERSION` IDs.
- Prompt changes are code-reviewed and evaluated against `evals/` before release; no runtime prompt-editing UI in M1.
- The prompt registry records the prompt version in `artifact_version`/`job_attempt` for traceability.
- Material and web text are always treated as untrusted data, separated from system instructions; structured output bounds the fields `[ARCH §12]`.

### 10.5 Cost and quota hooks

- Every model/search/parse/render/export call writes a `usage_record` at the adapter boundary with `operation_key`, project/stage/page/job/attempt attribution.
- A fingerprint hit installs an existing artifact with zero jobs and zero provider cost `[PRD NFR-COST-4]`.
- Per-project caps and per-job attempt/time limits are enforced before enqueue; soft budgets alert before hard stops `[ARCH §11]`.
- Failed attempts are metered but not charged twice; quota consumption commits once per logical operation.

---

## 11. Ingestion and research adapters

### 11.1 File parsing

| Type | Default parser | Notes |
| --- | --- | --- |
| `.pdf` | `pdfplumber` (layout/text), `pypdf` fallback | Page count, text extraction; scanned/image-only PDFs need OCR (deferred unless PRD-19 says M1). |
| `.docx` | `python-docx` | Text + basic structure; no macro execution. |
| `.xlsx` / `.csv` | `openpyxl` / stdlib `csv` | Sheet/row/column limits; treat formulas as data, never execute. |
| `.pptx` | `python-pptx` | Extract slide text/notes; no rendering. |
| `.md` / `.txt` | `markdown-it-py` / UTF-8 read | Size cap. |
| Images/scans | `pytesseract` + Tesseract (optional) | `[TBD-BE · backend, M1]` per PRD-19; CPU-heavy, runs in a thread pool. |

Rules:

- The supported-type list is a **proposed M1 default**. The final list and per-file size/page limits are `[TBD-BE-1 · backend, before development]`; the UI must not claim a type is supported until its parser passes the ingestion tests.
- Validate extension + MIME with `python-magic`; reject mismatch with a specific reason `[PRD FR-1.8]`.
- Enforce per-file size, page count, extracted-character, decompression-ratio, and parser-time limits; values are config, not hard-coded `[PRD BR-7]`.
- Run parsing off the event loop and as a job: a bounded thread pool for I/O-bound parsers, a process pool for CPU-bound parsers/OCR; one material failure does not block others `[PRD FR-1.9]`.
- Strip active content; never execute macros/scripts; quarantine/scan policy is `[TBD-INFRA · security]`.
- Persist raw + normalized content to object storage; only references and buckets go into metadata.

### 11.2 URL fetch/extraction

- `httpx` fetch with a strict timeout, redirect cap, content-type allowlist, and byte cap.
- `trafilatura` for readable text; `readability-lxml` fallback for simpler HTML.
- SSRF protection: resolve DNS, block loopback/private/link-local/metadata ranges, re-check after redirects, forbid credentials and non-HTTP(S) schemes.
- Login wall / anti-scraping / 404 → explicit failure + “paste the body text” suggestion; other sources remain `[PRD FR-1.10]`.
- Do not execute page JavaScript in M1; if a critical source class requires it, add a sandboxed Playwright fetch adapter later `[TBD-BE · backend, post-M1]`.
- Store the fetched text and source metadata; never emit the full URL to analytics; store `url_hash` + domain.

### 11.3 Web search

- Adapter interface: `search(query, cap) → results | zero_results | provider_error`.
- Tavily is the proposed default; vendor selection remains `[TBD-BIZ]`.
- Normalize each result to title, summary, URL (stored), domain, rank; the source panel shows title/summary/origin `[PRD FR-2.15]`.
- Zero results are a recorded outcome, never a silent skip; selected gaps are searched individually `[PRD FR-2.10/2.20]`.
- Enforce source/search caps per project/plan; the cap is visible to the user `[PRD FR-2.19]`.

---

## 12. Rendering and export

### 12.1 Canonical page model

- The design artifact is a structured **design body JSON**: page type, layout ID, blocks/elements, text runs, asset references, and resolved style values.
- `shared/layouts/*.json` defines slot geometry and capacity; `shared/themes/*.json` defines palette, fonts, and text styles. Both are versioned and read by the React renderer and the Python renderers.
- Chrome (page header, page number, section label, deck order) is applied deterministically at render time from the outline version and deck order; it is not baked into the design body `[ARCH AD-12]`.
- The same design body drives:
  - the React web preview/editor,
  - the offline HTML viewer,
  - the Chromium-printed PDF,
  - native PPTX shapes/text.
- This avoids divergent renderers and preserves one source of truth.
- `render_cache` is optional in M1: the SPA renders thumbnails from the design body, and the table is reserved for a future server-side preview/reuse path; it is rebuildable and never authoritative.

### 12.2 React renderer (web and offline HTML)

- `frontend/src/render/` maps the design body and shared layout/theme JSON to React components. Flex layouts use CSS flexbox/absolute positioning; the same geometry rules are mirrored in the Python PPTX renderer.
- The web editor and the read-only viewer use the same renderer; editing wraps text blocks in constrained `contenteditable` or inputs but does not change layout rules.
- A dedicated `viewer.html` single-file bundle is built at frontend build time (Vite library mode plus a single-file inline step, e.g. `vite-plugin-singlefile`). It contains the renderer, inline CSS, and inline font data; the export runner injects the deck JSON.
- Offline HTML: images are downloaded and inlined as data URIs (with per-image and total caps); fonts are embedded or substituted with a report; no external network request is needed at open time.
- Sanitization: user/web-derived text is escaped; no script from material content is ever embedded.

### 12.3 PDF

- The export subprocess loads the single-file viewer in Playwright Chromium via a `file://` URL.
- It waits for `window.__BOUND_READY__ === true`, then prints with:
  - width `13.333in`, height `7.5in` (16:9),
  - `print_background=True`,
  - no headers/footers,
  - a fixed 1280×720 CSS viewport to match the reference canvas.
- Post-export checks: page count equals deck pages, aspect ratio is 16:9, file size > 0, checksum recorded.
- Chromium runs only in the export subprocess; the API event loop never starts a browser.

### 12.4 PPTX

- `python-pptx` builds a 16:9 PPTX with **native text boxes, shapes, tables, charts, and images** derived from the design body and shared layout JSON. This is the path that preserves text/shape editability.
- The React/PDF render is the visual fidelity reference; an image-only page is not an acceptable final result `[PRD FR-6.12]`.
- Fonts: use licensed font families; use `fonttools` for metrics and subsetting where supported; set East Asian font names explicitly; produce a substitution report when a font is unavailable. Silent unlicensed embedding is forbidden `[PRD FR-6.17]`.
- Assets: images are decoded with Pillow, checked for bounds/orientation, and embedded at the required resolution; out-of-bounds/overflow assets fail validation.
- The PPTX package is reopened with `python-pptx` and checked for valid OOXML parts, slide count, text presence, and non-zero size; a checksum is recorded.
- See §19.1 for the `[CONFLICT]` between the PRD wording “SVG-composited PPTX” and the editability acceptance test.

### 12.5 Pre-export validation

The export job MUST run and record these checks before claiming success `[PRD FR-6.14]`:

- every page has a current design artifact;
- page count and deck order match the outline snapshot;
- style tokens and license status resolved;
- fonts available/embedded or substitution report generated;
- images/assets within bounds and non-zero;
- text fits its slot using FontTools metrics (error for structural overflow, warning for capacity risk);
- no empty page or incomplete render;
- HTML sanitized and self-contained;
- output package exists, size > 0, checksum matches;
- download reference resolves.

A failed check emits `exportFailed` with page/reason; the modal stays open with Retry and Try another format. No success state without a real file `[PRD FR-6.15/6.16]`.

### 12.6 Export isolation and QA

- The export handler spawns `python -m app.render.export_runner --export-id …` as a subprocess. The subprocess reads the frozen deck snapshot from PostgreSQL/object storage, validates, renders, writes the package, and exits. The parent marks the job succeeded only if the package exists and passes verification.
- One export at a time by default. The subprocess has a memory/time limit; a crash is an export failure with a reason, never an API crash.
- CI: reopen PPTX with `python-pptx`, print PDF with Playwright, scan HTML for external URLs; optional LibreOffice headless conversion for a visual smoke check.
- Release gate: manual PowerPoint 2016+ fidelity matrix (cover, TOC, six layouts, end page, two styles, text edit, shape edit, font substitution, PDF, HTML) `[PRD FR-6.18]`.
- Visual regression: Playwright screenshots of rendered pages at the fixed 1280×720 reference, compared with a tolerance.

---

## 13. Observability, cost, and operations

### 13.1 Logs

- `structlog` JSON logs with processors for redaction of cookies, authorization headers, emails, URLs, prompts, material text, and page bodies.
- Every log line carries `request_id`, `trace_id`, and, when applicable, `project_id`, `job_id`, `attempt_id`, `page_id`.
- No topic text, material text, file names, full URLs, emails, or page content in logs `[PRD NFR-PRIV-3]`.
- Log levels: `info` for lifecycle, `warn` for degraded behavior, `error` for failures; no per-token logging.

### 13.2 Traces and metrics

- OpenTelemetry Python SDK with auto-instrumentation for FastAPI, SQLAlchemy, and `httpx`; LangChain/model calls use explicit custom spans. OTLP export.
- Custom spans: command admission, gate validation, job attempt, model call, search call, parse, render page, export package, artifact commit.
- Metrics/dashboards:
  - queue depth and wait p95 (from `job` rows + in-memory gauge);
  - page job duration/failure rate by stage and page type;
  - model tokens/cost per stage/page;
  - export success rate and failure reasons;
  - SSE connection count, reconnect/resync rate, dropped slow subscribers;
  - DB pool usage and slow queries;
  - process RSS/CPU, event-loop lag, export subprocess memory.
- Alerts: export failure spike, queue backlog, event-loop lag, cost anomaly, cascade-factor breach, repeated page attempts, deletion backlog, provider outage `[PRD NFR-OBS-3]`.

### 13.3 Sentry

- `sentry-sdk[fastapi]` for the API; the export subprocess reports to the same project with a separate tag.
- Release tagging with git SHA; source maps are not applicable (Python), but source context is uploaded.
- PII/content scrubbing configured; Sentry must not receive material text or file names.

### 13.4 Cost control

- `usage_record` is the billing/cost source of truth; dashboards query the ledger, not logs.
- Per-stage soft budgets and per-project caps alert before hard stops; a regeneration allowance degrades gracefully and never hard-stops mid-deck `[PRD BR-4]`.
- Fingerprint reuse and incremental rerun are first-class cost controls, not optional optimizations `[PRD NFR-COST-3/4]`.
- Provider invoices reconcile to actual-cost adjustment rows; no overwrite of estimated cost `[ARCH §11]`.

### 13.5 Health endpoints

- `GET /api/health` — liveness; no dependency checks.
- `GET /api/health/ready` — DB connectivity, migration head, object-store reachability, runner state, and “single process” sanity. Readiness fails during shutdown so the load balancer stops routing before the drain.

---

## 14. Security and privacy

| Control | Implementation |
| --- | --- |
| Authentication | Opaque DB sessions in HttpOnly cookies; M1 invite-only; M2 account/org roles. |
| Authorization | Project/tenant scope check on every command/query; deny by default; cross-tenant tests in CI. |
| CSRF | `SameSite=Lax` cookies + origin check on mutating routes; same-origin SPA in production. |
| Rate limiting | In-process token buckets + PostgreSQL counters for expensive commands; return `Retry-After`. |
| Upload safety | Presign after metadata validation; HEAD verification; MIME sniff; size/page/decompression caps; parser sandbox; malware scan `[TBD-INFRA · security, before pilot]`. |
| SSRF | DNS resolution + private/link-local/metadata block; redirect re-check; scheme/time/size caps. |
| Untrusted content | Material/web text is data, never instructions; structured output validation; source refs recorded. |
| HTML/export safety | `nh3` sanitization; offline HTML has no external fetches; PPTX/PDF generated by a controlled renderer. |
| Secrets | Platform secret store; server-only env; rotation; no secrets in client bundles or images. |
| Encryption | TLS in transit; encryption at rest for PostgreSQL, object storage, backups; key management `[TBD-INFRA · security + tech lead, before pilot]`. |
| Logging/privacy | structlog redaction + OpenTelemetry attribute allowlist + Sentry scrubbing; zero content fields. |
| Deletion | Tombstone → cancel → delete content/derived data → verify with sweeper; ledger remains pseudonymous `[PRD NFR-PRIV-1]`. |
| Dependency security | `uv sync --frozen`, `uv.lock` committed, Dependabot/`pip-audit`, license review, no unaudited runtime packages. |

CSP: a nonce-based strict policy for the SPA; `connect-src` limited to the app/API and required telemetry endpoints; no `unsafe-eval` in production. The exact policy is validated in staging.

---

## 15. Testing and quality gates

| Layer | Tooling | Gate |
| --- | --- | --- |
| Type safety (Python) | mypy (strict on `app/domain`, `app/services`) | Blocks merge. |
| Type safety (TS) | `tsc --noEmit` | Blocks merge. |
| Lint/format | Ruff, Prettier, ESLint 9 + `eslint-plugin-jsx-a11y` | Blocks merge. |
| Unit | pytest | Domain services, fingerprint/JCS golden tests, stale matrix, ledger idempotency, validators, layout geometry. |
| Component | Vitest + React Testing Library | Six-stage controls, keyboard paths, reduced motion, error states. |
| Integration | pytest + Testcontainers PostgreSQL + MinIO | Repositories, transactions, artifact commit/undo, queue tasks, reconciliation, authz. |
| Contract | Pydantic/OpenAPI + JSON Schema + generated TS diff | Command/query/event/model-output schemas; unknown-field tolerance. |
| E2E | Playwright | Happy path, stale rerun, undo, reconnect, export failure, mobile breakpoints. |
| Accessibility | axe-core + Playwright + manual audit | WCAG 2.2 AA baseline; keyboard matrix; no pointer-only core action. |
| Visual | Playwright screenshots | Plan/design/style/export at 1440/1180/920/720/390. |
| Export | python-pptx reopen + Playwright PDF + HTML scan + manual PowerPoint matrix | Release gate `[PRD FR-6.18]`. |
| Model eval | pytest-marked `evals/` fixtures with recorded outputs | Before prompt/model/vocabulary changes; not in request path. |
| Load | pytest/httpx or k6 at the HTTP edge | API/SSE at pilot scale; runner concurrency. |
| Schema | `alembic upgrade head`, `alembic check`, migration test | Blocks merge/release. |
| Security | `pip-audit`, secret scan, authz tests, SSRF tests | Blocks release. |

Test doubles:

- A deterministic `MockModelAdapter` and `MockSearchAdapter` are test-only; production configuration MUST NOT resolve to them `[PRD FR-7.18/2.20]`.
- `respx` mocks external HTTP in Python tests; MSW mocks it in frontend tests.
- No test fixture may be bundled into the production client.

Definition of done includes behavior, failure path, state/persistence, accessibility, telemetry, cost scope, feature flag/kill switch, compliance notice, and sign-off `[PRD §14.3]`.

---

## 16. Tooling and CI/CD

### 16.1 Local development

```bash
# from the repository root
cp .env.example .env          # fill local values; never commit
docker compose up -d          # PostgreSQL + MinIO
cd backend && uv sync         # install Python deps
uv run alembic upgrade head   # migrations
uv run uvicorn app.main:app --reload --port 8000
# in a second terminal
cd frontend && npm ci
npm run dev                   # Vite on :5173, proxies /api to :8000
```

- One Python lockfile (`backend/uv.lock`) and one npm lockfile (`frontend/package-lock.json`).
- `uv run ruff check`, `uv run ruff format --check`, `uv run mypy app`, `uv run pytest`.
- `npm run typecheck`, `npm run lint`, `npm test`, `npm run build`.
- Local storage uses MinIO with the same S3 adapter as production.
- A local model/search stub is allowed for UI work; it is clearly labeled and cannot be enabled in staging/production.

### 16.2 CI pipeline (GitHub Actions)

1. Install Python with `uv sync --frozen`; install Node with `npm ci` (cache both).
2. `alembic upgrade head` + `alembic check` against a disposable PostgreSQL service.
3. Ruff, mypy, pytest unit/integration (Testcontainers PostgreSQL + MinIO).
4. Generate OpenAPI/JSON Schema; fail if generated TS/types differ from committed output.
5. Frontend typecheck, lint, unit tests, build.
6. Build the application Docker image (includes the frontend build and the export dependencies).
7. Playwright smoke against the built app with seeded data.
8. Export smoke (one PPTX/HTML/PDF) in the export environment.
9. Publish the image; deploy staging; run migrations; smoke.
10. Manual approval → production deploy; run migrations; smoke; keep the previous image for rollback.

Release rules:

- No production deploy without a passing migration check.
- No destructive migration without a verified backup and rollback plan.
- Feature flags/kill switches for model, search, and export are configuration, not redeploys `[PRD NFR-MAINT-5]`.
- A deploy is a short availability gap for in-flight jobs in M1; schedule it and use graceful drain (§9.8).

### 16.3 Docker

- Multi-stage build:
  - frontend stage: Node + `npm ci` + `npm run build` (including the viewer bundle);
  - backend stage: Python 3.12 slim + `uv sync --frozen --no-dev`.
- Non-root user; `tini`/`dumb-init` for signal handling.
- The runtime image includes Chromium and its system dependencies for PDF/HTML export. This is the largest layer; it is acceptable because export is the paid promise. If image size becomes a blocker, move export to a separate image/container behind the same subprocess contract `[TBD-INFRA]`.
- Health endpoints: `/api/health`, `/api/health/ready`.
- No secrets baked into images; runtime env/secret store only.

---

## 17. Deployment topology

### 17.1 M1 topology

```
                    ┌──────────────────────────────────────┐
      users ───────▶│ load balancer / reverse proxy        │
                    └──────────────────┬───────────────────┘
                                       ▼
                    ┌──────────────────────────────────────┐
                    │ application container (ONE process)  │
                    │ FastAPI + SPA static files           │
                    │ scheduler + in-process workers       │
                    │ SSE EventBus + rate limiter          │
                    └───────┬───────────────────┬──────────┘
                            │                   │
              ┌─────────────▼──┐        ┌───────▼─────────────┐
              │ PostgreSQL     │        │ object storage      │
              │ metadata/jobs  │        │ content/artifacts   │
              │ events/ledger  │        │ exports             │
              └────────────────┘        └─────────────────────┘
                            │
                    ┌───────▼──────────────────────────────┐
                    │ export subprocess (Chromium + pptx)  │
                    └──────────────────────────────────────┘
```

- **One application process.** No sticky sessions are needed because there is only one process. Do not run `uvicorn --workers N`; it breaks the queue and SSE.
- **Vertical scaling** (CPU/RAM) is the M1 scaling mechanism. The runner’s global concurrency is tuned to the container size.
- **Export subprocess** is spawned per export, one at a time, with a memory cap. It has no provider egress.
- **PostgreSQL**: managed primary; PITR; connection pooler; migration direct URL.
- **Object storage**: private; lifecycle; versioning; CORS only for presigned upload from the app origin.
- **Environments**: dev/staging/prod with separate credentials, buckets, database, and provider quotas. Staging runs the export fidelity smoke before release.
- **Region**: `[TBD-BIZ · founder + legal, before paid pilot]` (BM-8). Docker + PostgreSQL + S3 API keep the stack portable across regions.
- **Backup/restore**: metadata PITR, object versioning/lifecycle, event retention, and a restore drill before the pilot. RPO/RTO `[TBD-INFRA · ops, before pilot]`.
- **Runbooks**: queue backlog, event-loop lag, provider outage, export failure spike, SSE resync spike, DB pool exhaustion, deletion backlog, cost anomaly, process restart with queued jobs. Each has an owner, kill switch, and rollback.

### 17.2 Why not horizontal scaling in M1

A second API process would have its own in-memory queue and SSE bus. A command handled by process A would enqueue work that process B never sees; an SSE connection to process B would miss process A’s events. Making this correct requires a shared dispatch/replay mechanism (PostgreSQL `SKIP LOCKED` queue + `LISTEN/NOTIFY`, or Redis). That is a deliberate M2 upgrade (§9.11), not an M1 requirement for 5–10 design partners.

**Deploy behavior:** a rolling deploy of a single process stops all work briefly. Use a graceful drain, deploy in a low-activity window, and let the startup reconciler re-wake queued jobs. A blue/green deploy with two processes would violate the single-process invariant and is prohibited in M1.

---

## 18. Architecture deferred decisions (DD-1 … DD-20)

| ID | Deferred area | Resolution | Status |
| --- | --- | --- | --- |
| DD-1 | Language/framework/runtime | Python 3.12+ + FastAPI (single uvicorn worker) + React 19/Vite/TypeScript SPA; modular monolith | Frozen M1 |
| DD-2 | Metadata store | Managed PostgreSQL 16+ (default 17) + SQLAlchemy 2.0/Alembic | Frozen M1; vendor `[TBD-INFRA]` |
| DD-3 | Queue/broker | In-process `asyncio` `JobRunner`; authoritative `job`/`job_attempt` rows; startup + periodic reconciliation; **no Redis/broker** | Frozen M1 |
| DD-4 | Object/artifact store | S3-compatible object storage; Cloudflare R2 proposed; AWS S3/MinIO alternatives | Interface frozen; vendor `[TBD-INFRA]` |
| DD-5 | Cache | Process TTL/LRU for versioned static/config data + PostgreSQL projections; no Redis | Frozen M1 |
| DD-6 | Stream transport | SSE + in-process `EventBus` + `domain_event` replay; `Last-Event-ID`; ephemeral deltas not persisted | Frozen M1 |
| DD-7 | API style | REST JSON with Pydantic schemas + FastAPI OpenAPI; version + idempotency envelope | Frozen M1 |
| DD-8 | Model providers/routing | LangChain/LangGraph + `langchain-openai` adapters; stage-level `generation_profile`; primary provider/vendor `[TBD-BIZ]` | Adapter frozen; vendor deferred |
| DD-9 | Search provider | Adapter interface; Tavily proposed default | Adapter frozen; vendor `[TBD-BIZ]` |
| DD-10 | Parsing/OCR vendors | `pdfplumber`/`pypdf`, `python-docx`, `openpyxl`, `python-pptx`, `markdown-it-py`; OCR `pytesseract` only if PRD-19 requires M1 | Frozen M1; OCR `[TBD-BE]` |
| DD-11 | URL extraction | `httpx` + `trafilatura`/`readability-lxml`; SSRF guard; no JS execution in M1 | Frozen M1 |
| DD-12 | SVG composition/rendering | No Satori/SVG composition; shared design JSON → React renderer (web/offline HTML), Chromium (PDF), python-pptx (PPTX) | Frozen M1 |
| DD-13 | PPTX writer, HTML/PDF packaging, font embedding | `python-pptx` native shapes/text/tables/charts; Playwright Chromium PDF; single-file React HTML; `fonttools` metrics/subsetting; license/substitution report | Frozen M1; PPTX interpretation `[CONFLICT]` see §19.1 |
| DD-14 | Identity/auth provider | Opaque DB sessions in HttpOnly cookies; Argon2; invite-only M1; account/org M2/M3 | Frozen M1 |
| DD-15 | Billing/quota provider | PostgreSQL quota counters in M1; Stripe proposed for M2; no billing in M1 | M1 frozen; M2 `[TBD-BIZ]` |
| DD-16 | Observability vendor | structlog + OpenTelemetry + Sentry + Grafana Cloud proposed | Interface frozen; vendor `[TBD-INFRA]` |
| DD-17 | Secrets manager and upload scanning | Platform secret store; upload type/size/sandbox limits; malware scanner `[TBD-INFRA]` | Partial; scanner deferred |
| DD-18 | Deployment platform | One Docker container on Fly.io or Railway proposed; managed PostgreSQL + S3-compatible storage | Image frozen; vendor `[TBD-INFRA]` |
| DD-19 | Physical schema/indexes/partitioning | PostgreSQL schema + SQLAlchemy 2.0 + Alembic in `docs/ppt-agent-data-model.md`; no partitioning in M1 | Frozen M1 |
| DD-20 | CI/CD and promotion | GitHub Actions + Docker + `alembic upgrade head`; staging→production manual approval | Frozen M1 |

---

## 19. Risks, trade-offs, and conflicts

### 19.1 `[CONFLICT]` — “SVG-composited PPTX” vs editable native shapes

PRD FR-6.12 requires “a real PPTX assembled from SVG-composited pages that opens in PowerPoint 2016+ and keeps text and shapes editable.” A pure SVG image embedded in PPTX is not reliably editable as native text/shapes; PowerPoint may require a manual “convert to shape” step, and the acceptance test cannot depend on that. The v2 stack therefore uses:

- the structured design body as the canonical content;
- the React renderer (and Chromium print) as the visual/fidelity reference;
- `python-pptx` native DrawingML shapes/text for the PPTX package.

This preserves the acceptance test (text/shape editability) but changes the literal “SVG-composited” output claim. **This document does not resolve the conflict.** The `python-pptx` path is an implementation proposal for evaluation only; the export feature MUST NOT be sold or signed off as passing FR-6.12 until Product + Architecture record a decision and the PowerPoint fidelity matrix passes. Owner: Product + Architecture, before export implementation. If product insists on SVG-embedded pages, FR-6.12’s editability criterion must be renegotiated; both cannot be guaranteed by the same file.

### 19.2 Accepted trade-off — in-process queue and single process

| Property | M1 behavior | Consequence |
| --- | --- | --- |
| Durability | Committed `job` rows survive; in-memory dispatch does not | A restart re-runs queued/in-flight attempts; idempotent commit prevents duplicates. |
| Availability | One process; a deploy/restart pauses all jobs | Short planned gaps; no rolling multi-instance deploy in M1. |
| Scale | Vertical only | Fine for 5–10 design partners; M2 adds a shared queue if needed. |
| SSE | Same process only | Simple and correct; a second process would silently miss events. |
| Rate limits | Per process | Correct for one process; M2 shared counters if scaled. |
| CPU-heavy work | Thread pool/subprocess | The event loop stays responsive; export memory is isolated. |

**Hard rule:** if the deployment needs a second process, it MUST first replace the queue and event bus with shared mechanisms (§9.11). Running two processes with the in-memory design is a correctness bug, not a scaling choice.

### 19.3 Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Single-process outage | No jobs run while down | Graceful drain, low-activity deploys, startup reconciliation, health checks. |
| In-memory dispatch loss | Jobs wait until sweep | Startup + 30 s reconciler; committed `job` rows; idempotent wake. |
| Event-loop blocking | Slow API/SSE | Parsing/metrics in thread pool; export subprocess; event-loop lag alert. |
| Chromium/pptx memory | Export OOM | Dedicated subprocess, concurrency 1, memory cap, restart policy. |
| Python type/validation drift | Runtime errors | mypy + Pydantic v2 + contract tests + generated TS diff gate. |
| LangChain abstraction churn | Breaking upgrades | Pin versions; gateway isolates providers; eval fixtures. |
| Design JSON drift between React and Python | Web/PPTX mismatch | Shared JSON + JSON Schema CI gate + visual regression on both renderers. |
| Font metrics and CJK fallback | Overflow/substitution defects | FontTools metrics; explicit East Asian fonts; substitution report; warning/error tiers. |
| Model provider rate limits | Page timeouts/errors | Bounded concurrency, jittered retries, stage tiers, provider adapter, kill switch. |
| No Redis at higher scale | Queue/SSE bottleneck | Interface-based upgrade to PG queue/`LISTEN/NOTIFY` or managed broker in M2. |
| Malicious uploads | Parser exploit / stored malware | Type/size caps, sandboxed parsing, no macro execution, async scan `[TBD-INFRA · security, before pilot]`. |
| Vendor region mismatch | Launch blocked | Region decision before vendor freeze `[TBD-BIZ · founder + legal, before paid pilot]`; portable Docker/Postgres/S3. |

### 19.4 Trade-offs accepted for M1

- A modular monolith with one process rather than separate API/worker services. Module boundaries are enforced in code; splitting later is a deployment change plus a shared queue, not a domain rewrite.
- PostgreSQL as queue record, event log, and cache carrier to reduce moving parts. Redis is not required in M1.
- No runtime prompt-editing UI; prompt changes go through code review and evals. This favors trust over convenience in a paid pilot.
- No real-time collaboration, marketplace, native apps, or multi-region; these are M3/product non-goals `[PRD §4.4]`.

---

## 20. Deferred decisions and open questions

| ID | Question / decision | Owner / stage | Notes |
| --- | --- | --- | --- |
| TS-Q1 | Primary model provider, model IDs, and stage tiers | `[TBD-BIZ · founder + tech lead, before development]` | DD-8; adapter interface is ready. |
| TS-Q2 | Search provider and result quality bar | `[TBD-BIZ · founder + tech lead, before development]` | DD-9; Tavily is a proposed default only. |
| TS-Q3 | Launch region, data residency, subprocessors | `[TBD-BIZ · founder + legal, before paid pilot]` | BM-8; affects PostgreSQL/object-storage hosting. |
| TS-Q4 | Deployment vendor (Fly.io vs Railway vs other) | `[TBD-INFRA · tech lead, before pilot]` | One container; image is portable. |
| TS-Q5 | Observability vendor and retention | `[TBD-INFRA · tech lead, before pilot]` | OTLP/Sentry interfaces are vendor-neutral. |
| TS-Q6 | Malware scanner/quarantine product | `[TBD-INFRA · security, before pilot]` | Type/size/sandbox limits are mandatory regardless. |
| TS-Q7 | Exact supported browser matrix | `[TBD-FE · frontend, before M1]` | PRD-06. |
| TS-Q8 | PPTX fidelity bar and PowerPoint versions | `[TBD-BIZ · product + engineering, before M1]` | PRD-07; see §19.1 conflict. |
| TS-Q9 | PDF text vs raster expectations | `[TBD-BE · export implementation]` | Chromium gives vector text; verify with the fidelity matrix. |
| TS-Q10 | Font embedding policy and licensed font set | `[TBD-BIZ · legal, before paid launch]` | BM-11; substitution report is mandatory until resolved. |
| TS-Q11 | Event retention/full-resync threshold | `[TBD-INFRA · ops, before pilot]` | AQ-3; affects SSE retention. |
| TS-Q12 | History depth and export artifact retention | `[TBD-BIZ · product + finance/legal, before pilot]` | AQ-5; config keys, not hard-coded values. |
| TS-Q13 | Python version upgrade timing (3.13/3.14) | `[TBD-BE · backend, first maintenance window]` | Start on 3.12+; upgrade after dependency audit. |
| TS-Q14 | When to add a shared queue/broker | `[TBD-INFRA · ops, M2]` | Only if pilot concurrency or deploy needs multi-process. |
| TS-Q15 | Whether to split export into its own container | `[TBD-INFRA · ops, before pilot]` | Same subprocess contract; driven by image size/memory. |
| TS-Q16 | Offline HTML size cap and asset inlining policy | `[TBD-BE · export implementation]` | Self-containment vs file size; per-image/total caps. |

---

## 21. Traceability

| Architecture decision / requirement | Stack resolution |
| --- | --- |
| AD-1 server-authoritative workflow | React SPA + FastAPI; no client-owned stage/stale/history; `project.version` optimistic concurrency. |
| AD-2 durable resumable jobs | In-process `JobRunner` + authoritative `job`/`job_attempt` rows + leases/fencing + startup reconciliation + SSE reconnect. |
| AD-3 immutable artifacts + lineage | SQLAlchemy models `artifact_version`/`artifact_pointer`/`page_history_entry`/`artifact_lineage`; design JSON in object storage. |
| AD-4 derived staleness | `input_fingerprint` (SHA-256/JCS) + lineage; stage/page status projections. |
| AD-5 per-page jobs | Per-page handler, runnable concurrency, page-level error/retry, `active_operation_key`. |
| AD-6 adapters + metering | `app/llm`, `app/ingest`, `app/storage`, `app/render` interfaces + `usage_record`. |
| AD-7 isolated export | Export subprocess + separate slot; Chromium/python-pptx isolated from the API process. |
| AD-8 append-only ledger | `usage_record` unique original rows + adjustments. |
| AD-9 client countdown + server validation | React countdown hook + `advanceStage` version/token validation. |
| AD-10 snapshot + cursor | `project_snapshot_cache` + `domain_event.sequence` + SSE `Last-Event-ID`. |
| AD-11 stable page identity | `page` table + versioned outline page rows. |
| AD-12 body/chrome split | Design body JSON + `render_cache.chrome_version`; no model job for title/order. |
| AD-13 content/metadata separation | Object storage for content; structlog/OTel/Sentry redaction. |
| AD-14 nullable tenant scoping | `account_id` nullable from M1; session auth; M2 maps accounts. |
| NFR-PERF-3 streaming | SSE + ephemeral deltas + committed artifact reload. |
| NFR-REL-3/4 idempotent retries/reconnect | Idempotency records + job fencing + startup reconciliation + snapshot/cursor. |
| NFR-COST-1/2/3/4 | Adapter metering + ledger + fingerprint reuse + incremental rerun. |
| NFR-SEC-1/2/3 | Project-scoped authz, signed URLs, secret store, no client secrets. |
| NFR-PRIV-3 | structlog redaction + OTel allowlist + Sentry scrubbing + content-free events. |
| NFR-MAINT-1/2/3/5 | Alembic migrations + adapter ports + export regression matrix + config flags. |
| NFR-ACC-1–6 | Radix/shadcn + keyboard matrix + axe + reduced motion + focus contract. |
| NFR-COMPAT-4/5 | python-pptx native output + PDF/HTML checks + manual PowerPoint matrix. |

---

## 22. Change log

| Version | Date | Change |
| --- | --- | --- |
| v1 | 2026-11-19 | Initial implementation stack: Node.js/TypeScript + Next.js/React, PostgreSQL/Prisma, Graphile Worker, S3-compatible storage, SSE, AI SDK, Node parsing, Satori/Playwright/PptxGenJS rendering, Auth.js, OpenTelemetry/Sentry, npm workspaces/Turborepo, Docker/GitHub Actions. |
| v2.1 | 2026-11-19 | Added the `SEARCH` task to the job registry for targeted gap searches, matching the API contract and data model. |
| v2 | 2026-11-19 | Replaced the Node/TypeScript server with Python 3.12+/FastAPI/SQLAlchemy/Alembic and the Next.js client with a React 19/Vite SPA. Removed Redis, ARQ/Graphile Worker, BullMQ, Satori, PptxGenJS, Prisma, Auth.js, and pino. Introduced the in-process `asyncio` `JobRunner` with authoritative PostgreSQL job rows and startup reconciliation; in-process SSE `EventBus` with `domain_event` replay; LangChain/LangGraph model gateway; `python-pptx` native export; single-file React viewer for PDF/HTML; shared layout/theme JSON; OpenAPI → TypeScript contracts. Recorded the single-process/single-instance invariant and the M2 shared-queue upgrade path. |
