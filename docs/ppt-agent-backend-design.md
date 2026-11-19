# Bound PPT · Backend Implementation Design

> Version: v1.1 · 2026-11-19 · Status: Draft · Owner: Backend

> Requirements: `docs/ppt-agent-prd.md` (PRD v1). State and ownership: `docs/ppt-agent-architecture.md` (v1.1). Implementation choices: `docs/ppt-agent-tech-stack.md` (v2.1). Storage: `docs/ppt-agent-data-model.md` (v1.2). Wire contract: `docs/ppt-agent-api-contracts.md` (v1.1). Flow context: `docs/ppt-agent-interaction-flow.md` (v3).
> This document turns the six upstream documents into a backend build design. It does not define product behavior, wire shapes, or physical DDL. It claims no implementation: the repository has no backend code at this version.

---

## 1. Document control

| Field | Value |
| --- | --- |
| Document / version / date | Bound PPT Backend Implementation Design / v1 / 2026-11-19 |
| Status / owner / audience | Draft / Backend / engineering, QA, SRE, security |
| Precedence | PRD (behavior, acceptance) > Architecture (component ownership, state semantics, consistency) > Tech stack (implementation choices) > API contracts (wire shapes) > this document (backend structure) |
| Precedence, storage names | `docs/ppt-agent-data-model.md` is authoritative for table names, column names, keys, constraints, and transaction protocols, under the two rules above [DATA §1.3] |
| Scope | Runtime topology, module layout, request pipeline, domain algorithms, service boundaries, persistence/transaction protocol, job system, provider and ingestion adapters, export subprocess contract, error mapping, observability/security wiring, configuration, testing, traceability |
| Out of scope | Product behavior and acceptance (PRD), wire DTOs/envelopes (API), physical DDL and migrations content (DATA), prompt text and model choice (TECH §10, TS-Q1), UI structure (frontend design), vendor and region selection (TS-Q3/TS-Q4) |
| Normative language | MUST / MUST NOT / DEFAULT as in PRD §8.1. `[TBD-*]` marks an owner and stage; it is not permission to invent a value. `[ASSUMPTION]` marks a design premise; `[CONFLICT]` marks a source disagreement resolved in §18. |
| Review cadence | At M1, M2, M3 gates and before any change to the job commit protocol or the artifact fingerprint |

**Terminology.** Terms below are used with exactly this meaning throughout; wire terms remain as defined in [API §1.1].

| Term | Meaning in this document |
| --- | --- |
| **Command** | An intention-named mutation admitted through the pipeline in §5; carries `Idempotency-Key` and, when project-scoped, `X-Expected-Version` [API §2.4]. |
| **Query** | A side-effect-free read; never creates a job and never increments `project.version` [API §1.1]. |
| **Event** | A content-free notice appended to `domain_event` with a per-project `sequence`; `outlineDelta` is the only ephemeral exception [API §6]. |
| **Snapshot / projection** | A consistent project read at a known `sequence`; stage/page/stale status is derived, rebuildable, and never client-written [API §3.3; ARCH AD-4, §8.7]. |
| **Content** | Topic, material text, digests, profile prose, outline titles, page bodies, packages: object storage only, except the content-bearing DB columns allowed by [DATA §9.1]. |
| **Metadata** | IDs, kinds, statuses, counts, buckets, domains, timings, costs [ARCH §7.5]. |
| **Job / attempt** | A `job` row (type, payload, state, attempts, lease, fencing token, deadline, cancellation) and its `job_attempt` rows carrying per-attempt usage and cost [DATA §6.6]. |
| **Lease / fencing token** | Time-bounded worker claim; `fencing_token` is incremented per claim and verified at commit [TECH §9.5]. |
| **Idempotency key** | Client intent key; `(scope_key, idempotency_key)` is unique in `idempotency_record` [DATA §6.8]. |
| **Expected version** | The `project.version` the client last observed; mismatch is `error.conflict.stale_version` [API §2.8]. |
| **Input fingerprint** | SHA-256 over RFC 8785 JCS canonical JSON of the artifact's semantic inputs [DATA DM-9]. |
| **Chrome** | Page number, deck order, section label, and rendered title applied deterministically at render time; never a model input [ARCH AD-12]. |
| **Epoch** | `project.epoch`; incremented by restart; older-epoch results are discarded [ARCH §6.10]. |

---

## 2. Scope and decision summary

| ID | Decision | Rationale | Consequence |
| --- | --- | --- | --- |
| **BD-1** | Python 3.12+ / FastAPI modular monolith; Pydantic v2; SQLAlchemy 2.0 async + `asyncpg`; Alembic [TECH §3.1] | One language for API, workflows, ingestion, rendering; one schema source for API, DB payloads, model output, config | No service-to-service RPC in M1; module boundaries enforced by `import-linter`, not the network |
| **BD-2** | One `uvicorn` process with `workers=1`; no Redis and no broker [TECH §3.1, §4.1] | The in-process queue and SSE bus are per process; durability must come from PostgreSQL, not the transport | `workers>1` and multi-instance deployment are prohibited until the TECH §9.11 upgrade |
| **BD-3** | In-process `asyncio` `JobRunner`; `job`/`job_attempt` rows are authoritative [TECH §9, DATA DM-12] | Durable, cancellable, resumable per-page work without a broker | A restart loses dispatch memory, never committed work; startup reconciliation re-wakes |
| **BD-4** | PostgreSQL is the only authoritative metadata/job/event/ledger store; content is in S3-compatible object storage [DATA DM-1/DM-2] | Transactional state+event+job, event replay, ledger, projections in one store | No second database, cache, or search index may become truth |
| **BD-5** | SSE with an in-process `EventBus` plus `domain_event` replay [TECH §6.3] | Reconnect without duplicate jobs or silent gaps, no broker | Subscriber queues are bounded; slow subscribers receive `resync` |
| **BD-6** | One transaction per command: state + `domain_event` + `job` row; response only after commit [API §2.5, TECH §7.2] | Admission cannot acknowledge work that is not durable | Commit precedes response and `runner.wake()`; a failed commit returns an error and wakes nothing |
| **BD-7** | Immutable artifacts; pointer install is the commit point; content written before metadata [DATA P2/P7] | Undo, export snapshots, cost attribution, crash safety | An orphan object is possible; a pointer to missing content is not |
| **BD-8** | Generation fingerprint uses SHA-256 over RFC 8785 JCS; chrome is a composition input, not a generative input [DATA DM-9, ARCH AD-12] | Title/order edits must never cost a model job while still marking the design page stale | Two staleness tiers: `GENERATION_STALE` (job) and `COMPOSITION_STALE` (deterministic render) |
| **BD-9** | camelCase only at the HTTP boundary; snake_case everywhere inside and in the database [API §2.3] | One mapping boundary prevents accidental wire coupling in services | `schemas/` owns aliases; services and domain never see camelCase |
| **BD-10** | Export runs in a subprocess with no database credentials; the parent commits the result [TECH §12.6] | Chromium/`python-pptx` memory and crashes must not affect the API | The child may fail; only the parent can claim success |
| **BD-11** | `domain_event.payload` stores the wire-shaped (camelCase) content-free payload; `job.payload` and other internal JSON store snake_case IDs | Replay is a pass-through; internal payloads stay internal | One deliberate exception to BD-9, documented in §4.3 |
| **BD-12** | Features that the API does not expose (search job type, plan-incomplete gate key) are not invented; they are recorded as contract gaps in §18 | The wire contract is canonical | Blocking contract gaps stop at the decision boundary |

Non-decisions: model vendor and tiers `[TBD-BIZ · founder + tech lead]` (TS-Q1); search vendor `[TBD-BIZ]` (TS-Q2); region/subprocessors `[TBD-BIZ · legal]` (TS-Q3); retention values `[TBD-BIZ]`; deployment vendor `[TBD-INFRA]` (TS-Q4); physical DDL (DATA).

---

## 3. Runtime topology and process invariants

| Process | Entry point | Responsibilities | Concurrency |
| --- | --- | --- | --- |
| `api` | `uvicorn app.main:app` | SPA static files, auth, command/query API, SSE, in-process scheduler and workers, rate limiting | Exactly one process in M1 [TECH §4.1] |
| `export` | `python -m app.render.export_runner --export-id <uuid>` | Validation, Chromium printing, `python-pptx` assembly, packaging, checksum | One at a time by default; memory/time capped [TECH §12.6] |
| PostgreSQL | Managed service | Metadata, jobs, events, ledger, projections | Primary; pooler for the app, direct URL for migrations |
| Object storage | S3-compatible, private | Raw uploads, normalized text, digests, bodies, renders, packages | Presigned access only |

**Process invariants (a violation is an incident, not tuning).**

1. The API MUST run with `--workers 1`. The queue and SSE bus live in process memory; a request could enqueue on one worker and stream from another [TECH §17.2].
2. A job's durable state MUST be committed in PostgreSQL before `runner.wake(job_id)` is called [TECH §9.4].
3. No blocking work may run on the event loop: parsing/metrics use `asyncio.to_thread` or a bounded process pool; `boto3` runs through `asyncio.to_thread`; Chromium runs only in the export subprocess [TECH §4.1].
4. No provider call may run inside a database transaction [TECH §8.2].
5. The domain package MUST NOT import FastAPI, SQLAlchemy, LangChain, `httpx`, or `boto3` [TECH §4.2].
6. Only the API process owns the DB credentials; the export child uses presigned object URLs and a temp directory.
7. Readiness MUST fail during shutdown before the process stops accepting work, and a command response MUST NOT be emitted before its transaction commits [TECH §9.8, §13.5; API §2.5].

### 3.1 Lifespan

| Phase | Steps | Failure behavior |
| --- | --- | --- |
| Startup | Load and validate settings (fail fast) → init structlog/Sentry/OTel → create engine and `async_sessionmaker` → start `EventBus` → start `JobRunner` (worker tasks, reconcile loop) → mark ready | Any failure aborts boot; the process exits non-zero; readiness never turns green |
| Steady state | Reconcile loop every 30 s: re-wake `QUEUED`, requeue expired leases, expire past-deadline jobs, audit `SUCCEEDED` artifacts [TECH §9.8] | Audits log content-free findings; they never mutate project content |
| Shutdown | Readiness false → reject new commands with `503` → stop pulling jobs → grant `SHUTDOWN_GRACE_S` (default 30 s) → requeue unfinished attempts (`QUEUED`, release lease, `jobResumed`) → close SSE subscribers (`resync`) → flush OTel/Sentry → dispose engine | Unfinished attempts are re-run after restart; fencing prevents duplicate commits |

### 3.2 Startup reconciliation

1. Re-wake `QUEUED` rows not in the in-memory set, ordered by `priority DESC, created_at`, bounded batch [TECH §9.8].
2. Requeue `RUNNING` rows whose `lease_expires_at < now()`. In the single-process M1 topology, any `RUNNING` row observed at boot belongs to a dead process, so it is requeued immediately; the claim increments `fencing_token` and the stale worker cannot commit.
3. Set `EXPIRED` on `QUEUED` rows past `deadline_at` and emit the class failure event with `errorCode=deadline_exceeded` (§9.5).
4. Verify `SUCCEEDED` page jobs have a committed artifact and a resolvable pointer; log a content-free `audit_event` on mismatch and enqueue a projection rebuild [DATA B.2].

**Why `workers=1` is a correctness invariant.** `asyncio.Queue` and `EventBus` are process-local. With two uvicorn workers, a command handled by worker A enqueues work only A can see, and an SSE connection to B never receives A's events. PostgreSQL stores the job row, but no process would poll it (dispatch is not a DB queue) and no cross-process fan-out exists. Enabling a second process is therefore a data-loss/latency bug, not a scaling choice; the required precondition is the shared dispatch/replay upgrade [TECH §9.11, §17.2].

---

## 4. Module layout and dependency rules

```
backend/
  alembic/  tests/
  app/
    main.py                 # app factory, lifespan, middleware, SPA mount
    api/                    # deps.py (session, project scope, headers, idempotency); v1/ routers
    core/                   # config, db, security, ids, clock, errors, logging, telemetry, ratelimit
    domain/                 # pure: layouts, geometry, validation, fingerprints, stale, gates,
                            # page identity, advance token, history rules
    models/                 # SQLAlchemy 2.0 models mapped to DATA §6 names
    schemas/                # request/response/event/model-output Pydantic models (camelCase)
    services/               # projects, orchestrator, artifacts, ingestion, research, generation,
                            # outline, styles, export, events, metering, policy, idempotency
    workflows/  llm/        # LangGraph graphs; model gateway, providers, prompts, structured output
    ingest/                 # parsers, url_fetch, search, limits
    render/  storage/       # renderers, fonts, export_runner; S3/MinIO adapter, presigned URLs
    worker/                 # runner, registry, handlers, reconcile, shutdown
    cli/                    # create_user, reconcile, rebuild_projections, export_openapi, export_schemas
```

### 4.1 Architecture component → module

| Architecture component [ARCH §5] | Module(s) | Writes |
| --- | --- | --- |
| Edge/API | `app/api`, `app/core/security.py`, `app/services/idempotency.py` | `idempotency_record`, `session` |
| Stream gateway | `app/api/v1/events.py`, `app/services/events.py`, `app/worker/runner.py` | `domain_event` (append only) |
| Project service | `app/services/projects.py`, `app/domain/page_identity.py` | `project`, `page`, `project_event_counter` |
| Workflow orchestrator | `app/services/orchestrator.py`, `app/domain/gates.py`, `app/domain/stale.py`, `app/domain/advance_token.py` | `project_stage_state`, stage/pointer transitions |
| Artifact/version service | `app/services/artifacts.py`, `app/domain/fingerprints.py` | `artifact_version`, `artifact_pointer`, `page_history_entry`, `artifact_lineage`, `artifact_source_ref` |
| Style/asset registry | `app/services/styles.py` + `shared/themes/*.json` | `style_definition`, `style_selection` |
| Ingestion | `app/services/ingestion.py`, `app/ingest/*` | `material`, `material_digest`, `source_item` |
| Research | `app/services/research.py` | `interview_question`, `interview_answer`, `gap_suggestion`, `gap_decision`, `requirements_profile` |
| Generation | `app/services/generation.py`, `app/workflows/*`, `app/llm/*` | candidate only; commit via artifact service |
| Model gateway | `app/llm/gateway.py`, `app/llm/providers/*` | `usage_record` (via metering) |
| Search adapter | `app/ingest/search.py` | `source_item` (via research) |
| Render/export | `app/services/export.py`, `app/render/*` | `export_job`, `export_artifact`, `render_cache` |
| Scheduler/workers | `app/worker/runner.py`, `app/worker/handlers/*` | `job`, `job_attempt` |
| Event/telemetry/ledger | `app/services/events.py`, `app/services/metering.py` | `domain_event`, `usage_record`, `audit_event` |
| Policy/identity/billing | `app/services/policy.py`, `app/core/security.py` | `billing_account`, `app_user`, `session`, `policy_record`, `quota_counter` (M2) |
| Config/flags | `app/core/config.py`, `app/services/policy.py` | `config_version`, `generation_profile` |

### 4.2 Import rules (enforced by `import-linter` in CI)

| Rule | Violation example |
| --- | --- |
| `app/domain` imports only stdlib, `app.core.ids`, `app.core.errors` | importing `sqlalchemy` or `httpx` in `stale.py` |
| `app/services` may import `domain`, `models`, `storage`, `llm` interfaces, `schemas`; never `fastapi` | raising `HTTPException` from a service |
| `app/api` and `app/worker` may import services/domain/schemas/core; `app/api` never imports `models` for business logic and `app/worker` never calls a router | building a query in a router; calling a route from a handler |
| `app/llm` exposes stage-level interfaces; provider SDK imports stay in `app/llm/providers` | `import openai` in `generation.py` |
| `app/render` reads `shared/`, the design body, and the export snapshot; it MUST NOT call the model or mutate project state | writing `artifact_pointer` from the renderer |
| `app/models` imports only `app/models/base.py` and stdlib/SQLAlchemy | service imports inside a model |
| `frontend` never imports Python; contract types are generated [TECH §5.5] | hand-written duplicate DTOs |

### 4.3 DTO mapping boundary

| Layer | Representation | Rule |
| --- | --- | --- |
| HTTP request/response | camelCase (`projectVersion`, `pageJobDone` payloads) | `schemas/` uses `alias_generator=to_camel`, `populate_by_name=True`; FastAPI serializes by alias |
| Services/domain | snake_case dataclasses and domain types | No Pydantic response model is passed into a service |
| Database | snake_case tables/columns [DATA §6] | ORM mapping is mechanical; no aliasing |
| `domain_event.payload` | camelCase wire payload [API §6] | Stored wire-shaped, content-free; replayed verbatim |
| `job.payload`, `export_job.deck_snapshot`, `upstream_refs` | snake_case IDs | Internal only; never serialized directly |

Path/body enum adaptation: `{kind}` in `GET /api/projects/{projectId}/pages/{pageId}/artifacts/{kind}` and `GET /api/projects/{projectId}/pages/{pageId}/history?kind=design` accepts lowercase `plan|design` and maps to the DB enum `PLAN|DESIGN`; the body `kind` in `POST /api/projects/{projectId}/pages/{pageId}/retry` and `POST /api/projects/{projectId}/pages/{pageId}/undo` accepts `plan|design` likewise; responses always use `PLAN|DESIGN` [API §3.1, §4.6, §4.7].

---

## 5. Request pipeline

Middleware order, outermost first. Every step returns the standard error envelope [API §2.7]; no step writes content to logs.

| # | Step | Responsibility | Failure |
| --- | --- | --- | --- |
| 1 | Context and transport | `X-Request-Id` accepted if 1–128 safe characters, else generated; `trace_id` from OTel; bind structlog context; HTTPS in production, body size cap, `Content-Type` check, security headers | `400 validation` |
| 2 | Authentication | `bound_session` cookie → SHA-256 hash → `session` row → `app_user`; attach principal | `401 error.auth.session_required` (category `forbidden`) |
| 3 | Origin/CSRF | Mutating methods verify `Origin`/`Referer` against `APP_BASE_URL`; `SameSite=Lax` is defence in depth [TECH §6.4, §14] | `403 forbidden` |
| 4 | Project scope/authz | Resolve `{projectId}`; deny unless owner/member; unknown and non-member both look absent [API §4] | `404 error.not_found.project`; M2 role denial `403` |
| 5 | Rate limit | Token bucket per session/user; expensive commands also reserve a PostgreSQL counter [TECH §6.5] | `429 error.rate.limited` + `Retry-After` |
| 6 | Schema validation | Pydantic body/query/path validation; unknown fields ignored on input only where the contract allows | `422 validation`; field errors map to catalogued keys, generic body failure is C-6 |
| 7 | Header validation | `Idempotency-Key` and `X-Expected-Version` presence and format per route [API §2.4] | `400 error.validation.missing_header` |
| 8 | Idempotency | Lookup/claim `idempotency_record`; replay or reject reuse | `422 error.validation.idempotency_key_reused`; in-flight handling in §5.2 |
| 9 | Optimistic version | Inside the transaction: `UPDATE project ... WHERE version = :expected` | `409 error.conflict.stale_version` with `details.currentVersion` |
| 10 | Handler, commit, response | Domain handler writes state, `domain_event`, `job` row; commit before the envelope (`Cache-Control: no-store`, `ETag`, `Idempotent-Replay`) | Typed error → envelope; rollback leaves no effect and wakes nothing |

### 5.1 Command execution template

```python
async def run_command(cmd: Command, ctx: CommandContext) -> Envelope:
    # Steps 1-8 are complete. No provider call in this function.
    async with uow.transaction():                          # one transaction, smallest scope
        record = await idempotency.claim(ctx)              # INSERT ... ON CONFLICT (scope_key, key)
        if record.replay is not None:
            return record.replay                           # Idempotent-Replay: true; no new job/event/charge
        version = await projects.bump_version(ctx.project_id, ctx.expected_version)
        # UPDATE project SET version = version + 1 WHERE id = :id AND version = :expected RETURNING version
        result = await handler(cmd, ctx, version)           # state + domain_event + job row (+ counter)
        envelope = envelope_for(result, ctx, version)       # 200 or 202 + data + meta
        await idempotency.complete(record, status=envelope.status, body=envelope.body)
    after_commit(ctx)                                      # runner.wake(job_ids); EventBus.publish(event_ids)
    return envelope                                        # returned only after COMMIT succeeded
```

- `handler` MUST NOT call a model, search, parser, object store, or any other network dependency. The only exception is the bounded synchronous profile path (§10.5), which performs the provider call outside the transaction and then revalidates inputs at commit.
- `after_commit` is an explicit post-commit hook, not a FastAPI `BackgroundTask`. Background tasks are not durable and run after the response is queued.
- The event sequence and the response `meta.sequence` come from the same transaction: `meta.sequence` is the last event appended by that command.
- `meta.projectVersion` is the authoritative post-command version; `meta.idempotentReplay` is `true` only for a stored replay [API §2.6].

### 5.2 Async admission (202) variant

For every async command in §7 (the `202` endpoints: delete/restart, material add/finalize, research start/gap decisions, outline/plan/design generation, page regenerate/tweak/retry, and export), the same template applies with two differences:

1. The handler inserts `job` rows with `state='QUEUED'`, `operation_key`, `active_operation_key`, `payload` (IDs only), and `domain_event(jobQueued)` in the same transaction.
2. The envelope is `202` with the job/export handles. Acceptance is never completion: the client learns the outcome from `pageJobDone`, `exportDone`, `profileReady`, or polling [API §2.5, §5].

Idempotent-join rule: a second command whose `active_operation_key` collides returns the existing job.

| Situation | Response |
| --- | --- |
| Same `Idempotency-Key`, same `request_hash`, stored result exists | Stored status and body; `Idempotent-Replay: true` [API §2.8] |
| Same `Idempotency-Key`, different `request_hash` | `422 error.validation.idempotency_key_reused`; nothing executes [API §2.7] |
| Same intent, different key, active job with the same `active_operation_key` | `200` with the existing job and `meta.idempotentReplay: true` [API §2.8] |
| Same page, different intent, active page write | `409 error.gate.page_write_in_progress` [API §7] |
| First request still `IN_PROGRESS` | Wait on the row up to `IDEMPOTENCY_WAIT_MS` (default 5000), then replay; on timeout `429 error.rate.limited` + `Retry-After: 1`, same key [ASSUMPTION · backend, before implementation] |

`request_hash` is SHA-256 over JCS of `{method, routeTemplate, pathParams, body}`; the body itself is never stored. `response_json` stores the exact envelope data (which may include titles/display names, already permitted in the metadata DB by [DATA §9.1]); it is excluded from logs and telemetry. Rows expire by `expires_at`; the window is `[TBD-BE · backend, before pilot]` (API-Q4, AQ-11).

---

## 6. Domain core

The domain package is pure Python: no framework, no I/O, no clock. Inputs are read models; outputs are decisions and value objects. This makes gates, stale scope, fingerprints, and tokens unit-testable with golden tests.

### 6.1 Stage state machine

Status vocabulary is `LOCKED | AVAILABLE | IN_PROGRESS | COMPLETE | STALE | ERROR`; page status is `PENDING | PLANNING | DESIGNING | DONE | STALE | ERROR`; material status is `PENDING | INGESTING | DIGESTED | FAILED | REMOVED`; export state is `QUEUED | VALIDATING | COMPOSING | PACKAGING | SUCCEEDED | FAILED | CANCELLED` [API §3.1]. Every transition that changes the observable projection increments `project.version` once and appends `stageStateChanged` with `{stage, status, previousStatus, reachable, staleReasons, projectVersion}` [API §6].

| # | Trigger | Guard | Transition / effect | Event(s) |
| --- | --- | --- | --- | --- |
| S1 | `POST /api/projects` | Non-empty trimmed topic; mode default `FULLY_AUTOMATIC` | Insert `project` (`INTAKE`, `version=1`, `epoch=1`), `project_event_counter`, idempotency record | `projectCreated` |
| S2 | `POST /api/projects/{projectId}/research/start` | Topic exists; project `ACTIVE` | `INTAKE → RESEARCH` `IN_PROGRESS`; materialize four `interview_question` rows (the client reveals one at a time); enqueue `DIGEST` for materials without a current digest, or a `SEARCH` job for the web-only research plan; ingestion already started at material add | `stageStateChanged`, `questionAsked` ×4, `jobQueued` |
| S3 | `PUT /api/projects/{projectId}/research/answers/{questionKey}` | `stage=RESEARCH`; known question/option | Upsert one answer, `revision+1`; recompute `profileDirty`; no stage change | `answerRecorded` |
| S4 | `POST /api/projects/{projectId}/research/gaps/decisions` | Current batch; not yet decided; digests complete | Write `gap_decision` rows; enqueue one `SEARCH` job per selected gap; `webSkipped` clears selection and skips search | `gapDecided`, `jobQueued`; later `gapSearchCompleted`, `sourceAdded` |
| S5 | `POST /api/projects/{projectId}/research/profile` | Four answers; gap decision when materials exist | Insert `requirements_profile` version; install `project.current_profile_version_id`; clear dirty by fingerprint; clear `outline_version.confirmed_at` on the current outline | `profileReady` (v1) or `profileUpdated`; `stageStateChanged`; `staleChanged` when an outline existed |
| S6 | `POST /api/projects/{projectId}/outline/generate` | Profile exists, not dirty, no active `OUTLINE` job | `RESEARCH → OUTLINE` `IN_PROGRESS`; enqueue one `OUTLINE` job; stream `outlineDelta` while running | `jobQueued`, ephemeral `outlineDelta` |
| S7 | `OUTLINE` job commit | Validated full outline | Insert `outline_version` + sections + page rows; allocate COVER/TOC/END identities; install pointer; `OUTLINE` `COMPLETE` (`confirmed=false`) | `outlineDone`, `stageStateChanged` |
| S8 | `PATCH /api/projects/{projectId}/outline/pages/{pageId}`, `POST /api/projects/{projectId}/outline/pages`, `DELETE /api/projects/{projectId}/outline/pages/{pageId}`, `POST /api/projects/{projectId}/outline/pages/{pageId}/move` | Expected version; deletable page type; current outline | Insert a new `outline_version`; apply edit/move/insert/delete; retire deleted pages; set `confirmed_at=NULL`; compute stale scope; status `STALE` or `COMPLETE` | `staleChanged`, `stageStateChanged` (no dedicated outline-edit event exists in API §6) |
| S9 | `POST /api/projects/{projectId}/outline/confirm` | Outline exists; all pages identified | Set `confirmed_at`/`confirmed_by_user_id`; `OUTLINE` `COMPLETE`; Plan reachable | `stageStateChanged` |
| S10 | `POST /api/projects/{projectId}/plan/generate` | Outline exists + confirmed; profile clean | `OUTLINE → PLAN` `IN_PROGRESS`; plan per-page jobs or zero-job pointer installs | `jobQueued`, `stageStateChanged` |
| S11 | `PLAN_PAGE` commit / failure | Fencing/epoch/cancel valid | Artifact commit; status `DONE`; on failure `ERROR` for that page | `pageJobStarted`, `pageJobDone` / `pageJobFailed`; `stageStateChanged` when the aggregate flips |
| S12 | `PUT /api/projects/{projectId}/style` | Style active; expected version | Write `style_selection`; no generation; Style `IN_PROGRESS` | `stageStateChanged` |
| S13 | `POST /api/projects/{projectId}/style/confirm` | Selection exists | Set `confirmed_at`; Style `COMPLETE`; Design reachable | `stageStateChanged` |
| S14 | `POST /api/projects/{projectId}/design/generate` | Style confirmed; plan current for all pages | `STYLE → DESIGN` `IN_PROGRESS`; page jobs or reuse installs | `jobQueued`, `stageStateChanged` |
| S15 | `DESIGN_PAGE` commit / failure | Fencing/epoch/cancel valid | Artifact commit; history push when a pointer existed; `DONE`/`ERROR` | `pageJobStarted`, `pageJobDone` / `pageJobFailed`; `stageStateChanged` |
| S16 | `POST /api/projects/{projectId}/pages/{pageId}/plan/regenerate`, `POST /api/projects/{projectId}/pages/{pageId}/plan/tweak`, `POST /api/projects/{projectId}/pages/{pageId}/design/regenerate`, `POST /api/projects/{projectId}/pages/{pageId}/design/tweak` | No active page write; page not single-layout for design regenerate | One `PLAN_PAGE`/`DESIGN_PAGE` job; a plan change marks that page's design stale, a design change does not | `pageJobStarted`, `staleChanged` (`PAGE_REPLAN`/`PAGE_TWEAK`), `pageJobDone`/`pageJobFailed` |
| S17 | `POST /api/projects/{projectId}/pages/{pageId}/undo` | Active history row exists | Pointer move; mark history row popped; plan undo marks design stale | `historyPopped`; `staleChanged` when plan was restored |
| S18 | `POST /api/projects/{projectId}/stages/advance` | Mode, gate, stage version, token | Advance `fromStage → toStage`; no job is created here — entering the target stage reruns missing/stale artifacts through the idempotent fan-out command (`POST /api/projects/{projectId}/plan/generate`, `POST /api/projects/{projectId}/design/generate`) | `stageStateChanged` |
| S19 | `POST /api/projects/{projectId}/exports` | Every page has a current design; format valid | Insert `export_job` with frozen `deck_snapshot` + `job(EXPORT)`; `DESIGN → DESIGN` (export is an action) | `jobQueued`; then `exportProgress`, `exportDone` / `exportFailed` |
| S20 | `POST /api/projects/{projectId}/jobs/{jobId}/cancel` | Job exists | `cancel_requested_at` set; worker stops at checkpoint; cancelled never succeeds | `jobCancelled` |
| S21 | `POST /api/projects/{projectId}/restart` / `DELETE /api/projects/{projectId}` | `confirm=true` for restart | Cancel jobs; `epoch+1` and reset, or `status=DELETING` + `DELETE_PROJECT` job | `jobCancelled` ×N, `stageStateChanged`; deletion is observed by `404` |

### 6.2 Gate evaluation

The same pure function serves three callers: `GET /api/projects/{projectId}/snapshot` (projection), command admission (raise a typed gate error), and the projection audit. It runs in this order:

1. Load `project` (stage, version, epoch), pointers (`current_profile_version_id`, `current_outline_version_id`, `current_style_selection_id`), current outline version + page rows, style selection, and page status aggregates.
2. Compute `profileDirty = profile exists AND expected_profile_fingerprint(answers, materials, gaps, sources) != profile.input_fingerprint`. It is never stored [DATA P1/P9].
3. Evaluate the ordered precondition list for each stage. Deny by default: an unknown condition is a closed gate.
4. Set `reachable = (no blocking precondition)`; `LOCKED` when a prerequisite stage is incomplete; `AVAILABLE` when reachable but no artifact; `IN_PROGRESS` when an active job exists for the stage; `ERROR` when a required job failed and no current artifact exists; `STALE` when at least one required generation fingerprint differs; `COMPLETE` otherwise [DATA §8.2].
5. Emit `blockers` only for conditions with a catalogued gate key [API §7]; pure sequencing locks (no profile yet, no plan yet) have an empty `blockers` array and are explained by the previous stage's status. This avoids inventing message keys.
6. `staleReasons` are content-free codes such as `profile_version_changed`, `outline_version_changed`, `outline_unconfirmed`, `style_changed`, `plan_version_changed`, `artifact_missing` [DATA §6.2].

| Gate (enforced on) | Preconditions (all MUST hold) | Error when violated |
| --- | --- | --- |
| `POST /api/projects/{projectId}/research/profile` | Four answers; gap decision when materials exist | `error.gate.answers_incomplete` / `error.gate.gaps_undecided` [API §4.4] |
| `POST /api/projects/{projectId}/research/gaps/decisions` | Current batch undecided; selected digests current | `error.gate.gaps_already_decided`, `error.gate.digest_incomplete` |
| `PUT /api/projects/{projectId}/research/answers/{questionKey}` | `stage=RESEARCH`; known question/option | `error.gate.research_not_active`, `error.validation.unknown_question`, `error.validation.unknown_option` |
| `POST /api/projects/{projectId}/outline/generate` | Profile exists and not dirty; no active outline job | `error.gate.profile_dirty` (with `details.reason` = `profile_missing` or `dirty`) [C-6] |
| `POST /api/projects/{projectId}/outline/confirm` | Current outline exists; pages identified | `error.gate.outline_missing`, `error.gate.outline_page_identity` |
| `POST /api/projects/{projectId}/plan/generate` | Outline exists and confirmed; profile clean | `error.gate.outline_missing`, `error.gate.outline_unconfirmed`, `error.gate.profile_dirty` |
| `PUT /api/projects/{projectId}/style`, `POST /api/projects/{projectId}/style/confirm` | Plan current for all pages; selection exists for confirm | `error.gate.plan_incomplete`, `error.gate.style_not_selected` |
| `POST /api/projects/{projectId}/design/generate` | Style selection confirmed; current plan for every scheduled page | `error.gate.style_unconfirmed`, `error.gate.style_not_selected` |
| `POST /api/projects/{projectId}/exports` | Every page has a current design | `error.gate.design_incomplete` |
| `POST /api/projects/{projectId}/outline/pages/{pageId}/move`, delete | Body page; expected version | `error.gate.fixed_page_not_deletable` |
| Material add/remove after research | `stage ∈ {INTAKE, RESEARCH}` only | `error.gate.material_locked` with `details.restartRequired: true` [API §4.3.1] |
| Material add / upload | Required data notice accepted | `error.gate.consent_required` [API §4.1 A5/A6] |
| Topic change | `stage=INTAKE` | `error.gate.topic_locked` |
| Regenerate design | Page has more than one layout | `error.gate.single_layout_use_tweak` |

### 6.3 Stable page identity

- `page.id` is a UUIDv7 assigned once and never reused [DATA P3, DM-4].
- `page.page_type` is `COVER | TOC | BODY | END`. COVER, TOC, and END are created at outline v1, cannot be retired, and may have their titles edited [PRD FR-3.2].
- A body page receives an ID at generation or insertion. Insert creates a new ID. Delete sets `page.retired_at` and tombstones plan/design/history for that page; the row remains for audit [DATA §7.6].
- Position and `section_key` live in `outline_page_version`, so move/reorder never changes identity [ARCH AD-11].
- Outline regeneration reconciles by an explicit generated page key when the model supplies one; otherwise by `(section_key, normalized_title)` only when unique within the section. Ambiguous matches MUST NOT reuse identity or history. The exact rule is `[TBD-BE · backend, before outline v2]` (AQ-2, DM-Q4).
- A retired page MUST NOT be re-activated by a late job: the artifact commit checks `page.retired_at IS NULL`.

### 6.4 Input fingerprints

Canonicalization is SHA-256 over RFC 8785 JCS with UTF-8, sorted object keys, and no insignificant whitespace [DATA DM-9]. Floats MUST be integers or decimal strings; timestamps MUST NOT appear. `fingerprint_version` is a config value and is part of every input.

```json
{"artifactKind":"PLAN","projectId":"…","pageId":"…","pageType":"BODY","sectionKey":"part-1","keyPoints":["…"],"outlinePageSchemaVersion":1,"layoutVocabularyVersion":"v1","generationProfile":"plan.economy@3","promptVersion":"plan@7","planSchemaVersion":1,"fingerprintVersion":1}
```

```json
{"artifactKind":"DESIGN","projectId":"…","pageId":"…","planArtifactVersionId":"…","styleDefinitionId":"…","styleVersion":2,"designVocabularyVersion":"v1","generationProfile":"design.quality@5","promptVersion":"design@9","designSchemaVersion":1,"fingerprintVersion":1}
```

| Rule | Reason |
| --- | --- |
| A PLAN fingerprint MUST include page type, `section_key`, key points, outline page schema, layout vocabulary, generation profile, prompt version | These are the plan's semantic inputs [ARCH §8.4] |
| A PLAN fingerprint MUST NOT include the outline page row id, title, position, profile id, or style | A title edit or reorder must not invalidate the plan [PRD §8.9.1 R1/R2] |
| A DESIGN fingerprint MUST include the current plan artifact version id, style definition id/version, design vocabulary, profile, prompt | These are the design's semantic inputs |
| A DESIGN fingerprint MUST NOT include its own output version, title, deck order, or chrome hash | Chrome is a composition input [ARCH AD-12] |
| `chrome_version = sha256(jcs({pageId, title, position, deckOrder, sectionKey, sectionLabel, chromeSchemaVersion}))` | A title/order change re-renders deterministically with zero model jobs |

The DATA §7.3 sketch lists `outlineChromeVersion` inside the artifact fingerprint. Read literally, a title edit would change the design's generation fingerprint and require a model job, contradicting [ARCH AD-12] and [PRD §8.9.1 R1]. This design resolves the tension by keeping chrome in the composition tier only (C-7 in §18); `artifact_version.input_fingerprint` remains the generation fingerprint, and `render_cache.chrome_version` records composition.

### 6.5 Stale derivation and affected scope

1. Read the current pointers and the current outline page row for every non-retired page; compute the expected PLAN and DESIGN generation fingerprints (§6.4).
2. Compare with `artifact_pointer` → `artifact_version.input_fingerprint`: `MISSING` (no pointer), `GENERATION_STALE` (differs), `CURRENT`. Compute `chrome_version`; a current design body with no `render_cache` row for `(artifact_version_id, chrome_version)` is `COMPOSITION_STALE`.
3. Affected scope = `GENERATION_STALE ∪ MISSING` per kind; recomposition scope = `COMPOSITION_STALE`.
4. Reuse before enqueue: look up the newest `artifact_version` for `(project_id, page_id, kind, input_fingerprint = expected)` (index `(project_id, input_fingerprint)` [DATA §6.5]). If found, install the pointer (push the displaced current onto history only if a pointer existed and changed) with zero jobs; this is `counts.reused` in `POST /api/projects/{projectId}/plan/generate` and `POST /api/projects/{projectId}/design/generate` [API §4.7, §4.9].
5. Schedule one job per remaining stale artifact. Chrome-only pages are recomposed deterministically and never enter the generation queue.
6. Emit `staleChanged` with `{fromStage, cause, affectedPageIds, affectedPages, rerunPages, cascadeRatio, projectVersion}`. `cascadeRatio = rerunPages / max(1, pages with changed semantic inputs)`, `null` when the denominator is 0; chrome-only recompositions are excluded from the numerator [ARCH §8.4, §11].

| Matrix row [PRD §8.9.1] | Cause code | Plan | Design | Jobs |
| --- | --- | --- | --- | --- |
| Edit page title | `OUTLINE_EDIT` | keep | recomposition (status stale until rendered) | 0 |
| Reorder within section | `OUTLINE_MOVE` | keep | recomposition | 0 |
| Move across sections | `OUTLINE_MOVE` | generation stale (section key changed) | generation stale | plan + design for moved pages |
| Add page | `OUTLINE_INSERT` | missing (new chain) | missing | plan + design for the new page |
| Delete page | `OUTLINE_DELETE` | tombstone | tombstone | 0 |
| Re-plan / tweak one page | `PAGE_REPLAN` / `PAGE_TWEAK` | current page regenerated | that page stale | 1 job (+1 design on the next fan-out) |
| Change style | `STYLE_CHANGE` | keep | generation stale for all pages | design jobs only |
| Update profile (outline exists) | `PROFILE_UPDATE` | outline unconfirmed, then diff after reconfirm | stale | reconfirm first; then diff-scoped |
| Material removed during RESEARCH after a profile | `MATERIAL_REMOVED` | profile dirty | nothing yet | 0 (profile update required) |

### 6.6 Undo / history

**Restore.** Lock the pointer `FOR UPDATE`, select the active `page_history_entry` for `(project_id, page_id, kind)` with the highest `stack_sequence` and `popped_at IS NULL`, set `artifact_pointer.artifact_version_id` to that entry's version, and set `popped_at = now()` (never delete) [DATA §7.2]. Emit `historyPopped` with `{pageId, kind, restoredArtifactVersionId, version, historyDepth, projectVersion}`.

**No side effects.** No new artifact, no model call, no `usage_record`, no `job` [ARCH §8.5, PRD FR-6.5]. Undoing a PLAN marks that page's design generation stale with `cause=UNDO` [API §3.10]. Undoing a DESIGN emits no stale change (`stale: null`).

**Depth.** `historyDepth` = active rows; `canUndo` = depth > 0; cap `PAGE_HISTORY_MAX_DEPTH` (placeholder 20, `[TBD-BIZ · product + finance]` AQ-5) [DATA §9.3]; versions beyond the cap remain immutable until retention GC.

### 6.7 Auto-advance token

| Property | Design |
| --- | --- |
| Issue condition | `mode=FULLY_AUTOMATIC` (`EXPERT_COPILOT` is never eligible); `fromStage` `COMPLETE`; gate eligible; no active job; no pending edit; a target stage exists [ARCH AD-9, §8.8] |
| Wire fields | `StageStateDTO.advanceToken`, `advanceTokenExpiresAt`; 30-second expiry [API §4.5] |
| Format | `base64url(payload).base64url(HMAC-SHA256(payload))`; payload `{projectId, fromStage, stageVersion, outlineVersionId?, issuedAt, nonce}`; key derived from `SESSION_SECRET` |
| Validation | Signature; expiry; `fromStage == project.stage`; `stageVersion == project.version`; gate still eligible; mode still automatic |
| Errors | Expired → `error.gate.token_expired`; stage moved → `error.conflict.stage_changed`; ineligible or version moved → `error.gate.auto_advance_ineligible` [API §4.5] |
| Single use | Not stored server-side; replay after success fails the stage check and returns `error.conflict.stage_changed` |
| Ownership | The client owns the visible countdown; the server never advances on a timer [ARCH AD-9; FLOW §2 stage 3] |

### 6.8 Concurrency

- **One page writer.** `job.active_operation_key = 'page:{pageId}'` is unique for active rows; it covers PLAN and DESIGN page jobs and is cleared on terminal state [DATA P8, §7.5]. A second intent returns `409 error.gate.page_write_in_progress`; the same intent joins the active job with `200` and `meta.idempotentReplay: true`.
- **One project version.** Every project-scoped command carries `X-Expected-Version`; success increments `project.version` exactly once; job/artifact completion increments it once per commit [API §2.8].
- **Idempotency.** Every command carries `Idempotency-Key`; `(scope_key, idempotency_key)` is unique; a reused key with a different request hash is rejected [DATA §6.8].
- **Structure is server-serialized.** Outline edits, moves, inserts, deletes, and style changes take the project version; the response wins over optimistic ordering. A conflict returns `409 error.conflict.stale_version` with `details.currentVersion`; the client refetches and re-issues with a new key [ARCH §8.6, API §8.2].

---

## 7. Service-by-service design

All services take a `UnitOfWork` and repository protocols. Only repositories import `AsyncSession`. No service returns ORM objects to `app/api`.

| Service | Responsibility / authoritative data | Transaction boundary | Key failure paths | Endpoints served |
| --- | --- | --- | --- | --- |
| **ProjectService** | Lifecycle, name/topic/mode, stage pointer, version, epoch, page registry, profile/outline/style pointers, snapshot assembly. Authoritative: `project`, `page`, `project_event_counter`, `project_stage_state` (written via orchestrator). | create/rename/restart/delete in one transaction each; snapshot is a read-only transaction | Empty topic; topic locked after intake; version conflict; restart while deleting; delete partial → `DELETING` + sweeper | `POST /api/projects`; `GET /api/projects/{projectId}/snapshot`; `PATCH /api/projects/{projectId}`; `POST /api/projects/{projectId}/restart`; `DELETE /api/projects/{projectId}` |
| **Orchestrator** | Gates, transitions, `profileDirty`, stale derivation, affected scope, reuse, job planning, advance-token validation, stage/page projections. Authoritative: `project_stage_state` (rebuildable projection), no content. | Called inside the command transaction; stale computation is pure and side-effect free | Gate violation (no mutation); missing lineage → smallest safe superset + alert; projection drift → audit repair | `POST /api/projects/{projectId}/stages/advance`; `GET /api/projects/{projectId}/pages` (status projection); internal to every command |
| **ArtifactService** | Immutable versions, pointer map, history stack, lineage, source refs, commit protocol, reuse installs. Authoritative: `artifact_version`, `artifact_pointer`, `page_history_entry`, `artifact_lineage`, `artifact_source_ref`. | One transaction per commit (§8.2); content written before it | Fencing/epoch/cancel mismatch → discard; input fingerprint moved → attempt fails `stale_inputs`; orphan object → sweeper | `GET /api/projects/{projectId}/pages/{pageId}/artifacts/{kind}`; `GET /api/projects/{projectId}/pages/{pageId}/history`; `POST /api/projects/{projectId}/pages/{pageId}/undo` |
| **IngestionService** | Material registry, per-material status, per-material isolation, URL/upload handshake, provided sources. Authoritative: `material`, `material_digest`, `source_item` (`origin=PROVIDED`). | Add/remove/finalize: one transaction with job row + event; worker commit per material | Parse failure isolates the material; URL unreachable recorded on the material; MIME mismatch; cap reached; material locked after research | `GET /api/projects/{projectId}/materials`; `POST /api/projects/{projectId}/materials/paste`; `POST /api/projects/{projectId}/materials/url`; `POST /api/projects/{projectId}/materials/upload-url`; `POST /api/projects/{projectId}/materials/{materialId}/finalize`; `DELETE /api/projects/{projectId}/materials/{materialId}` |
| **ResearchService** | Interview catalog/answers, gap suggestions/decisions, profile versions, web source items, search orchestration. Authoritative: `interview_question`, `interview_answer`, `gap_suggestion`, `gap_decision`, `requirements_profile`, `source_item` (`origin=WEB`). | Answer/decision/profile in one transaction each; search commits per result batch | Answers incomplete; gaps undecided/decided; zero results; provider failure; digest incomplete; profile provider unavailable | `POST /api/projects/{projectId}/research/start`; `GET /api/projects/{projectId}/research`; `PUT /api/projects/{projectId}/research/answers/{questionKey}`; `POST /api/projects/{projectId}/research/gaps/decisions`; `POST /api/projects/{projectId}/research/profile`; `GET /api/projects/{projectId}/sources` |
| **GenerationService** | Outline/plan/design/tweak handlers, prompt registry, structured output, one repair, candidate production. Authoritative: none (candidates only). | No transaction during the provider call; commit delegated to ArtifactService | Invalid structured output → one repair → failed attempt; provider timeout/unavailable; single-layout regenerate; non-empty instruction required | `POST /api/projects/{projectId}/plan/generate`; `POST /api/projects/{projectId}/pages/{pageId}/plan/regenerate`; `POST /api/projects/{projectId}/pages/{pageId}/plan/tweak`; `POST /api/projects/{projectId}/pages/{pageId}/retry`; `POST /api/projects/{projectId}/design/generate`; `POST /api/projects/{projectId}/pages/{pageId}/design/regenerate`; `POST /api/projects/{projectId}/pages/{pageId}/design/tweak` |
| **OutlineService** | Outline versions, sections, page rows, edits/moves/inserts/deletes, confirmation, identity reconciliation. Authoritative: `outline_version`, `outline_section_version`, `outline_page_version` (identity allocation delegated to ProjectService). | One transaction per edit: new version + page rows + page allocation/retire + unconfirm + stale + event | Version conflict; fixed-page delete; unknown section; ambiguous reconciliation refuses reuse | `POST /api/projects/{projectId}/outline/generate`; `GET /api/projects/{projectId}/outline`; `POST /api/projects/{projectId}/outline/confirm`; `PATCH /api/projects/{projectId}/outline/pages/{pageId}`; `POST /api/projects/{projectId}/outline/pages`; `DELETE /api/projects/{projectId}/outline/pages/{pageId}`; `POST /api/projects/{projectId}/outline/pages/{pageId}/move` |
| **StyleService** | Built-in catalog, token resolution, preview signing, selection/confirmation, asset resolution/authorization; scope `BUILTIN`/`ACCOUNT`/`ORGANIZATION`; license `CLEARED`/`SUBSTITUTION_REQUIRED`/`UNKNOWN`/`BLOCKED`. Authoritative: `style_definition` (seeded by migration), `style_selection`. | Selection/confirm in one transaction each; catalog read-only | Unknown/inactive style → `404`; license status surfaced; preview URL never logged; unreferenced asset → `404` | `GET /api/styles`; `GET /api/styles/{styleKey}`; `PUT /api/projects/{projectId}/style`; `POST /api/projects/{projectId}/style/confirm`; `GET /api/projects/{projectId}/assets/{assetId}` |
| **ExportService** | Frozen deck snapshot, export job state, validation report, package/checksum, download authorization. Authoritative: `export_job`, `export_artifact`. | Create: one transaction with `job(EXPORT)`. Completion: parent transaction after the child exits | Validation failure; child crash/timeout; empty package; checksum mismatch; not ready; expired artifact | `POST /api/projects/{projectId}/exports`; `GET /api/projects/{projectId}/exports/{exportId}`; `GET /api/exports/{exportId}/download` |
| **Scheduler / Worker** | Queue dispatch, leases, fencing, attempts, retries, deadlines, cancellation, reconciliation. Authoritative: `job`, `job_attempt`. | Claim and commit are separate transactions (§9) | Queue full (reconciler picks up); lost lease; crash; DB unavailable; cancel during commit | `GET /api/projects/{projectId}/jobs/{jobId}`; `POST /api/projects/{projectId}/jobs/{jobId}/cancel` |
| **EventService / SSE** | Sequence allocation, durable append, in-process fan-out, replay, resync, heartbeat; `Last-Event-ID` is accepted only when `cursor` is absent [API §2.4]. Authoritative: `domain_event` + `project_event_counter`. | Append in the caller's transaction; publish after commit | Cursor too old → `resync`; slow subscriber → disconnect + `resync`; duplicate sequence on reconnect deduped | `GET /api/projects/{projectId}/events?cursor={sequence}` |
| **MeteringService** | Append-only usage, operation keys, unit prices, adjustments. Authoritative: `usage_record`. | Same transaction as the artifact commit or attempt close | Duplicate original row blocked by unique key; failed attempts recorded on `job_attempt` | None (ledger only) |
| **Policy / Config** | Sessions/auth, project authorization, rate counters, entitlements (M2), client config, config versions, feature flags, data notices and consent records. Authoritative: `app_user`, `session`, `billing_account`, `policy_record`, `config_version`, `generation_profile`, `quota_counter` (M2). | Auth reads; config writes are versioned inserts; consent is an idempotent `policy_record` insert | Invalid credentials; expired session; rate limited; capability disabled → `503` with no job; consent missing → `error.gate.consent_required` | `POST /api/auth/login`; `POST /api/auth/logout`; `GET /api/auth/me`; `GET /api/config`; `GET /api/policy/notices`; `POST /api/policy/consent`; `GET /api/health`; `GET /api/health/ready` |

Service rules: ProjectService never writes artifacts; Orchestrator never generates content; GenerationService never mutates pointers; ArtifactService is the only writer of `artifact_pointer`/history; ExportService never mutates project state or style; MeteringService never updates ledger rows.

---

## 8. Persistence and transaction design

### 8.1 Repository and session rules

- Repositories are the only layer importing `AsyncSession`; services depend on protocols. Raw SQL is allowed for job claim, reconciliation, projection audits, and event replay, always parameterized [TECH §8.2].
- One `UnitOfWork` per command or per worker step; `async with session.begin()` scopes the smallest possible transaction. No transaction spans a provider, search, parser, object-store, or subprocess call.
- Relationships use `lazy="raise"`; repositories opt into `selectinload`/`joinedload` [DATA A.1].
- `SELECT ... FOR UPDATE` is used only for the artifact pointer during commit/undo and for the job claim/commit rows. It is never held during a provider call.
- Money/units use `Numeric(18,6)` mapped to `Decimal`; never `float`. The M2-facing `auth_account`, `verification_token`, and `account_style_preference` tables exist but are not on the M1 request path [DATA §6.1, §6.4].

### 8.2 Artifact commit protocol

The worker commits a candidate only after content is written and structured validation passes. One transaction, in this order [DATA §7.1]:

| Step | Action | Failure |
| --- | --- | --- |
| 1 | Lock and verify `job`: `state='RUNNING'`, `lease_owner`, `fencing_token`, `cancel_requested_at IS NULL`; verify `project.epoch == payload.epoch`; verify `page.retired_at IS NULL` | Abort; discard candidate; log `fenced`/`cancelled`/`page_retired` |
| 2 | Recompute the expected generation fingerprint from current upstream rows; compare with the candidate's fingerprint | Abort as retryable `stale_inputs`; requeue |
| 3 | Insert `artifact_version` (content ref/digest, fingerprint, upstream refs, source refs, producer job/attempt/model/prompt, schema version) | Roll back; orphan object for the sweeper |
| 4 | Insert `artifact_lineage` edges and `artifact_source_ref` rows | Roll back |
| 5 | Lock `artifact_pointer`; if present and different, insert `page_history_entry` with `stack_sequence = max(active)+1` and the commit reason | Roll back |
| 6 | Upsert `artifact_pointer` to the new version — **the commit point** | Roll back |
| 7 | Close `job_attempt` (`SUCCEEDED`, ended_at, usage fields), set `job.state='SUCCEEDED'`, clear `active_operation_key`, set `completed_at`; insert `usage_record` rows | Roll back; no pointer change |
| 8 | Increment `project.version`, append `pageJobDone` (or `outlineDone`), append `stageStateChanged` if the aggregate flips; update `project_event_counter` in the same transaction | Roll back |

Rules: content is never mutated; a failed transaction leaves metadata unchanged and an orphan object; a late worker whose fencing token no longer matches MUST NOT install a pointer or history row [ARCH §8.6]. The commit reason is `REGENERATE`, `TWEAK`, `REPLAN`, `STYLE_CHANGE`, or `MANUAL`; `MANUAL` covers a reuse install that displaces a current pointer. A terminal job writes exactly one original `usage_record` per `(operation_key, unit_type)` — on success in step 7, on final failure in the attempt-close transaction — while the per-attempt breakdown stays on `job_attempt`.

### 8.3 Key SQL shapes

```sql
-- Optimistic version (all project-scoped commands)
UPDATE project SET version = version + 1, updated_at = now()
WHERE id = :project_id AND version = :expected_version
RETURNING version;                                  -- 0 rows => 409 error.conflict.stale_version

-- Event sequence (same transaction as the state change)
UPDATE project_event_counter SET last_sequence = last_sequence + 1
WHERE project_id = :project_id RETURNING last_sequence;

-- Job claim (single conditional update; the returned token fences the commit)
UPDATE job SET state = 'RUNNING', lease_owner = :worker_id,
       lease_expires_at = now() + interval '60 seconds',
       fencing_token = fencing_token + 1, attempt_count = attempt_count + 1,
       updated_at = now()
WHERE id = :job_id AND state = 'QUEUED'
  AND (deadline_at IS NULL OR deadline_at > now())
RETURNING fencing_token, attempt_count, project_id, type, payload;
-- then INSERT job_attempt (job_id, attempt_no = attempt_count, fencing_token, state='RUNNING', ...)

-- History push (no shifting; the unique partial index guards active duplicates)
INSERT INTO page_history_entry (id, project_id, page_id, kind, artifact_version_id,
                                stack_sequence, reason, created_at)
SELECT :id, :project_id, :page_id, :kind, :prior_version_id,
       COALESCE(MAX(stack_sequence), 0) + 1, :reason, now()
FROM page_history_entry
WHERE project_id = :project_id AND page_id = :page_id AND kind = :kind AND popped_at IS NULL;

-- Active write slot (unique nullable column; multiple NULLs are allowed)
INSERT INTO job (..., active_operation_key) VALUES (..., 'page:' || :page_id)
ON CONFLICT (active_operation_key) DO NOTHING RETURNING id;
```

Idempotency uses `INSERT ... ON CONFLICT (scope_key, idempotency_key) DO NOTHING RETURNING id`, then a read of `request_hash`, `state`, `response_json`. A row is marked `COMPLETED` with the response in the same transaction as the effect; a deterministic 4xx marks it `FAILED` with the response so retries replay the failure; an unexpected 5xx deletes the row so the client can retry the same intent. Expired rows are purged by a sweeper on `(expires_at)`.

### 8.4 Content before metadata and orphan sweeping

1. The worker writes the candidate body to the object key from [DATA §9.1] with `Content-Type: application/json`, computing SHA-256 while streaming; the metadata transaction then installs the reference, and the pointer install is the commit point.
2. The orphan sweeper lists objects older than `ORPHAN_GRACE_S` with no `artifact_version`, `material`, `material_digest`, `export_artifact`, or `render_cache` reference, deletes only under the expected tenant prefix, and logs counts, never keys [DATA §9.2].
3. A pointer MUST NOT reference missing content: `GET` verifies object existence and returns `500 error.internal.unexpected` (not a fabricated body) if it is absent.

### 8.5 Deletion, restart, retention

| Operation | Protocol |
| --- | --- |
| Remove material before research | Delete content refs, mark `REMOVED`, restore capacity; no downstream artifacts exist [PRD FR-1.6] |
| Remove material during research after a profile | Retire the material, cancel its ingestion, recompute `profileDirty` (it becomes true), emit `materialStatusChanged`; `POST /api/projects/{projectId}/research/profile` creates a new version |
| Add/remove material at OUTLINE or later | Rejected with `error.gate.material_locked` + `details.restartRequired: true` [API §4.3.1] |
| Delete page | Retire `page`, tombstone artifacts/history, remove from the new outline version; existing export snapshots unaffected [ARCH §7.4] |
| Restart | Cancel jobs, `epoch+1`, reset stage/pointers, tombstone prior artifacts under retention, clear snapshot cache [API §4.2] |
| Delete project | `status=DELETING`, cancel jobs, enqueue `DELETE_PROJECT`; sweeper deletes/retires materials, digests, bodies, history, exports, renders, caches, then writes the tombstone (`DELETED` is only observable as `404`); ledger rows stay pseudonymous/content-free [PRD FR-8.2, NFR-PRIV-1] |
| Retention | `PAGE_HISTORY_MAX_DEPTH`, export artifact expiry, event retention, raw-material retention are config keys with `[TBD-BIZ]`/`[TBD-INFRA]` owners [DATA §9.3] |

---

## 9. Job system

### 9.1 Record fields used by the runner

| Field | Use |
| --- | --- |
| `type` | One of `INGEST`, `DIGEST`, `GAP_SUGGEST`, `PROFILE`, `OUTLINE`, `PLAN_PAGE`, `DESIGN_PAGE`, `EXPORT`, `DELETE_PROJECT` [API §3.1] |
| `operation_key` | Intent identity, e.g. `PLAN_PAGE:{pageId}:regen:{n}` |
| `active_operation_key` | `page:{pageId}` for page writes; `outline:{projectId}`, `profile:{projectId}`, `export:{projectId}`, `ingest:{materialId}`, `digest:{materialId}`, `research:{projectId}:gaps`, `delete:{projectId}`; unique while active, NULL on terminal |
| `payload` | IDs and non-content parameters only, including `epoch`; a tweak instruction lives in `instruction_ref` (object storage) [DATA §6.6] |
| `state` | `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED`, `EXPIRED` |
| `attempt_count` / `max_attempts` | Cross-attempt accounting; default max 3 (`[TBD-BE]` PRD-11) |
| `deadline_at` / `cancel_requested_at` | No execution after the deadline; cooperative cancellation flag |
| `lease_owner` / `lease_expires_at` | Ownership and expiry; default lease 60 s, heartbeat every 20 s |
| `fencing_token` | Incremented per claim; commit must match |
| `last_error_code` / `last_error_class`; `queue_job_id` | Stable job error code/class (§13); `queue_job_id` is unused in M1 and reserved for a future transport |

### 9.2 Enqueue → claim → commit

| Step | Behavior |
| --- | --- |
| Enqueue / wake | In the command transaction: insert `job` (`QUEUED`, `operation_key`, `active_operation_key`, `payload`), append `jobQueued`, update the projection. After commit: non-blocking `runner.wake(job_id)`; a full queue drops the wake, not the job, and the reconciler re-wakes committed `QUEUED` rows [TECH §9.4] |
| Claim | Conditional `UPDATE ... RETURNING` (§8.3) + `job_attempt` insert in one transaction |
| Heartbeat | Extend `lease_expires_at` every 20 s; zero rows updated means the lease was lost, so abort without committing |
| Commit | §8.2; the success path closes the attempt, installs the artifact, increments the version, appends events, and clears the write slot atomically |
| Terminal | `SUCCEEDED`, `FAILED`, `CANCELLED`, `EXPIRED`; `active_operation_key` is cleared and `completed_at` set |

### 9.3 Retry, backoff, cancel, deadline

| Situation | Behavior |
| --- | --- |
| Retryable failure | Close attempt `FAILED`; set job `QUEUED`; keep the write slot; schedule `wake` after jittered exponential backoff (base 2 s, cap 60 s; `[TBD-BE]` PRD-11); attempts counted at claim |
| Non-retryable failure or attempts exhausted | Close attempt `FAILED`; job `FAILED`; clear slot; page status `ERROR`, other pages continue [PRD FR-4.8, NFR-REL-6]; emit the class failure event with a stable code |
| Cancel | Set `cancel_requested_at`; the handler checks before the provider call, between pages, and before packaging; a cancelled job never installs a pointer; a late result is fenced; `CANCELLED` never becomes success [PRD FR-7.5] |
| Deadline | `QUEUED` past `deadline_at` → `EXPIRED` with `errorCode=deadline_exceeded`; `RUNNING` past deadline is asked to stop at the next checkpoint and then expired |
| Process restart | `RUNNING` rows with expired leases are requeued by the reconciler; `QUEUED` rows are re-woken; retry timers are lost but the committed job is not [TECH §9.8] |
| DB unavailable | The command fails with `503 error.provider.unavailable` (retryable); no in-memory work can commit; the worker requeues |

### 9.4 Pools and fairness

| Pool | Default | Scope |
| --- | --- | --- |
| Generation workers | 4 | `OUTLINE`, `PLAN_PAGE`, `DESIGN_PAGE`, `GAP_SUGGEST`, `PROFILE`, `SEARCH` (search is I/O-bound but bounded by the same per-project slots) |
| Per-project slots | 2 | Any generation job; prevents one project monopolizing the process |
| Ingestion workers | 2 | `INGEST`, `DIGEST`; parsing does not starve page generation |
| Export workers | 1 | `EXPORT`; subprocess with memory/time cap |

Ordering is `priority DESC, created_at ASC`; retries do not jump ahead of user-initiated work indefinitely. `page:{pageId}` uniqueness enforces the single-writer rule independently of pool sizing [TECH §9.7]. The reconciler runs at startup and every 30 s; graceful shutdown follows §3.1 (readiness false, stop pulling, 30 s grace, requeue unfinished attempts with `jobResumed`, then exit).

### 9.5 Task registry

| Job type | Handler | Visible effect (the only API-visible outcome) |
| --- | --- | --- |
| `INGEST` | `ingest-material` | `materialStatusChanged`, `sourceAdded`; material status `INGESTING → DIGESTED/FAILED` |
| `DIGEST` | `digest-material` | `digestReady`; current `material_digest` version |
| `GAP_SUGGEST` | `suggest-gaps` | `gapSuggested`; `gap_suggestion` rows |
| `SEARCH` | `search-gaps` | `gapSearchCompleted` per selected gap; `sourceAdded` per result; zero/failure recorded |
| `PROFILE` | `build-profile` | `profileReady`/`profileUpdated`; profile version + pointer |
| `OUTLINE` | `generate-outline` | `outlineDone` (+ ephemeral `outlineDelta` during the job) |
| `PLAN_PAGE` | `plan-page` | `pageJobDone`/`pageJobFailed`; plan pointer/history |
| `DESIGN_PAGE` | `design-page` | `pageJobDone`/`pageJobFailed`; design pointer/history |
| `EXPORT` | `export-deck` | `exportProgress`, `exportDone`/`exportFailed`; `export_artifact` |
| `DELETE_PROJECT` | `delete-project` | Project becomes `404`; no event for a deleted project |

Non-page failures (for example `OUTLINE`) have no dedicated failure event in API §6; they emit `stageStateChanged` with status `ERROR` and surface the error through `GET /api/projects/{projectId}/jobs/{jobId}`. `EXPORT` uses `exportFailed`; material jobs use `materialStatusChanged`.

### 9.6 Effectively-once semantics

At-least-once execution plus an idempotent commit gives effectively-once results: `job` claim is conditional, the commit requires the current `fencing_token`, `project.epoch`, `cancel_requested_at IS NULL`, and a matching expected fingerprint; `artifact_version` is unique on `(project_id, page_id, kind, version)`; history is unique on the active stack position; `usage_record` is unique on `(operation_key, unit_type)`; `pageJobDone`/`historyPopped` repeat only if a newer commit legitimately occurred. Retrying a page never creates duplicate history or a second charge [PRD NFR-REL-3].

---

## 10. Model gateway and workflows

### 10.1 Gateway surface

| Method | Stage | Output schema | Notes |
| --- | --- | --- | --- |
| `digest(material_text)` | DIGEST | `MaterialDigest` | Length bucket + extraction summary; no invented facts |
| `gaps(digests, profile_inputs)` | GAP_SUGGEST | `GapSuggestion[]` | Exactly three in M1, reasons + recommended |
| `profile(answers, digests, sources, gaps)` | PROFILE | `requirements_profile` | Seven fields, material-first strategy |
| `outline(profile, digests, sources, answers)` | OUTLINE | `Outline` | Streams schema-shaped deltas; final full validation |
| `plan_page(page, sources, layout_vocab)` | PLAN_PAGE | `PlanBodyV1` | Grayscale layout only; no new facts |
| `design_page(plan, style_tokens, design_vocab)` | DESIGN_PAGE | `DesignBodyV1` | Style applied to the plan; chrome excluded |
| `tweak(page_snapshot, instruction, kind)` | PLAN/DESIGN | same body | Instruction is content; stored via `instruction_ref` |
| `repair(invalid_output, schema, errors)` | any | same body | Exactly one repair round per attempt |

The gateway exposes stage-level methods only; provider SDK types never leave `app/llm/providers`. Model, base URL, key, and params come from the active `generation_profile` row and environment; the artifact fingerprint includes `key@version` [DATA §6.9].

### 10.2 Structured output, streaming, prompts, metering

| Concern | Design |
| --- | --- |
| Structured output | Pydantic model + `with_structured_output`; JSON-mode fallback with the schema in the prompt; full Pydantic validation before commit. Invalid output is a failed attempt, never a confirmed artifact [TECH §10.1] |
| Repair | One bounded repair with the validation errors; metered and recorded on the attempt; a second failure ends the attempt |
| Streaming | `astream`; the worker batches deltas every 100–250 ms and publishes ephemeral `outlineDelta` frames to the `EventBus` only; never in `domain_event`; the client reloads the committed outline if it misses them [TECH §6.3] |
| Prompt versioning | `app/llm/prompts/` modules with explicit `PROMPT_VERSION`; reviewed and evaluated in `evals/`; version stored on `artifact_version` and `job_attempt`; no runtime prompt editing [TECH §10.4] |
| Routing | Stage-level `generation_profile`; proposed economy for digest/gap/plan and quality for outline/design; final vendor/tier is `[TBD-BIZ]` (TS-Q1); a fallback MUST pass the same validation and quality bar [ARCH AQ-14] |
| Metering | Per-attempt usage on `job_attempt` (provider, model, tokens, latency, estimated cost); per-logical-operation ledger rows in `usage_record` keyed by `(operation_key, unit_type)`; failed attempts are visible per attempt but never charged twice [ARCH §11, DATA DM-7] |
| Failure mapping | Timeout → `error.provider.timeout` (`504`) inside a retryable attempt; unavailable → `error.provider.unavailable` (`503`); invalid output → `invalid_model_output` on the attempt |
| No mock on the paid path | `MockModelAdapter`/`MockSearchAdapter` are test-only; startup MUST fail when `APP_ENV=production` resolves to a mock provider [TECH §15, PRD FR-7.18] |

### 10.3 Workflows

- **Outline graph:** select/trim source context by precedence → generate structured outline → validate page/section counts, layout IDs, source refs → one repair → candidate.
- **Page graph:** trim the page's sources → generate a structured draft → geometry/overflow fit → validate structure and richness → one repair → candidate.
- **Edit graph:** bind tools to the page snapshot → the model proposes structured operations → the domain applies them with bounds checks → validate before commit.

A graph produces a candidate only. It never mutates a pointer, never commits, and never schedules. The runner schedules, the artifact service commits [ARCH §5.3].

### 10.4 Grounding

Context is assembled in precedence order: first-party materials, then organizational assets when available (M3), then web supplements. Source identities are passed as IDs; the artifact records `artifact_source_ref` rows. Missing or unknown refs fail structured validation. Material and web text are data, never instructions [ARCH §5.3, PRD FR-2.16/2.17, NFR-SEC-3].

### 10.5 Synchronous profile path

`POST /api/projects/{projectId}/research/profile` documents a `200` response and permits an enqueued alternative, but the contract does not define a `202` DTO for that alternative [API §4.4, §5]. DEFAULT for M1: the request performs a bounded provider call outside any transaction, then opens a transaction, re-reads the profile input fingerprint and `project.version`, and commits only if both are unchanged; on a change it returns `409 error.conflict.stale_version`. On provider timeout/unavailable it returns `504 error.provider.timeout`/`503 error.provider.unavailable` and creates no job. The enqueue alternative, and therefore the `PROFILE` job type in the registry, is blocked on API-Q7 `[TBD-BE · backend, before implementation]`.

---

## 11. Ingestion and research implementation

### 11.1 Parsers and limits

| Type | Parser | Extraction |
| --- | --- | --- |
| `.pdf` | `pdfplumber` (text/layout), `pypdf` fallback | Text, page count; scanned PDFs need OCR |
| `.docx` / `.pptx` | `python-docx` / `python-pptx` | Paragraphs/tables or slide text/notes; no macros, no rendering |
| `.xlsx` / `.csv` | `openpyxl` / stdlib `csv` | Values only; formulas are data, never executed |
| `.md` / `.txt` | `markdown-it-py` / UTF-8 read | Text |
| Images/scans | `pytesseract` optional | `[TBD-BE · backend, M1]` per PRD-19 |

Supported type list and every limit are configuration, not code: `ingest.max_bytes`, `ingest.max_pages`, `ingest.max_chars`, `ingest.max_decompression_ratio`, `ingest.timeout_s`, `material.max_count` (`[TBD-BE-1, TBD-UX, BR-7]`). The UI MUST NOT claim a type is supported until its parser passes ingestion tests. Material kinds are `PASTE`, `FILE`, `URL`; source types are `PASTE`, `FILE`, `URL`, `WEB_RESULT`, `INTERVIEW_ANSWER`; origins are `PROVIDED`, `WEB` [API §3.1].

### 11.2 Validation and sandboxing

1. Validate extension allowlist + MIME sniff with `python-magic`; a mismatch is `error.parse.type_mismatch` [PRD FR-1.8].
2. Enforce size/page/character/decompression/parser-time caps before parsing; oversize is `error.validation.file_too_large`.
3. Parse as a job off the event loop (thread pool for I/O-bound parsers, process pool for CPU-bound/OCR); strip active content, never execute macros/scripts, fetch no external relationships, and apply the quarantine/scan policy `[TBD-INFRA · security]`; one material failure never blocks others [PRD FR-1.9, NFR-REL-6].
4. Persist raw + normalized text to object storage; metadata holds refs, sizes, buckets only [DATA §9.1].

Upload handshake: presign after validation → browser `PUT` directly to storage → `finalize` HEADs the object, verifies actual size/type, then enqueues `INGEST`; missing object is `error.validation.upload_missing` [API §4.3]. Raw bytes never pass through the API process.

### 11.3 URL fetch and SSRF

- Normalize a missing scheme to `https://`; reject non-HTTP(S), credentials in the URL, and malformed hosts with `error.validation.invalid_url` [PRD FR-1.5].
- Resolve DNS and block loopback, private, link-local, and metadata ranges; re-check after every redirect; cap redirects, bytes, time, and content type.
- Extract readable text with `trafilatura` (fallback `readability-lxml`); no JavaScript execution in M1.
- Login wall / anti-scraping / 404 → `error.parse.url_unreachable` recorded on the material plus a paste-body suggestion; keep other sources [PRD FR-1.10].
- Store the full URL only in `material.source_url`; telemetry stores `url_hash` + domain [DATA §9.1, PRD §11.5].

### 11.4 Search and research orchestration

| Search outcome | Handling |
| --- | --- |
| Results | Normalize title/summary/URL/domain/rank; insert `source_item` (`origin=WEB`, `source_type=WEB_RESULT`); emit `sourceAdded` per item |
| Zero results | Record an explicit empty outcome; keep the gap; no fabrication; profile records the missing supplement [PRD FR-2.10] |
| Provider error | Retry within the adapter; then fail the search job with `provider_unavailable`; material-only degradation is recorded, never silent [PRD FR-2.20, §13] |

Orchestration: ingest → digest per material → `GAP_SUGGEST` (enqueued by the last `DIGEST` commit once all selected digests are current and no batch exists) → decisions → one targeted search per selected gap → profile. Suggestion status is `SUGGESTED`, `SELECTED`, or `REJECTED`, and a decision is immutable after a profile exists. With no materials, the configured web-only plan runs; with `webSkipped`, no search runs. Search caps are configuration and visible in the profile [PRD FR-2.19, BR-12]. `DIGEST` reuses a current digest when `parser_profile_version` and material version match `[PRD NFR-COST-4]`.

---

## 12. Export pipeline

### 12.1 Subprocess contract

| Item | Contract |
| --- | --- |
| Invocation | Parent spawns `python -m app.render.export_runner --export-id <uuid>` with a temp working directory |
| Inputs | Frozen `export_job.deck_snapshot` (ordered page IDs, current design artifact version IDs, style key/version, format, rendered counts) plus presigned read URLs for each design body and asset |
| Outputs | Child writes the package to a presigned PUT URL and prints one JSON line: `{ok, checksum, byteSize, pagesRendered, validationChecks, substitutions}` |
| Exit codes | `0` success; `2` validation failure; `3` composition failure; `4` internal failure |
| Credentials | No DB credentials, no provider keys, no bucket keys; only short-lived signed URLs and `EXPORT_*` limits |
| Timeout/memory | `EXPORT_TIMEOUT_S`, `EXPORT_MEMORY_MB` (`[TBD-INFRA]`); kill on breach → `exportFailed` |
| Commit | The parent HEADs the object, verifies size > 0 and SHA-256, then commits `export_artifact` + `exportDone` [PRD FR-6.16] |

### 12.2 Mandatory validation

The child MUST run and report every check before success [PRD FR-6.14, TECH §12.5]:

| Code | Check | On failure |
| --- | --- | --- |
| `missing_design`, `page_count_mismatch` | Every snapshot page resolves to a current design; rendered pages equal snapshot pages in order | `FAIL` |
| `empty_page`, `render_incomplete` | No page has zero visible blocks; `renderedCount == pageCount` | `FAIL` |
| `fonts_missing` | Every font resolves/embeds, or a substitution exists | `FAIL` or `WARN` per license policy |
| `asset_out_of_bounds` | Every asset within canvas bounds and non-zero | `FAIL` |
| `text_overflow` | FontTools metrics: structural overflow `FAIL`, capacity risk `WARN` | `FAIL`/`WARN` |
| `license_blocked` | No unlicensed asset is embedded | `FAIL` |
| `html_external_ref` | Offline HTML has no external fetches | `FAIL` |
| `package_integrity` | Output size > 0; parent-recomputed SHA-256 matches; scoped download resolves | `FAIL` |

`ExportValidationCheckDTO.status` is `PASS|FAIL|WARN|SKIP`; failed checks name `pageIds` [API §3.9]. A `FAIL` produces `state=FAILED`, `error.category=export_validation_failure`, `messageKey=error.export.validation_failed`, keeping the modal open for Retry / another format [PRD FR-6.15; FLOW §6].

### 12.3 Composition

| Format | Path |
| --- | --- |
| `PPTX` | `python-pptx` native text boxes/shapes/tables/charts/images built from the design body + `shared/layouts` + `shared/themes`; reopen and verify OOXML parts, slide count, text presence, size; substitution report |
| `HTML` / `PDF` | Single-file viewer with embedded deck JSON, inlined assets, `nh3` sanitization, and no external fetches; Chromium prints it at 13.333×7.5 in with a fixed 1280×720 viewport, `print_background=True`, no headers/footers; page count/aspect checked |

Chrome (page number, section label, deck order, current title) is applied deterministically at composition from the frozen snapshot, never from the design body. Re-export always freezes a fresh snapshot; a cached package is never served after an edit [PRD FR-6.21].

### 12.4 Success criteria and retry

Success requires: package exists, `byte_size > 0`, checksum matches, all mandatory checks pass (no `FAIL`), and the authorized download resolves. Only then does the parent emit `exportDone` with `{exportId, format, artifactId, byteSize, checksum, expiresAt}` [API §6]. Retry is a new export request with a fresh snapshot and a new `exportId`; "Try another format" is also a new request. Export never mutates project state, style selection, or page artifacts; export terminal completion increments `project.version` because `latestExportId` and status are observable.

`ExportDTO.deckSnapshot.excludedPageIds` is populated only under an approved partial-export policy; M1 defaults to blocking export when any page is not current (`error.gate.design_incomplete`), and the partial policy remains API-Q3/PRD-03 `[TBD-BIZ · product + UX, M1]`.

---

## 13. Error handling

### 13.1 Typed exception hierarchy (`app/core/errors.py`)

| Base / subclass | Category | HTTP | Retryable | Notes |
| --- | --- | --- | --- | --- |
| `AppError` | — | — | — | Holds `message_key`, `details`, `http_status`, `retryable`; serialized by one handler |
| `ValidationAppError` | `validation` | 400/422 | No | Field errors map to catalogued keys; generic body failure is C-6 |
| `GateViolationError` | `gate_violation` | 409 | No | One subclass per catalogued gate key |
| `ForbiddenError` | `forbidden` | 401/403 | No | Auth/logon and authorization |
| `NotFoundError` | `not_found` | 404 | No | Project, outline, artifact, export |
| `ConflictError` | `conflict` | 409 | Yes after reconcile | `error.conflict.stale_version`, `error.conflict.stage_changed` |
| `RateLimitedError` | `rate_limited` | 429 | Yes | Carries `Retry-After` |
| `ProviderTimeoutError` | `provider_timeout` | 504 | Yes, bounded | Model/search/parse boundary |
| `ProviderUnavailableError` | `provider_unavailable` | 503 | Yes/queued | Also used when a capability is disabled |
| `ParseFailureError` | `parse_failure` | 422 | No auto-repeat | Recorded on the material |
| `ExportValidationFailure` | `export_validation_failure` | 422 | Conditional | Carries failed checks |
| `QuotaExceededError` | `quota_exceeded` | 402 | No | M2 |
| `InternalError` | `internal` | 500 | Yes once | Never includes exception text or content |
| `FencedJobError`, `CancelledJobError`, `DeadlineExceededError`, `StaleInputsError` | job-internal | — | — | Never serialized to HTTP; drive attempt state |

### 13.2 Mapping and content rules

- Every handler raises a subclass with a fixed `messageKey` from [API §7]; routers never build error dicts. `details` may contain IDs, counts, field names, enum values, booleans; it MUST NOT contain topic, material text, file names, full URLs, prompts, page bodies, or PII [API §2.7, PRD NFR-PRIV-3].
- Authentication failure is `401` with category `forbidden` and `error.auth.session_required`; authorization failure is `403`; any unhandled exception is logged with IDs only and returned as `500 error.internal.unexpected` with `requestId`/`traceId` [API §2.7].
- Request-schema failures use FastAPI `422` but are rewritten into the error envelope. Known field errors map to `error.validation.empty_topic`, `empty_paste`, `invalid_url`, `unsupported_type`, `file_too_large`, `unknown_question`, `unknown_option`, `empty_title`, `empty_instruction`; there is no catalogued generic key (C-6).

### 13.3 Job error codes

Stable codes stored in `job.last_error_code` / `job_attempt.error_code` and surfaced as `PageError.code`: `provider_timeout`, `provider_unavailable`, `invalid_model_output`, `parse_failure`, `url_unreachable`, `type_mismatch`, `validation_failed`, `export_validation_failed`, `stale_inputs`, `fenced`, `cancelled`, `deadline_exceeded`, `internal`. `PageError.category` uses the taxonomy value; `messageKey` uses the catalogued UI key; `retryable` mirrors the scheduler decision.

### 13.4 Retry ownership

| Owner | Scope |
| --- | --- |
| Adapter | Small bounded transient retries inside one attempt (model 429/5xx, search 5xx, URL 5xx), metered per call, no visible state change |
| Scheduler | Cross-attempt retry/backoff, max attempts, deadlines, lease recovery; cancellation wins [ARCH §10] |
| Orchestrator | User-initiated retry (`POST /api/projects/{projectId}/pages/{pageId}/retry`) creates a new attempt or operation key with no duplicate history or charge |
| Client | Resubscribe and resend pending intent with the same idempotency key; never auto-resubmit generation after a `4xx` except `409` (refetch/re-issue) and `429`/`503` [API §2.5] |

---

## 14. Observability, security, privacy

| Area | Design |
| --- | --- |
| Structured logs | `structlog` JSON with redaction processors for cookies, authorization, emails, URLs, prompts, material text, titles, page bodies; allowlisted keys only; every line carries `request_id`, `trace_id`, and when applicable `project_id`, `job_id`, `attempt_id`, `page_id` [TECH §13.1] |
| Traces | OpenTelemetry auto-instrumentation (FastAPI, SQLAlchemy, `httpx`) plus custom spans: admission, gate evaluation, job attempt, model call, search, parse, page render, export package, artifact commit; OTLP export [TECH §13.2] |
| Metrics | Queue depth/wait p95, per-stage/page duration and failure rate, model tokens/cost per stage, export success/failure reasons, SSE connections/reconnects/resyncs, DB pool and slow queries, event-loop lag, export child RSS [TECH §13.2] |
| Sentry | `sentry-sdk[fastapi]`; release = git SHA; `before_send` scrubs request bodies, cookies, headers, and content-bearing locals; the export child reports with a separate tag [TECH §13.3] |
| Auth / CSRF | Opaque 32-byte session token in an HttpOnly, `Secure` (prod), `SameSite=Lax`, `Path=/` cookie; only the SHA-256 hash is stored; logout deletes the row; TTL `SESSION_TTL_HOURS` `[TBD-BE]`; same-origin SPA plus `Origin`/`Referer` check on every mutation [TECH §6.4, §14] |
| Passwords | Argon2 via `pwdlib[argon2]`; generic `error.auth.invalid_credentials`; no account enumeration |
| Project authz | Deny by default on every command/query after resolving `{projectId}`; non-member and unknown IDs both return `404 error.not_found.project`; M2 adds role checks with `403` [PRD NFR-SEC-1] |
| Upload/download | Presign after metadata validation; HEAD verification; MIME sniff; type/size caps; scanner `[TBD-INFRA]`; downloads return a signed URL, never an object key; `Cache-Control: no-store` on all API and SSE responses |
| Rate limiting | In-process token buckets per session/user; durable PostgreSQL counters for expensive commands so a restart does not reset a paid allowance; `429` + `Retry-After` [TECH §6.5] |
| Secrets | Platform secret store in staging/prod; root `.env` locally; `.env.example` placeholders only; no secret in the repo, image, client bundle, or logs [TECH §14] |
| Content-free enforcement | Event payload Pydantic schemas reject unknown keys in dev/test; the writer validates against a per-type allowlist and drops+alerts in prod; log processors redact known content fields; audit tests assert zero content keys [PRD NFR-PRIV-3] |
| Audit | `audit_event` from M1 for project view, artifact download, and break-glass support access; hashed IP; no content [ARCH §12] |

---

## 15. Configuration, feature flags, migrations, commands

### 15.1 Configuration keys

Values are versioned rows in `config_version`; secrets are environment only. Names below are the implementation keys; defaults marked `[TBD-*]` MUST be set before pilot.

| Key | Purpose | Default / owner |
| --- | --- | --- |
| `material.max_count` | Material cap per project | `[TBD-UX]` (PRD-10, BR-7) |
| `page.max_count`, `sources.cap` | Deck/source caps | `[TBD-BIZ]` (NFR-SCALE-2, PRD-10) |
| `PAGE_HISTORY_MAX_DEPTH` | Undo depth | 20 placeholder `[TBD-BIZ]` (AQ-5) |
| `idempotency.retention_s` | Key retention | `[TBD-BE]` (API-Q4, AQ-11) |
| `event.retention` | `domain_event` retention/resync threshold | `[TBD-INFRA]` (AQ-3) |
| `export.*` | Retention, signed-URL lifetime, subprocess time/memory | `[TBD-BIZ]` / `[TBD-INFRA]` (DM-Q5, TS-Q15) |
| `job.*` | Max attempts, lease, heartbeat | 3 / 60 s / 20 s `[TBD-BE]` (PRD-11) |
| `runtime.*` | Reconcile interval, shutdown grace | 30 s / 30 s |
| `sse.*`, `advance_token.ttl_s` | Heartbeat, queue bound, countdown token | 15 s / 256 / 30 s |
| `fingerprint.version`, `prompt.*`, `generation_profile` | Fingerprint algorithm and prompt/profile versions | 1; TECH §10 |

### 15.2 Feature flags and kill switches

`capability.model`, `capability.search`, `capability.export`, and per-stage switches are configuration with an audit trail, no deploy required [PRD NFR-MAINT-5]. Disabling a capability makes dependent commands return `503 error.provider.unavailable` and creates no job; it MUST NOT fabricate success, delete committed artifacts, or silently switch to mock content. Flags are read per request from a version-keyed in-process cache refreshed on write.

### 15.3 Migrations

Alembic is the only schema mechanism; migrations are forward-only, expand/contract, idempotent, and resumable [DATA §11]. `alembic upgrade head` runs as a release step with an advisory lock; the app never auto-migrates. `alembic check` and a migration test block merge. Partial indexes, checks, and deferred FKs live in a hand-written migration (DATA Appendix B). Projections (`project_stage_state`, page status, `project_snapshot_cache`, `render_cache`) may be dropped and rebuilt; authoritative rows may not.

### 15.4 Local and CI commands

```bash
docker compose up -d                                  # PostgreSQL + MinIO
cd backend && uv sync && uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
uv run python -m app.cli.create_user --email … && uv run python -m app.cli.reconcile && uv run python -m app.cli.rebuild_projections
uv run python -m app.cli.export_openapi && uv run python -m app.cli.export_schemas
uv run ruff check && uv run ruff format --check && uv run mypy app && uv run pytest
```

CI order: `uv sync --frozen` → `alembic upgrade head` + `alembic check` → Ruff/mypy → pytest unit/integration (Testcontainers PostgreSQL + MinIO) → OpenAPI/JSON Schema diff → frontend typecheck/lint/tests/build → Docker build → Playwright smoke → export smoke → staging deploy → manual approval → production [TECH §16.2].

---

## 16. Testing strategy and quality gates

| Layer | Scope | Gate |
| --- | --- | --- |
| Unit | Domain gates, stale matrix, fingerprint/JCS golden vectors (nulls, floats, unicode, key order), page identity, advance token, history rules, error mapping | Blocks merge |
| Integration | Repositories, transactions, artifact commit/undo, idempotency replay, one-writer admission, job claim/lease/fencing, reconciliation, authz, migration | Testcontainers PostgreSQL + MinIO; blocks merge |
| Contract | Pydantic → OpenAPI; event/artifact JSON Schema; committed generated TypeScript diff; unknown-field tolerance | CI diff fails the build [API §9] |
| Async failure and SSE | Worker kill mid-attempt, lease expiry requeue, late commit fenced, duplicate delivery, cancel during provider call, queue-full wake loss; snapshot-first replay, `resync` on expired cursor, heartbeat, slow-subscriber disconnect, reconnect after restart | Blocks merge |
| Export smoke | One PPTX reopened with `python-pptx`, one PDF page count/aspect, one HTML external-URL scan, zero-byte rejection | Release gate |
| Load and manual | HTTP/SSE at pilot scale, runner concurrency, event-loop lag; PowerPoint fidelity matrix, screen-reader and keyboard audit | Before pilot / release gate [PRD FR-6.18, NFR-ACC] |

Requirement coverage is explicit; a P0 requirement without a mapped automated test cannot be marked done.

| Requirement | Test |
| --- | --- |
| FR-3.12, FR-7.3, NFR-COST-3, NFR-COST-4 | Seven-row stale matrix golden test; R1/R2 schedule 0 model jobs and R3/R4 do not fan out; fingerprint reuse installs a pointer with zero jobs and no new `artifact_version` |
| FR-7.4, FR-6.9, NFR-REL-3 | Two concurrent page commands: exactly one job/history entry; the second returns `error.gate.page_write_in_progress` or the active job; retries never duplicate charge or history |
| FR-7.5, NFR-REL-4, FR-7.9 | Kill the process mid-generation; restart; job resumes; snapshot + cursor restores stage, stale markers, history, pointers with no duplicate or gap |
| FR-6.14, FR-6.16, NFR-COMPAT-5 | Export validation failure table test; success only with a non-zero package and checksum |
| FR-2.4, FR-2.13/2.14, FR-3.14 | Answer overwrite and profile-dirty/unconfirm tests |
| NFR-PRIV-3, NFR-SEC-1 | Event/log schema allowlist and Sentry scrub tests; cross-tenant project/artifact/download authz and signed-URL scoping |
| NFR-MAINT-1, API §9 | `alembic upgrade head` on a populated database; OpenAPI + JSON Schema + generated TypeScript diff test |

---

## 17. Risks and trade-offs

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Single-process availability | A deploy/restart pauses all jobs; no rolling multi-instance deploy | Graceful drain, low-activity deploys, readiness gating, startup reconciliation, documented M2 shared-queue upgrade [TECH §19.2] |
| In-memory dispatch loss | `QUEUED` work waits until the sweep | Durable `job` rows, startup + 30 s reconciler, idempotent wake, fencing on commit |
| Event-loop blocking | Slow API/SSE and request timeouts | Parsing/metrics in thread/process pools, `boto3` via `to_thread`, export in a subprocess, event-loop lag alert |
| Projection drift | Wrong gate or status | Projection computed from authoritative rows, rebuilt on schedule; audit logs and repairs divergence [DATA B.2] |
| Provider rate limits/timeouts | Page errors, slow first design | Bounded concurrency, stage tiers, jittered retries, per-stage kill switch, page-scoped retry |
| Chromium/`python-pptx` memory | Export OOM | Dedicated subprocess, concurrency 1, memory/time caps, parent-side verification |
| Fingerprint canonicalization edge cases | False stale or false reuse | JCS + golden vectors for floats/nulls/unicode; `fingerprint_version` in the input; conservative fail-closed on mismatch |
| Contract gaps (C-1…C-8) | Client/backend mismatch | No invented enums/keys; gaps are blocking decisions before the affected endpoint is implemented |
| Event/log content leakage | Privacy breach | Schema allowlists, redaction processors, Sentry scrubbing, audit tests |
| Restart/deletion partial failure | Content resurrection or stale access | Epoch/fencing, `DELETING` visibility, sweeper verification, no late job can install a pointer |

---

## 18. Open questions

### 18.1 Source-document gaps and conflicts

| ID | Gap / conflict | Impact | Resolution boundary |
| --- | --- | --- | --- |
| **C-1** | Search job type absent from `JobType` | Returned `searchJobIds` had no valid `JobDTO.type` | **Resolved:** `SEARCH` is an additive `JobType` value in API §3.1, data model §6.6, and the task registry; migration adds the enum value. |
| **C-2** | DATA Appendix A.3 defined `PageType` as `COVER/TOC/SECTION/CONTENT/SUMMARY`; DATA §6.4 and API §3.1 define `COVER/TOC/BODY/END` | A migration would bake the wrong labels | **Resolved:** Appendix A corrected to `COVER/TOC/BODY/END`; catalog + API win. |
| **C-3** Catalog completeness | Four keys used by endpoints were absent from API §7 | Client message catalog could not resolve them | **Resolved:** API §7 adds `error.validation.gap_selection_invalid`, `unknown_section`, `upload_missing`, and `error.gate.digest_incomplete` (plus later `unknown_style`, `plan_incomplete`, `consent_required`, `notice_version_unknown`, `not_found.asset`). |
| **C-4** | Stale `error.gate.research_finished` reference | Two keys for one gate | **Resolved:** `error.gate.material_locked` is canonical; the stale reference is removed. |
| **C-5** | `StaleSummaryDTO.cause` had no undo value | Cause vocabulary incomplete | **Resolved:** `UNDO` added to the cause enum; plan undo uses it. |
| **C-6** | Missing keys for generic body-schema failure, `profile_missing`, and plan-incomplete | Two gates could not name a key | **Partially resolved:** `error.gate.plan_incomplete` is catalogued; a missing profile is expressed as `error.gate.profile_dirty` with `details.reason="profile_missing"` (no separate key); generic body-schema failure stays an internal validation detail, never a user-facing key. |
| **C-7** `[CONFLICT]` | DATA §7.3 lists `outlineChromeVersion` in the artifact fingerprint; a title edit would then require a model job, contradicting [ARCH AD-12] and `0 model jobs` for R1 | Stale semantics and cost | Chrome is a composition input only; generation fingerprints exclude it; `render_cache.chrome_version` records composition. Owner: architecture + data model, before implementation. |
| **C-8** | `history_pop` in DATA §7.2 vs `historyPopped` in API §6 | Event-name drift in prose | **Resolved:** DATA §7.2 now uses the wire name `historyPopped`. |

### 18.2 Inherited open questions (not resolved here)

| ID | Question | Owner / stage |
| --- | --- | --- |
| API-Q1 | Material mutation after research: restart-only (as specified in §4.3.1) vs re-search (FR-2.18) | Product + backend, before M1 |
| API-Q2 | Outline edits after confirmation: allow + reconfirm (as specified in §4.5.1) vs lock | Product + UX, before M1 |
| API-Q3 | Partial export policy and `excludedPageIds` on success | Product + UX, M1 |
| API-Q4 | Idempotency retention and client key format (AQ-11) | Backend, before pilot |
| API-Q5 | Event retention / full-resync threshold (AQ-3, TS-Q11) | Ops + architecture, before pilot |
| API-Q6 | Exact shared artifact body schema and layout-vocabulary versioning | Backend + design, before plan implementation |
| API-Q7 | Synchronous vs enqueued `POST /api/projects/{projectId}/research/profile` | Backend, before implementation |
| API-Q8 | Browser streaming/reconnect support | Frontend, before M1 |
| AQ-1, AQ-4 | Server-timed auto-advance; redo after undo | Architecture/UX + product, M1 hardening/post-M1 |
| AQ-2, DM-Q4, AQ-5, DM-Q1, TS-Q12 | Outline page matching; history depth vs retention | Backend/architecture/product+finance, before outline v2/pilot |
| AQ-8, AQ-12, AQ-13 | Export pool; material changes after research; restart erase policy | Architecture/ops + product + legal, M1/pilot |
| TS-Q1/Q2 | Model and search vendors, stage tiers | Founder + tech lead, before development |
| DM-Q3, DM-Q7 | Fingerprint edge cases; field-level encryption | Backend/security, implementation/M1 review |
| PRD-03, PRD-11, PRD-19 | Partial export, queue timeouts, OCR | Product/backend, M1 |

---

## 19. Traceability

| Backend module | Requirements | Architecture component |
| --- | --- | --- |
| `api`, `core/security`, `services/idempotency` | PRD FR-7.4/7.9, NFR-SEC-1/3, §11.6; API §2 | Edge/API |
| `api/v1/events`, `services/events`, `worker/runner` | PRD FR-3.1, FR-7.5/7.9, NFR-PERF-3, NFR-REL-4; API §4.12 | Stream gateway |
| `services/projects`, `domain/page_identity` | PRD FR-1.1, FR-8.1/8.2, FR-7.8/7.9, NFR-MAINT-1 | Project service |
| `services/orchestrator`, `domain/gates`, `domain/stale`, `domain/advance_token` | PRD FR-2.13/2.14, FR-3.10–3.12, FR-4.4/4.10, FR-5.5, FR-7.3–7.5, NFR-COST-3/4; PRD §8.9.1 | Workflow orchestrator |
| `services/artifacts`, `domain/fingerprints` | PRD FR-6.5, FR-6.21, FR-7.7, NFR-REL-2/3; API §3.7 | Artifact/version service |
| `services/styles`, `app/render` | PRD FR-5.1–5.6, FR-6.17; NFR-COMPAT-4/5 | Style/asset registry |
| `services/ingestion`, `ingest/*` | PRD FR-1.3–1.11, FR-2.2/2.5, NFR-REL-6 | Ingestion service |
| `services/research`, `ingest/search` | PRD FR-2.1–2.21, FR-2.10/2.20, NFR-COST-4 | Research + search |
| `services/generation`, `workflows/*`, `llm/*` | PRD FR-2.12, FR-3.1–3.3, FR-4.1–4.9, FR-6.2–6.9, FR-7.18; NFR-MAINT-2 | Generation + model gateway |
| `services/outline` | PRD FR-3.1–3.15, FR-3.14 | Project/outline core |
| `services/export`, `render/export_runner` | PRD FR-6.10–6.21, NFR-COMPAT-4/5, NFR-MAINT-3 | Render/export |
| `worker/*` | PRD FR-7.5/7.6/7.8, NFR-REL-3/4, NFR-SCALE-1; PRD-11 | Job scheduler + workers |
| `services/metering` | PRD §11.4, NFR-COST-1/2; ARCH §11 | Event/telemetry/ledger |
| `services/policy`, `core/config` | PRD FR-1.12, NFR-SEC-1/2, NFR-PRIV-1/2/4, NFR-MAINT-5; M2 quota | Policy/config |
| `core/logging`, `core/telemetry` | PRD NFR-PRIV-3, NFR-OBS-1/2/3 | Platform |
| `app/models`, `alembic`, `cli` | PRD FR-7.9, NFR-MAINT-1; DATA §11 | Persistence |
| `tests/*` | PRD §14.3; API §9; TECH §15 | All |

---

## 20. Change log

| Version | Date | Change |
| --- | --- | --- |
| v1.1 | 2026-11-19 | Reconciled with API contract v1.1: added the `SEARCH` job type and handler, config/notice/consent/asset endpoints, `error.gate.plan_incomplete`, `UNDO` stale cause, and resolved C-1…C-5/C-8 (C-6 partial, C-7 remains an architecture/data-model decision). |
| v1 | 2026-11-19 | Initial backend implementation design: runtime topology and single-process invariants, module/dependency rules, request pipeline and idempotency protocol, stage/gate/stale/fingerprint/undo/advance semantics, thirteen service designs, persistence and artifact commit protocol, in-process job system, model gateway, ingestion/research, export subprocess, error mapping, observability/security, configuration, tests, risks, contract gaps C-1…C-8, and traceability. No implementation claimed. |
