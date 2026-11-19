# Bound PPT · PPT Agent

A productization repo based on the linux.do post ["Probably the strongest PPT Agent right now, with a full breakdown of the approach"](https://linux.do/t/topic/1782304). Current interaction design version: **v3** (sequential interview, Agent gap suggestions, undoable single-page edits, stale-propagation reruns, accessibility improvements). The PRD is **v1**, the architecture is **v1.1**, the data model is **v1.2**, and the implementation stack is **v2.1** (React + Python, no Redis, in-process job queue). The implementation design set is **v1.1**: backend design, frontend design, API contracts, and the frontend–backend boundary.

## Repository layout

- `backend/` — FastAPI application, SQLAlchemy models, in-process job runner, SSE, ingestion, generation, render/export, tests, Alembic
- `frontend/` — React 19 + TypeScript + Vite SPA, shared deck renderer, Playwright E2E
- `shared/` — versioned layout and theme JSON used by both React and Python renderers
- `infrastructure/` — deployment assets (placeholders; `docker-compose.yml` at the root provides PostgreSQL/MinIO locally)
- `docs/implementation-status.md` — what is implemented, development-only defaults, and remaining manual M1 gates
- `docs/linux-do-1782304-ppt-agent-extract.md` — post extract (design rationale + original prompts)
- `docs/ppt-content-sources.md` — content-source design (v2.1: five source channels, ingestion priority, data contracts, Agent gap suggestions)
- `docs/ppt-agent-interaction-flow.md` — product interaction flow v3 (six-stage flow, state machine, stale propagation, error contracts, accessibility baseline)
- `docs/ppt-agent-business-model.md` — business model v1 (segments, Business Model Canvas, six-stage cost map, packaging hypothesis, unit-economics framework, GTM, risks, open decisions)
- `docs/ppt-agent-prd.md` — product requirements v1 (M1/M2/M3 scope, FR/NFR IDs, acceptance criteria, metrics, dependencies, release gates, open decisions)
- `docs/ppt-agent-architecture.md` — stack-free system architecture v1.1 (components and ownership, runtime flows, data/state model, stale/undo semantics, failure recovery, cost ledger, security boundaries, M1–M3 evolution; v1.1 clarifies job-record durability and single-process topology)
- `docs/ppt-agent-data-model.md` — physical data model v1.2 (PostgreSQL, SQLAlchemy 2.0/Alembic schema, keys/indexes, artifact/history protocols, object-store layout, retention, M2/M3 extension; v1.2 adds the `SEARCH` job type and aligns the page/undo enums with the wire contract)
- `docs/ppt-agent-tech-stack.md` — implementation technology stack v2.1 (React 19/Vite/TypeScript, Python 3.12+/FastAPI, SQLAlchemy/Alembic, in-process asyncio job queue without Redis, SSE, S3-compatible storage, python-pptx/Chromium export, deployment; v2.1 adds the `SEARCH` job handler)
- `docs/ppt-agent-api-contracts.md` — API contracts v1.1 (transport conventions, success/error envelopes, enums and DTOs, command/query endpoints, SSE event catalog, upload/download handshakes, compatibility and CI gates)
- `docs/ppt-agent-backend-design.md` — backend implementation design v1.1 (runtime topology, module and dependency rules, request pipeline, stage/gate/stale semantics, service designs, transactions and artifact commit, in-process job system, model gateway, ingestion, export, testing)
- `docs/ppt-agent-frontend-design.md` — frontend implementation design v1.1 (routing, four-class state model, query keys and event invalidation, API/SSE clients, renderer, screen-by-screen contracts, accessibility, responsive, performance, testing)
- `docs/ppt-agent-frontend-backend-boundary.md` — frontend–backend boundary v1.1 (ownership matrix, command/query/event rules, SSE lifecycle, optimistic reconciliation, content/metadata and security boundaries, failure ownership, cross-boundary sequences, contract-change checklist)
- `docs/ppt-agent-ux-review.md` — UX review (v2 → v3 issue list, validation log, remaining items)
- `docs/images/` — key workflow screenshots from the post
- `prototype/ppt-agent-prototype.html` — clickable interaction prototype (single file, built-in mock LLM streaming)

The implementation design set is read in this order: `docs/ppt-agent-api-contracts.md` (wire contract), `docs/ppt-agent-backend-design.md` (server build), `docs/ppt-agent-frontend-design.md` (client build), and `docs/ppt-agent-frontend-backend-boundary.md` (ownership and cross-boundary protocols). The architecture's deferred decisions (DD-1…DD-20) are resolved by `docs/ppt-agent-tech-stack.md` §18; the physical schema is in `docs/ppt-agent-data-model.md`. The stack borrows proven patterns from [yuyuanweb/ai-ppt-generator](https://github.com/yuyuanweb/ai-ppt-generator) (FastAPI + LangChain/LangGraph + python-pptx + React SPA) while replacing its Redis/ARQ queue with an in-process `asyncio` queue and authoritative PostgreSQL job records.

## Running the implementation

The M1 implementation is `frontend/` (React 19 + TypeScript + Vite) and `backend/` (FastAPI + SQLAlchemy async + in-process jobs + SSE). The shared deck vocabulary is in `shared/`.

### 1. Local API

```bash
cp .env.example .env
cd backend && uv sync
cd .. && PYTHONPATH=backend uv run --project backend uvicorn app.main:app --port 8000
```

- SQLite is the zero-setup local default (`AUTO_CREATE_TABLES=true`). Production requires PostgreSQL; run `uv run alembic upgrade head` from `backend/` and set `AUTO_CREATE_TABLES=false`.
- The pilot user is seeded from `PILOT_EMAIL` / `PILOT_PASSWORD` (default `pilot@boundppt.local` / `boundppt-demo`). Use `uv run python -m app.cli.create_user --email … --password …` to add pilot accounts.
- `MODEL_PROVIDER=stub` and `SEARCH_PROVIDER=stub` are deterministic development providers. They are rejected when `APP_ENV=production`; set an OpenAI-compatible model (`MODEL_BASE_URL`, `MODEL_API_KEY`, `MODEL_ID`) and `SEARCH_PROVIDER=tavily` with `SEARCH_API_KEY` for real generation and search.
- Object storage defaults to `backend/storage/`; set `STORAGE_BACKEND=s3` plus the `S3_*` values for an S3-compatible bucket. `docker-compose.yml` provides optional PostgreSQL and MinIO.

### 2. Local web app

```bash
cd frontend
npm install
npm run dev          # http://127.0.0.1:5173
```

Vite proxies `/api` to `http://127.0.0.1:8000`. Use `VITE_API_TARGET=http://127.0.0.1:<port>` if the API runs elsewhere. The production build (`npm run build`) is served by FastAPI from `frontend/dist` when present.

### 3. Verification

```bash
cd backend && uv run pytest -q
cd ../frontend && npx tsc -b && npm run build && npm test
npx playwright install chromium
E2E_BASE_URL=http://127.0.0.1:5173 npx playwright test
```

The Playwright happy path covers login → material intake → research interview → outline → plan → style → design → per-page regenerate/undo → refresh restore → real PPTX export and download. Backend tests cover materials/research, generation/artifacts/export, projects/jobs/SSE, and produce real PPTX/HTML/PDF files.

### Implementation notes

- Server state is authoritative: stage reachability, `profileDirty`, stale status, page status, and per-page history are derived on the server and streamed over SSE.
- Jobs are durable rows dispatched by an in-process `asyncio` runner (no Redis). Restart reconciliation re-wakes queued work; cancellation is cooperative.
- Export runs in an isolated subprocess and produces native `python-pptx` shapes, a self-contained HTML file, and a 16:9 PDF. Success is reported only after a non-zero artifact exists and its download resolves.
- The design body JSON is one shared model: React renders it in the browser, and Python rebuilds the same slots/blocks for PPTX, PDF, and HTML.

## Running the prototype

```bash
cd prototype && python3 -m http.server 8931
# open http://127.0.0.1:8931/ppt-agent-prototype.html
```

Or open `prototype/ppt-agent-prototype.html` directly in a browser.

## Workflow (v3)

Material intake (paste text / drag files / URL, optional) → research (material digestion + Agent gap suggestions + sequential interview + editable profile) → sticky-note outline (drag / buttons / keyboard, auto-advance pausable) → plan draft (Bento wireframe, confirm only after completion) → design draft (lock pages while generating, single-page variant switching with undo, tweaks, export)

> Principle: first-party materials come first; web search is downgraded to a gap-filling tool. When the material slot is empty, fall back to the v1 web-only research path.
