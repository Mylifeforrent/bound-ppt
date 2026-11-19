# Bound PPT · System Architecture (v1.1)

> Version: v1.1 · 2026-11-19 · Status: Draft · Owner: Architecture
> Requirements source: `docs/ppt-agent-prd.md` (PRD v1). Implementation companions: `docs/ppt-agent-tech-stack.md` (React + Python implementation, vendors, protocols, deployment products, release tooling) and `docs/ppt-agent-data-model.md` (physical schema, indexes, retention).
> This document is deliberately stack-free: no language, framework, library, database, queue, cache, cloud, identity, billing, observability, model, search, parser, or rendering product is selected. All such choices are recorded in §15.2 and resolved by the implementation companions. No requirement is claimed implemented; the prototype is a simulation [PRD Appendix A].

---

## 1. Document control

| Field | Value |
| --- | --- |
| Document / version / date | Bound PPT System Architecture / v1 / 2026-11-18 |
| Status / owner / audience | Draft / Architecture / engineering, product, QA, security, legal review points |
| Requirements source | PRD v1, which owns behavior, gates, and acceptance [PRD §1.3] |
| Implementation companions / out of scope | `docs/ppt-agent-tech-stack.md`: stack, vendor, protocol, deployment product, release tooling, CI/CD, secrets. `docs/ppt-agent-data-model.md`: physical schema, indexes, retention. |
| Supersedes / review cadence | None / at M1, M2, and M3 gates |

**Precedence.** PRD wins every behavior or acceptance conflict; FLOW wins user-experience behavior subject to PRD; BM wins business scope and milestone gating; SRC wins stages 1–2 content mechanics; UX is evidence only; EXTRACT is background only [PRD §1.3]. This document owns component boundaries, state ownership, consistency, logical contracts, and failure/cost/security topology. If this document and the PRD disagree, the PRD wins and the disagreement is logged in §18.

| Tag | Meaning |
| --- | --- |
| `[PRD FR-x.y]`, `[PRD NFR-xxx-n]`, `[PRD §x]` | PRD requirement ID or section, including normative matrices §8.9.1–§8.9.4. Within a bracket, the PRD prefix applies to every FR/NFR ID in that bracket. |
| `[FLOW §x]`, `[BM §x]`, `[SRC §x]`, `[UX §x]` | Source document section |
| `[ASSUMPTION]` | Architectural premise not verified by a source |
| `[TBD-TECH]` | Choice reserved for the tech implementation document |
| `AD-n`, `DD-n`, `AQ-n` | Architecture decision, deferred decision, open architecture question |

**Glossary.** **Component:** independently owned unit with one authoritative responsibility and an explicit "does not own" boundary. **Artifact:** durable product output (digest, profile, outline, plan page, design page, export). **Artifact version:** immutable generation record with content digest, input fingerprint, lineage, producer, and time. **Lineage:** directed upstream→downstream version refs used to derive stale scope. **Input fingerprint:** canonical digest over all semantic inputs (upstream versions, semantic parameters, style token version, generation profile version); digest algorithm is `[TBD-TECH]`. **Projection:** derived, rebuildable view (stage flags, page status, progress); never sole truth. **Job:** durable async work unit with type, inputs, state, attempts, deadline, cancellation. **Lease:** time-bounded worker claim with a fencing token. **Snapshot:** consistent project read at a known sequence. **Stream cursor:** per-project monotonic resume position. **Gate:** server-enforced prerequisite for a stage transition. **Stale:** artifact whose expected fingerprint differs from its recorded fingerprint. **Generation epoch:** project counter incremented by restart; older-epoch results are discarded. **Usage record:** append-only metering entry (§11). **Tenant:** isolation boundary above a project (pilot account M1, account M2, organization M3).

---

## 2. Architecture summary

Bound PPT is a stateless experience tier over a **server-authoritative project and workflow core**. Stage, gates, page status, stale markers, history pointers, and job state are server state; the browser holds a projection plus ephemeral view state. Long-running work runs as durable, leased jobs that survive navigation, refresh, and network loss. Output is stored as **immutable versioned artifacts with lineage and an input fingerprint**; "current" is a separate pointer and staleness is derived by comparing expected with recorded fingerprints. Model, search, parsing, and export capabilities sit behind adapters so providers are replaceable and metered. Export is isolated and validation is mandatory before any success claim. An append-only usage ledger makes cost and quota observable per project, stage, page, job, and (M2) account.

```
┌────────────────────────────────────────────────────────────┐
│ Experience: web client · edge/API · stream gateway         │
└───────────────────────────┬────────────────────────────────┘
┌───────────────────────────▼────────────────────────────────┐
│ Core: project · orchestrator · artifact/version · style    │
└───────────────┬──────────────────────────────┬─────────────┘
┌───────────────▼──────────────┐  ┌────────────▼─────────────┐
│ Scheduler + workers          │  │ Metadata/artifact store  │
│ ingestion/research/gen/export│  │ queue/cache/event/ledger │
└───────────────┬──────────────┘  └──────────────────────────┘
┌───────────────▼────────────────────────────────────────────┐
│ External: model · search · parse/OCR · URL · billing (M2)  │
└────────────────────────────────────────────────────────────┘
```

| Load-bearing decision | Why |
| --- | --- |
| **AD-1 Server-authoritative workflow** | Gates, stale markers, page status, and history cannot be trusted to a client that refreshes or disconnects; server truth is required by FR-7.9 and NFR-REL-4. |
| **AD-2 Durable resumable jobs** | Paid value depends on decks finishing after navigation, real cancellation, and reconnect without duplication [PRD FR-7.5; NFR-REL-3/4]. Durability is carried by the authoritative job record and its commit protocol; the dispatch transport may be in-process at pilot scale (tech-stack §9). |
| **AD-3 Immutable artifacts + lineage** | Undo, previous version, export snapshots, and cost attribution must address a specific generation, not a mutable "current page" [PRD FR-6.5, FR-6.21, FR-7.7]. |
| **AD-4 Derived staleness** | Staleness must survive restart and answer "which pages"; hand-maintained booleans cannot keep cascade factor near 1.0 [PRD NFR-COST-3]. |
| **AD-5 Per-page jobs** | Page failure isolation, inspect-while-generating, single-page rerun, and page history all fail with one deck-level job [PRD FR-4.9, FR-6.2, FR-6.4]. |
| **AD-6 Adapters + metering** | Model/search/parse portability and stage-level cost telemetry are prerequisites for pricing and vendor negotiation [PRD NFR-MAINT-2, NFR-COST-1]. |

Supporting: AD-7 isolated export, AD-8 append-only ledger, AD-9 client countdown/server-validated advance, AD-10 snapshot+cursor, AD-11 stable page identity, AD-12 body/chrome split, AD-13 content/metadata separation, AD-14 nullable tenant scoping (§15.1). Structural decisions only: stack, protocol, vendor, and physical schema are out of scope.

---

## 3. Architectural drivers

| Driver | Requirements | Design consequence |
| --- | --- | --- |
| Full six-stage flow, two modes | [PRD §7.1–§7.6; FR-1.13, FR-7.17] | One stage machine and artifact graph serve both modes; mode changes only advance mechanics. |
| Material-first ingestion, per-material isolation | [PRD FR-1.8–1.11, FR-2.2; NFR-REL-6] | One ingestion job/status per material; partial success is normal. |
| Sequential interview, gaps, profile gate | [PRD FR-2.3–2.14, FR-2.21; SRC §5] | Answers versioned by question identity; gap decisions recorded; `profileDirty` is an orchestrator guard. |
| Cheap outline/plan edits, exact stale matrix | [PRD FR-3.4–3.12, FR-7.3; PRD §8.9.1] | Stable page identity, immutable outline versions, derived staleness, body/chrome split. |
| Page-level generate/regenerate/tweak/undo | [PRD FR-6.2–6.9, FR-7.4, FR-7.7] | Page-scoped jobs, one writer per page, per-page current pointer/history, no fake variants. |
| Background tasks, cancel, reconnect | [PRD FR-7.5; NFR-REL-3/4] | Durable queue, leases with fencing, idempotency keys, snapshot+cursor, jobs independent of connection. |
| Real export + validation before success | [PRD FR-6.12–6.18, FR-6.20/6.21] | Isolated pipeline, frozen deck snapshot, validation first-class, artifact existence as sole success criterion. |
| Server-side cost telemetry | [PRD NFR-COST-1/2; PRD §11.4] | Append-only ledger, metering at adapter boundaries, attribution to attempt, invoice reconciliation. |
| No content in analytics/logs | [PRD NFR-PRIV-3; PRD §11.5] | Content only in artifact store; events/logs carry IDs, counts, buckets, domains. |
| Persistence and schema versioning | [PRD FR-7.9; NFR-MAINT-1] | Durable project records, command-granular autosave, event log, versioned schema, lazy migration. |
| Accessibility as a client contract | [PRD NFR-ACC-1–6; PRD §8.9.3] | Server exposes status text, stage state, progress, error reasons; client owns roles/focus/live regions/motion. |
| M2/M3 evolution | [PRD §6.1; BM §11.3] | Nullable tenant scoping, policy boundary, scoped style registry, connector adapter boundary, audit-shaped events. |

**Quality attributes, in priority order.** 1) **Reliability/resumability:** 5–10 design partners completing deadline-bound decks; a lost deck or duplicate charge is worse than slower generation [BM §0, §11.3; PRD §14.2 #8]. 2) **Cost predictability:** unit economics are unknown until telemetry exists; unbounded rerun makes the pilot unpriceable [BM §5, §7; NFR-COST]. 3) **Latency:** time to first design page is a guardrail, but a slower correct deck beats a fast broken one [PRD NFR-PERF-1/3]. 4) **Scalability:** pilot concurrency is small; scale horizontally without redesign, avoid premature multi-region [PRD NFR-SCALE-1]. 5) **Simplicity:** fewer moving parts, but never by returning authoritative state to the client. Explicit non-drivers: real-time co-editing, marketplace, multi-locale UI, native apps, global history [PRD §4.4].

---

## 4. System context and boundaries

| Actor | Stage | Interaction |
| --- | --- | --- |
| Deck maker | M1+ | Creates projects, supplies material, answers, edits outline/plan, selects style, regenerates, exports. |
| Account owner/buyer | M2 | Subscription, quota, payment; may not author decks [BM §2.4]. |
| Team admin | M3 | Seats, shared styles/libraries, retention, connectors, audit [BM §6.2, BM-9]. |
| Support/ops | M1+ | Uses pseudonymous IDs, ledger, audit; content access only by approved break-glass [PRD NFR-PRIV-3]. |

| External system | Capability | Degradation |
| --- | --- | --- |
| Model provider(s) | Digest, gaps, profile, outline, plan, design, tweak | Page/job error with retry; never silent success [PRD §13]. |
| Search service | Gap filling, web-only path | Material-only with recorded skipped supplement, or zero-results contract [PRD FR-2.10/2.20]. |
| Parsing/OCR; URL fetch targets | File and URL ingestion | One material not digested, or fetch failure + paste-body suggestion; others continue [PRD FR-1.9/1.10]. |
| Artifact storage substrate | Durable content | Brokered by artifact service; visible failure, no data loss [PRD §13]. |
| Identity/payment | M2 accounts, billing | Not used in M1; manual pilot onboarding `[ASSUMPTION]` [BM §11.3, PRD-01]. |
| Connectors | M3 organizational knowledge | Not in M1; adapter boundary only [SRC §4.3]. |
| Font/image licensors | Export assets | Substitution reported or export blocked [PRD FR-6.17]. |

| Trust boundary | Rule |
| --- | --- |
| Client ↔ edge | Client untrusted; never supplies authoritative stage/status/stale/history; every command re-validated. |
| Server ↔ providers | Minimum necessary context leaves the boundary; provider data-use is contractual + configuration evidence [PRD NFR-PRIV-2]. |
| Tenant | Every record tenant-scoped; artifact references authorized before issuance. |
| Export artifact | Leaves the platform with deck content and license/substitution report only. |
| Ops/admin | Pseudonymous IDs; content access exceptional, logged, time-bounded. |

```
deck maker ─┐
buyer ──────┼─▶ web client ──untrusted──▶ edge/API + stream gateway
admin ──────┘                                      │
support/ops ───────────────────────────────────────┤
                          ┌────────────┬───────────┴────────┐
                          ▼            ▼                    ▼
                    project/workflow  artifact store   event/usage log
                          │
                          ▼ egress (minimum necessary context)
                    model · search · parsing/OCR · URL · billing (M2)
```

Inside the boundary: experience tier, workflow core, content pipeline, job orchestration, artifact metadata/content, style registry, export pipeline, telemetry/ledger, policy boundary. External: provider capabilities, user device, payment rails, M3 organizational systems. Artifact storage is an external substrate but never a public boundary: all access is brokered by the artifact service.

---

## 5. Logical architecture

```
┌─────────── Experience tier ────────────┐
│ web client · edge/API · stream gateway │
└──────────────────┬─────────────────────┘
┌──────────────────▼─ Core ──────────────────────────────────┐
│ project · orchestrator · artifact/version · style registry │
└──────────┬─────────────────────────────────┬───────────────┘
┌──────────▼─ Content pipeline ──────────────▼───────────────┐
│ ingestion · research · generation · model gateway · search │
└──────────┬─────────────────────────────────────────────────┘
┌──────────▼─ Delivery pipeline ─────────────────────────────┐
│ export: validation → composition → packaging → artifact    │
└──────────┬─────────────────────────────────────────────────┘
┌──────────▼─ Platform ──────────────────────────────────────┐
│ scheduler/workers · telemetry · policy/identity/billing    │
└────────────────────────────────────────────────────────────┘
```

### 5.1 Experience tier

| Component | Responsibility | Owns | Does not own | Interfaces | Refs |
| --- | --- | --- | --- | --- | --- |
| **Web client** | Six-stage UI, local view state, streaming consumer, optimistic updates with reconciliation, countdown, keyboard/screen-reader/responsive behavior | Selected page, open modal, draft text, local pin, countdown | Stage truth, stale truth, job state, page status, history, authorization | Commands/queries, resumable subscription, authorized artifact content refs | [PRD FR-1.1–1.14, FR-3.1–3.11, FR-5.1–5.3, FR-6.1–6.11, FR-7.1–7.17, §8.9.3/4; NFR-ACC-1–6] |
| **Edge/API layer** | Session, request validation, authz (M2+), rate limiting, routing, idempotency enforcement, correlation | Admission decisions, idempotency ledger, rate counters | Project state, job execution, cost computation, provider calls | Command/query admission, authz check, idempotency lookup | [PRD NFR-SEC-1/3, §11.6] |
| **Stream gateway** | Resumable event delivery, cursors, snapshot handoff, heartbeat, gap detection | Per-project ordered buffer and cursor positions (durable source is the event log) | Domain state, artifact content, job transitions | Subscribe(cursor), snapshot-at-sequence, replay, resync | [PRD FR-3.1, FR-7.5, FR-7.9; NFR-PERF-3, NFR-REL-4] |

Boundary rules: the client **must never** own stale truth or job state; the edge **must never** decide business gates, only shape/identity/rate/idempotency.

### 5.2 Project and workflow core

| Component | Responsibility | Owns | Does not own | Interfaces | Refs |
| --- | --- | --- | --- | --- | --- |
| **Project service** | Lifecycle, topic, mode, current stage, per-stage status projection, outline structure, page identity registry, profile/style selection pointers, project version, epoch | Project record, stage state, page identity registry, project-level current pointers (profile/outline/style), version | Artifact content, plan/design pointers, jobs, ledger, provider calls | create/update/delete/restart, projectSnapshot, stageState, advance validation input | [PRD FR-8.1/8.2, FR-7.8/7.9, FR-1.13; NFR-MAINT-1] |
| **Workflow orchestrator** | Gates, transitions, stale derivation, affected-scope computation, job planning, auto-advance validation, profileDirty enforcement | Transition decisions, affected-artifact sets, job plans | Job execution, model calls, artifact bytes, client timing | plan jobs, validate gate, reconcile stale, staleChanged, confirm/advance guards | [PRD FR-2.13/2.14, FR-3.10–3.12, FR-4.4/4.10, FR-5.5, FR-7.3–7.5; §8.9.1] |
| **Artifact/version service** | Immutable records, artifact current pointers (plan/design), per-page history, lineage, retention, content addressing, commit protocol | Artifact metadata, version chain, artifact pointer map, history stacks | Generation logic, stage, style definitions, packaging | commit version, install/read pointer, history push/pop, lineage query, delete/retain | [PRD FR-6.5, FR-6.21, FR-7.7; NFR-REL-2] |
| **Style/asset registry** | Style definitions/tokens, previews, licensed asset catalog, style versions | Style IDs, token versions, previews, license records | Page generation, selection, export assembly | list/resolve styles and assets, license check | [PRD FR-5.1–5.6, FR-6.17; BM-11] |

Boundary rules: the orchestrator decides **whether** work is needed, never **how** content is generated; only the artifact service writes pointers/metadata; the registry never applies styles.

### 5.3 Content pipeline

| Component | Responsibility | Owns | Does not own | Interfaces | Refs |
| --- | --- | --- | --- | --- | --- |
| **Ingestion service** | Material registry, paste/file/URL adapters, normalization, per-material status, type/size/cap validation | Material records, ingestion status, normalized content ref | Research, outline, stage, provider selection | add/remove material, ingestion job, materialStatusChanged, digest request | [PRD FR-1.3–1.11, FR-2.2; SRC §4.2] |
| **Research service** | Digest orchestration, sufficiency, gaps, targeted search orchestration, profile synthesis, re-search | Digests, gap suggestions/decisions, profile versions, source selection | Search mechanics, model routing, stage, outline | startResearch, answer/updateAnswer, decideGaps, updateProfile, digestReady/gapSuggested/profileReady | [PRD FR-2.1–2.21; SRC §2.3, §5] |
| **Generation service** | Outline/plan/design/tweak handlers, prompt registry, structured output validation, repair/retry, candidate production | Candidate artifacts and validation verdicts | Project state, pointers, style definitions, scheduling | generate/validate stage output, return candidate | [PRD FR-2.12, FR-3.1–3.3, FR-4.1–4.9, FR-6.2–6.9, FR-7.18] |
| **Model gateway** | Provider abstraction, stage/model routing, token/latency/cost capture, timeouts, retries, safety, failover policy | Provider call records, usage measurements, routing decisions | Prompt ownership, gates, artifact commit, billing | invoke(stage, tier, payload contract), usage record, timeout/retry policy | [PRD FR-7.18, NFR-MAINT-2, NFR-COST-1] |
| **Search adapter** | Query execution, result normalization, caps, zero-result/failure semantics | Normalized results and search call records | Gap judgment, source selection, profile synthesis | search(query, cap) → results or zero/failure outcome | [PRD FR-2.8–2.10, FR-2.19/2.20; SRC §4.2] |

Boundary rules: generation **must never** mutate project state; the gateway **must never** decide gates; the search adapter **must never** invent results.

**Grounding and source precedence.** The research service assembles the outline context in precedence order — first-party materials, organizational assets when available, then web supplements — and passes source identities, not just prose. Generation treats all material and web text as untrusted data, never as instructions. Every outline, plan, and design artifact records the source refs it used (IDs only); a missing or unknown ref fails structured validation, and reviewers can trace a claim from artifact to source [PRD FR-2.16/2.17, §9.4/§9.5]. Source priority is a content-policy rule enforced in the context contract, not a model preference.

### 5.4 Delivery pipeline

| Component | Responsibility | Owns | Does not own | Interfaces | Refs |
| --- | --- | --- | --- | --- | --- |
| **Render/export service** | Deterministic composition on the fixed 16:9 (1280×720 reference) canvas, pre-export validation, font/asset resolution and substitution, PPTX/HTML/PDF assembly, packaged artifact/checksum, format retry | Export job state, validation report, package, substitution report | Project state, design content, style definitions, queue policy | exportDeck, validate, compose, assemble, exportProgress/Done/Failed | [PRD FR-6.10–6.21; NFR-COMPAT-4/5, NFR-MAINT-3] |

Boundary rule: export **must never** mutate project state, style selection, or page artifacts. Validation is a required step; failure blocks the success claim [PRD FR-6.14/6.16].

### 5.5 Platform

| Component | Responsibility | Owns | Does not own | Interfaces | Refs |
| --- | --- | --- | --- | --- | --- |
| **Job scheduler + worker pool** | Queueing, fairness, leases, attempts, retries/backoff, cancellation, background continuation, page concurrency, timeouts | Job state, attempts, leases, retry counters, cancel flags | Business rules, artifact content, provider routing | enqueue, lease, heartbeat, complete/fail, cancel, retry, jobStatus, job events | [PRD FR-7.5; NFR-REL-3/4; NFR-SCALE-1] |
| **Event/telemetry service** | Domain event log, usage records, cost ledger, guardrail metrics, audit, correlation IDs | Event sequence, usage/cost records, metrics projections | Project truth, artifact content, identity truth | emit event, append usage, query metrics, replay, audit query | [PRD §11.1–11.6; NFR-COST-1/2, NFR-OBS-1/2/3] |
| **Policy/identity/billing boundary** | Identity (pilot provisioning, M2 accounts, M3 roles), authz, entitlements, quotas, consent/notice | Tenant/account mapping, entitlements, quota counters, consent versions | Project content, generation, artifact access outside issued refs | authenticate, authorize, entitlement, quota reserve/commit, consent | [PRD FR-1.12; NFR-SEC-1, NFR-PRIV-1/2/4; BM §6.2] |
| **Configuration/feature flags** | Stage/model/search/export switches, caps, question catalog, vocabulary versions, rollouts | Versioned config and flag state | Business state, ledger, project data | read config, evaluate flag, versioned change record | [PRD FR-1.7, FR-2.9/2.19, FR-5.4; NFR-MAINT-5, NFR-SCALE-2] |

Boundary rules: the scheduler owns **when/how often**, never **whether**; policy owns entitlements, never content; telemetry is not a second project truth; disabling a capability must not fabricate success or delete committed artifacts.

**Deployment note (M1).** The scheduler and worker pool run inside the single application process, and export runs in an isolated subprocess; the transport is an implementation concern resolved in tech-stack §9. This does not change ownership: job state, attempts, leases, and cancellation remain scheduler-owned records, and a restart replays non-terminal work from those records rather than from memory.

**Offline quality harness (supporting capability).** A versioned evaluation set of topics, materials, expected structures, and grounding samples runs outside the request path before model, prompt, layout-vocabulary, or style changes. It produces release evidence and regression comparisons; it never writes project artifacts or user-visible state [BM §1.3; PRD CR-5]. The harness is intentionally not a runtime dependency of the six-stage flow.

---

## 6. Runtime flows

Each flow names the owning component per step and its failure path; happy paths alone are not contracts [PRD FR-7.6].

**6.1 Project start and material intake.** 1. **Web client** validates a non-empty topic; **edge** admits and **project service** creates the project (`stage=intake`, epoch 1, version 1) [PRD FR-1.1, FR-8.1]. 2. **Ingestion service** validates each material's type/size/page/cap and rejects with a specific reason and no success chip [PRD FR-1.4–1.8]. 3. **Scheduler** runs one ingestion job per material; parse/fetch adapters extract normalized text; the **artifact service** commits a digest candidate; `materialStatusChanged` reports per material [PRD FR-1.9/1.10, FR-2.2]. 4. **Artifact service** exposes content only through an authorized reference; **telemetry** emits `sourceAdded` metadata (title/summary/origin), never content [PRD FR-1.11, FR-2.15; NFR-PRIV-3]. 5. `removeMaterial` retires the material, cancels ingestion, and marks dependent profile/outline stale if research started [PRD FR-1.6; AQ-12]. 6. `startResearch` guards the topic and enters Research + interview [PRD FR-1.2]. **Failure:** a bad file/URL fails only that material with removal/replacement or paste-body fallback; other materials and the project continue [PRD FR-1.9/1.10, NFR-REL-6]. Cap violations are explicit; retries are idempotent.

**6.2 Research and interview.** 1. **Research service** materializes four single-choice questions one at a time; `answerQuestion`/`updateAnswer` write one answer per question identity, never incrementing a count [PRD FR-2.3/2.4]. 2. Digestion runs in parallel with questions; gap suggestions wait for all selected digests [PRD FR-2.5; UX 2.5]. 3. **Research service** judges sufficiency using a structured candidate from the **generation service**, and records three gaps with reasons/recommendations; `gapSuggested` fires [PRD FR-2.6, FR-2.11; SRC §2.3]. 4. `decideGaps` records selection or "not needed" (which clears others and skips web) [PRD FR-2.7, FR-2.21]. 5. **Search adapter** runs one targeted query per gap within caps; results become sources; zero results are an explicit recorded outcome, never a silent skip [PRD FR-2.8–2.10, FR-2.19/2.20]. 6. No-material path runs the configured default web plan [PRD FR-2.9]. 7. With four answers (and, when materials exist, a gap decision), the **generation service** produces a structured profile candidate; the **research service** validates and commits v1 and emits `profileReady` [PRD FR-2.12]. 8. An answer edit after profile sets `profileDirty`; `updateProfile` creates a new version, clears dirty, and unconfirms any outline [PRD FR-2.13/2.14]. 9. Re-search (P1) reuses digests, reruns changed gap queries, and produces a new profile version [PRD FR-2.18]. **Failure:** search outage degrades to material-only with a recorded skipped scope or the zero-results contract; profile synthesis is blocked, not guessed, on missing inputs; dirty is an orchestrator gate, not a client flag.

**6.3 Outline generation, editing, confirmation.** 1. `generateOutline` requires a current clean profile; **orchestrator** enqueues one job [PRD FR-2.13, FR-3.1]. 2. **Generation service** streams schema-shaped outline deltas through the **stream gateway**; the client renders sticky notes incrementally; deltas are ephemeral, not the artifact [PRD FR-3.1; NFR-PERF-3]. 3. On completion, generation validates/repairs the full outline; **orchestrator** reconciles page identities; **artifact service** commits the outline version and ordered pages [PRD FR-3.2/3.3; AD-11]. 4. `outlineDone` fires; stage is `outline_unconfirmed`; counts and the >2-page deviation warning are server-derived [PRD FR-3.9]. 5. `editOutlinePage`, `movePage`, `insertPage`, `deletePage` carry the expected outline version and commit a new outline version; **orchestrator** derives stale artifacts (§8.4) [PRD FR-3.4–3.8, FR-3.12]. 6. `confirmOutline` requires a current outline and fully identified pages [PRD FR-3.10]. 7. In auto mode the client counts down and sends `advanceStage`; the orchestrator validates per §8.8 [PRD FR-3.11]. **Failure:** stream loss costs only partial deltas; the committed outline always reloads; conflicting edits return the authoritative version; invalid output becomes an error, never a confirmed outline.

**6.4 Plan generation.** 1. `generatePlan` requires a confirmed outline; **orchestrator** computes required pages and skips matching fingerprints [PRD FR-4.1/4.9; NFR-COST-4]. 2. **Scheduler** runs one job per page with bounded concurrency; page status `planning` [PRD FR-4.2/4.3; AD-5]. 3. **Generation service** returns a structured plan using the six layout combinations; validation checks vocabulary, cards, bounds; **artifact service** commits; `pageJobDone` [PRD FR-4.1]. 4. A failed page is `error`; others continue; `retryPage` reruns one page [PRD FR-4.8, NFR-REL-6]. 5. `replanPage`/`tweakPlanPage` enqueue one page job and a new plan version; that page's design is stale [PRD FR-4.5–4.7, FR-4.11]. 6. Completion gate: all done, none error; stage `plan_complete`; auto mode may request Style [PRD FR-4.4/4.10]. **Failure:** no stage success while any page lacks a current artifact; retries are idempotent and create no duplicate history or charge; pending pages show skeletons [PRD FR-4.3].

**6.5 Style selection and design generation.** 1. `selectStyle` records the style with the project version; no generation starts from selection alone [PRD FR-5.3]. 2. **Style registry** resolves tokens, preview, and license metadata [PRD FR-5.1, FR-6.17]. 3. `generateDesign` fans out one job per page; each reads the page's current plan version and the style token version [PRD FR-6.2; AD-5]. 4. **Artifact service** commits per page; progress derives from artifacts, not client timers [PRD FR-6.2, FR-7.16]. 5. Thumbnail selection/pinning is **client-only** and never changes scheduling [PRD FR-6.3]. 6. A style change marks all design stale; scope is recomputed on entry, not eagerly regenerated [PRD FR-5.5, FR-6.21]. **Failure:** a missing asset or invalid token fails per page with a reason while others continue; export stays blocked until design is complete; old-style in-flight results are recorded but not current for the new style.

**6.6 Single-page regenerate, tweak, undo.** 1. `regeneratePage` requires no active page write and more than one layout; a single-layout page returns a business-rule error plus the tweak suggestion, never a fake variant [PRD FR-6.6, FR-6.9, FR-7.4]. 2. **Edge** dedupes by idempotency key; a duplicate click returns the active job [PRD FR-6.9]. 3. On success, **artifact service** writes a new version, pushes the previous current onto page history, and moves the pointer; `historyPush`/`pageJobDone` fire [PRD FR-6.4/6.5]. 4. `tweakDesignPage` follows the same path; empty instruction is rejected before enqueue [PRD FR-6.7]. 5. `undoPage` pops history and installs it as current: no job, no model call, no new artifact [PRD FR-6.5, FR-7.7]. 6. A new regenerate after undo pushes the restored current and creates a new version; the undone version remains immutable but is unreachable by undo (no redo in M1) [AQ-4]. **Failure:** a failed regeneration leaves current/history unchanged; a late worker result is fenced if the head moved or the job was cancelled [PRD NFR-REL-3].

**6.7 Stale rerun and incremental scheduling.** 1. On entry to a stage, **orchestrator** recomputes expected fingerprints for every required artifact from current upstream pointers [PRD FR-7.3; AD-4]. 2. The stale set is the diff of expected vs recorded fingerprints, including missing artifacts and changed upstream refs [PRD FR-3.12, FR-7.3]. 3. It emits `staleChanged` if the projection flips and schedules only the stale set; a matching existing version is installed by pointer with zero jobs [PRD NFR-COST-3/4]. 4. Chrome-only changes create a deterministic composition version with no generative job [AD-12]. 5. The stage clears only when all affected artifacts are current; `stale_rerun` records cause, affected/rerun pages, and estimated/actual cost. **Failure:** a failed rerun leaves the stage stale and the page in error; retry is page-scoped; there is no silent full-deck rerun. If lineage is incomplete, the orchestrator uses the smallest safe superset, logs it, and alerts.

**6.8 Export.** 1. `exportDeck` creates an **ExportJob** with a frozen deck snapshot (ordered pages, current design versions, style, format, render completeness) [PRD FR-6.10, FR-6.19/6.21]. 2. **Export service** validates first: missing fonts, out-of-bounds assets, empty pages, incomplete renders, license policy [PRD FR-6.14, FR-6.17]. 3. Validation failure emits `exportFailed` with page/reason; no success, modal stays, Retry and Try another format [PRD FR-6.15, FR-6.20]. 4. On pass, workers compose body + chrome, assemble PPTX/HTML/PDF, and write a package with checksum/size [PRD FR-6.12/6.13]. 5. Success is emitted only when the artifact exists and a scoped, expiring download reference resolves [PRD FR-6.16]. 6. Re-export always takes a fresh snapshot; no stale file [PRD FR-6.21]. 7. Export never mutates project state; the artifact records the represented deck version. **Failure:** assembly failure is retryable/page-aware; validation failure requires repair or explicit partial scope with excluded pages named (PRD-03 `[TBD-UX]`); alternate format is offered; success without a real file is forbidden.

**6.9 Background continuation and reconnect.** 1. **Scheduler** owns execution; navigation, refresh, and network loss change nothing server-side [PRD FR-7.5; NFR-REL-4]. 2. On reconnect the client loads `projectSnapshot` at sequence `S`, then subscribes from cursor `C`; within the retained window it replays, otherwise it resyncs to a full snapshot [AD-10]. 3. Duplicate commands are deduped by idempotency key; the client renders the existing job [PRD NFR-REL-3]. 4. `cancelJob` marks cancellation; workers stop at the next checkpoint; a late result is discarded; cancelled never becomes success [PRD FR-7.5]. 5. Statuses and history are re-derived from jobs/artifacts, so refresh restores exact server state [PRD FR-7.9]. **Failure:** a stream gap forces resync, never silent divergence; a lost cancel is retried idempotently; background completion is never lost because the client was away.

**6.10 Restart and delete.** 1. `restartProject` requires confirmation; **project service** increments the epoch and **scheduler** cancels jobs [PRD FR-7.8]. 2. Workers see epoch/fencing mismatch and discard results; no old-epoch artifact can become current [AD-2]. 3. The project resets to intake; prior artifacts are tombstoned under retention (restart is not delete) [AQ-13]. 4. `deleteProject` marks `deleting`, cancels jobs, deletes/retires materials, digests, plans, designs, exports, and derived metadata, and records a tombstone [PRD FR-8.2; NFR-PRIV-1]. 5. A deletion sweeper verifies metadata, artifact store, and caches and retries partial failures; no late job can resurrect content. **Failure:** partial deletion is visibly `deleting` and retried; the project is inaccessible while deleting; ledger rows remain pseudonymous/content-free; both commands are idempotent.

---

## 7. Data architecture (conceptual)

```
Account (M2) 1 ── * Project
Project 1 ── * Material 1 ── 0..1 MaterialDigest
Project 1 ── * SourceItem
Project 1 ── * InterviewQuestion 1 ── 0..1 InterviewAnswer
Project 1 ── * GapSuggestion 1 ── 0..1 GapDecision
Project 1 ── 1..* RequirementsProfile   (versioned; current pointer)
Project 1 ── 1..* Outline 1 ── * OutlinePage
Project 1 ── 0..1 StyleSelection ── StyleDefinition
OutlinePage 1 ── * ArtifactVersion (plan | design)
ArtifactVersion 1 ── * PageHistoryEntry
Project 1 ── * Job 1 ── * JobAttempt 1 ── * UsageRecord
Project 1 ── * ExportJob 1 ── 0..1 ExportArtifact
Project 1 ── * DomainEvent · * PolicyRecord
ArtifactVersion * ── * ArtifactVersion (lineage edges, upstream → downstream)
UsageRecord * ── 1 Account (M2)
```

| Entity | Conceptual fields | Authoritative for / notes |
| --- | --- | --- |
| **Account** (M2) | id, plan, billing status, quota counters, preferences | Billing, entitlements, account style preference; M1 uses a pilot-account placeholder `[ASSUMPTION]` [BM §11.3] |
| **Project** | tenant, name, topic, mode, stage, stage-status projection, version, epoch, schema version | Lifecycle and stage state only [PRD FR-7.9, FR-8.1] |
| **Material** | id, kind, origin metadata, size/type bucket, status, content ref | Material registry/ingestion status [PRD FR-1.4–1.6] |
| **MaterialDigest** | material id, extraction summary, length bucket, status, artifact ref | Per-material extraction [PRD FR-2.5] |
| **SourceItem** | origin (`provided`/`web`), title, summary, domain, rank, material/query ref | Source panel and grounding; full URL never in analytics [PRD FR-2.15, §11.5] |
| **InterviewQuestion/Answer** | question id, index, option-set version; answer value, revision | One answer per identity; edits overwrite [PRD FR-2.3/2.4] |
| **RequirementsProfile** | version, seven fields, materials/web rows, strategy, dirty projection | Profile versions + current pointer [PRD FR-2.12/2.13] |
| **GapSuggestion/Decision** | label, reason, recommended; selected, decided_at, "not needed" | Agent proposal + user decision; immutable after profile [PRD FR-2.6/2.7, FR-2.21] |
| **Outline** | version, confirmed flag, page/section order | Immutable outline versions [PRD FR-3.1/3.10] |
| **OutlinePage** | page id, position, section id, title, page type, content points | Stable identity/order; title and position mutable in a new version [PRD FR-3.2–3.8] |
| **StyleSelection** | style id, style version, confirmed, preference | Current style choice [PRD FR-5.3/5.6] |
| **PlanArtifact / DesignArtifact** | typed artifact kinds: layout/cards/bounds vs style-applied body + composition metadata | Stored as `ArtifactVersion`; plan is layout only, design is body not chrome [PRD FR-4.1, FR-6.2] |
| **ArtifactVersion** | id, kind, version, content ref/digest, input fingerprint, upstream refs, source refs (IDs only), producer, timestamp | Immutable; pointer separate; the commit point [PRD FR-6.21; NFR-REL-2] |
| **PageHistory** | ordered version refs, current position, max depth, push/pop reason | Per-page undo stack; bounded [PRD FR-6.5, FR-7.7] |
| **Job / JobAttempt** | state, type, operation key, priority, deadline, cancel flag; attempt lease/fencing/error/usage refs | Execution and retry accounting [PRD FR-7.5; NFR-REL-3] |
| **ExportJob / ExportArtifact** | format, deck snapshot, validation report, status, package ref, checksum, size, substitution report | Only evidence of export success [PRD FR-6.14–6.16] |
| **UsageRecord** | operation key, attribution, units, unit-price version, estimated/actual cost, adjustment ref | Append-only cost/quota source [§11.4; NFR-COST-1/2] |
| **DomainEvent / PolicyRecord (Policy/Consent)** | event id, sequence, type, schema version, IDs only; notice/consent/retention/no-training | Stream/audit, never content; consent evidence [§11.5; PRD FR-1.12, NFR-PRIV-2/4] |

**7.1 Stable page identity.** A page ID is assigned on first appearance (cover/TOC/end at outline v1; body pages at first generation or insertion), is immutable, and is never reused. Position/section are fields, so move/reorder change fields only [PRD FR-3.5/3.7]. Insert creates a new ID; delete retires the ID and tombstones its plan/design/history; cover/TOC/end cannot be deleted [PRD FR-3.2/3.6]. Outline regeneration after a profile update reconciles pages by an explicit generated page key, else deterministic matching (same section + normalized title, only when unambiguous); matched pages keep identity and reusable artifacts. The matching algorithm is `[TBD-TECH]`; identity-preserving reconciliation is architectural [ASSUMPTION; AQ-2].

**7.2 Immutable artifacts with lineage.** Every generation writes a new version; no version is edited. A version records content ref/digest, input fingerprint, upstream version refs, source refs used for grounding (IDs only), producer job/attempt, and time. The current pointer is a separate mutable map; installing it is the commit point. Content is written before metadata; an orphan-content sweeper removes unreferenced writes. Lineage edges drive stale scope and let export answer which exact design versions produced a deck. History is a bounded stack; versions beyond depth remain immutable until retention/GC [AQ-5].

**7.3 Source of truth.** Project/stage/gates/epoch, page identity registry, and project-level pointers (profile/outline/style): project service. Material/ingestion status: ingestion service. Digests/gaps/answers/profile versions: research service (content in artifact store). Outline versions: artifact service. Plan/design versions/pointers/history: artifact service. Style definitions/licenses: style registry. Job state/attempts/leases: scheduler. Export state/report/package: export service. Usage/cost: telemetry ledger. Stage flags, page status, progress, stale markers: derived projections, never client-written.

**7.4 Retention and deletion.** Remove material before research: content/digest deleted, count/cap restored [PRD FR-1.6]. Remove after research: material retired, dependents stale, re-research or restart per product decision [AQ-12]. Delete page: page and descendants tombstoned; existing export snapshots unaffected [PRD FR-3.6]. Restart: cancel, epoch++, reset, tombstone under retention [PRD FR-7.8; AQ-13]. Delete project: cancel → delete materials/digests/plans/designs/exports/history → tombstone → verify; ledger remains pseudonymous/content-free [PRD FR-8.2; NFR-PRIV-1]. Tenant deletion cascades to all projects; financial records follow legal policy `[TBD-BIZ]`.

**7.5 Content vs metadata.** Material text, digests, prompts, model responses, page bodies, and packages are **content**: artifact store only, encrypted, authorized references. IDs, kinds, sizes, buckets, domains, timings, costs, statuses are **metadata**: allowed in metadata store, event log, telemetry. Events/logs never carry topic text, material text, file names, full URLs, emails, or other PII; errors reference IDs and classes [PRD NFR-PRIV-3, §11.5].

**7.6 Storage classes.** Durable metadata store (transactional, version-checked, backed up, schema-versioned); artifact/object store (immutable, content-addressed, lifecycle, no public access); queue (at-least-once, visibility/lease, dead-letter, bounded retry); cache (rebuildable, TTL, tenant-scoped, never truth); event log (append-only, per-project sequence, retention/replay); usage/cost ledger (append-only, idempotent operation keys, long retention, adjustments).

---

## 8. State and consistency model

### 8.1 Project stage state machine

Per-stage status: `locked`, `available`, `in_progress`, `complete`, `stale`, `error`. The project has one current stage plus a status projection. Reachability follows [PRD §7.3]; mode changes only advance mechanics [PRD FR-7.17].

| # | Event | Transition | Guard | Effects |
| --- | --- | --- | --- | --- |
| S1 | createProject | none → intake available | Non-empty topic | Project, epoch 1, version 1, `projectCreated` [PRD FR-1.1] |
| S2 | startResearch | intake → research in_progress | Topic; no active research | Research jobs; ingestion may continue [PRD FR-1.2] |
| S3 | answer/updateAnswer | research in_progress | Valid question identity | One answer; if profile exists → `profileDirty` [PRD FR-2.4] |
| S4 | updateProfile | research complete or dirty | Four answers present | New profile version; clear dirty; if outline exists → unconfirmed, plan/design stale [PRD FR-2.13/2.14] |
| S5 | generateOutline | research complete → outline in_progress | Profile current, not dirty | One outline job; Outline locked until done [PRD FR-2.13, FR-3.1] |
| S6 | outline committed | outline in_progress → outline_unconfirmed | Valid structured outline | Outline version + page identities [PRD FR-3.2] |
| S7 | outline edit/move/insert/delete | outline_unconfirmed/complete | Expected outline version | New outline version; stale derivation [PRD FR-3.12] |
| S8 | confirmOutline | outline_unconfirmed → outline_complete | Current outline; all pages identified | Plan available [PRD FR-3.10] |
| S9 | plan complete | plan in_progress → plan_complete | All pages done, none error | Style available; auto-advance eligible [PRD FR-4.4/4.10] |
| S10 | selectStyle + confirm | style available → style_complete | Style selected | Design available/stale [PRD FR-5.3/5.6] |
| S11 | design complete | design in_progress → design_complete | All pages done and current | Export available [PRD FR-6.2] |
| S12 | upstream change / enter stale | complete → stale → in_progress | Change in taxonomy §8.4; stage reachable | Recompute affected set; `staleChanged`; schedule only stale/missing [PRD FR-7.3] |
| S13 | cancelJob | in_progress → prior stable | Active job | No partial artifact installed [PRD FR-7.5] |
| S14 | restart / delete project | any → intake or deleting → deleted | Confirmation | Cancel; epoch++/reset or cascade + tombstone [PRD FR-7.8, FR-8.2] |

Gate invariants: Outline is unreachable while dirty; Plan before outline confirmation, Style before plan completion, and Design before style confirmation are unreachable; Export is never automatic [PRD §7.3/§7.4]. These are orchestrator checks, not client checks.

### 8.2 Job state machine

| From | Event | To | Guard / effect |
| --- | --- | --- | --- |
| — | enqueue | queued | Unique active operation key; duplicate returns existing job [PRD NFR-REL-3] |
| queued | lease (heartbeat) | running | Worker owns lease + fencing token; heartbeat extends under deadline |
| running | commit | succeeded | Candidate validated and committed; attempt token matches |
| running | transient failure | queued | Attempts < max; jittered backoff; attempt recorded |
| running | permanent failure | failed | Exhausted or non-retryable; page/section error |
| running/queued | lease expired | queued | Worker presumed dead; fencing advanced; attempt counted |
| queued | deadline | expired | No execution; visible timeout |
| running/queued | cancel | cancelled | Cooperative stop; in-flight result discarded; never success [PRD FR-7.5] |
| running/queued | process restart | queued | Non-terminal job rows survive; startup reconciliation re-wakes them; lease expiry and fencing make re-execution safe; no committed artifact is duplicated. |

Job identity is `(project, operation_key)` for active work; attempts are separate. Completion is effectively once: at-least-once execution plus idempotent commit and head/fencing checks [PRD NFR-REL-3/4]. **Durability is the job record, not the dispatch transport.** An in-process queue (tech-stack §9) can lose wake-up state on restart, but reconciliation rebuilds it from non-terminal rows; it cannot lose a committed result.

### 8.3 Page state derivation

| Condition | Plan status | Design status |
| --- | --- | --- |
| Active job of that kind | planning | designing |
| Last attempt failed, no current artifact | error | error |
| Current artifact, fingerprint matches | done | done |
| Current artifact, fingerprint differs | stale | stale |
| No artifact, no active/failed job | pending | pending |
| Page retired/deleted | not listed | not listed |

Precedence: error > active job > stale > done > pending. Stage-level stale is the union of stale/missing required artifacts. A page can be `done` while its stage is stale because only some pages are affected [PRD FR-4.2, FR-7.3].

### 8.4 Stale derivation

**Why derived.** A boolean answers only "is the stage stale"; it cannot answer "which pages", drifts on partial success, must be updated at every mutation site, and is lost or wrong after restart. Lineage plus fingerprints answer both, are recomputable, and fail closed.

| Edge (upstream → downstream) | Fingerprint includes |
| --- | --- |
| Material → digest | material version, parser profile version |
| Digests + answers + gap decisions + sources + topic → profile | exact upstream versions, strategy rule version |
| Profile + digests + sources + answers → outline | profile version, source refs, outline schema version |
| Outline page content + section membership + page type → plan body | outline page version, section ref, page type, layout vocabulary version |
| Plan body + style → design body | plan version, style token version, design vocabulary version |
| Outline title/section/position → page chrome | outline chrome version, deck order version |
| Deck snapshot (ordered pages + current designs + style) → export | exact versions, format, validation policy version |

| Change (matrix row) | Plan draft | Design draft | Computed affected scope |
| --- | --- | --- | --- |
| R1 Edit page title | Keep (header re-render) | Needs rerun | Chrome composition only; **0 model jobs** [PRD §8.9.1] |
| R2 Reorder within section | Keep | Needs rerun | Deck-order chrome for moved pages; **0 model jobs**; export composition stale |
| R3 Move across sections | Needs rerun | Needs rerun | Moved page(s): plan + design + chrome; section membership is a plan input |
| R4 Add / delete page | Needs rerun | Needs rerun | Add: new chain only; delete: page and descendants tombstoned; no other page invalidated |
| R5 Re-plan / tweak single page | That page complete | Needs rerun | That page only: new plan then new design |
| R6 Change style | Unchanged | Needs rerun | All design pages; plan untouched |
| R7 Update profile (outline exists) | Needs reconfirmation | Needs rerun | Outline unconfirmed; after reconfirm, diff old vs new outline, unchanged pages keep artifacts |

**Matrix consequence.** The matrix fixes stage-level outcomes, while computed scope fixes job count: chrome-only rows (R1/R2) never invoke a model, and diff-scoped rows (R3/R4/R7) never fan out to the whole deck. This is the implementation rule behind [PRD §8.9.1] and [PRD NFR-COST-3].

**Cascade guarantee.** The orchestrator computes the affected set before scheduling, schedules one job per stale artifact, installs an existing matching version with zero jobs, and treats chrome-only changes as deterministic recomposition. `rerun_cascade_factor = generative rerun pages ÷ pages with changed semantic inputs` is emitted per `stale_rerun` with cause and estimated/actual cost [§11.2; NFR-COST-3]. The stage flag is a projection of the same computation, so it cannot disagree with scheduled scope; a projection audit alerts on divergence.

### 8.5 Versioning and undo

| Operation | Current pointer | History | Artifact | Model cost |
| --- | --- | --- | --- | --- |
| Regenerate/tweak/style rerun succeeds | New version | Previous current pushed | New immutable version | One job (one per page for style) |
| Submit during generation | Unchanged | Unchanged | None | Rejected/duplicate-join |
| Generation fails | Unchanged | Unchanged | No current change | Metered, no visible variant |
| Undo | Pops top, installs it | Top removed | No new version | Zero |
| Regenerate after undo | New version | Restored current pushed | New version | One job |

Undo is a pointer move, never regeneration [PRD FR-6.5]. A rerun whose fingerprint matches an existing version reuses it with zero jobs [PRD NFR-COST-4]. Redo is not in M1; the undone version stays immutable but is unreachable through history [AQ-4]. No global cross-project history in M1 [PRD FR-7.7, PRD-25].

### 8.6 Concurrency

- **One writer per page:** the orchestrator admits one mutating page operation; a second returns "generating, please wait" and creates no job/history entry [PRD FR-6.9, FR-7.4].
- **Optimistic concurrency:** every write carries an expected aggregate version; mismatch returns `conflict` with current version and authoritative projection.
- **Idempotency keys:** every command carries an intent key; duplicates return the prior result or active job; retention `[TBD-TECH]` [AQ-11].
- **Leases, fencing, commit ordering:** a worker commits only if its attempt/fencing token matches the job head; content is written before metadata, pointer install is the commit point, orphan content is swept, deletion is metadata-first plus tombstone with retried content removal [AD-2].
- **Atomic state+event commit:** an authoritative state change and its domain event commit in one boundary; the event log acts as the outbox. Consumers dedupe by event ID, and a reconciliation audit detects either a committed change without an event or an event without a committed change.
- **No auto-merge for structure:** reorder/insert/delete/style are server-serialized and the client replaces optimistic order; cross-aggregate changes (profile/style) take the project version, invalidate derived artifacts in one orchestrator boundary, then schedule asynchronously.

### 8.7 Server-authoritative vs optimistic client

| Interaction | Optimistic? | Reconciliation |
| --- | --- | --- |
| Title draft | Local only | Commit on save; draft loss on disconnect acceptable `[ASSUMPTION]` |
| Reorder/move | Visual only | Server order wins; conflict replaces local order |
| Chip add/remove; answer selection | Pending/highlight | Status or answer event confirms; cap/count and dirty state server-computed |
| Style selection | Highlight | Confirm waits for ack; selection does not generate |
| Page selection/pin; countdown pause | Local | Never sent as project state; jobs continue; server never advances on its own |
| Generation/export/undo/delete/restart/profile | No | Wait for result/event; show progress |

### 8.8 Auto-advance ownership

**Decision:** the client owns the visible countdown, the server validates the advance. At outline completion the client starts a 3-second countdown only in fully automatic mode; any title edit, insert/delete, or reorder cancels it. At zero the client sends `advanceStage` with expected stage version and countdown token. The orchestrator validates mode, gate eligibility, unchanged outline version, and no pending edit; failure returns a gate/conflict error and fresh snapshot, never advancement [PRD FR-3.11, FR-7.3]. Rationale: a server timer can fire while the user is disconnected or focused in an input, which is exactly what the countdown prevents [UX §3.2]. Background jobs continue; only navigation is client-initiated. On reconnect the outline stays unconfirmed; the countdown restarts only while the user is present. Plan-completion auto-advance follows the same rule and never skips style confirmation [PRD §7.4]. Server-timed auto-advance is deferred (AQ-1).

### 8.9 Persistence, autosave, schema versioning

- Commands are durable before acknowledgment; only client-local drafts are volatile.
- A project snapshot plus event cursor is the reconnect contract; an expired cursor forces full snapshot resync [AD-10].
- `schema_version` is independent of optimistic `version`; migrations are forward-only, lazy or backfill-driven, with a compatibility window [PRD NFR-MAINT-1]. Event schemas are versioned and consumers ignore unknown fields/types, so additive changes require no project migration.
- Refresh/reconnect restores stage, stale markers, page statuses, history, and pointers from server state [PRD FR-7.9].
- A projection audit recomputes stage/page/stale projections from records and artifacts and repairs drift.

---

## 9. Interface contracts (logical, not protocol)

Commands are intention-named writes; queries are side-effect-free reads; events are ordered, immutable, content-free notices. Transport, encoding, and API style are `[TBD-TECH]` (DD-6, DD-7). Every write carries an expected version token and idempotency key; every event carries a per-project sequence and schema version; clients resume from cursors and resync when a cursor has expired.

### 9.1 Commands

| Command | Owner | Purpose | Consistency / idempotency | Refs |
| --- | --- | --- | --- | --- |
| createProject | Project | Create project with topic/mode | Key prevents duplicate project | [PRD FR-1.1, FR-8.1] |
| updateTopic | Project | Change topic before research | Expected version; after research requires restart `[ASSUMPTION]` | [PRD FR-1.1] |
| addMaterial | Ingestion | Add paste/file/URL | Per-item key; cap/type/size validated; pending status | [PRD FR-1.3–1.8] |
| removeMaterial | Ingestion | Remove chip, cancel ingestion | Idempotent; downstream stale if research started | [PRD FR-1.6, AQ-12] |
| startResearch | Orchestrator | Enter Research | Idempotent; no-op if started | [PRD FR-1.2, FR-2.1] |
| answerQuestion | Research | Record answer by question identity | One answer; duplicate returns current | [PRD FR-2.3] |
| updateAnswer | Research | Edit an answered question | Overwrite only; dirty if profile exists | [PRD FR-2.4] |
| updateProfile | Research | New profile version | Four answers; clears dirty; unconfirms outline | [PRD FR-2.13/2.14] |
| decideGaps | Research | Record gaps / not needed | One decision; immutable after profile | [PRD FR-2.6/2.7, FR-2.21] |
| generateOutline | Generation/orchestrator | Start outline job | Clean profile; active-job join | [PRD FR-2.12, FR-3.1] |
| editOutlinePage | Outline core | Edit title | Expected outline/page version; chrome stale | [PRD FR-3.4] |
| movePage | Outline core | Reorder within/across | Expected version; matrix stale | [PRD FR-3.5/3.7] |
| insertPage | Outline core | Insert body page | New identity; expected version | [PRD FR-3.6] |
| deletePage | Outline core | Delete body page | Non-deletable fixed pages; tombstone | [PRD FR-3.2/3.6] |
| confirmOutline | Orchestrator | Lock structure | Current outline; identified pages | [PRD FR-3.10] |
| generatePlan | Orchestrator | Fan out plan jobs | Confirmed outline; skips matches | [PRD FR-4.1/4.9] |
| replanPage | Generation | New layout for one page | One page; design stale | [PRD FR-4.5, FR-4.11] |
| tweakPlanPage | Generation | Layout tweak | Non-empty instruction; one page | [PRD FR-4.6] |
| selectStyle | Project | Record style | Expected version; no generation | [PRD FR-5.3] |
| generateDesign | Orchestrator | Fan out design jobs | Style confirmed; one job/page | [PRD FR-6.2] |
| regeneratePage | Generation | New variant | One writer; single-layout rejected; history on success | [PRD FR-6.4/6.6] |
| tweakDesignPage | Generation | Design tweak | Non-empty; history on success | [PRD FR-6.7] |
| undoPage | Artifact | Restore prior version | Pointer move; no job; idempotent at top | [PRD FR-6.5, FR-7.7] |
| advanceStage | Orchestrator | Advance per mode/gate | Version + countdown token; no-op if advanced | [PRD FR-3.10/3.11, FR-4.10] |
| cancelJob | Scheduler | Cancel queued/running | Idempotent; cancelled never succeeds | [PRD FR-7.5] |
| retryPage | Scheduler | Retry failed page | New attempt; no duplicate history/charge | [PRD FR-4.8, FR-7.6] |
| exportDeck | Export | Export frozen snapshot | Idempotent; re-export uses current state | [PRD FR-6.10–6.21] |
| deleteProject | Project | Delete project/derived data | Idempotent cascade + tombstone | [PRD FR-8.2, NFR-PRIV-1] |
| restartProject | Project | Reset working project | Confirmation; epoch++; cancel | [PRD FR-7.8] |

### 9.2 Queries and events

| Query | Returns | Notes | Refs |
| --- | --- | --- | --- |
| projectSnapshot | Project, stage states, pointers, version, sequence | Primary reconnect read; no material content | [PRD FR-7.9] |
| stageState | Status, reachability, stale reasons, blockers | Rebuildable projection | [PRD FR-7.2/7.3] |
| pageList | Ordered pages with plan/design status | Grouped by section; status text not color-only | [PRD FR-4.2, FR-6.1] |
| pageArtifact | Current plan/design version | Authorized content reference | [PRD FR-6.1; NFR-SEC-1] |
| pageHistory | Bounded versions, current position, variant count | Per page only | [PRD FR-6.5] |
| jobStatus | State, attempts, cancellation, error class | Correlation IDs | [PRD FR-7.5/7.6] |
| exportStatus | Validation report, progress, artifact ref, substitutions | No success without artifact | [PRD FR-6.14–6.16] |
| sourcePanel | Grouped materials/web, counts, empty/skeleton | Title/summary/domain only | [PRD FR-2.15] |

| Event group / purpose | Events | Properties (content-free) | Refs |
| --- | --- | --- | --- |
| Project/material lifecycle | `projectCreated`, `materialStatusChanged`, `sourceAdded` | project_id, mode, counts, kind, status, size_bucket, domain, rank | [§11.2] |
| Research/interview progress | `digestReady`, `questionAsked`, `answerRecorded`, `gapSuggested`, `gapDecided`, `profileReady`, `profileUpdated` | material_id, buckets, index, option_id, counts, web_skipped, profile_version | [§11.2] |
| Outline stream | `outlineDelta`, `outlineDone` | job_id, chunk_index, page/section counts, deviation, cost | [PRD FR-3.1; §11.2] |
| Per-page job lifecycle | `pageJobStarted`, `pageJobDone`, `pageJobFailed` | stage, page_id, page_type, layout_id, variant, tier, tokens, latency, cost, error_code | [PRD FR-4.2/4.8, FR-6.2; §11.2] |
| Stale projection | `staleChanged` | from_stage, cause_change, affected_pages, rerun_pages, cascade_ratio | [PRD FR-3.12, FR-7.3] |
| Export lifecycle | `exportProgress`, `exportDone`, `exportFailed` | format, page/style/rendered counts, validation_result, error_code | [PRD FR-6.10–6.16] |
| Job lifecycle | `jobQueued`, `jobCancelled`, `jobResumed` | job_type, page_id, wait_ms, reason | [PRD FR-7.5] |

`outlineDelta` is ephemeral stream data, not durable content; the durable outline is an artifact. No event carries topic text, material text, file names, full URLs, or PII [PRD NFR-PRIV-3].

### 9.3 Error taxonomy

| Category | Retryable? | User action | Contract |
| --- | --- | --- | --- |
| validation | No | Correct input; focus field | [PRD FR-1.1/1.5, FR-4.6, §8.9.2] |
| gate_violation | No | Complete prerequisite | [PRD FR-2.13, FR-3.10, FR-4.4] |
| forbidden | No | Request access / switch project | [PRD NFR-SEC-1] |
| not_found | No | Refresh; recreate if deleted | [PRD FR-7.9] |
| conflict | Yes after reconcile | Wait/refresh; server wins | [PRD FR-6.9, FR-7.4] |
| rate_limited | Yes with backoff | Wait; retry same intent | [PRD NFR-SCALE-1] |
| provider_timeout | Yes, bounded | Retry page/job; others continue | [PRD FR-4.8, FR-7.6] |
| provider_unavailable | Yes/queued | Retry or degraded scope | [PRD FR-7.6, NFR-MAINT-5] |
| parse_failure | No auto-repeat | Replace material or paste body | [PRD FR-1.9/1.10] |
| export_validation_failure | Conditional | Repair page, retry, alternate format | [PRD FR-6.14/6.15] |
| quota_exceeded (M2) | No | Upgrade/wait; edit/export remain | [BR-4, §11.2] |
| internal | Yes once | Retry; contact support with IDs | [PRD FR-7.6] |

Errors carry category, retryability, message key, safe details, and correlation IDs; they never echo user text.

---

## 10. Failure and recovery architecture

| Failure class | Isolation | Behavior |
| --- | --- | --- |
| Parse/URL failure | One material | `not_digested`; others continue; no dead end [PRD FR-1.9/1.10, NFR-REL-6] |
| Search zero/outage | One gap | Explicit empty/skipped outcome; no fabricated source [PRD FR-2.10/2.20] |
| Page generation failure | One page | Error + retry; others continue [PRD FR-4.8, FR-6.2] |
| Provider timeout/unavailable | One call/attempt | Bounded retries; no success claim [PRD NFR-REL-3] |
| Worker task crash | One attempt | Lease expiry requeues; fencing blocks duplicate commit [PRD NFR-REL-4] |
| Application process restart / deploy | All in-flight attempts | Job rows survive; startup reconciliation requeues non-terminal work; graceful drain first; fencing rejects late commits. The single process is briefly unavailable (tech-stack §9.8/§19.2). |
| Dispatch queue loss (no external broker) | Dispatch only | Durable `job` rows plus startup/periodic sweep re-wake missing work; no committed artifact, event, or ledger row is lost. |
| Client disconnect | Connection | Jobs continue; reconnect restores [PRD FR-7.5] |
| Export failure | One export | Reason/retry/alternate; no file, no success [PRD FR-6.15/6.16] |
| Deletion partial | One project | Visible deleting; sweeper retries; no resurrection [PRD NFR-PRIV-1] |

**Retry ownership.** Adapters own small bounded transient retries inside one attempt (metered per call, no user-visible state change). The scheduler owns cross-attempt retry/backoff with per-job max attempts and deadline; cancellation wins. The orchestrator owns user-initiated retry (new attempt or operation key; no duplicate history/charge). The client only resubscribes and resends pending intent with the same idempotency key; it never auto-resubmits generation. A reconciliation sweeper owns orphans, expired leases, partial deletes, and projection drift.

| FLOW §6 contract | Owner/mechanism | Invariant |
| --- | --- | --- |
| Material parsing failure | Ingestion + scheduler | Failed material isolated; removal/replacement allowed [PRD FR-1.9] |
| URL fetch failure | Ingestion adapter + client | Failure + paste-body suggestion; other sources kept [PRD FR-1.10] |
| Zero search results | Search adapter + research | Empty outcome recorded; continue/adjust; no skip [PRD FR-2.10] |
| Single-page generation failure | Generation + scheduler | Page error + retry; others continue [PRD FR-4.8] |
| Export failure | Export | Reason + Retry + alternate; modal stays; no success [PRD FR-6.15] |
| Leaving the page | Scheduler/stream | Job continues; state restores [PRD FR-7.5] |
| Concurrent operations | Orchestrator/edge | One writer; please wait; no duplicate history [PRD FR-7.4] |
| Profile dirty | Orchestrator gate | Outline blocked until update [PRD FR-2.13] |
| Downstream stale | Orchestrator + graph | Marked; rerun on entry; no stale-as-current [PRD FR-7.3] |
| Delete page | Outline + history | Confirmation/toast undo P1; artifacts tombstoned [PRD FR-3.13; AQ-13] |
| Auto-advance while editing | Client + validator | Edit/pause cancels; no focus steal; version check [PRD FR-3.11] |
| Material over limit | Ingestion policy | Entry disabled + explanation; no silent drop [PRD FR-1.7] |
| Gap change after profile | Research/product | Immutable at profile; re-search P1 or restart [PRD FR-2.21/2.18] |

**No fake success.** A page `done` requires a committed plan/design version; export `done` requires a packaged artifact with checksum/size; material `digested` requires a digest artifact. Cancellation, timeout, validation failure, provider failure, and partial completion never produce success; partial success is represented per material/page and never promoted to deck-level success. Edge, orchestrator, and export service enforce this independently; the client cannot manufacture success because it renders server status [PRD FR-6.16, FR-7.6; UX §5 R1/R7].

---

## 11. Cost and quota architecture

**Ledger.** Append-only records per billable operation: operation key, project/stage/page/job/attempt, provider/capability, unit type/quantity, unit-price version, estimated cost, actual cost when reconciled, currency, timestamp, `adjustment_of`. Corrections are adjustment rows, never overwrites [§11.4; NFR-COST-1/2]. Unique `(operation_key, unit_type)` prevents duplicate charging on retry; provider usage from failed attempts is still recorded for unit economics, while quota/billing consumption commits once per logical operation [PRD NFR-REL-3].

| Metering point | Units | Attribution |
| --- | --- | --- |
| Parse/OCR | pages, bytes, OCR pages | project, material, stage=research, job/attempt |
| URL fetch/extract | fetch, bytes | project, material, job/attempt |
| Model call (digest, gap, profile, outline, plan, design, tweak, repair) | input/output units or provider units | project, stage, page (if any), job/attempt, tier |
| Search | query, results | project, stage, gap/query |
| Render/composition | page | project, page, export job |
| Export packaging | page per format | project, format, export job |
| Storage/egress (M2+) | bytes/month, bytes out | project/account, artifact class |

`cost_per_research`, `cost_per_plan_page`, `cost_per_design_page`, and `cost_per_exported_deck` must be derivable without client events [§11.4; BM §7]. Regeneration and stale rerun are separately attributable; one page regenerated twice is two paid operations.

**Control.** Fingerprint reuse installs a pointer instead of running a job, project-scoped only (never cross-tenant) [PRD NFR-COST-4; AD-13]. Rerun scope comes from lineage, never a stage-level rerun-all [PRD NFR-COST-3; BR-8]. Stage routing may use a cheaper tier for digest/plan than design; routing is configuration [BM §5.1 #3]. Guards: per-project page/material caps, per-job attempt/time limits, per-stage soft budgets, per-account monthly budget at M2; soft breach alerts and degrades before hard-stopping [BM §5.1 #4, BR-4]. Preflight page estimates alert on anomalies `[TBD-TECH]`. Failed attempts are metered but not charged twice; no history or visible variant. M2 quota enforcement is an admission entitlement check plus ledger reserve/commit; export and editing remain available when a regeneration allowance is exhausted [BR-4].

**Reconciliation and observability.** Provider invoices import as actual-cost rows keyed by provider/period/account; variance is reported and corrected by adjustments, not edits [PRD NFR-COST-2]. Dashboards: cost/deck, stage cost, regeneration intensity, cascade factor, cache-hit ratio, export success, queue depth, failure rate [PRD NFR-OBS-2]. Alerts: export failure spike, backlog, cost anomaly, cascade above threshold, repeated page attempts [PRD NFR-OBS-3]. Every `stale_rerun` carries cause, affected/rerun pages, ratio, and estimated/actual cost; the ratio is computed server-side, broken down by change type, and alerted when a local change schedules more than its affected set. Chrome-only recompositions are counted separately and never inflate the generative ratio, making near-1.0 observable and enforceable [M-06; NFR-COST-3].

---

## 12. Security, privacy, and compliance architecture

| Control | Architecture |
| --- | --- |
| Authentication | M1 pilot provisioning `[ASSUMPTION]`; M2 account identity; M3 organizational identity/SSO — all in the policy boundary, never in client/project service. |
| Authorization | Project-scope check on every command/query before routing; M2 account roles; M3 org roles/asset ACLs; deny by default. |
| Tenant isolation and artifact access | Tenant scope on every record; references issued only after authorization; short-lived scoped refs, no public object URLs; no cross-tenant cache reuse [PRD NFR-SEC-1]. |
| Encryption | Transport encryption every hop; stored-data encryption for metadata/artifacts/backups/event/ledger; rotation and separation `[TBD-INFRA]` [PRD NFR-SEC-2]. |
| Secrets | Server-side, per-capability, rotated; never in client bundles/repos [PRD NFR-SEC-3]. |
| Untrusted content (materials, URLs, web) | All source text is data, never instructions. Ingestion strips active content, enforces URL allow/deny (block private, link-local, and metadata endpoints), redirect limits, type/size/decompression caps, and a quarantine/scanning policy, and records provenance. Model context separates task instructions from source text; structured-output validation bounds fields [PRD FR-1.8–1.10, FR-7.18; NFR-SEC-3]. |
| Export safety | HTML output sanitizes active content; PPTX/PDF are generated by the controlled renderer with no external fetches at open time; a license/substitution report is included [PRD FR-6.13/6.17]. |
| Provider egress | Only through adapters; minimum necessary stage context; allow-listed endpoints; data-use configuration recorded [PRD NFR-PRIV-2]. |
| Logging/tracing | Allow-listed attributes only; no content/topic/filename/full URL/PII; errors use IDs/classes [PRD NFR-PRIV-3]. |

**Privacy and retention.** A data-handling notice appears before the first material; notice/consent version is recorded [PRD FR-1.12; NFR-PRIV-4]. Default no-training follows BM-7 and needs contractual + configuration evidence `[TBD-BIZ · legal, before paid pilot]` [PRD NFR-PRIV-2]. Deletion propagates project → materials → digests → plans/designs/history → exports → caches with a verification sweeper; ledger rows remain pseudonymous and content-free [PRD NFR-PRIV-1]. Subprocessor/region disclosures are prerequisites `[TBD-BIZ · legal, before paid pilot]`; adapters let providers/regions change without UX change [PRD NFR-PRIV-5, NFR-MAINT-2]. Export artifacts carry deck content plus license/substitution report only, never internal IDs/provenance.

**Licensing.** The style registry records license status for every bundled font/image/icon. Export validation substitutes with a reported substitution or blocks per policy; silent unlicensed embedding is forbidden [PRD FR-6.17; BM-11]. User-supplied third-party content remains the user's responsibility; the product asserts no ownership [PRD §9.7].

| Legal/business confirmation needed | Owner / stage |
| --- | --- |
| Training/no-training commitment | Legal + founder · before paid pilot (BM-7) |
| Retention/deletion SLA | Legal + founder · before paid pilot |
| Subprocessors and processing regions | Founder + legal · before paid pilot (BM-8) |
| Generated-deck ownership and third-party responsibility | Legal · before paid launch |
| Font/image licensing policy | Legal · before paid launch (BM-11) |
| Break-glass support access policy | Security + legal · M1 |

Audit events (who accessed which project/artifact, when, role) are emitted from M1 even though the audit console is M3, avoiding a later retrofit.

---

## 13. Deployment and operations topology (conceptual)

```
                ┌────────────────────────────────┐
    users ─────▶│ edge/API + stream gateway      │
                └───────────────┬────────────────┘
                                ▼
    ┌───────────────────────────────────────────────────────────┐
    │ application process (M1: exactly one)                     │
    │ project/workflow · scheduler + in-process workers         │
    │ SSE fan-out · rate limiting · in-process dispatch         │
    └───────────┬───────────────────────────┬───────────────────┘
                │                           │
        ┌───────▼─────────────┐   ┌─────────▼─────────────────┐
        │ metadata + cache    │   │ event log + telemetry/    │
        │ (PostgreSQL)        │   │ ledger (PostgreSQL)       │
        └───────┬─────────────┘   └───────────────────────────┘
                │
        ┌───────▼──────────────────────────────────────────┐
        │ content pipeline: ingestion · research · gen     │
        │ export subprocess: validation + packaging         │
        └───────────────────────┬──────────────────────────┘
                                ▼
                      ┌──────────────────┐
                      │ artifact store   │
                      └──────────────────┘
```

Diagram simplification: only content-pipeline work egresses to model/search/parse providers; the export subprocess has no provider egress. All artifact reads/writes are brokered by the artifact service. The in-process dispatch queue and SSE bus are not durable stores; `job` rows and `domain_event` are (tech-stack §9).

| Concern | Architecture |
| --- | --- |
| Environments | dev/staging/prod with separate credentials, stores, provider quotas; staging runs the export fidelity matrix before release [PRD FR-6.18; NFR-MAINT-3]. |
| Stateless tiers | The application process holds no durable domain state; the only process-local state is dispatch and SSE fan-out. M1 runs exactly one process, which keeps that local state consistent; a second process would silently break dispatch and stream delivery, so it is prohibited without the shared-queue upgrade (tech-stack §9.11/§17.2). |
| Worker tier | Scheduler and ingestion/generation workers share the M1 process with bounded concurrency; export runs in an isolated subprocess with concurrency 1. Only content-pipeline work has provider egress `[ASSUMPTION]` [AQ-8]. |
| Scaling | Vertical in M1. Horizontal scale requires replacing the in-process queue and event bus with a shared mechanism; the domain contracts do not change (tech-stack §9.11). |
| Config/flags | Model tier, search, export formats, stage kill switches, caps, question catalog are versioned config with audit; no deploy [PRD NFR-MAINT-5]. |
| Migrations | Expand/contract with dual-read; schema version triggers lazy migration; idempotent backfills [PRD NFR-MAINT-1]. |
| Backup/restore | Metadata point-in-time restore, artifact versioning/replication, event retention, restore drills; RPO/RTO `[TBD-INFRA]` [PRD NFR-REL-2]. |
| Incident hooks | Runbooks for backlog, lease storms, provider outage, export spike, deletion backlog, cost anomaly, and process restart with queued jobs; each has an owner, kill switch, rollback [PRD §14.3]. |

No deployment product is selected; products/tooling are deferred (DD-17, DD-18, DD-20).

---

## 14. Evolution path

| Milestone | What changes | Already anticipated in M1 | Must not be built early |
| --- | --- | --- | --- |
| **M1 Paid pilot** | Manual onboarding; no self-serve accounts/billing; single-project experience; telemetry and export validation live | Nullable tenant/account on every record; policy-boundary stub; ledger attributes project/stage/page [BM §11.3; PRD-01] | Billing UI, quotas, workspace, collaboration, connectors |
| **M2 Self-serve** | Accounts, identity, billing, quotas, plan limits, project list/rename/duplicate, account style preference | Account/tenant scope exists; policy boundary becomes quota enforcement; ledger has operation keys/reconciliation; multiple projects per scope supported | Team roles, shared libraries, SSO, connectors |
| **M3 Team/enterprise** | Organizations, seats, roles, shared brand styles/material libraries, admin, connectors, SSO, audit console, retention controls, private-network deployment | Tenant scope raises account→organization; style registry supports scoped definitions/ACLs; ingestion accepts connector adapters; event log audit-shaped; export workers isolated | Real-time co-editing, marketplace, multi-region, per-tenant infrastructure, microservice split |

Connector boundary: an M3 connector is an ingestion adapter with least-privilege delegated authorization, incremental sync, and per-tenant ACLs; it must not bypass ingestion or write artifacts directly [SRC §4.3]. Shared style registry: scopes (built-in/account/organization) and license records exist from M1, so M3 adds visibility/ACLs, not a new subsystem [BM §6.2]. Collaboration, marketplace, and org administration are deliberately not built because they are blocked on capabilities not designed in v3 [PRD §4.4; BM-6].

---

## 15. Architecture decisions and deferred decisions

### 15.1 Decisions made here

| ID | Decision | Rationale | Alternatives rejected |
| --- | --- | --- | --- |
| AD-1 | Server-authoritative workflow/state; client is a projection | Persistence, reconnect, stale truth, multi-tab safety [PRD FR-7.9; NFR-REL-4] | Client-owned state (drifts); dual writers |
| AD-2 | Durable jobs with leases, attempts, fencing, cancellation, deadlines | Background continuation, crash recovery, idempotency [PRD FR-7.5; NFR-REL-3/4] | In-process tasks (lost on deploy); client-driven generation |
| AD-3 | Immutable artifact versions + lineage + fingerprint + separate pointer | Undo, export snapshots, cost attribution, reproducible rerun [PRD FR-6.5/6.21; NFR-REL-2] | Mutable page rows; copy-on-write without lineage |
| AD-4 | Stale derived by fingerprint/lineage reconciliation | Survives restart, answers which pages, keeps cascade near 1.0 [PRD FR-7.3; NFR-COST-3] | Hand-maintained flags; timestamp comparison |
| AD-5 | Per-page jobs with bounded concurrency | Failure isolation, inspect-while-generating, page rerun/cost [PRD FR-4.9, FR-6.2/6.4] | One deck job; unbounded fan-out |
| AD-6 | Provider-agnostic model gateway + metering | Portability, cost control, consistent failure semantics [PRD FR-7.18; NFR-MAINT-2, NFR-COST-1] | Direct provider calls; client-side model calls |
| AD-7 | Separate export pipeline, validation mandatory | Export is the paid promise and highest fidelity risk [PRD FR-6.14–6.18; NFR-COMPAT-4] | Reusing generation workers; trusting page state |
| AD-8 | Append-only ledger with idempotent operation keys | Cost/deck, quota, invoice reconciliation [§11.4; NFR-COST-2] | Mutable counters; analytics-only cost |
| AD-9 | Client countdown + server-validated advance | No surprise advancement during disconnect/editing [PRD FR-3.11; UX §3.2] | Server-timed advance; no countdown |
| AD-10 | Snapshot + per-project cursor delivery | Reconnect without duplicate jobs or silent gaps [PRD FR-7.5/7.9] | Fire-and-forget; full reload every time |
| AD-11 | Stable page identity + identity-preserving outline reconciliation | History/artifacts/scope survive reorder/edit [PRD FR-3.5–3.8; NFR-COST-3] | Position IDs; regenerate all IDs |
| AD-12 | Generated body split from deterministic chrome | Title/order changes must not cost a model job while still marking design stale [§8.9.1 R1/R2; NFR-COST-3] | Bake chrome into generated page content; ignore chrome changes |
| AD-13 | Content/metadata separation; project-scoped caches only | No-content telemetry and no cross-tenant leak [PRD NFR-PRIV-3; NFR-SEC-1] | Content in events/logs; global content cache |
| AD-14 | Nullable tenant/account scoping from M1 | Avoid painful M2 retrofit while allowing manual pilot [BM §11.3] | Single-tenant schema; build billing in M1 |

### 15.2 Deferred decisions and resolution register

These decisions were deliberately deferred here. `docs/ppt-agent-tech-stack.md` §18 resolves DD-1…DD-20; `docs/ppt-agent-data-model.md` owns DD-19. The table remains the register and the option categories remain for traceability; it does not restate the selected products.

**v1.1 resolution note.** The implementation stack is React + Python, and DD-3/DD-5/DD-6 are resolved without an external broker: dispatch is an in-process `asyncio` queue, SSE fan-out is an in-process event bus, and restart recovery comes from authoritative `job` records plus reconciliation. This changes the transport, not the durability contract in §8.2/§10: a committed job is never lost because the queue memory was lost.

| ID | Decision area | Why deferred | Option categories (no selection) | Owner | Stage |
| --- | --- | --- | --- | --- | --- |
| DD-1 | Language/framework/runtime | Productivity and maintenance | Monolith vs modular services; typed vs dynamic | Tech lead | Before development |
| DD-2 | Metadata store | Access patterns known; product is not | Managed vs self-hosted; transactional vs document-oriented | Tech lead | Before development |
| DD-3 | Queue/broker | Delivery semantics and ops burden | Managed vs self-hosted; at-least-once + idempotency vs exactly-once claims | Tech lead | Before development |
| DD-4 | Object/artifact store | Durability, lifecycle, egress, region | Managed vs self-hosted; versioning/lifecycle features | Tech lead | Before development |
| DD-5 | Cache | Performance vs consistency | In-process vs shared; TTL vs version-keyed | Tech lead | Before development |
| DD-6 | Stream transport | UX contract fixed; protocol is not | Server-push vs long-poll vs client polling | Tech lead | Before development |
| DD-7 | API style | Command/query contract fixed; encoding is not | Single command endpoint vs resource-oriented; response vs operation-based | Tech lead | Before development |
| DD-8 | Model providers/routing | Quality, cost, region trade-offs | Single vs multi-provider; stage tiers; failover | Founder + tech lead | Before development |
| DD-9 | Search provider | Coverage, cost, region, quality | Managed API vs aggregated sources; region choice | Founder + tech lead | Before development |
| DD-10 | Parsing/OCR vendors | Supported types depend on availability [TBD-BE-1] | Managed document AI vs self-hosted; OCR on/off | Tech lead | Before development |
| DD-11 | URL extraction | Anti-scraping/login-wall degradation [TBD-BE-2] | Direct fetch vs extraction service; headless rendering | Tech lead | Before development |
| DD-12 | Page composition/rendering | Fidelity/font risk | Server-side composition vs browser-based | Tech lead | Before export implementation |
| DD-13 | PPTX writer, HTML/PDF packaging, font embedding/subsetting | Core export risk [PRD FR-6.13, FR-6.18; R7] | Library vs custom writer; single-file HTML vs bundle; embed vs substitute; supported font set | Tech lead + design | Before export implementation |
| DD-14 | Identity/auth provider | M2 requirement; M1 is manual | Managed vs build; account vs org model | Founder + tech lead | M2 |
| DD-15 | Billing/quota provider | Pricing/plan model unset [BM §6.3] | Managed billing vs manual invoicing; metered vs subscription | Founder + finance | M2 |
| DD-16 | Observability vendor | Dashboards/alerts required; vendor is not | Managed vs self-hosted stack | Tech lead | Before pilot |
| DD-17 | Secrets manager and upload safety scanning | Security requirements fixed; products are not | Managed secret store vs platform vault; inline scan vs async quarantine | Security + tech lead | Before pilot |
| DD-18 | Deployment platform | Topology fixed; products are not | Managed containers vs VMs vs serverless mix | Tech lead | Before pilot |
| DD-19 | Physical schema/indexes/partitioning | Conceptual entities fixed; physical design not | Normalized vs read models; tenant partitioning | Tech lead | Before development |
| DD-20 | CI/CD and promotion | Process fixed; tooling not | Managed pipeline vs self-hosted; promotion policy | Tech lead | Before development |

### 15.3 Open architecture questions

| ID | Question | Why it matters | Owner | Stage |
| --- | --- | --- | --- | --- |
| AQ-1 | Should auto-advance ever be server-timed? | Current model needs a connected client | Architecture + UX | M1 hardening |
| AQ-2 | Exact outline-regeneration matching rule | Wrong matches preserve history on the wrong page; too strict cascades | Architecture + backend | Before outline v2 |
| AQ-3 | Event-log retention/full-resync threshold | Offline reconnect behavior and storage cost | Architecture + ops | Before pilot |
| AQ-4 | Redo after undo | Users may expect it; M1 has undo only | Product + UX | Post-M1 |
| AQ-5 | History depth vs artifact retention | Storage/cost vs user protection | Product + finance | Before pilot |
| AQ-6 | Partial export policy and excluded-page disclosure | PRD-03 unresolved; architecture supports explicit scope | Product + UX | M1 |
| AQ-7 | Cross-page style consistency mechanism | Independent page generation can drift | Architecture + design | Before design v2 |
| AQ-8 | Dedicated export workers vs shared pool | Export reliability vs infrastructure simplicity | Architecture + ops | Before pilot |
| AQ-9 | Account-shared cache under consent | Cost reduction vs privacy boundary | Product + security | M2 |
| AQ-10 | Ledger reconciliation cadence/ownership | Cost accuracy depends on reconciliation | Finance + architecture | Before pricing |
| AQ-11 | Idempotency-key retention window | Too short duplicates; too long grows state | Architecture | Before pilot |
| AQ-12 | Material changes after research | Stale matrix does not cover them | Product + architecture | M1 |
| AQ-13 | Restart: tombstone vs immediate erase | Recovery, storage, expectations | Product + legal | M1 |
| AQ-14 | Multi-provider failover quality bar | Cheap fallback may violate quality | Product + architecture | M2 |

---

## 16. Traceability

| Architecture area | Requirement groups | NFRs |
| --- | --- | --- |
| Experience tier (§5.1) | FR-1.1–1.14, FR-2.22, FR-3.1–3.11 client, FR-5.2, FR-6.1–6.11, FR-7.1–7.17 | NFR-ACC-1–6, PERF-3, COMPAT-1–3 |
| Project & workflow core (§5.2) | FR-8.1/8.2, FR-7.8/7.9, FR-1.13, FR-2.13/2.14, FR-3.10–3.12, FR-4.4/4.10, FR-5.1–5.6, FR-6.5/6.17/6.21, FR-7.3–7.5/7.7/7.8 | NFR-MAINT-1, REL-2/4, COST-3/4 |
| Ingestion & research (§5.3) | FR-1.3–1.11, FR-2.1–2.21 | NFR-REL-6, COST-4 |
| Generation, model gateway, search (§5.3) | FR-2.8–2.12, FR-2.19/2.20, FR-3.1–3.3, FR-4.1–4.9, FR-6.2–6.9, FR-7.18 | NFR-MAINT-2, COST-1 |
| Render/export (§5.4) | FR-6.10–6.21 | NFR-COMPAT-4/5, MAINT-3, REL-5 |
| Scheduler/workers (§5.5) | FR-7.5, FR-7.8 | NFR-REL-3/4, SCALE-1 |
| Event/telemetry/ledger (§5.5) | PRD §11 | NFR-COST-1/2, OBS-1/2/3, PRIV-3 |
| Policy/identity/billing (§5.5) | FR-1.12, M2 quota/billing | NFR-SEC-1, PRIV-1/2/4 |
| Config/flags (§5.5) | FR-1.7, FR-2.9/2.19, FR-5.4 | NFR-MAINT-5, SCALE-2 |
| Flows (§6) | FR-6.12–6.21, FR-7.5/7.6/7.9, FR-8.2 | NFR-REL-3/4/6, COMPAT-4/5 |
| State/consistency (§8) | FR-3.12, FR-6.5/6.9, FR-7.3/7.4/7.7/7.9 | NFR-COST-3, MAINT-1, REL-3 |
| Security/privacy (§12) | FR-1.12, FR-6.17 | NFR-SEC-1/2/3, PRIV-1–5 |
| Content policy and grounding (§5.3, §7) | FR-2.16/2.17, CR-1–CR-7 | NFR-PRIV-3 |
| Untrusted input and export safety (§12) | FR-1.8–1.10, FR-6.13/6.17, FR-7.18 | NFR-SEC-3 |

**Not owned by architecture (intentional):** client-only behavior — FR-1.14 scenario chips, FR-2.22 scroll, FR-3.5–3.8 keyboard/drag interactions, FR-7.14/7.15 responsive, NFR-ACC implementation — are frontend/UX work; the architecture exposes the required state. Process gates — FR-6.18 fidelity matrix, NFR-MAINT-3 regression suite — are release processes enabled by the export pipeline/validation report. M2/M3 product decisions — FR-8.3 workspace (PRD-09), billing/quotas, collaboration/connectors/SSO/audit console — remain product/business decisions; §14 defines extension points only. Partial: FR-2.18 re-search is P1 with `[TBD-FE]` interaction (architecture supports it; M1 fallback is restart); FR-3.13 delete undo is P1 (tombstones support it; toast/confirmation is undefined in FLOW); FR-5.4 account-scoped preference is M2 (M1 project scope). No PRD requirement is left without an owner.

---

## 17. Risks and trade-offs

| Risk | Impact | Mitigation | Early warning |
| --- | --- | --- | --- |
| Projection/truth divergence; stream resume gaps | Wrong gate / lost completion | Projection audit, single writer, snapshot fallback, cursor validation, idempotent events | Audit repairs > 0; resync rate; duplicate reports |
| Artifact storage growth | Cost/retention pressure | History cap, lifecycle, project-scoped dedupe, GC | Storage grows faster than pages |
| Page identity edge cases | Wrong history/cascade | Stable generated keys, conservative matching, diff review | Rematch rate; cascade spike after profile update |
| Worker scaling; provider rate limits | Slow first design, timeouts, page errors | Bounded concurrency, fair queueing, autoscaling, backoff, flags, degradation | Queue wait p95; rate errors by provider |
| Export fidelity failure | Paid promise undeliverable | Validation, fidelity matrix, alternate formats | PowerPoint repair prompts; font overflow |
| Tenant isolation defect; cache correctness | Confidential exposure; stale presented as current | Tenant scope, authorized refs, isolation tests, full-input fingerprints | Cross-tenant test failure; mismatch hits |
| Over-engineering for M3 | Slower M1 | Only nullable scoping/adapter boundaries now | Roadmap additions before M2 metrics |
| Retry/cost leakage | Cost/deck erosion | Per-attempt metering, caps, budgets, reuse | Failed-attempt cost share; cascade above target |
| Auto-advance surprise | Lost edits/trust | Client countdown + version-checked advance | Unexpected navigation reports |
| Single-process availability (no broker) | A deploy/restart pauses all jobs; no rolling multi-instance deploy | Graceful drain, low-activity deploys, readiness gating, startup reconciliation | Deploy-time job pause; readiness flapping |
| In-memory dispatch loss (no broker) | Queued work waits until the sweep runs | Durable `job` rows, startup + periodic reconciler, idempotent wake, fencing on commit | Queue-depth stall; reconciler wake count |
| CPU-heavy work on the event loop | Slow API and SSE, request timeouts | Parsing/metrics in a thread pool; export in a subprocess; event-loop lag alert | Event-loop lag p95; request latency |

---

## 18. Change log

| Version | Date | Change |
| --- | --- | --- |
| v1 | 2026-11-18 | Initial stack-free architecture: logical components and ownership boundaries, ten runtime flows, conceptual data model, stage/job/page state machines, derived stale and undo semantics, logical contracts/error taxonomy, failure isolation, usage ledger, security/privacy boundaries, conceptual topology, M1–M3 evolution, AD/DD/AQ registers, and traceability. No implementation claimed. |
| v1.1 | 2026-11-19 | Aligned with the React + Python, no-broker implementation: clarified that durability is the job record, added process-restart and dispatch-loss transitions to the job state machine and failure table, recorded the M1 single-process deployment topology and scaling invariant, added availability/dispatch-loss/event-loop risks, and noted the DD-3/DD-5/DD-6 resolution. No requirement or state semantics changed. |

*Stack, vendor, protocol, physical schema, and deployment product choices are owned by `docs/ppt-agent-tech-stack.md` (§18 resolves DD-1…DD-20) and `docs/ppt-agent-data-model.md` (DD-19).*
