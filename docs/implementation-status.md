# Bound PPT · Implementation Status

> Updated: 2026-11-19 · Scope: M1 core loop (paid-pilot readiness), implemented from PRD v1 and the implementation design set v1.1.

## Implemented end to end

| Area | Implementation |
| --- | --- |
| Global shell | Skip link, project name, mode badge, stage nav with reachability/stale markers, mobile stage `<select>`, restart/delete confirmations, active-job dialog with cooperative cancel. |
| Authentication | Invite/pilot email+password (`pwdlib[argon2]`), opaque HttpOnly database session, project-scope authorization. CLI: `python -m app.cli.create_user`. |
| Materials | Paste, URL fetch with SSRF guard, file upload handshake (presign → PUT → finalize), PDF/DOCX/XLSX/PPTX/MD/TXT/CSV parsers, per-material failure isolation, removable chips, data-notice consent gate. |
| Research | Per-material digest, Agent gap suggestions, targeted per-gap web search (`Tavily` adapter; deterministic development adapter), zero-result and provider-failure outcomes, configurable source cap, four sequential interview questions with answer editing, versioned requirements profile, `profileDirty`/outline-unconfirmation, two-group source panel. |
| Outline | Streaming ephemeral deltas, fixed cover/TOC/end, section grouping, inline title edit, button/keyboard/drag reordering, insert/delete, page-count warning, expert confirmation, pausable 3-second auto-advance with stale-token reconciliation. |
| Plan draft | Grayscale 16:9 Bento wireframes over the shared layout vocabulary, per-page durable jobs, status/progress/skeleton, single-page re-plan/tweak/retry, completion gate, fingerprint-keyed reuse. |
| Style | Four built-in themes from `shared/themes/`, real token previews, radiogroup keyboard navigation, remember-preference, confirmation gate. |
| Design draft | Three-column workbench, page-by-page generation, pinning during generation, per-page regenerate/tweak, single-layout guard, per-page history and undo, stale recomposition, retry. |
| Export | Real native-shape PPTX (`python-pptx`), self-contained HTML, 16:9 PDF, isolated render subprocess, pre-export validation report, font-substitution report, checksummed artifact, authorized download redirect, no success without a file. |
| Jobs / SSE / recovery | Durable PostgreSQL/SQLite job rows, in-process asyncio runner, leases/fencing, retries, deadlines, cancellation, startup/periodic reconciliation, SSE snapshot-first replay with heartbeats/resync, durable page state across refresh/navigation. |
| Telemetry / policy | Append-only `usage_record` for model/search calls, content-free domain events, consent record, project deletion with content purge. |
| Tests | `pytest` suite (materials/research, generation/artifacts/export, projects/jobs/SSE), Vitest/RTL component tests, Playwright six-stage E2E including undo, refresh restore, and real PPTX download. |

## Development defaults that MUST NOT ship to production

- **SQLite** is the zero-setup local database. Production uses PostgreSQL + `alembic upgrade head`; `APP_ENV=production` rejects SQLite and auto-created tables.
- **`MODEL_PROVIDER=stub`** and **`SEARCH_PROVIDER=stub`** are deterministic development adapters. `APP_ENV=production` startup fails if either is a stub, satisfying the no-mock-on-the-paid-path rule.
- Local object storage is `backend/storage/`. Production uses the S3-compatible adapter (`STORAGE_BACKEND=s3`).
- The local upload/download endpoints are signed short-lived development handshakes; production uses direct presigned object-storage URLs.

## Known M1 limitations (manual or deferred)

- **Font binaries are not embedded.** Export validation emits a `fonts_missing` warning and a substitution report naming the theme families. The PowerPoint 2016+ fidelity matrix (FR-6.18), font licensing, and the acceptance sign-off remain manual gates.
- **Image/chart/table assets** are represented as structured blocks/placeholders. M1 does not generate or ingest page image assets; `GET /assets/{id}` therefore returns `not_found`.
- **Accounts, billing, quotas, team libraries, SSO, and connectors** are M2/M3 and are intentionally absent.
- Project list, rename/duplicate workspace, and global cross-project history remain out of M1 (PRD-09 / UX R6).
- OCR for scanned documents is not enabled by default; unsupported material fails with a specific parse error and a paste-body fallback.
- Observability fields for OTLP/Sentry exist in configuration but M1 ships structured logs and readiness checks only; dashboards/alerts require the deployment stack.
- Mobile is functional (stage select, stacked workbenches, horizontal thumbnail strip) but the pilot cohort is desktop-first.

## Verification commands

```bash
cd backend && uv run ruff check app tests && uv run pytest -q
cd ../frontend && npx tsc -b && npm run build && npm test && npm run lint
npx playwright install chromium
E2E_BASE_URL=http://127.0.0.1:5173 npx playwright test
```
