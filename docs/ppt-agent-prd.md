# Bound PPT · Product Requirements Document (PRD)
> Version: v1 · 2026-11-18
> Status: Draft
> Owner: Product
> Scope: Buildable, testable product requirements for M1 (paid pilot readiness), with M2/M3 boundaries.
> This is a product requirements document, not an architecture document. It deliberately does not prescribe stack, frameworks, database, queue, hosting, API protocol, or model vendors. Where architecture is implied, the item is marked `[TBD-INFRA · architecture stage]` or `[TBD-BE · tech implementation]`.

---
## 1. Document control
### 1.1 Metadata
| Field | Value |
| --- | --- |
| Document | Bound PPT PRD |
| Version | v1 |
| Date | 2026-11-18 |
| Status | Draft |
| Owner | Product |
| Audience | Product, design, engineering, QA, legal/security, founder |
| Review cadence | At each milestone gate |
| Supersedes | None |
### 1.2 Source documents
| Source | Version | Date | Contribution to this PRD |
| --- | --- | --- | --- |
| `docs/ppt-agent-business-model.md` | v1 | 2026-11-18 | Primary for segments, value proposition, cost model, packaging constraints, unit economics, milestones, risks, and open business decisions. |
| `docs/ppt-agent-interaction-flow.md` | v3 | 2026-11-18 | Primary for six-stage UX behavior, stage contracts, state semantics, stale propagation, failure contracts, and accessibility/responsive baseline. |
| `docs/ppt-content-sources.md` | v2.1 | 2026-11-18 | Supporting for the five content channels, ingestion priority, material sufficiency, gap logic, conflict priority, and content-source open questions. |
| `docs/ppt-agent-ux-review.md` | v2 → v3 | 2026-11-18 | Supporting for defect evidence, follow-ups R1–R9, validation log, keyboard matrix, semantics, and breakpoints. |
| `docs/linux-do-1782304-ppt-agent-extract.md` | Post extract | 2026-11-16 | Background for the research-first method, plan/design split, Bento layout rationale, and SVG/Office rationale. Not a product commitment. |
| `README.md` | Repo context | 2026-11-18 | Confirms current design version v3 and repository layout. |
| `prototype/ppt-agent-prototype.html` | 3,037 lines | 2026-11-18 | Status evidence only. The prototype is a client-side simulation; its mock behavior is not a requirement. |
### 1.3 Precedence and conflict rule
- **User experience:** FLOW v3 wins. BM v1 explicitly delegates the user experience to the interaction flow and excludes accounts, billing, admin, collaboration, and data policy from it [BM preamble].
- **Business scope, packaging, milestones, pricing:** BM v1 wins.
- **Content-source mechanics in stages 1–2:** SRC v2.1 wins within its scope; FLOW v3 is aligned.
- **Known defects and follow-ups:** UX review records evidence and remediation status; it does not override FLOW behavior.
- **Background:** EXTRACT informs rationale only.
- Conflicts are marked `[CONFLICT]` in §1.6 with the winning source and affected requirement.
### 1.4 Evidence conventions
| Tag | Meaning |
| --- | --- |
| `[FLOW §x]` | Interaction flow v3, section x. |
| `[BM §x]` | Business model v1, section x. |
| `[SRC §x]` | Content sources v2.1, section x. |
| `[UX §x]` | UX review, section x. |
| `[EXTRACT §x]` | Post extract, section x. |
| `[ASSUMPTION]` | Unverified hypothesis. Must be validated; not a commitment. |
| `[TBD-BIZ]` | Business decision not yet made. Owner and confirmation stage are stated in §16. |
| `[TBD-UX]` | Design/UX decision not yet made. Owner and stage are stated in §16. |
| `[TBD-FE]` / `[TBD-BE]` / `[TBD-INFRA]` | Frontend, backend, or infrastructure decision not yet made. Owner and stage are stated in §16. |
| `[CONFLICT]` | Sources disagree. The winning source and resolution are stated. |

Rules:

- No price, market size, vendor comparison, or competitor figure is asserted anywhere in this document. Category-level alternative descriptions are allowed [BM §1.2].
- MUST, SHOULD, and MAY are normative. "Must" inside a requirement statement is normative.
- A requirement's source citation identifies the product fact; it does not imply the behavior is implemented.
- Bare tags in compact tables are expanded in §16. Defaults: metric targets `TBD-BIZ · founder + finance, after paid pilot`; UX decisions `TBD-UX · design, visual design stage`; backend decisions `TBD-BE · backend, before development`; infrastructure decisions `TBD-INFRA · architecture stage`; frontend decisions `TBD-FE · frontend, before development`.
### 1.5 Glossary
| Term | Definition |
| --- | --- |
| **Material** | A first-party input supplied in Material intake: pasted text, an uploaded file, or a URL. Displayed as a removable chip [FLOW §2 stage 1; SRC §1.1]. |
| **Digest** | The per-material extraction summary produced after ingestion, explaining what the Agent extracted from that material [FLOW §2 stage 2]. |
| **Gap suggestion** | An Agent-proposed missing content item for the deck, with a reason, a recommended flag, and optional pre-selection. The user confirms or rejects it; the user does not diagnose the gaps [FLOW §2 stage 2; SRC §5]. |
| **Requirements profile** | The editable stage-2 card containing audience, goal, page count, style/mood, materials, web scope, and content strategy [FLOW §2 stage 2]. |
| **profileDirty** | State after the profile has been shown and an interview answer changes. Entering Outline is blocked until the profile is updated [FLOW §3.1]. |
| **Sticky-note outline** | The outline rendered as per-page notes with inline title editing, move/insert/delete buttons, drag, and keyboard sorting [FLOW §2 stage 3]. |
| **Plan draft** | Per-page grayscale 16:9 Bento wireframe, layout only, with no style applied [FLOW §2 stage 4]. |
| **Design draft** | Style-applied page render, with per-page variants and version history [FLOW §2 stage 6]. |
| **Variant** | One generation of a page. Regenerate or tweak pushes the previous variant onto that page's history stack [FLOW §3.1, §3.4]. |
| **Stale / needs rerun** | A downstream artifact invalidated by an upstream change. The stage nav shows an amber dot and `aria-label="needs rerun"`; entering the stage reruns missing artifacts [FLOW §3.4]. |
| **Bento layout** | The six-combination card-grid vocabulary used by both plan and design: single, 2-column, 3-column, primary + secondary (asymmetric), top hero, and mixed grid [FLOW §2 stage 4, §5; EXTRACT §II.4]. |
| **SVG-composited PPTX** | A PPTX assembled from full-page SVG, intended to keep text and shapes editable in Office 2016+ [FLOW §2 stage 6; EXTRACT §IV]. Fidelity is not yet validated; see R7. |
| **Fully automatic** | Mode in which the flow auto-advances at defined gates; the outline stage uses a pausable 3-second countdown [FLOW §1, §2 stage 3]. |
| **Expert copilot** | Mode in which every stage ends at a confirmation control so the user can inspect and adjust before continuing [FLOW §1]. |
| **Source** | A material or web supplement shown in the stage-2 content source panel. Origin is `provided` or `web` [SRC §5]. |
| **M1 / M2 / M3** | Paid pilot readiness / self-serve paid launch / team and enterprise, per [BM §11.3]. |

Terminology note: this PRD uses the canonical stage names **Material intake, Research + interview, Outline, Plan draft, Style selection, Design draft**. FLOW's short stage-nav labels are New, Research, Outline, Plan, Style, and Design [FLOW §1, §4]. "Bound PPT" is used consistently; "the Agent" refers to the product's research/planning/design pipeline, not a specific model.
### 1.6 Source conflicts register
| ID | Conflict | Sources | Resolution |
| --- | --- | --- | --- |
| C-1 | R3 (long-task background, cancellation, reconnect) and R7 (pre-export validation) are labeled P1 in the UX follow-up list, but BM lists them among the blockers for paid launch and M1. | [UX §5 R3, R7]; [BM §0; §10.1; §11.3] | **BM wins for milestone gating.** R3 and R7 are P0-M1 requirements in this PRD. The UX P1 labels remain build-sequencing guidance, not a release waiver. |
| C-2 | FLOW §1 describes an automatic chain "after stage 2 interview → stage 3"; FLOW §2 stage 2 and the prototype require an explicit "Requirements look good, generate outline" confirmation. | [FLOW §1; §2 stage 2]; [FLOW §5] | **The more specific stage contract wins.** Profile-to-outline is a deliberate gate in both modes. Whether fully automatic mode should auto-advance after a profile update is `[TBD-UX · design, M1]` (PRD-22). |

---
## 2. Executive summary
**Problem.** Knowledge workers with material-rich, deadline-driven decks spend most of their time on structure and layout before the content is right. One-click tools generate a generic outline and force it into a template; they ignore first-party material and make design-stage changes expensive. AI outputs are also hard to trust because undo, stale detection, and failure recovery are usually missing [BM §1.1; FLOW §0.1; UX §1].

**Product.** Bound PPT is an "expert team–style" PPT Agent. The user supplies a topic and, optionally, existing materials. The Agent runs a researcher → planner → designer pipeline across six stages, while the user makes a small number of high-leverage confirmations: Material intake → Research + interview → Outline → Plan draft → Style selection → Design draft/export [FLOW §0, §1]. The output is intended to be an editable deck, not an image-only artifact.

**Target users and beachhead.** Primary users are product managers, marketing teams, pre-sales/solutions teams, and founders/executives [BM §2.1]. The beachhead hypothesis is pre-sales/bidding and product/marketing launch decks inside material-rich organizations [BM §2.3] `[ASSUMPTION]`. Validate with 10–15 problem interviews and 5 paid pilots before freezing the segment.

**Three differentiators.**

1. **Material-first content.** First-party materials are digested before any outline; web search is downgraded to gap filling; first-party material wins conflicts [SRC §0, §5].
2. **Control before expensive design.** Outline and grayscale plan-draft gates let users make cheap structural changes before style is applied [FLOW §2 stages 3–4; EXTRACT §II.3].
3. **Editable, recoverable output.** SVG-composited PPTX is intended to be editable in Office; per-page history, stale markers, and failure recovery make generation predictable [FLOW §2 stage 6, §3.4; BM §1.1].

**Current maturity.** The current artifact is a clickable prototype with mock parsing, mock search, mock model generation, and mock export. It makes no network requests and does not produce real files [FLOW §5; BM §0]. It is evidence for interaction behavior, not for production readiness.

**Paid-launch blocker.** Paid pilot launch (M1 exit) is blocked on **real model generation and real web search (FR-7.18, FR-2.20), R1 failure/recovery, R3 background task execution/cancellation/reconnect, R4 real material parsing and URL fetching, R7 pre-export validation plus real export validation**, and **real server-side cost telemetry**. BM §11.3 additionally requires a terms/privacy page and 5–10 design partners completing real decks [BM §0; §11.3; UX §5].

---
## 3. Background and problem statement
| Problem | Why current tools fail | Evidence | Product response |
| --- | --- | --- | --- |
| One-click generation produces generic decks | The common pattern is "topic → rough outline → off-the-shelf template"; the user's material is ignored or forced into the template. | [FLOW §0.1 #1]; [BM §1.1, §1.2]; [EXTRACT §V] | Sequential interview and Agent gap suggestions before the outline; material digestion first. |
| Web-only research is insufficient | In 7 of 8 high-frequency scenarios the primary source is first-party material; only competitive analysis is genuinely web-first. | [SRC §0, §3]; [BM §1.1] | Material slot, per-material digest, targeted gap search; web-only remains the fallback when no materials are supplied. |
| Design-stage edits are expensive | Layout and style are entangled in a finished slide, so a structural change requires regeneration or manual rework. The planner/designer split exists to separate layout from decoration. | [BM §1.1]; [EXTRACT §II.3]; [FLOW §2 stages 3–4] | Sticky-note outline and grayscale plan draft precede style; outline and plan edits invalidate only the affected downstream scope. |
| AI output is not trustworthy for important work | Regeneration overwrites good pages, stale artifacts remain visible, failures are silent, and the user cannot tell what changed. | [FLOW §0.1 #9; §3.4]; [UX §1, §3.4] | Per-page history and "Previous version", no fake variants, stale markers, explicit failure/recovery contracts, pausable auto-advance. |
| AI output is not editable in Office | Image-based or rigid-template output cannot be edited by the user or a designer afterward. | [BM §1.1, §1.2]; [EXTRACT §IV] | SVG-composited PPTX as the primary deliverable, plus HTML and PDF. Fidelity is unverified until R7 passes. |

Implication: the defensible layer is workflow and state quality — interview logic, gates, undo, stale propagation, failure recovery, ingestion, export fidelity, and evaluation — not prompt novelty [BM §1.3].

---
## 4. Goals, non-goals, and success metrics
### 4.1 Product goals
| ID | Goal | Acceptance intent |
| --- | --- | --- |
| G1 | **Material-grounded first draft.** The outline and design are derived from the user's materials, the requirements profile, and only the selected web supplements. | When materials and web sources conflict, the outline follows first-party material [SRC §5]. |
| G2 | **Cheap structural edits.** Users can change titles, order, sections, and page count before style is applied, with predictable downstream invalidation. | Outline edits do not require design regeneration unless the stale matrix says so [FLOW §3.4]. |
| G3 | **Predictable, undoable generation.** Every long-running stage shows per-page status; single-page operations are reversible; failures have a retry path. | No fake variant increments; no success state without an artifact; per-page history restores the prior variant [FLOW §2 stage 6, §6]. |
| G4 | **Editable, Office-usable export.** The user can download a real PPTX that opens in PowerPoint and remains editable, plus HTML and PDF. | Real export fidelity review passes before M1 go-live [BM §0 #2; UX R7]. |
| G5 | **One product, two modes.** Fully automatic and expert copilot share the same stages, gates, data, failure contracts, and per-page controls; only advance mechanics differ. | Both modes complete the same six stages and produce the same editable output [FLOW §1]. |
### 4.2 Business goals
| ID | Goal | Signal | Source |
| --- | --- | --- | --- |
| B1 | Reach paid pilot readiness without pretending the prototype is a product. | 5–10 design partners complete real decks; export fidelity sign-off; unit cost measured. | [BM §11.3] |
| B2 | Validate that material-rich users pay for relevance and control, not only speed. | Pilot conversion and willingness-to-pay interviews above free-tier limits. | [BM §0, §2.3, §11.4] |
| B3 | Make variable cost per exported deck leave room for gross margin. | Stage-level cost telemetry and cost per exported deck. | [BM §0 #4, §7] |
| B4 | Prove repeat use, not one-off novelty. | More than one deck per quarter; second deck within 30 days. | [BM §0 #5, §8.2] |
| B5 | Let the free tier prove the full loop. | Free users can complete Material intake → Research + interview → Outline → Plan draft → Style selection → Design draft → capped PPTX export. | [BM §6.1, §6.2] |
| B6 | Protect trust features on every plan. | Undo, history, stale detection, accessibility, and error recovery are never paywalled. | [BM §6.4; §5.1 rule 7] |

**North star (proposal)** `[ASSUMPTION]`: exported decks per active account per month [BM §11.1]. Pair it with regeneration intensity and export success rate so volume does not hide quality problems.

**Guardrails:** cost per exported deck, p95 time to first design page, generation failure rate, export failure rate, and support contacts per 100 decks [BM §11.1].
### 4.3 Success metrics
All targets are unset unless a source gives one. Metric owners and confirmation stages are in §16. Measurement is server-side; the prototype's client simulator is not sufficient [FLOW §3.2; BM §7].

| ID | Metric | Definition / formula | Target | Measurement source |
| --- | --- | --- | --- | --- |
| M-01 | North star: exported decks per active account per month | Successful deck exports ÷ active accounts ÷ months | `[ASSUMPTION]`; numeric target `TBD-BIZ` | Server export and account events |
| M-02 | `cost_per_research` | (LLM input + search + parsing cost) ÷ projects passing the profile gate | `TBD-BIZ` | Cost ledger |
| M-03 | `cost_per_plan_page` | Plan inference cost ÷ plan pages generated | `TBD-BIZ` | Cost ledger |
| M-04 | `cost_per_design_page` | Design inference + render cost ÷ design pages generated | `TBD-BIZ` | Cost ledger |
| M-05 | `regeneration_intensity` | Regenerated design pages ÷ designed pages | `TBD-BIZ`; quality guardrail | `history_push`, `page_done` |
| M-06 | `rerun_cascade_factor` | Pages rerun ÷ pages actually changed | Must approach 1.0 [BM §7]; numeric threshold `TBD-BIZ` | `stale_rerun` |
| M-07 | `cost_per_exported_deck` | Total variable cost ÷ successful exports | `TBD-BIZ`; core unit cost | Cost ledger + export events |
| M-08 | `gross_margin_per_deck` | (Revenue − variable cost) ÷ revenue | `TBD-BIZ` | Billing + cost ledger |
| M-09 | `export_success_rate` | Successful exports ÷ export attempts | Guardrail; target `TBD-BIZ` | Export events + artifact check |
| M-10 | `free_to_paid_conversion` | Paying accounts ÷ activated free accounts | `TBD-BIZ` | Billing + activation |
| M-11 | `decks_per_paid_account` | Exported decks ÷ paid accounts per period | `TBD-BIZ` | Export + billing |
| M-12 | `cac_payback_months` | CAC ÷ monthly contribution margin | `TBD-BIZ` | Finance + billing |
| M-13 | Activation | First export of a deck with at least N pages; N is `TBD-BIZ` | `[ASSUMPTION]` definition | Export event + page count |
| M-14 | Interview completion rate | Profiles generated ÷ research starts | `TBD-BIZ` | `profile_ready`, `question` |
| M-15 | Time to profile | Median and p95 from research start to `profile_ready` | `TBD-BIZ` | Event timestamps |
| M-16 | Outline edit rate | Outline edit/sort/add/delete events ÷ outline pages generated | `TBD-BIZ` | Outline events |
| M-17 | p95 time to first design page | Time from outline confirmation to first design `page_done` | Guardrail; target `TBD-BIZ` | Event timestamps |
| M-18 | Export attempt → paid conversion | Paid accounts with an export attempt ÷ accounts with an export attempt | `TBD-BIZ` | Export + billing |
| M-19 | Second-deck rate within 30 days | Accounts with at least 2 exported decks in 30 days ÷ activated accounts | `TBD-BIZ` | Export events |
| M-20 | Repeat project rate | Accounts starting a second project ÷ activated accounts | `TBD-BIZ` | Project events |
| M-21 | Cohort retention | Activated cohort active in week/month N | `TBD-BIZ` | Account events |
| M-22 | Referred sign-ups | Sign-ups attributed to referral or invite | `TBD-BIZ` | Referral events |
| M-23 | Gap acceptance rate | Selected gaps ÷ suggested gaps | `TBD-BIZ` | `gap_suggest`, `gap_decision` |
| M-24 | Web-skip rate | Projects choosing "not needed" ÷ projects with materials | `TBD-BIZ` | `gap_decision` |
| M-25 | Generation failure rate | Failed page jobs ÷ page jobs | Guardrail; target `TBD-BIZ` | `page_done` status |
| M-26 | Support contacts per 100 decks | Support contacts ÷ exported decks × 100 | Guardrail; target `TBD-BIZ` | Support system |
### 4.4 Non-goals
| Non-goal | Why it is excluded | Horizon |
| --- | --- | --- |
| Real-time co-editing | Team collaboration starts with shared libraries and brand kits; real-time co-editing is not in the v3 flow [BM §12 BM-9]. | Post-M3 |
| Template marketplace | Built-in styles first; a marketplace requires creator demand and review [BM §12 BM-10]. | Post-M2 |
| Image-generation-only decks | The product promise is editable, Office-compatible output, not image slides [BM §1.2]. | Never as the primary mode |
| Organizational connectors in M1 | Feishu/Notion/Confluence OAuth is later roadmap [SRC §4.3]. | M3 |
| Billing, accounts, and admin in M1 | Required for self-serve paid launch, not for the paid pilot [BM §10.1, §11.3]. | M2 |
| Mobile-native apps | The sourced experience is a responsive web app; native apps are not designed [FLOW §5, §7]. | Not planned |
| Speech transcription, IM/email import, old-PPT reuse | Explicitly later roadmap [SRC §4.3]. | Post-M2 |
| Global cross-project version history | Only per-page variant history is designed; global history is R6/P2 [UX §5]. | P2 |
| Students, one-off users, template buyers, competitive-analysis-only users | Low willingness to pay, high support volume, or weakest differentiation [BM §2.3]. | Not a beachhead |
| Shared libraries, SSO, VPC, audit, custom styles in M1 | Team/enterprise capabilities do not exist in v3 [BM §6.2, §10.1]. | M3 |
| Multi-locale UI in M1 | No source specifies internationalization; launch locale follows BM-8. UI and deck locale are `[TBD-UX]` / `[TBD-BIZ]` (PRD-05). | Post-M1 |
| Public deck sharing and attribution | Mentioned as a GTM channel, not designed in FLOW [BM §8.3]. | M2+ |

---
## 5. Users, personas, and jobs
### 5.1 Segment and persona table
The sources define role-based segments, not demographic personas.

| Segment | Core job | Trigger | Material richness | Repeat use | Value that matters most | WTP hypothesis |
| --- | --- | --- | --- | --- | --- | --- |
| Product managers | Product launch, roadmap review, quarterly report | Release cadence, review cycles | High (PRDs, data, tickets) | High | Accuracy, speed, editable output | Medium-high `[ASSUMPTION]` |
| Marketing | Campaign, launch, brand, and event decks | Campaign calendar | Medium-high (briefs, assets, past decks) | High | Visual quality, brand consistency, speed | Medium-high `[ASSUMPTION]` |
| Pre-sales / solutions | Client proposal, bid/tender, solution defense | RFP deadlines | Very high (RFP, case library, pricing) | High and deadline-driven | Client relevance, case reuse, editable output | High `[ASSUMPTION]` |
| Founders / executives | Fundraising, board, company introduction | Fundraising rounds, board meetings | Medium-high (metrics, narrative, old decks) | Episodic but high-stakes | Polish, narrative, confidentiality | High per deck `[ASSUMPTION]` |
| Team / enterprise (later) | Brand consistency, shared case material, governed access | Team charter, security review | High organizational assets | High | Shared libraries, admin, governance, invoiceability | Buyer-level `[ASSUMPTION]`; blocked on M3 capabilities |

Persona note: the material-rich individual is the primary user. For individual plans the deck maker is the buyer; for team/enterprise plans the buyer is a team lead, enablement owner, or IT/security. The buyer cares about brand consistency, shared case/material libraries, seat administration, data governance, and invoiceability — capabilities not designed in v3 [BM §2.4].
### 5.2 Scenario × primary source matrix
| Scenario | Primary sources | Role of web search | Fit for material-first positioning |
| --- | --- | --- | --- |
| Project / quarterly report | BI data, weekly reports, tickets | Almost none | **Strong** |
| Product launch | Internal docs + business data | Fill industry benchmarks | **Strong** |
| Fundraising roadshow | Business data | Market size, competitors, industry reports | Medium-strong; web supplements matter |
| Pre-sales / bidding | Client RFP + internal case library | Qualifications and industry trends | **Strong**; high value, deadline-driven |
| Tech sharing | Code repository, design docs, README | Community and ecosystem news | Medium |
| Training deck | Internal standards + old decks | Basically none | **Strong** for organizations |
| Competitive analysis | Competitor public materials | Primary source | Weak; web-first, least differentiated |
| Thesis / graduation defense | Thesis + experiment data | None | Weak as a business segment |
### 5.3 Beachhead rationale `[ASSUMPTION]`
Start with **pre-sales/bidding** and **product/marketing launch** decks inside material-rich organizations [BM §2.3]:

- The user already has the raw material the flow is designed to exploit [SRC §0].
- A poor deck is expensive and the deadline is real, so quality and reliability outrank price.
- Decks recur, which supports subscription rather than one-off purchase.
- The output must be edited afterward, so editable export is a purchase requirement, not a nice-to-have.

Validation plan: 10–15 problem interviews and 5 paid pilots before freezing the segment `[TBD-BIZ · founder, before paid pilot]` [BM §2.3]. `[ASSUMPTION]` The pilot cohort is recruited from pre-sales and product/marketing launch teams.
### 5.4 Jobs to be done and pain points
| ID | Job to be done | Pain today | Product response | Acceptance signal |
| --- | --- | --- | --- | --- |
| JTBD-1 | Turn my existing material into a client-specific first draft. | Every proposal starts from zero even though cases and past bids exist. | Material intake, digest, targeted gap search, profile, outline. | Time to profile; gap acceptance; case reuse in review. |
| JTBD-2 | Keep structural control before visual design. | Editing a finished slide to fix structure is expensive. | Sticky-note outline and plan draft gates; stale matrix. | Outline edit rate; plan re-plan rate. |
| JTBD-3 | Fix only the page that is wrong. | Regeneration overwrites good pages. | Single-page regenerate/tweak; per-page history. | Regeneration intensity; "Previous version" use. |
| JTBD-4 | Hand off a deck I can edit. | Image or template output is not editable in Office. | SVG-composited PPTX, HTML, PDF; pre-export validation. | Export success; PowerPoint fidelity sign-off. |
| JTBD-5 | Recover when the AI does something unexpected. | No undo, silent stale artifacts, silent failures. | Per-page history, stale dots, failure contracts, retry. | Undo rate; failure recovery rate; support contacts. |
| JTBD-6 | Keep confidential material inside. | Unclear retention and training use. | Data-handling notice, no-training default, deletion policy. | Security review; deletion test. |
| JTBD-7 | Get a usable draft without babysitting. | Automation is either too slow or too uncontrollable. | Fully automatic mode with pausable countdown and background jobs. | Activation; second-deck rate. |

---
## 6. Scope and release boundaries
### 6.1 Milestones
| Milestone | Scope | Exit criteria | Key blocking requirements (not exhaustive; §8 is the P0 register) |
| --- | --- | --- | --- |
| **M0 · Prototype (current)** | Clickable single-file prototype; mock parsing, search, model, design, and export; no network. | Flow walkthrough complete; known gaps R1–R9 recorded. Not sellable. | None; this is the baseline. |
| **M1 · Paid pilot readiness** | Real material ingestion and URL fetch, real model generation and web search, real export with validation, failure recovery, background tasks, cost telemetry, terms/privacy, pilot onboarding. No self-serve billing. | Conditions 1–2 built and validated; conditions 3–6 measured during the pilot; 5–10 design partners complete real decks; export fidelity sign-off; unit cost measured. | FR-1.8–1.10, FR-2.10, FR-2.20, FR-6.12–6.18, FR-7.4–7.6, FR-7.18, NFR-COST, NFR-PRIV, NFR-COMPAT-4. |
| **M2 · Self-serve paid launch** | Accounts, billing, quotas, support runbook, scenario landing pages, plan-based limits. | Conversion and margin targets met on a small cohort; price points set after telemetry and pilot. | M2 account/quota/billing requirements; NFR-SEC; §11 quota events. |
| **M3 · Team / Enterprise** | Collaboration, shared libraries, admin, connectors, SSO, security review, retention controls. | First team contract; security questionnaire passed. | M3 capabilities not designed in v3; BM-6. |

M1 does not include self-serve accounts or billing. The paid pilot may use manual commercial onboarding `[ASSUMPTION]` (PRD-01).
### 6.2 In scope vs architecture-owned
| In scope for this PRD | Out of scope / architecture-owned |
| --- | --- |
| User-visible behavior, states, gates, and acceptance criteria per stage. | Stack, framework, database, queue, hosting, API protocol, model vendors. |
| Content-source rules, conflict priority, and output fidelity expectations. | Prompt text, model routing implementation, token budgets. `[TBD-BE · tech implementation]` |
| Failure taxonomy and recovery contracts. | Job-queue implementation, retry backoff, worker topology. `[TBD-INFRA · architecture stage]` |
| Accessibility semantics, keyboard matrix, responsive breakpoints. | Component library choice and CSS architecture. `[TBD-FE · tech implementation]` |
| Cost and analytics semantics, correlation IDs, privacy constraints. | Telemetry vendor, storage schema, dashboard implementation. `[TBD-INFRA · architecture stage]` |
| Packaging constraints and plan dimensions. | Price points, billing provider, invoice/tax implementation. `[TBD-BIZ]` / `[TBD-BE]` |
| Export format promise and validation expectations. | Renderer, font embedding, SVG-to-PPTX conversion, artifact storage. `[TBD-BE · tech implementation]` |
### 6.3 Priority definitions
| Priority | Meaning | Release rule |
| --- | --- | --- |
| **P0** | M1 pilot gate. Required for the first paid pilot cohort; no manual workaround is acceptable for a core product promise. | Cannot exit M1 without it. |
| **P1** | M1 hardening or M2. Required before broadening the pilot or self-serve launch; the first cohort may proceed with a documented limitation. | May trail the first M1 cohort; must close before M2 or be explicitly waived. |
| **P2** | Later. Valuable but not required for M1 or M2. | Scheduled after M2 (M3 or later). |

**How to read the priority mix.** P0 is the M1 scope boundary, not a severity or effort ranking. Because a paid pilot exercises the complete six-stage loop, most core-flow requirements are P0 by definition; treating them as "nice to have" would ship a demo, not a pilot. P1 exists for behavior that improves the pilot but has a documented fallback: the page-count deviation warning, section-level page insertion, responsive/mobile layout under a desktop-first pilot `[ASSUMPTION]`, operational alerting, and similar hardening. Risk and effort are managed through the milestone sequence and the M1 go/no-go checklist, not by demoting the core loop.

`[CONFLICT]` C-1: UX §5 labels R3 and R7 as P1; BM §0 and §11.3 make them paid-launch blockers. BM wins for release gating; both are P0 here.

---
## 7. End-to-end experience
### 7.1 Six-stage overview
| Stage | User intent | User actions | Agent work | Exit gate |
| --- | --- | --- | --- | --- |
| **Material intake** | Start with a topic and, optionally, my own material. | Enter topic; optionally paste text, upload/drag files, or add URLs; remove chips; choose mode; start. | None; transition to Research + interview. | Non-empty topic. Materials optional; empty slot means web-only path [FLOW §2 stage 1]. |
| **Research + interview** | Make the deck targeted, not generic. | Answer four basic questions one at a time; edit answers; confirm gaps or choose "not needed"; review/edit profile; generate outline. | Digest materials, propose gaps, run targeted supplements, generate profile. | Profile generated and not `profileDirty`; user confirms outline generation [FLOW §2 stage 2]. |
| **Outline** | Control structure cheaply. | Edit titles; move/insert/delete; drag or use keyboard; confirm. | Stream outline JSON; render sticky notes; warn on page-count deviation. | User confirms, or automatic 3-second countdown completes after the outline streams [FLOW §2 stage 3]. |
| **Plan draft** | Control layout before style. | Inspect pages; re-plan; tweak; confirm. | Plan each page as a grayscale Bento wireframe. | All pages complete and no page in error; confirm, or automatic advance in fully automatic mode [FLOW §2 stage 4]. |
| **Style selection** | Choose the visual system. | Select one of four styles; optionally remember; confirm. | Apply preview styling; no page generation yet. | Style selected; confirm enabled [FLOW §2 stage 5]. |
| **Design draft** | Get finished pages and export. | Page through; regenerate; restore previous version; tweak; export. | Generate design page by page; variants and history; validation; export. | Real artifact produced and downloadable; export success is never shown without a file [FLOW §2 stage 6; §6]. |
### 7.2 Global shell
- **Top bar:** logo, project name, stage nav, mode badge, restart control; skip link before the bar [FLOW §1, §5].
- **Stage nav:** completed stages are clickable; future stages are disabled; stale stages show an amber dot and explicit `aria-label="needs rerun"`; current stage has `aria-current="step"` [FLOW §1, §3.4].
- **Mode badge:** always shows fully automatic or expert copilot [FLOW §1].
- **Mobile:** at ≤920px the stage nav becomes a native `<select>` with equivalent reachability and stale text [FLOW §5, §7.3].
- **Restart:** requires a confirmation modal with default focus on Cancel; active jobs are cancelled and project state is cleared [FLOW §2 stage 1; §4; UX 1.5].
### 7.3 Stage reachability and back navigation
| Stage | Reachable when | Entry effect | Locked state |
| --- | --- | --- | --- |
| Material intake | Always; restart confirmation if a project already has content. | Shows current topic/materials or a new project form. | N/A |
| Research + interview | A topic exists or research has started. | Resumes incomplete research or restores the conversation. | Disabled before topic start. |
| Outline | Profile generated and not `profileDirty`. | Restores outline; reruns if the outline is stale/unconfirmed. | Blocked with "update the profile first" when dirty. |
| Plan draft | Outline confirmed. | Restores plan; reruns stale/missing pages. | Disabled before outline confirmation. |
| Style selection | Plan complete, or plan pages exist in the prototype. | Restores selection; no rerun. | Disabled before a usable plan. |
| Design draft | Style confirmed. | Restores design; reruns stale pages. | Disabled before style confirmation. |

Back navigation is always available to a reachable stage. Changing an upstream artifact marks downstream stages stale; entering a stale stage automatically reruns the missing/stale artifacts [FLOW §1, §3.4].
### 7.4 Auto-advance rules
| Transition | Fully automatic | Expert copilot | Pause / exception rules |
| --- | --- | --- | --- |
| Research + interview → Outline | Explicit profile confirmation; no countdown. | Explicit profile confirmation. | `profileDirty` blocks Outline in both modes. [CONFLICT C-2] |
| Outline → Plan draft | 3-second countdown after the outline streams; Pause button. | Explicit "Outline looks good, generate plan draft". | Any title edit, add/delete, or sort auto-pauses; if focus is in an input/editable area at zero, pause instead of navigating; navigating away clears the countdown. |
| Plan draft → Style selection | Automatic after all pages complete. | Explicit "Confirm plan draft, choose style". | A page in `error` or pending keeps the gate closed. |
| Style selection → Design draft | Explicit style selection and confirm. | Explicit style selection and confirm. | Confirm disabled until a style is selected. |
| Design draft → Export | Explicit export action. | Explicit export action. | Export is never automatic. |

Both modes keep the same stage sequence, data, stale matrix, failure contracts, and per-page controls. Auto-advance never skips a gate that requires a user decision: profile confirmation, style selection, and export [FLOW §1, §2].
### 7.5 Long-task behavior
| Concern | Required behavior | Prototype today |
| --- | --- | --- |
| Background continuation | Navigating away from a generating stage does not abort the job; the job continues and the UI restores its state on return. | Navigating aborts the flow via a run token [FLOW §1, §6]. |
| Cancellation | The user can cancel a job explicitly; cancelled is a visible state; cancellation does not produce a success artifact. | No explicit cancel; navigation aborts. |
| Reconnect | Refresh, tab close, or network loss does not duplicate or lose generation; reconnecting restores project state, page statuses, and history. | In-memory only; refresh resets. |
| Page locking | Selecting a thumbnail during generation pins the current page; remaining pages continue in the background. | Implemented client-side [FLOW §2 stage 6]. |
| Queueing | Jobs are queued and bounded; per-page work does not run unbounded in parallel. | Simulated serially. |
| Failure/timeout | A timeout or model error sets a per-page error state with Retry; other pages continue. | Error status is reserved, never triggered [FLOW §3.1]. |
### 7.6 Fully automatic vs expert copilot
| Dimension | Fully automatic | Expert copilot |
| --- | --- | --- |
| Default at project start | Yes [FLOW §2 stage 1]. | No. |
| Stage confirmations | Profile, style, and export remain explicit; outline and plan auto-advance per §7.4. | Every stage ends at a confirmation control. |
| Outline countdown | 3 seconds, pausable, edit-paused [FLOW §2 stage 3]. | No countdown. |
| Per-page regenerate/tweak/history | Available throughout Design draft. | Available throughout Design draft. |
| Stale propagation and rerun | Same matrix; rerun on entry. | Same matrix; rerun on entry. |
| Background jobs and page locking | Same. | Same. |
| Failure recovery | Same. | Same. |
| Mode switching mid-project | Not required for M1; `[TBD-UX]` (PRD-04). | Not required for M1. |

---
## 8. Functional requirements
### 8.1 Requirement conventions
| Status | Meaning |
| --- | --- |
| `Prototype` | The interaction exists in the clickable prototype. All model, search, parsing, and export behavior behind it is mocked unless the requirement says otherwise [FLOW §5]. A parenthetical qualifier states the part that is real, e.g. `state only`, `client guard`, or `metadata only`. |
| `Designed` | Specified in FLOW/SRC/BM, not implemented. |
| `Contract` | A failure/recovery contract exists in FLOW §6, but the behavior is not implemented. |
| `Missing` | Neither implemented nor fully specified; must be built/decided. |

`Prototype` is not production evidence. A P0 requirement that promises real ingestion, real generation, real export, real persistence, or real recovery is `Missing` or `Contract` even if a mock UI exists. Every P0 row below has testable acceptance criteria. Sources in the last column identify the product fact; they do not imply implementation. IDs are stable identifiers; non-contiguous suffixes indicate items removed or deferred during v1 trimming, not missing requirements.
### 8.2 FR-1 Material intake
| ID | Requirement | Pri | Status | Acceptance criteria | Source |
| --- | --- | --- | --- | --- | --- |
| FR-1.1 | The system MUST require a non-empty topic before starting a project. | P0 | Prototype | • Empty submit: no stage change; topic input focused; visible message.<br>• Non-empty topic: enters Research + interview. | FLOW §2 stage 1; UX 1.1 |
| FR-1.2 | The material slot MUST be optional; an empty slot MUST start the web-only research path. | P0 | Prototype | • Zero materials: no material tool cards; no-material opening script and web path.<br>• Materials present: material-first script. | FLOW §2 stages 1–2; SRC §4.2 |
| FR-1.3 | The system MUST accept pasted text as one material with a submit shortcut and a removable chip. | P0 | Prototype | • Paste text creates a `paste` chip.<br>• Cmd/Ctrl+Enter submits; empty paste is rejected with a message. | FLOW §2 stage 1; SRC §4.2 |
| FR-1.4 | The system MUST accept files by picker and drag-and-drop, multiple per action, showing filename, type, and size. | P0 | Prototype (metadata only) | • Drop/select N files creates up to the remaining quota of chips.<br>• Chip shows name, type, size; no parse-success claim until real parsing succeeds. | FLOW §2 stage 1; SRC §4.2 |
| FR-1.5 | The system MUST accept URLs, auto-prefix `https://`, validate format, and reject invalid input inline without losing the entered text. | P0 | Prototype | • `example.com` becomes `https://example.com`.<br>• Malformed URL: inline error, no chip, input preserved. | FLOW §2 stage 1; UX 1.3 |
| FR-1.6 | Added materials MUST appear as removable chips; removal MUST update the count and restore capacity. | P0 | Prototype | • Remove chip: count decrements; capacity restored.<br>• Removed material does not appear in Research + interview. | FLOW §2 stage 1 |
| FR-1.7 | The material count MUST be visible. Adding at the limit MUST be blocked with an explanation; a multi-file add over the limit MUST add only the remaining quota and explain what was skipped. The real default limit is `[TBD-UX]`; the prototype's 6 is a demo constraint. | P0 | Prototype | • Count shows `N / limit`.<br>• At limit: add entry disabled; over-limit add shows a specific message; no silent drop.<br>• Removing a chip re-enables adding. | FLOW §2 stage 1; UX 1.2; BM §6.2 note; SRC §5 |
| FR-1.8 | The real product MUST define and enforce a supported file-type list and per-file size/page limits before development; unsupported or oversized files MUST be rejected with a specific reason. | P0 | Missing | • Supported list is published in-product.<br>• Unsupported extension gets a specific error and no success chip.<br>• Oversized file is rejected before parse with a specific error. | SRC §4.2; TBD-BE-1 |
| FR-1.9 | The system MUST parse supported files server-side. A parse failure MUST mark that material "not digested", allow removal/replacement, and MUST NOT block other materials or the project. | P0 | Missing | • Corrupted file shows a failed tool card and "not digested".<br>• Other materials complete; user can continue with remaining sources.<br>• Project does not dead-end. | FLOW §6; SRC §4.2; UX R4 |
| FR-1.10 | The system MUST fetch and extract readable content from URLs. On login wall, anti-scraping, or 404 it MUST show a failure state suggesting body-text paste and keep other sources. | P0 | Contract | • 404/login wall shows failure + paste suggestion.<br>• Other sources remain usable.<br>• No fabricated source content. | FLOW §6; SRC TBD-BE-2 |
| FR-1.11 | Materials and provenance MUST persist across all stages and MUST appear in the Research + interview source panel. | P0 | Prototype | • Navigate to Outline and back: materials unchanged.<br>• Each material appears under "Your materials". | FLOW §2 stage 2; SRC §5 |
| FR-1.12 | The product MUST show a data-handling notice at intake, SHOULD default to no training on customer data pending BM-7 (recommended default), and MUST support deletion/retention per policy. | P0 | Missing | • Notice appears before the first material is added.<br>• No-training commitment has contractual/config evidence.<br>• Deleting a project removes materials and derived artifacts within the `[TBD-BIZ]` SLA. | BM §8.4, §10.3, BM-7; NFR-PRIV |
| FR-1.13 | Material intake MUST expose both generation modes: fully automatic (default) and expert copilot. The selection MUST set the mode badge and the later auto-advance behavior; mid-project mode switching is not required for M1. | P0 | Prototype | • Default is fully automatic.<br>• Selecting expert copilot changes the badge and disables auto-advance at outline/plan.<br>• Arrow keys switch modes when the mode group has focus. | FLOW §2 stage 1, §7.1; PRD-04 |
| FR-1.14 | Material intake SHOULD offer scenario shortcut chips that fill an example topic without submitting it. | P1 | Prototype | • Four chips are available.<br>• Activating a chip fills the topic field and moves focus to the start control.<br>• No project starts until the user submits. | FLOW §2 stage 1, §4 |
### 8.3 FR-2 Research + interview
| ID | Requirement | Pri | Status | Acceptance criteria | Source |
| --- | --- | --- | --- | --- | --- |
| FR-2.1 | The opening script MUST branch on whether materials exist. | P0 | Prototype | • With materials: "digest materials first, then fill gaps".<br>• Without materials: "search the web first". | FLOW §2 stage 2 |
| FR-2.2 | The Agent MUST show one tool card per material (`read_paste_text`, `ingest_file`, `fetch_url` equivalent), complete each independently, and add successful material to "Your materials". | P0 | Prototype | • One card per material; cards complete independently.<br>• Failed material follows FR-1.9/1.10 and does not block others. | FLOW §2 stage 2; SRC §4.2 |
| FR-2.3 | The system MUST ask four basic single-choice questions one at a time. | P0 | Prototype | • Only the current question is interactive.<br>• Answered questions collapse to "Recorded: X · Edit".<br>• All four are answered before the profile can be generated. | FLOW §2 stage 2; UX 2.1 |
| FR-2.4 | The user MUST be able to edit any answered question. Editing MUST overwrite that answer only, not increment a count, and MUST mark `profileDirty` if the profile was already shown. | P0 | Prototype | • Change an answer twice: still one answer, not three.<br>• Profile shows "Needs update"; Outline entry is blocked. | FLOW §2 stage 2; UX 2.2 |
| FR-2.5 | With materials, the Agent MUST show a material digest card explaining what was extracted per material before gap suggestions. | P0 | Prototype | • Digest appears after material processing resolves.<br>• Each material has an entry; not a generic summary.<br>• Gap card does not appear before the digest. | FLOW §2 stage 2; UX 2.5 |
| FR-2.6 | With materials, the Agent MUST propose three gap suggestions, each with a reason and a recommended flag; recommended items MUST be pre-checked. | P0 | Prototype | • Exactly three suggestions in the M1 flow.<br>• Each has a reason and a suggested/recommended badge.<br>• Recommended items start checked; user can uncheck. | FLOW §2 stage 2; SRC §4.2, §5 |
| FR-2.7 | The user MUST be able to add/remove gaps or choose "Not needed — just use my materials", which clears other selections and skips web. | P0 | Prototype | • "Not needed" clears all gap selections.<br>• No web search follows; profile Web row says "No web". | FLOW §2 stage 2; UX 2.9 |
| FR-2.8 | For each selected gap, the Agent MUST run a targeted web search, not a blanket search, and light up the Web supplements group item by item. | P0 | Prototype | • N selected gaps produce N targeted search tool cards.<br>• Zero selected gaps produce no searches.<br>• Each source appears as it arrives. | FLOW §2 stage 2; SRC §2.3 |
| FR-2.9 | With no materials, the Agent MUST run the default web research path. The prototype uses four searches and twelve sources; real counts are `[TBD-BE]`. | P0 | Prototype | • No-material project uses the web-first opening script.<br>• Prototype shows 4 search cards and 12 sources; production count is configurable. | FLOW §2 stage 2; SRC §4.2 |
| FR-2.10 | Zero search results MUST keep the gap/question, state that nothing was found, and offer continue or adjust gaps. The system MUST NOT silently skip. | P0 | Contract | • Simulated zero results shows a visible "not found" message.<br>• User can continue; profile records the missing supplement. | FLOW §6 |
| FR-2.11 | The Agent MUST judge material sufficiency after digest. The user MUST NOT be asked to self-diagnose gaps from a hardcoded list. | P0 | Prototype (mock judgment) | • Gap card appears only after digest.<br>• User only confirms/removes Agent suggestions; no "what is missing?" self-report. | SRC §2.3, §5; UX §3.1 |
| FR-2.12 | The system MUST generate the requirements profile only after all basic questions are answered. The profile MUST include audience, goal, page count, style/mood, materials, web, and content strategy. | P0 | Prototype | • Profile generation is unavailable before all four answers.<br>• All seven fields are present.<br>• With materials, the strategy row states material-first conflict handling. | FLOW §2 stage 2; SRC §5 |
| FR-2.13 | The profile MUST be editable. If answers change after the profile is shown, the system MUST set `profileDirty` and block Outline until "Update profile". | P0 | Prototype | • Edit answer: Outline nav blocked with message.<br>• Update profile: unblocked; status returns to aligned. | FLOW §2 stage 2; UX 2.3 |
| FR-2.14 | Updating the profile after an outline exists MUST mark the outline unconfirmed and plan/design stale. | P0 | Prototype (state only) | • After update, Outline requires reconfirmation.<br>• Plan and Design show "needs rerun"; entering them reruns. | FLOW §3.4 |
| FR-2.15 | The source panel MUST show two groups, "Your materials" and "Web supplements", with counts, empty states, and skeleton loading states; "Your materials" is hidden when none exist. Every shown source MUST have a title, summary, and origin; placeholders that look real are prohibited. | P0 | Prototype | • With materials: both groups appear.<br>• Without materials: only Web group.<br>• Skeleton precedes web results; count updates; no source lacks title/summary/origin. | FLOW §2 stage 2; SRC §5; UX 2.7 |
| FR-2.16 | Content conflict priority MUST be first-party materials > organizational assets > web supplements. The profile MUST state it, and outline generation MUST follow it. | P0 | Designed | • Profile strategy row states the priority.<br>• Reviewer finds no case where web overrides a first-party fact.<br>• Missing/conflicting data is surfaced, not invented. | SRC §5; FLOW §2 stage 2 |
| FR-2.17 | Interview answers and the requirements profile MUST be injected into outline generation as content constraints and sources. | P0 | Designed | • Changing audience/goal/page count/style changes the profile and the outline request context.<br>• Outline page count is measured against the agreed count.<br>• Reviewer sees profile constraints reflected in titles/structure. | SRC §1.5, §5; FLOW §3.3 |
| FR-2.18 | After the profile exists, the user SHOULD be able to change web scope and re-search without restarting the entire research flow. | P1 | Missing | • "Change gaps / re-search" re-runs selected gap searches and updates the profile.<br>• Material digestion is not repeated unnecessarily.<br>• `[TBD-FE]` interaction is resolved before build. | FLOW §2 stage 2; SRC §5; TBD-FE-1 |
| FR-2.19 | The system MUST enforce a configurable cap on sources/searches per project or plan; hitting the cap MUST be visible, not silent. | P0 | Missing | • Setting cap N stops further searches at N.<br>• User sees a cap notice; profile records the cap.<br>• No silent omission. | BM §5, §5.1 rule 4 |
| FR-2.20 | The M1 product MUST use a real web search service for gap filling and the no-material path; mock search results MUST NOT be served on the paid path. Every result MUST carry a title, summary, and origin and MUST follow the zero-results and failure contracts. | P0 | Missing | • Selected gaps produce real queries and real results.<br>• No result is fabricated or copied from built-in demo data.<br>• Zero results and provider failure behave per §8.9.2. | SRC §4.2; FLOW §2 stage 2, §6; Appendix A |
| FR-2.21 | Gap confirmation is a material strategy and MUST NOT be editable at the profile stage. Changing gaps requires re-search (P1) or restarting research (M1 fallback). | P0 | Prototype | • Profile has no gap-edit control.<br>• "Change gaps" routes to restart in M1; after FR-2.18, it routes to re-search. | FLOW §2 stage 2; SRC §5 |
| FR-2.22 | On desktop, the Research + interview conversation MUST be an independent scroll container that follows new content without stealing focus; on mobile it MUST scroll with the page. | P1 | Prototype | • Long conversation does not stretch the page on desktop.<br>• New content follows without moving focus out of an active control.<br>• Mobile uses page scroll. | FLOW §2 stage 2; UX 2.6 |
### 8.4 FR-3 Outline
| ID | Requirement | Pri | Status | Acceptance criteria | Source |
| --- | --- | --- | --- | --- | --- |
| FR-3.1 | The outline MUST stream and render sticky notes incrementally; the user MUST see notes before the full response completes. | P0 | Prototype | • First note appears before stream completion.<br>• Notes fly in one by one; no blank wait for the full deck. | FLOW §2 stage 3 |
| FR-3.2 | Cover, TOC, and end MUST be fixed-position notes with editable titles and no delete action. | P0 | Prototype | • Title edit works.<br>• No delete affordance; delete cannot remove these notes. | FLOW §2 stage 3 |
| FR-3.3 | Body pages MUST be grouped by section; each note MUST show page number, title, and key content keywords. | P0 | Prototype | • Section grouping matches the outline structure.<br>• Note displays number/title/keywords.<br>• Page count and section count are visible. | FLOW §2 stage 3 |
| FR-3.4 | The user MUST be able to edit a note title inline; Enter saves. A title change MUST invalidate design only, per the stale matrix. | P0 | Prototype | • Inline edit; Enter saves.<br>• Design shows needs rerun; plan keeps the page and re-renders the header. | FLOW §2 stage 3, §3.4 |
| FR-3.5 | The user MUST be able to move a page up/down within its section via buttons and `Alt + ↑/↓`; boundary buttons are disabled. | P0 | Prototype | • Button and keyboard move produce the same order.<br>• First/last item cannot move beyond the section. | FLOW §2 stage 3; §7.1 |
| FR-3.6 | The user MUST be able to insert a page after a note and insert a page at section level; the user MUST be able to delete a page. | P0 | Prototype | • Insert adds a note in the correct section.<br>• Delete removes the note and its plan/design artifacts.<br>• Cover/TOC/end remain non-deletable. | FLOW §2 stage 3; UX 3.7 |
| FR-3.7 | The user MUST be able to drag notes across sections and reorder them; dropping on a note inserts before it. | P0 | Prototype | • Cross-section drag updates grouping and order.<br>• Drop target semantics match "insert before".<br>• Result matches the post-drag page count. | FLOW §2 stage 3, §4 |
| FR-3.8 | Sticky notes MUST support keyboard alternatives: `Alt + ↑/↓` within a section and `Shift + Alt + ←/→` to move to the end of an adjacent section. | P0 | Prototype | • Focused note moves with both shortcuts.<br>• Focus remains on the moved note.<br>• No pointer-only ordering operation exists. | FLOW §2 stage 3, §7.1; UX 3.1 |
| FR-3.9 | The outline MUST show "N pages · M sections" and warn when the page count is more than two pages off the agreed count. The warning is non-blocking. This is pilot hardening, not a first-cohort gate. | P1 | Prototype | • Agreed + 3: warning visible.<br>• Agreed + 2: no warning.<br>• Confirm remains available. | FLOW §2 stage 3 |
| FR-3.10 | The outline MUST NOT advance to Plan draft in expert copilot without explicit confirmation; fully automatic mode uses the countdown in FR-3.11. | P0 | Prototype | • No navigation before confirm/countdown.<br>• Confirm enabled only after the outline is complete. | FLOW §2 stage 3 |
| FR-3.11 | In fully automatic mode, the outline MUST show a 3-second countdown and a Pause control. Any title edit, add/delete, or sort MUST auto-pause; if focus is in an input/editable area at zero, the system MUST pause instead of navigating. | P0 | Prototype | • Countdown visible and pauses on demand.<br>• Edit/add/delete/sort pauses with an explanation.<br>• Focus in an input at zero prevents navigation. | FLOW §2 stage 3; UX §3.2 |
| FR-3.12 | Every outline change MUST apply the stale propagation matrix in §8.9.1; affected downstream stages MUST show "needs rerun". | P0 | Prototype (state only) | • Each of the seven matrix rows passes its expected plan/design state.<br>• Stage nav shows amber dot plus aria-label.<br>• No stale artifact is presented as current. | FLOW §3.4 |
| FR-3.13 | Page and section deletion SHOULD offer toast undo or confirmation; the current prototype deletes immediately. | P1 | Missing | • Delete shows an undo window or confirmation.<br>• Undo restores page, position, and section membership. | UX §5 R2; FLOW §6 |
| FR-3.14 | Updating the profile after an outline exists MUST mark the outline unconfirmed; Plan/Design MUST NOT rerun until the outline is reconfirmed. | P0 | Prototype | • Outline shows unconfirmed state.<br>• Plan/Design entry prompts reconfirmation.<br>• After reconfirmation, plan/design rerun per matrix. | FLOW §3.4 |
| FR-3.15 | A section-level insert MUST add a page to that section and mark plan and design stale. | P1 | Prototype | • New page belongs to the section.<br>• Plan and design show needs rerun. | FLOW §2 stage 3; UX 3.7 |
### 8.5 FR-4 Plan draft
| ID | Requirement | Pri | Status | Acceptance criteria | Source |
| --- | --- | --- | --- | --- | --- |
| FR-4.1 | Each page MUST render as a 16:9 grayscale Bento wireframe with visible "what goes here" card labels; plan MUST use the six-combination layout vocabulary. | P0 | Prototype | • Every content page has one of the six layout types.<br>• Wireframe is grayscale; no style is applied.<br>• Card labels describe content placement. | FLOW §2 stage 4, §5; EXTRACT §II.4 |
| FR-4.2 | The left page list MUST be grouped by section and show per-page status: pending, planning, done, or error. Status MUST NOT be conveyed by color alone. | P0 | Prototype | • Status has text/icon plus `aria-label`.<br>• Error is distinguishable from pending/planning/done.<br>• Grouping matches the outline sections. | FLOW §2 stage 4; UX 4.2 |
| FR-4.3 | The plan MUST show completion progress; unplanned pages MUST show a skeleton placeholder, not a finished-looking wireframe. | P0 | Prototype | • Progress reflects completed/total pages.<br>• Pending page shows skeleton and `aria-busy`.<br>• No "final" wireframe before generation. | FLOW §2 stage 4; UX 4.3 |
| FR-4.4 | The confirm control MUST be enabled only when all pages are done and none is in error. | P0 | Prototype | • One pending page keeps confirm disabled.<br>• One error page keeps confirm disabled until retry.<br>• All done enables confirm. | FLOW §2 stage 4; UX 4.1 |
| FR-4.5 | The user MUST be able to re-plan the current page, producing a new layout variant without re-planning other pages. | P0 | Prototype | • Re-plan changes only the current page.<br>• Other page statuses/content remain unchanged.<br>• Design is marked stale. | FLOW §2 stage 4 |
| FR-4.6 | The user MUST be able to enter a natural-language tweak for the current page; an empty instruction MUST show an inline error. | P0 | Prototype | • Tweak re-renders only the current page.<br>• Empty instruction shows a field error and does not submit.<br>• Design is marked stale. | FLOW §2 stage 4; UX 4.5 |
| FR-4.7 | Re-plan or tweak on a page MUST mark the design draft stale. | P0 | Prototype (state only) | • Design stage shows needs rerun after each operation.<br>• Other pages' design state is unchanged until rerun. | FLOW §3.4 |
| FR-4.8 | A page generation timeout or model error MUST set that page to `error` with "Retry this page"; other pages MUST continue. | P0 | Contract | • Error page shows retry.<br>• Other pages complete.<br>• Confirm remains disabled while the error persists. | FLOW §6; FLOW §3.1 |
| FR-4.9 | Plan generation MUST proceed page by page so completed pages can be inspected while later pages are pending. | P0 | Prototype | • Page N can be opened while N+1 is planning.<br>• Statuses update independently.<br>• No all-or-nothing blank state. | FLOW §2 stage 4 |
| FR-4.10 | In fully automatic mode, complete plan draft MUST auto-advance to Style selection; expert copilot MUST wait for confirm. | P0 | Prototype | • Auto mode advances only after all pages complete.<br>• Copilot mode does not advance without confirm.<br>• Error/pending page blocks both. | FLOW §1, §2 stage 4 |
| FR-4.11 | Single-page re-plan MUST preserve unchanged pages and MUST NOT trigger a full-deck re-plan. | P0 | Prototype | • Only the current page emits a new plan job.<br>• Other pages keep their layout and do not enter planning.<br>• Cost telemetry records one page. | BM §5.1 rule 1; NFR-COST-3 |
### 8.6 FR-5 Style selection
| ID | Requirement | Pri | Status | Acceptance criteria | Source |
| --- | --- | --- | --- | --- | --- |
| FR-5.1 | Style selection MUST show four cards, each with a representative page preview, palette, and use-case description. | P0 | Prototype | • Four cards render.<br>• Each has preview, palette, and description.<br>• Previews use the actual style tokens, not placeholder colors. | FLOW §2 stage 5 |
| FR-5.2 | Style cards MUST be a single-select radiogroup with `aria-checked`; arrow keys MUST move and select. | P0 | Prototype | • Only one card selected.<br>• Arrow keys move focus and selection.<br>• Screen reader announces selected style. | FLOW §2 stage 5; UX 5.2 |
| FR-5.3 | The confirm control MUST be disabled until a style is selected. | P0 | Prototype | • Fresh project: confirm disabled.<br>• Selecting any style enables confirm. | FLOW §2 stage 5 |
| FR-5.4 | "Remember my preference" SHOULD persist the selection. The prototype uses `localStorage`; the real product is account-scoped `[TBD-BE]`. | P1 | Prototype | • Checked preference is preselected next time.<br>• "Last used" is shown.<br>• Account-scoped behavior is verified after accounts exist. | FLOW §2 stage 5; TBD-BE |
| FR-5.5 | Changing the style after design generation MUST mark design stale; it MUST NOT change the outline or plan. | P0 | Prototype (state only) | • Plan remains unchanged.<br>• Design shows needs rerun.<br>• Rerun applies the new style to all pages. | FLOW §3.4 |
| FR-5.6 | The selected style MUST apply consistently to all design pages and be reported in the export scope summary. | P0 | Prototype | • Every page uses the selected style ID.<br>• Export summary names the style.<br>• No mixed-style page unless explicitly designed. | FLOW §2 stages 5–6 |
### 8.7 FR-6 Design draft and export
| ID | Requirement | Pri | Status | Acceptance criteria | Source |
| --- | --- | --- | --- | --- | --- |
| FR-6.1 | Design draft MUST use a three-column workbench: left thumbnail list grouped by section with status, center 16:9 canvas, right current-page actions. | P0 | Prototype | • Three regions render at desktop width.<br>• Thumbnails grouped by section.<br>• Canvas is 16:9. | FLOW §2 stage 6 |
| FR-6.2 | Design pages MUST generate page by page with per-page status and progress. | P0 | Prototype | • Thumbnails show generating/done/error.<br>• Progress reflects completed/total.<br>• Completed pages are inspectable during generation. | FLOW §2 stage 6; UX 6.4 |
| FR-6.3 | Selecting a thumbnail during generation MUST pin the current page; remaining pages MUST continue generating in the background. | P0 | Prototype (client) | • Generation does not steal the selected page back.<br>• Remaining pages complete.<br>• Pinned page state survives navigation within the stage. | FLOW §2 stage 6; UX 6.3 |
| FR-6.4 | "Regenerate" MUST regenerate only the current page and rotate to a new variant. | P0 | Prototype | • Only the current page changes.<br>• Variant increments for multi-layout pages.<br>• No other page is regenerated. | FLOW §2 stage 6 |
| FR-6.5 | Each page MUST keep a history stack; "Previous version" MUST restore the prior variant. | P0 | Prototype | • Regenerate twice: Previous version returns to the immediately prior variant.<br>• History count updates.<br>• History is per page. | FLOW §2 stage 6; UX 6.1 |
| FR-6.6 | Cover, TOC, and end MUST NOT fake a variant increment; because they have one layout, the UI MUST prompt the user to use a tweak instead. | P0 | Prototype | • Regenerate on a single-layout page does not show V2.<br>• UI explains that the page has one layout and suggests a tweak.<br>• Visual result is not falsely changed. | FLOW §2 stage 6; UX 6.2 |
| FR-6.7 | The user MUST be able to enter a natural-language tweak for the current page; an empty instruction MUST show a field error. | P0 | Prototype | • Tweak re-renders only the current page.<br>• Empty instruction does not submit.<br>• Prior variant is pushed to history. | FLOW §2 stage 6 |
| FR-6.8 | All page actions (regenerate, tweak, history, export scope) MUST be scoped to the current page except export, which is deck-level. | P0 | Prototype | • Regenerate/tweak/history affect one page.<br>• Export summary is deck-level.<br>• No "regenerate whole deck" action exists. | FLOW §2 stage 6 |
| FR-6.9 | While the current page is generating, page-level actions MUST show "please wait" and MUST NOT write concurrently to the same page. | P0 | Prototype | • Actions disabled during generation.<br>• Second click does not create a second job or history entry.<br>• Status remains consistent. | FLOW §6 |
| FR-6.10 | Export MUST present PPTX (SVG-composited, recommended), HTML, and PDF, with a scope summary of page count, style, and render completeness. | P0 | Prototype | • Three formats visible.<br>• PPTX marked recommended.<br>• Summary matches current project state. | FLOW §2 stage 6 |
| FR-6.11 | The export modal MUST use dialog semantics, a focus trap, Esc close, focus return to the trigger, and `role="progressbar"` with `aria-valuenow`. | P0 | Prototype | • Tab cycles inside the modal.<br>• Esc closes and returns focus.<br>• Progress is announced. | FLOW §2 stage 6, §7.2; UX 6.6 |
| FR-6.12 | Export MUST produce a real PPTX assembled from SVG-composited pages that opens in PowerPoint 2016+ and keeps text and shapes editable. | P0 | Missing | • File opens without repair in PowerPoint.<br>• Text and shape edits are possible.<br>• No image-only page substitution. | FLOW §2 stage 6; EXTRACT §IV; BM §0 #2 |
| FR-6.13 | Export MUST produce a real self-contained HTML file (self-containment is a proposed `[ASSUMPTION]`) and a real PDF with 16:9 pages matching the canvas. | P0 | Missing | • HTML opens offline without external dependencies.<br>• PDF page count and aspect match the deck.<br>• No placeholder files. | FLOW §2 stage 6; EXTRACT §VI #7 |
| FR-6.14 | Pre-export validation MUST detect missing fonts, out-of-bounds assets, empty pages, and incomplete renders, and MUST report the affected page and reason. | P0 | Missing | • Missing font is identified by page and font.<br>• Empty/out-of-bounds page is identified.<br>• Validation failure prevents a success claim. | UX §5 R7; BM §5.1 rule 5 |
| FR-6.15 | Export failure MUST show a reason, Retry, and Try another format; the modal MUST stay open; success MUST NOT be shown. | P0 | Contract | • Failure state shows all three elements.<br>• Retry is possible without redoing the deck.<br>• Modal remains open. | FLOW §6 |
| FR-6.16 | The system MUST NOT report export success until a real artifact exists and is downloadable. Mock progress or a success toast without a file is prohibited in production. | P0 | Missing | • Failed export: no success state.<br>• Success state has a resolvable download.<br>• Artifact size is greater than zero. | FLOW §6; UX 6.7 |
| FR-6.17 | Font and asset handling MUST embed or substitute per licensing, report substitutions, and reject or repair assets outside the canvas. | P0 | Missing | • Substitution is visible in the export report.<br>• No silent overflow.<br>• Licensed asset sources are documented. | BM §10.3, BM-11; UX R7 |
| FR-6.18 | Before M1 go-live, a manual PowerPoint fidelity matrix MUST pass: cover, TOC, all six content layouts, end page, at least two styles, text edit, shape edit, font substitution, PDF, and HTML. | P0 | Missing | • Signed checklist with zero blocker defects.<br>• Tested on the supported PowerPoint versions.<br>• Defects have owners and dates. | BM §0 #2, §11.3; NFR-COMPAT-4 |
| FR-6.19 | The export scope summary MUST reflect actual page count, style, and rendered completeness, including incomplete pages. | P0 | Prototype | • Summary matches thumbnail statuses.<br>• Changing a page updates the summary.<br>• Incomplete pages are not counted as rendered. | FLOW §2 stage 6; UX 6.5 |
| FR-6.20 | Export MUST NOT claim success when pages are incomplete, errored, or validation fails. The choice between blocking and partial export is `[TBD-UX]`; the user must be told which pages are excluded. | P0 | Missing | • Incomplete deck: no success without explicit scope.<br>• Excluded pages are named.<br>• No silent omission. | FLOW §6; PRD-03 |
| FR-6.21 | Re-export after any edit MUST use the current project state, not a stale cached artifact. | P0 | Missing | • Edit a page, export: artifact reflects the edit.<br>• Scope summary reflects the edit.<br>• No stale file is served. | FLOW §2 stage 6 |
### 8.8 FR-7 Cross-cutting requirements
| ID | Requirement | Pri | Status | Acceptance criteria | Source |
| --- | --- | --- | --- | --- | --- |
| FR-7.1 | The app MUST provide the global shell: logo, project name, stage nav, mode badge, restart, skip link. | P0 | Prototype | • All elements present on every stage.<br>• Skip link targets main content.<br>• Restart opens a confirmation. | FLOW §1, §5 |
| FR-7.2 | Stage navigation MUST allow any reachable stage, disable unreachable stages, and show stale status explicitly. | P0 | Prototype | • Reachability matches §7.3.<br>• Completed stages clickable; future stages disabled.<br>• Stale stage has amber dot and aria-label. | FLOW §1, §3.4 |
| FR-7.3 | Stale propagation MUST implement the matrix in §8.9.1 exactly; entering a stale stage MUST automatically rerun missing/stale artifacts. | P0 | Prototype (state only) | • All seven matrix rows pass.<br>• Rerun scope matches the affected artifact.<br>• No silent full-deck rerun. | FLOW §3.4 |
| FR-7.4 | At most one active write per page MUST be allowed; concurrent page actions MUST be rejected with a visible message; history MUST NOT receive duplicate entries. | P0 | Prototype (client guard) | • Second concurrent action is blocked.<br>• One history entry per completed operation.<br>• Backend enforces the same rule. | FLOW §6; FLOW §3.1 |
| FR-7.5 | Research, outline, plan, design, and export jobs MUST be queued, cancellable, and able to continue in the background across navigation, refresh, and network loss; reconnecting MUST restore state. | P0 | Missing | • Navigate away during generation: job continues.<br>• Refresh/disconnect: state restores without duplicate jobs.<br>• Cancel stops the job and leaves a consistent state. | FLOW §1, §6; UX R3; BM §10.1 |
| FR-7.6 | The failure and recovery contracts in §8.9.2 MUST be implemented and MUST NOT dead-end the user. | P0 | Contract | • Each of the 13 contract rows passes its expected behavior.<br>• Failure states are specific and actionable.<br>• No silent failure or fake success. | FLOW §6 |
| FR-7.7 | Undo and version semantics MUST be per-page for design variants; undo, previous version, stale markers, and recovery MUST be available on every plan. | P0 | Prototype | • Previous version restores the prior variant.<br>• No global cross-page history in M1 (R6/P2).<br>• Trust features are not gated by plan. | FLOW §2 stage 6; BM §6.4; UX R6 |
| FR-7.8 | Restart MUST require confirmation with default focus on Cancel; it MUST cancel active jobs and clear the current project state. | P0 | Prototype | • Cancel is the default focus.<br>• Confirm clears project content.<br>• Active jobs are cancelled, not orphaned. | FLOW §4; UX 1.5 |
| FR-7.9 | Project state MUST persist server-side: topic, materials, answers, profile, outline, plans, style, design, stale flags, and per-page history. Refresh or reconnect MUST restore the state. | P0 | Missing | • Refresh after each stage restores the stage.<br>• Stale markers survive refresh.<br>• No lost edits. | FLOW §3.1; FLOW §6 |
| FR-7.10 | The keyboard matrix in §8.9.3 MUST work; no core action may be pointer-only. | P0 | Prototype | • Every matrix row passes.<br>• Modal focus is trapped and restored.<br>• Sticky-note ordering and page navigation have keyboard paths. | FLOW §7.1; UX §5 R8 |
| FR-7.11 | Semantics and focus MUST include `role="log"`, a separate `role="status"` for milestones, `aria-busy`, `aria-current`, focus-visible rings, modal focus trap/restore, and stage-change focus to the heading. | P0 | Prototype | • Screen reader announces milestones, not every token.<br>• Focus moves to h1 on stage change.<br>• Closing a modal returns focus to its trigger. | FLOW §7.2 |
| FR-7.12 | Reduced motion MUST be honored; animation durations approach zero and typewriter text renders immediately. No information may exist only in animation. | P0 | Prototype | • With `prefers-reduced-motion: reduce`, typewriter outputs full text.<br>• Notes do not fly in.<br>• All content remains readable. | FLOW §7.4 |
| FR-7.13 | Body and secondary text MUST meet at least 4.5:1 contrast on the supported backgrounds; focus indicators MUST be visible. | P0 | Prototype | • Automated contrast audit passes all text.<br>• Focus ring is visible on every interactive element.<br>• Disabled state is distinguishable without relying on color alone. | FLOW §7.4; UX §6 |
| FR-7.14 | Responsive breakpoints in §8.9.4 MUST be implemented; the core flow MUST remain usable on each. The first pilot cohort is desktop-first `[ASSUMPTION]`, so this is hardening rather than a first-cohort gate. | P1 | Prototype | • 1440/1180/920/720/390 checks pass.<br>• Stage nav becomes a select at ≤920.<br>• No core action disappears. | FLOW §7.3 |
| FR-7.15 | Mobile behavior MUST keep the flow usable: page list becomes a horizontal strip, canvas is 680px with horizontal scrolling, brand/example chips trim at ≤480. This is pilot hardening, not a first-cohort gate. | P1 | Prototype | • Core actions remain reachable.<br>• Canvas is readable via horizontal scroll.<br>• No page-level horizontal scroll except the canvas. | FLOW §5, §7.3; UX 6.3 |
| FR-7.16 | Long-running work MUST show progress and per-page status; indefinite spinners without status are prohibited. ETA display is `[TBD-UX]`. | P0 | Prototype | • Progress visible during research/plan/design/export.<br>• Page statuses update.<br>• No operation appears frozen without a status. | FLOW §2 stages 4, 6; UX G8 |
| FR-7.17 | Mode behavior MUST match §7.6; both modes MUST share the same stages, gates, data, failure contracts, and per-page controls. | P0 | Prototype | • Mode badge correct.<br>• Auto-advance/pause rules match §7.4.<br>• Per-page controls available in both. | FLOW §1, §2; UX §3.2 |
| FR-7.18 | All model-generated artifacts in M1 (material digest, gap suggestions, profile, outline, plan, design, tweaks) MUST be produced by the configured model pipeline; the prototype's built-in mock content MUST NOT be served on the paid path. Each call MUST record stage, page, model tier, token usage, latency, and cost. | P0 | Missing | • An end-to-end deck is generated from the user's topic/materials, not demo data.<br>• No `MOCK` content is reachable in production.<br>• Cost and latency are attributed per call. | FLOW §5; BM §7; Appendix A; NFR-COST-1 |
### 8.9 Cross-cutting reference tables
#### 8.9.1 Stale propagation matrix
This matrix is normative and is reproduced from FLOW §3.4. It has exactly seven rows and is the acceptance basis for FR-3.12, FR-7.3, and NFR-COST-3.

| Change | Plan draft | Design draft | Notes |
| --- | --- | --- | --- |
| Edit page title | Keep (re-render page header) | Needs rerun | Layout unchanged; design page header needs re-rendering |
| Reorder within section | Keep | Needs rerun | Plan content unchanged; order affects the final deck |
| Move across sections | Needs rerun | Needs rerun | Grouping structure changes |
| Add / delete page | Needs rerun | Needs rerun | Deleting a page also clears its plan/slide |
| Re-plan / tweak single page | That page complete | Needs rerun | Layout change requires re-applying the style |
| Change style | Unchanged | Needs rerun | Affects the design draft only |
| Update requirements profile (outline already generated) | Needs reconfirmation | Needs rerun | Prototype marks the outline unconfirmed; after re-confirming the outline, rerun plan/design |

The stage nav MUST show an amber dot plus `aria-label="needs rerun"`; entering the stage MUST automatically rerun the missing/stale artifacts. A change MUST NOT invalidate more than the matrix says.
#### 8.9.2 Failure and recovery contracts
These thirteen rows are the v3 contract, not an implemented feature list [FLOW §6]. Each row is an acceptance case for FR-7.6.

| Scenario | Trigger | Required behavior | Prototype today | Owner |
| --- | --- | --- | --- | --- |
| Material parsing failure | Corrupted file / unsupported type | Tool card red state; mark material "not digested"; allow removal/replacement; do not block other materials | Not simulated | `[TBD-FE]` / `[TBD-BE]` |
| URL fetch failure | Login wall / anti-scraping / 404 | Failure state; suggest pasting the body text; keep other sources | Not simulated | `[TBD-BE]` |
| Zero search results | Gap too narrow / query returns nothing | Keep the gap/question; prompt "not found; continue/adjust gaps"; do not silently skip | Not simulated | `[TBD-FE]` |
| Single-page generation failure | Timeout / model error | Page status `error`; "Retry this page"; other pages continue | Not simulated | `[TBD-FE]` |
| Export failure | Missing font / out-of-bounds asset / write failure | Failure reason; Retry; Try another format; do not close the modal | Not simulated | `[TBD-FE]` |
| Leaving the page | Stage switch / refresh | Prototype aborts; a real product continues in the background and restores on return | Aborts | `[TBD-BE]` |
| Concurrent operations | Single-page action during generation | "Generating, please wait"; forbid writing the same page concurrently | Prevented | — |
| Profile dirty data | Answers changed after profile generation without update | Block Outline; prompt to update the profile first | Implemented | — |
| Downstream stale | Outline/plan/style change | Stage nav shows "needs rerun"; rerun on entry | Implemented | — |
| Delete page | Note "Delete" | Immediate delete in the prototype; a real product offers toast undo or confirmation | No undo | `[TBD-FE]` |
| Auto-advance | Fully automatic + editing | Detect editing and auto-pause; do not steal focus | Implemented | — |
| Material over limit | 7th item in the prototype | Entry disabled + limit hint | Implemented (6-item demo constraint) | `[TBD-UX]` |
| User changes gap decision | Wants to change web scope after profile | Real product supports "re-search and update profile"; M1 fallback is restart | Not supported; restart research | `[TBD-FE]` |
#### 8.9.3 Accessibility keyboard matrix
The matrix below is normative for FR-7.10 and is reproduced from FLOW §7.1.

| Area | Key | Behavior |
| --- | --- | --- |
| Global | `Tab` / `Shift + Tab` | Move in visual order; cycle within modals |
| Global | `Esc` | Close the current modal; focus returns to the trigger |
| Home mode | `←` / `→` / `↑` / `↓` | Switch between fully automatic and expert copilot |
| Interview | `Tab` + `Space` / `Enter` | Select an option; check gap items individually, then confirm |
| Sticky notes | `Alt + ↑/↓` | Move up/down within the section |
| Sticky notes | `Shift + Alt + ←/→` | Move to the end of an adjacent section |
| Sticky notes | `Enter` | Finish title editing and save |
| Style | `←` / `→` / `↑` / `↓` | Switch and select style cards |
| Design draft | `←` / `→` | Previous/next page |
| Export modal | `Tab` / `Shift + Tab` / `Esc` | Focus trap; close and return focus |

Additional semantics: conversation `role="log"` with `aria-live="off"`; milestones announced through a separate `role="status"`; question options `role="radio"` / `role="checkbox"` with `aria-checked`; canvas `role="img"` with `aria-label`; thumbnails decorative with `aria-hidden="true"`; generation container `aria-busy`; progress `role="progressbar"` with `aria-valuenow`; current stage `aria-current="step"`; needs-rerun stated in `aria-label` [FLOW §7.2].
#### 8.9.4 Responsive breakpoints
| Breakpoint | Layout |
| --- | --- |
| ≥1180 | Full two- or three-column research/plan/design |
| ≤1180 | Right panel moves below; design draft order "canvas → actions → thumbnails" |
| ≤920 | Top stage nav switches to a native `<select>` |
| ≤720 | Home single column; survey full-width; page list horizontal strip; canvas 680px with horizontal scroll |
| ≤480 | Trim brand and example chips; keep core actions |

Verification viewports: 1440, 1180, 920, 720, and 390 [UX §6].
### 8.10 FR-8 Project lifecycle and workspace
The sources define a single active project experience, not a multi-project workspace. Items not supported by a source are marked out of scope rather than invented.

| ID | Requirement | Pri | Status | Acceptance criteria | Source |
| --- | --- | --- | --- | --- | --- |
| FR-8.1 | A project MUST have a name; the default name is the topic; the name is visible in the top bar. | P0 | Prototype | • Starting with topic T shows T as the project name.<br>• The name is visible on every stage. | FLOW §1 |
| FR-8.2 | The user MUST be able to delete the current project, with confirmation, and the deletion MUST remove materials and derived artifacts. | P0 | Missing | • Confirmation is required.<br>• Materials/plans/designs/exports are removed per policy.<br>• Deletion completes within the `[TBD-BIZ]` SLA. | NFR-PRIV-1; BM §10.3 |
| FR-8.3 | Project list, rename, duplicate, and multiple projects per account are NOT required for M1; they are deferred to M2. | P2 | Missing | • No M1 acceptance test.<br>• Decision recorded in PRD-09 before M2. | FLOW scope; BM §10.1 |

---
## 9. Content and output requirements
### 9.1 CR-1 Five source channels
| Channel | Examples | M1 ingestion | Status |
| --- | --- | --- | --- |
| First-party work output | PRDs, proposals, design docs, reports, spreadsheets, old decks, screenshots, transcripts | Paste text, file upload, URL | Partial: UI mock; real parsing/fetch missing (R4) [SRC §1.1, §4.2] |
| Organizational knowledge | Internal wikis, policies, training decks, case/bid libraries, CRM exports | Authorized connectors | Out of M1; M3 [SRC §1.2, §4.3] |
| External public information | Search results, news, reports, public filings, papers, competitor public material | Web search, targeted to confirmed gaps | Mock only; real search missing [SRC §1.3] |
| Interpersonal and offline | Client RFP, quotes, email attachments, recordings, scans, brochures | File upload for documents; transcription later | Partial; recordings/scans later [SRC §1.4, §4.3] |
| In-head and conversation | A topic, keywords, spoken ideas, a rough outline, interview answers | Topic input, interview Q&A, profile | Implemented in the flow [SRC §1.5] |
### 9.2 CR-2 Ingestion priority
Paste text / drag files → URL fetch → (later) speech transcription → (later) authorized access to internal systems [SRC §4.1]. M1 MUST implement the first two. Later channels MUST NOT be implied as available in the M1 UI.
### 9.3 CR-3 Material sufficiency and gap logic
| Step | Required behavior | Source |
| --- | --- | --- |
| 1 | Digest each material and show what was extracted; one digest entry per material. | [FLOW §2 stage 2] |
| 2 | Judge whether the digested material is sufficient to support the requested deck. | [SRC §2.3] |
| 3 | Propose three gaps with reasons, recommended flags, and pre-checked recommended items. | [FLOW §2 stage 2; SRC §5] |
| 4 | User confirms, removes, or chooses "not needed"; "not needed" clears the others. | [FLOW §2 stage 2; SRC §5] |
| 5 | Run targeted web search per selected gap; show each source as it arrives. | [FLOW §2 stage 2] |
| 6 | If no gaps are selected, skip web entirely; the outline is material-only. | [FLOW §2 stage 2; UX 2.9] |
| 7 | Record materials and web scope in the profile; no gap editing at the profile stage. | [FLOW §2 stage 2; SRC §5] |

If there are no materials, the default web path applies: the prototype uses four searches and twelve sources; production counts are `[TBD-BE]` [FLOW §2 stage 2].
### 9.4 CR-4 Conflict priority
**First-party materials > organizational assets > web supplements** [SRC §5]. The priority MUST be stated in the profile and used by outline generation. When a first-party fact and a web claim conflict, the first-party fact wins; the web claim is supporting evidence at most. The system MUST NOT silently average or invent a compromise. Missing or contradictory data MUST be surfaced to the user rather than fabricated.
### 9.5 CR-5 Context injection and grounding
| Stage | Required context | Rule |
| --- | --- | --- |
| Outline | Topic, requirements profile, interview answers, material digests, selected web supplements | The outline MUST reflect the profile constraints and MUST use the selected sources; it MUST NOT assert externally verifiable facts absent from those inputs without flagging them. |
| Plan draft | Outline page, source page points, content type | Plan MUST use the selected page content and MUST NOT introduce new factual claims; layout only. |
| Design draft | Plan page, selected style, design vocabulary | Design MUST apply the style to the plan; it MUST NOT change the content scope. |
| Export | Current deck, style, validation state | Export MUST use current state and MUST report render completeness. |

Grounding acceptance: for each pilot deck, a reviewer samples at least 10 pages and traces every numeric or externally verifiable claim to the source panel or an interview answer; unsourced claims are flagged. `[ASSUMPTION]` This rubric is the M1 quality bar until an automated evaluation set exists.
### 9.6 CR-6 Output formats and fidelity expectations
| Format | Primary use | Fidelity expectation | M1 status |
| --- | --- | --- | --- |
| **PPTX (SVG-composited)** | Editable Office deliverable; recommended | Opens in PowerPoint 2016+; text and shapes editable; fonts/assets validated; no image-only pages | Missing; mock progress only [FLOW §2 stage 6; EXTRACT §IV] |
| **HTML** | Personal use where editability is not required | Self-contained single file (proposed `[ASSUMPTION]`); no external dependencies; opens offline | Missing; mock only [FLOW §2 stage 6; EXTRACT §IV] |
| **PDF** | Distribution and presentation | Fixed 16:9 pages matching the canvas; page count matches the deck | Missing; mock only [FLOW §2 stage 6] |

Trade-offs: PPTX carries the editability promise and the highest fidelity risk; HTML is the better fit for personal, non-editable use [EXTRACT §IV]; PDF is for distribution. The product MUST NOT treat PPTX success as implied by HTML or PDF success. The fixed canvas is 16:9; the source prompts use a 1280×720 reference [EXTRACT §III prompt 3; FLOW §3.3].
### 9.7 CR-7 Licensing and user responsibility
- The user is responsible for third-party content they supply; the product must provide clear terms and export warnings [BM §10.3, BM-11].
- Fonts, images, and icons used in SVG-composited exports require licensed sources or documented substitution; this is `[TBD-BIZ · legal, before paid launch]` [BM §10.3].
- Generated decks must not imply ownership of user-supplied third-party assets; the legal position is not asserted here.
- Export validation must not silently embed an unlicensed asset; it must report the substitution or block the export per policy.

---
## 10. Business rules and packaging constraints
These are product-level rules, not price decisions. No price point is asserted.

| ID | Rule | Rationale / source | Implication |
| --- | --- | --- | --- |
| BR-1 | The free tier MUST complete the full loop, including a capped PPTX export. The recommended packaging is no watermark, pending BM-3 `[TBD-BIZ · founder + product, before paid pilot]`. | The central claim is editable output; gating PPTX prevents verification [BM §6.2, BM-3]. | M2 packaging must expose a capped PPTX path. |
| BR-2 | Undo, per-page history, stale detection, accessibility, basic export, and error recovery MUST NOT be paywalled. | Trust features reduce churn and support cost [BM §6.4; §5.1 rule 7]. | Depth may differ later, but the core recovery loop is on every plan. |
| BR-3 | Plan dimensions are materials, pages, and regenerations. | These are the three cost-scaling dimensions [BM §5.1 rule 4; §6.3]. | Do not price by tokens or hide the dimensions. |
| BR-4 | A regeneration allowance MUST degrade gracefully; do not hard-stop mid-deck. | Regeneration is anxiety-inducing and cost-relevant [BM §6.2]. | User can still edit and export; extra regenerations next cycle. |
| BR-5 | Team and enterprise tiers MUST NOT be sold until collaboration, shared libraries, admin, connectors, and SSO exist. | The v3 flow does not design them [BM §2.4, §6.2, BM-6]. | M3 gate, not a pricing-page gate. |
| BR-6 | No price points may be published before cost telemetry and pilot conversion exist. | Price-setting follows measurement [BM §6.3, BM-4]. | All price cells are `TBD-BIZ`. |
| BR-7 | The real material default limit MUST NOT be hard-coded to the prototype's 6. | The 6-item limit is a demo constraint [BM §6.2; SRC §5]. | Use a configurable limit; value `TBD-UX`. |
| BR-8 | Rerun MUST be incremental; no silent full-deck rerun. | Full-deck rerun breaks unit economics [BM §5.1 rule 1]. | Page-level affected scope; cascade factor approaches 1.0. |
| BR-9 | Priority queue is a paid lever, not an M1 requirement. | Queue priority is a packaging hypothesis [BM §5, §6.2]. | M2; M1 uses fair queueing. |
| BR-10 | Built-in style gallery is 4 styles in M1; a free-plan hypothesis gives access to 2. | Flow shows 4 cards; BM packaging hypothesis says 2 for free [FLOW §2 stage 5; BM §6.2]. | 4 built-in, plan availability is a packaging decision, not a flow change. |
| BR-11 | M1 pilot commercial onboarding may be manual; self-serve billing is M2. | BM separates M1 pilot readiness from M2 accounts/billing [BM §11.3]. | `[ASSUMPTION]` Manual contracts/invoices for pilot. |
| BR-12 | Source/search caps may differ by plan; the free tier may default to the web-only path. | Source caps are a cost lever; web-only is the v1 fallback [BM §5; SRC §4.2]. | Cap values `TBD-BIZ` / `TBD-BE`. |
| BR-13 | Charge for delivered value (exportable decks, capacity, quality, collaboration, governance), not tokens. | Revenue principles [BM §6.1]. | Packaging language must avoid token pricing. |
| BR-14 | Do not charge for export in a way that hides the central editable-output claim. | Free users must be able to verify the claim [BM §6.2 note]. | Capped, not watermark-gated. |

---
## 11. Instrumentation and analytics requirements
### 11.1 Server-side requirement
All events used for cost attribution, quota enforcement, billing, or published metrics MUST be emitted server-side. Client events MAY supplement UX analytics but MUST NOT be the source of truth. The prototype's event sequence is a client-side simulator and is not acceptable for M1 [FLOW §3.2; BM §7, §11.2].
### 11.2 Event taxonomy
| Event | Trigger | Required properties | Consumer |
| --- | --- | --- | --- |
| `project_created` | Topic submitted | `project_id`, `mode`, `material_count`, `has_materials`, `locale` | Product analytics |
| `material_added` | Material chip added | `project_id`, `material_id`, `kind`, `size_bucket`, `page_count_bucket` (no name/content) | Product, cost |
| `tool` | Material tool or web search call | `project_id`, `tool_name`, `target_type`, `material_id`, `duration_ms`, `result`, `error_code` | Reliability, cost |
| `source` | Source appended to the panel | `project_id`, `origin`, `source_type`, `material_id`, `domain`, `rank` (no full URL) | Product, cost |
| `question` | Interview question shown | `project_id`, `index`, `total`, `has_materials` | Product analytics |
| `question_answer` | Answer selected or edited | `project_id`, `index`, `option_id`, `is_edit`, `elapsed_ms` | Product analytics |
| `digest` | Material digest complete/fail | `project_id`, `material_id`, `status`, `extracted_char_bucket`, `duration_ms` | Product, cost |
| `gap_suggest` | Gap suggestions shown | `project_id`, `gap_count`, `recommended_count`, `has_materials` | Product analytics |
| `gap_decision` | User confirms gaps | `project_id`, `selected_count`, `suggested_count`, `web_skipped`, `not_needed` | Product, cost |
| `profile_ready` | Profile generated | `project_id`, `profile_version`, `materials_count`, `web_source_count`, `web_skipped`, `time_since_start_ms` | Product analytics |
| `profile_updated` | Profile updated | `project_id`, `profile_dirty_duration_ms`, `outline_existed` | Product analytics |
| `message_delta` / `card_delta` | Stream chunk received | `project_id`, `stage`, `job_id`, `chunk_index`, `latency_ms` (no content) | Reliability |
| `outline_delta` | Outline chunk received | `project_id`, `chunk_index`, `job_id` | Reliability |
| `outline_done` | Outline stream complete | `project_id`, `page_count`, `section_count`, `agreed_count`, `deviation`, `duration_ms`, `input_tokens`, `output_tokens`, `cost` | Product, cost |
| `auto_advance` | Countdown starts/ends | `project_id`, `from_stage`, `to_stage`, `seconds`, `paused`, `pause_reason` | Product analytics |
| `page_start` / `page_done` | Plan/design page job | `project_id`, `stage`, `page_id`, `page_type`, `layout_id`, `variant`, `model_tier`, `input_tokens`, `output_tokens`, `latency_ms`, `cost`, `status`, `error_code` | Product, cost, reliability |
| `history_push` / `history_pop` | Regenerate, tweak, or undo | `project_id`, `stage`, `page_id`, `variant`, `reason` | Product, cost |
| `job_queued` / `job_cancelled` / `job_resumed` | Long-task lifecycle | `project_id`, `job_id`, `job_type`, `page_id`, `wait_ms`, `reason` | Reliability |
| `stale_rerun` | Stale rerun triggered | `project_id`, `from_stage`, `cause_change`, `affected_pages`, `rerun_pages`, `cascade_ratio`, `cost` | Cost, product |
| `export` | Export attempt/result | `project_id`, `format`, `page_count`, `style_id`, `rendered_count`, `validation_result`, `latency_ms`, `cost`, `result`, `error_code` | Product, cost, billing |
| `export_validation` | Pre-export validation | `project_id`, `format`, `checks`, `failed_checks`, `page_ids` | Reliability |
| `quota_check` / `quota_exceeded` | M2 quota enforcement | `account_id`, `dimension`, `limit`, `used`, `action` | Billing |
| `account_created` / `subscription_changed` | M2 account/billing | `account_id`, `plan_id`, `seats`, `billing_period` | Billing |
| `referral` / `invite` | Referral or invite | `account_id`, `channel`, `project_id` | Product analytics |
| `support_contact` | Support interaction | `account_id`, `category`, `deck_id` (no content) | Product analytics |
### 11.3 Business mapping from FLOW events
| Flow event | Business meaning | Metric |
| --- | --- | --- |
| `tool` / `source` | Material and research cost; ingestion success | M-02, parse/search success rates |
| `question` / `question_answer` | Interview completion and drop-off | M-14, M-15 |
| `digest` / `gap_suggest` / `gap_decision` | Gap acceptance, web-skip rate, material sufficiency | M-23, M-24 |
| `profile_ready` | Activation milestone | M-13, M-15 |
| `outline_delta` / `outline_done` | Outline generation time and edit intensity | M-16 |
| `page_start` / `page_done` (plan/design) | Throughput, per-page cost, failure rate | M-03, M-04, M-25 |
| `history_push` / `history_pop` | Regeneration and undo behavior | M-05 |
| `export` | Conversion moment and export success | M-07, M-09, M-18 |
| Stale/rerun (new server-side event) | Rerun cascade factor and cost leakage | M-06 |

This mapping follows [BM §11.2]. Events MUST be emitted server-side for billing, quota, and cost attribution.
### 11.4 Cost attribution
- Every model call, search call, parse/OCR page, render, and export MUST record billable units and an estimated cost against `project_id`, `stage`, `page_id` (where applicable), and `job_id`.
- `cost_per_research`, `cost_per_plan_page`, `cost_per_design_page`, and `cost_per_exported_deck` MUST be derivable from the ledger without client events [BM §7].
- Regeneration and stale rerun MUST be separately attributable; a single page regenerated twice is two paid operations.
- Cost records MUST be immutable or append-only; corrections are adjustments, not overwrites.
### 11.5 Privacy constraints
- Analytics MUST NOT contain material content, topic text, file names, full URLs, email addresses, names, or other PII.
- IDs MUST be pseudonymous. Web source `domain` may be recorded; material URLs must not be logged in full.
- Event schema MUST be versioned; retention and consent are `[TBD-BIZ · legal, M1]` (PRD-08).
- Logs and traces MUST follow the same no-content rule; error messages must not echo user text.

### 11.6 Correlation IDs
Every event and job MUST carry: `project_id`, `job_id` (when applicable), `page_id` (when applicable), `request_id`, and `trace_id`. M2 adds `account_id`. These IDs allow reconstruction of a project/page/job without storing content. Idempotency keys MUST be recorded for retries.

---

## 12. Non-functional requirements
Targets are quantified only where a source provides one. Everything else is `TBD-BE` or `TBD-INFRA`, with owners in §16. The Requirement column is normative: P0 rows are MUST, P1 rows are SHOULD; MAY is used only where explicitly stated.

| ID | Requirement | Target | Verification | Pri |
| --- | --- | --- | --- | --- |
| NFR-PERF-1 | p95 time to first design page, measured from outline confirmation to first design `page_done`. | Guardrail; target `TBD-BIZ` | Event timestamps on pilot decks; load test | P0 |
| NFR-PERF-2 | Per-page plan/design generation latency expectation by page type and style. | `TBD-BE` | p50/p95 from `page_done`; per-stage dashboards | P0 |
| NFR-PERF-3 | Streaming responsiveness: first streamed content appears before the full response; UI remains interactive. | First chunk `TBD-BE`; no full-response wait | Time-to-first-chunk; interaction test during streaming | P0 |
| NFR-REL-1 | Core-flow availability. | `TBD-INFRA` | Monthly uptime monitoring; incident log | P0 |
| NFR-REL-2 | Durability of project artifacts: committed materials, plans, designs, history, exports. | RPO/RTO `TBD-INFRA`; no committed loss | Fault injection; backup restore test | P0 |
| NFR-REL-3 | Retries of failed jobs/pages are idempotent. | No duplicate charge, history entry, or artifact | Retry tests; ledger reconciliation | P0 |
| NFR-REL-4 | Background jobs survive client disconnect and restore on reconnect. | No duplicate or lost job | Kill client/network during generation; reconnect | P0 |
| NFR-REL-5 | Export success rate is measured and guarded. | Guardrail; target `TBD-BIZ` | `export` result ratio; artifact existence check | P0 |
| NFR-REL-6 | Failure isolation: one material or page failure does not fail the deck. | Deck continues with remaining sources/pages | Fault injection per material/page | P0 |
| NFR-SEC-1 | Project isolation: no cross-project access to materials or artifacts. | Zero cross-project access | Authorization tests; signed-URL tests | P0 |
| NFR-SEC-2 | Encryption in transit and at rest. | `TBD-INFRA` | Configuration audit | P0 |
| NFR-SEC-3 | Least privilege and secret management; no secrets in client bundles. | No client-side secrets | Code/config review; secret scan | P0 |
| NFR-PRIV-1 | Deletion/retention: deleting a project removes materials and derived artifacts within the policy SLA. | SLA `TBD-BIZ`; default no training | Deletion test; artifact scan | P0 |
| NFR-PRIV-2 | No training on customer data by default, pending BM-7 (recommended default). | Contractual + configuration evidence | Vendor review; configuration audit | P0 |
| NFR-PRIV-3 | No PII or material content in analytics, logs, or traces. | Zero content fields | Schema audit; sampled log review | P0 |
| NFR-PRIV-4 | Data-handling notice and required consent before upload. | Notice visible before first upload | UI test; legal review | P0 |
| NFR-PRIV-5 | Subprocessor and region disclosures exist before paid pilot. | `TBD-BIZ` legal | Legal review; published page | P0 |
| NFR-ACC-1 | WCAG 2.2 AA baseline for the core flow (proposed `[ASSUMPTION]`; confirm with design/legal). | AA | Automated + manual audit | P0 |
| NFR-ACC-2 | Body and secondary text contrast at least 4.5:1; focus ring visible. | 4.5:1 | Contrast audit | P0 |
| NFR-ACC-3 | Keyboard can complete the main flow per §8.9.3. | No pointer-only core action | Scripted keyboard run | P0 |
| NFR-ACC-4 | Focus visible, modal trap/restore, skip link. | Every modal and stage change | Keyboard test | P0 |
| NFR-ACC-5 | Screen reader semantics: roles, live regions, status not by color alone. | Milestones announced; no token chatter | Screen reader audit | P0 |
| NFR-ACC-6 | Reduced motion respected. | Typewriter outputs full text; animations near zero | OS setting test | P0 |
| NFR-COST-1 | Stage-level cost telemetry for every model/search/parse/render/export call. | 100% of billable calls attributed | Ledger coverage audit | P0 |
| NFR-COST-2 | `cost_per_exported_deck` computed server-side from the ledger. | Formula matches §4.3 | Reconciliation against provider invoices | P0 |
| NFR-COST-3 | Incremental rerun: pages rerun ÷ pages changed approaches 1.0; no silent full-deck rerun. | Approach 1.0 [BM §7]; threshold `TBD-BIZ` | Stale matrix tests; cascade metric | P0 |
| NFR-COST-4 | Input-keyed caching: reuse digest/plan/design when inputs are unchanged. | No regeneration for unchanged inputs | Cache hit/miss and cost comparison | P0 |
| NFR-OBS-1 | End-to-end traces with project/page/job correlation IDs. | Trace covers every stage | Sample trace walkthrough | P0 |
| NFR-OBS-2 | Dashboards for guardrails: p95 time to first design page, failure rate, export success, cost/deck, queue depth. | Dashboard exists before pilot | Dashboard review | P0 |
| NFR-OBS-3 | Alerts for export failure rate, queue backlog, and cost anomaly. | `TBD-INFRA` thresholds | Alert injection test | P1 |
| NFR-SCALE-1 | Concurrent projects/pages during pilot. | `TBD-INFRA` | Load test at pilot scale | P0 |
| NFR-SCALE-2 | Project size limits: materials, pages, regenerations per plan. | `TBD-BIZ`; enforced | Cap tests | P0 |
| NFR-COMPAT-1 | Browser support matrix. | `TBD-FE` | Cross-browser matrix before M1 | P0 |
| NFR-COMPAT-2 | Responsive breakpoints §8.9.4. | 1180/920/720/480 | Viewport checks at 1440/1180/920/720/390 | P1 |
| NFR-COMPAT-3 | Mobile core flow usable; canvas readable via 680px horizontal scroll; stage select at ≤920. | No blocked core action | Mobile walkthrough | P1 |
| NFR-COMPAT-4 | PPTX opens in PowerPoint 2016+ and remains editable. | Text/shape edit; no repair prompt | Manual matrix on Windows/Mac PowerPoint | P0 |
| NFR-COMPAT-5 | HTML is self-contained; PDF is 16:9 and matches page count. | Offline open; aspect check | File inspection | P0 |
| NFR-MAINT-1 | Project state schema is versioned; old projects load after migration. | No broken project on upgrade | Migration test | P0 |
| NFR-MAINT-2 | Model/provider portability: swapping provider does not change UX contracts. | Config-level swap | Swap test on staging | P1 |
| NFR-MAINT-3 | Export regression matrix covers cover/TOC/end, six layouts, at least two styles, fonts/assets. | Every export change runs matrix | Regression suite | P0 |
| NFR-MAINT-5 | Feature flags/kill switches for model, search, and export. | Can disable without deploy | Flag test | P1 |

---

## 13. Dependencies and external integrations
Criticality: **Critical** = core flow cannot complete; **High** = a degraded path exists; **Medium** = pilot can continue manually.

| Dependency | Role | Criticality | Degradation if unavailable | Owner / stage |
| --- | --- | --- | --- | --- |
| Model provider(s) | Research digest, outline, plan, design, tweak | Critical | Page/job enters error with retry; no output is shown as successful; fallback provider is `[TBD-BE · architecture stage]`. | `[TBD-BIZ · founder]` vendor; `[TBD-BE · architecture stage]` |
| Search API | Gap filling and no-material research path | Critical for web path | With materials: continue material-only and record skipped web. Without materials: zero-results contract; do not fabricate. | `[TBD-BIZ · founder]`; `[TBD-BE · before development]` |
| Document parsing / OCR | File ingestion | Critical for material promise | Mark material not digested; allow paste-body fallback; continue other sources. | `[TBD-BE · before development]` |
| URL fetch / extraction | URL material ingestion | High | Show failure + suggest pasting body text; keep other sources. | `[TBD-BE · before development]` |
| Storage (objects/artifacts) | Materials, renders, exports, history | Critical | Visible retry/failure; no data loss; no success claim. | `[TBD-INFRA · architecture stage]` |
| Export / render | PPTX, HTML, PDF generation and validation | Critical | Retry; alternate format; no success without artifact. | `[TBD-BE · export implementation]` |
| Identity / payment | M2 accounts, billing, quotas | Critical at M2 | M1 pilot uses manual onboarding `[ASSUMPTION]`; no self-serve billing. | `[TBD-BE · M2]` |
| Organizational connectors | M3 Feishu/Notion/Confluence and shared libraries | Not in M1 | N/A; do not imply availability. | `[TBD-BIZ · founder, M3]` |
| Font/image/icon assets | Export fidelity and licensing | High | Substitute + report; block unlicensed embedding per policy. | `[TBD-BIZ · legal, before paid launch]` |
| Observability / analytics store | Cost, guardrails, incidents | High | Local buffering; no billing or published metric without telemetry. | `[TBD-INFRA · architecture stage]` |
| Email/support | M2 support and notifications | Medium | M1 pilot uses manual support; no SLA. | `[TBD-BIZ · founder, M2]` |
| Launch-region infrastructure | Search, payment, compliance, hosting region | High | Region-specific launch is blocked until decided. | `[TBD-BIZ · founder, before paid pilot]` |

---

## 14. Release plan and acceptance
### 14.1 Milestone gates
| Milestone | Required scope | Exit criteria | Key blocking requirements (not exhaustive; §8 is the P0 register) |
| --- | --- | --- | --- |
| **M0 · Prototype** | Clickable mock; no network | Flow walkthrough; known gaps recorded | N/A |
| **M1 · Paid pilot readiness** | Real ingestion, real model generation and web search, real export + validation, failure recovery, background tasks, cost telemetry, terms/privacy, pilot onboarding | M1 go/no-go checklist in §14.2; 5–10 design partners complete real decks; export fidelity sign-off; unit cost measured | FR-1.8–1.10, FR-2.10, FR-2.20, FR-6.12–6.18, FR-7.4–7.6, FR-7.18, NFR-COST-1/2, NFR-PRIV-1/2/4, NFR-COMPAT-4 |
| **M2 · Self-serve paid launch** | Accounts, billing, quotas, support runbook, landing pages, plan limits; all P1 items closed or explicitly waived | Conversion and margin targets met on a small cohort; price points set after telemetry and pilot | M2 billing/account/quota requirements; NFR-SEC-1; §11 quota events; P1 register |
| **M3 · Team / Enterprise** | Collaboration, shared libraries, admin, connectors, SSO, security review, retention controls | First team contract; security questionnaire passed | M3 capabilities; BM-6 |

### 14.2 M1 go/no-go checklist
The first six rows are BM §0 "what must be true"; the next rows make R1/R3/R4/R7 and the remaining M1 prerequisites explicit. R4 overlaps condition 1 and R7 overlaps condition 2; both are tracked by ID. Conditions 3–6 are pilot-measured; a fail triggers a pivot review, not necessarily a build stop.

| # | Condition | Evidence required | Blocking requirements |
| --- | --- | --- | --- |
| 1 | Material ingestion works reliably for common formats and URLs. | Parse success rate by file type; URL degradation test; failure isolation test. | R4; FR-1.8–1.10; FR-2.10 |
| 2 | Export produces an Office-usable, editable PPTX. | PowerPoint fidelity matrix; text/shape edit; font/asset handling; HTML/PDF checks. | R7; FR-6.12–6.18; NFR-COMPAT-4/5 |
| 3 | Users perceive the interview and gap confirmation as value, not friction. | Pilot completion rate, time to profile, answer edit rate, interviews. | FR-2.3–2.13; M-14/15/16 |
| 4 | Variable cost per exported deck leaves room for gross margin. | Server cost ledger; cost per exported deck; cascade factor. | NFR-COST-1/2/3; M-06/07/08 |
| 5 | Users produce more than one deck per quarter. | Pilot repeat project/export data. | M-19/20/21 |
| 6 | Some segment shows willingness to pay above free-tier limits. | Pilot conversion; willingness-to-pay interviews. | M-10/18 |
| 7 | R1 failure and recovery are real, not contracts. | All 13 contract rows tested; no dead ends. | FR-7.6; §8.9.2 |
| 8 | R3 long tasks survive navigation, refresh, and disconnect; cancellation works. | Background job test; reconnect test; cancel test; idempotency test. | FR-7.5; NFR-REL-3/4 |
| 9 | R4 real parsing and URL fetch are live for the supported types. | Same evidence as #1; supported-type list published. | FR-1.8–1.10 |
| 10 | R7 pre-export validation is live. | Missing font, out-of-bounds asset, empty page, incomplete render tests. | FR-6.14 |
| 11 | Real cost telemetry is live server-side. | Ledger coverage; cost per deck; provider invoice reconciliation. | §11; NFR-COST-1/2 |
| 12 | Terms and privacy page are published. | No-training statement; retention/deletion; subprocessor/region disclosure. | FR-1.12; NFR-PRIV-1/2/4/5 |
| 13 | Export fidelity is signed off. | Checklist with zero blocker defects. | FR-6.18 |
| 14 | 5–10 design partners complete real decks. | Pilot log; deck review; support notes. | BM §11.3 |
| 15 | Real model generation and real web search are live; no mock content on the paid path. | End-to-end deck generated from user inputs; real search results; no `MOCK` data reachable; cost recorded per call. | FR-2.20, FR-7.18; NFR-COST-1 |

### 14.3 Definition of done for a requirement
| Area | Definition of done |
| --- | --- |
| Behavior | End-to-end real behavior for M1/P0 items; no mock backend on the paid path; acceptance bullets pass with evidence. |
| Failure | Error and recovery path implemented and tested; no fake success; no dead end. |
| State | Persistence, stale propagation, concurrency, and restart semantics verified. |
| Accessibility | Keyboard, screen reader, contrast, reduced motion checked; no regression against §8.9.3/§8.9.4. |
| Telemetry | Server events emitted with required properties; cost attributed per stage/page. |
| Cost | No unbounded rerun; cache/rerun scope matches the matrix. |
| Operations | Feature flag or kill switch; runbook entry; rollback path. |
| Compliance | Notice/terms/deletion where applicable. |
| Sign-off | Product, design, engineering, QA; evidence attached to the requirement. |

---

## 15. Risks and mitigations
| ID | Risk | Impact | Mitigation | Owner / stage | Early warning signal |
| --- | --- | --- | --- | --- | --- |
| R-01 | Inference cost or provider pricing changes. | Gross-margin erosion. | Model routing, caching, incremental rerun, plan caps. | `[TBD-BIZ · founder + engineering]` | Cost per exported deck rises; provider price change notice. |
| R-02 | Regeneration and rerun cost blowout. | Unpredictable unit economics. | Regeneration allowance; cascade-factor target; page-level rerun. | `[TBD-BIZ · product + engineering]` | Cascade factor above target; regeneration intensity rising. |
| R-03 | Low willingness to pay versus free chat tools. | Conversion failure. | Beachhead with high-stakes decks; prove export and material reuse. | `[TBD-BIZ · founder, paid pilot]` | Low conversion; pilot interviews cite "good enough" free tools. |
| R-04 | Confidential material exposure. | Enterprise disqualification; reputational harm. | No-training default; retention/deletion; least privilege; region options. | `[TBD-BIZ · legal + security]` | Security review findings; unexpected data in logs. |
| R-05 | Copyright or font/image licensing in generated decks. | Legal exposure for users and product. | User responsibility terms; licensed assets; export warnings. | `[TBD-BIZ · legal]` | Unlicensed asset detected in validation; legal review flag. |
| R-06 | Hallucinated or unsupported content. | Trust damage in high-stakes decks. | Material-first priority; source panel; grounding rubric; no invented facts. | Product + backend | Reviewer finds unsourced numeric claims; pilot complaints. |
| R-07 | Model-provider dependency. | Quality or price shock. | Abstraction layer; evaluation set; multi-provider option. | `[TBD-BE · architecture stage]` | Provider outage; quality regression after model change. |
| R-08 | Team/enterprise scope creep. | Engineering diverted before product-market fit. | Freeze Team until collaboration/admin exists; focus on Pro. | `[TBD-BIZ · founder]` | Roadmap additions before M2 metrics. |
| R-09 | Region-specific search, payment, and compliance. | Launch blocked in chosen market. | Decide region before vendor and pricing work. | `[TBD-BIZ · founder]` | Vendor unavailable in region; compliance questions unresolved. |
| R-10 | Export fidelity failure. | One bad PPTX damages the core promise. | Pre-export validation; sample matrix; fast repair; fallback to HTML/PDF. | `[TBD-BE · export]` | Export failure rate; PowerPoint repair prompts; font overflow reports. |
| R-11 | Long-task/background reliability. | Lost decks; duplicated cost; user distrust. | Queue, cancellation, reconnect, idempotent retries. | `[TBD-BE · architecture stage]` | Jobs stuck; duplicate history entries; refresh losses. |
| R-12 | Missing failure paths or silent failure. | Dead ends; support load; trust loss. | R1 contracts; error taxonomy; no fake success. | Frontend + backend | Support contacts; error pages without retry. |
| R-13 | Interview/gap friction; users skip the differentiator. | Weak differentiation; lower activation. | Sequential questions; Agent suggestions; measure skip/edit; pivot to optional expert mode if needed. | Product + design | Low completion; high "not needed" without review; skip requests. |
| R-14 | PPTX fidelity cannot reach an acceptable bar. | The paid promise is not deliverable. | Fidelity matrix; pivot toward HTML/PDF for personal use if needed. | Founder + product | Repeated blocker defects; pilot rejection of PPTX. |
| R-15 | Accessibility regressions. | Excluded users; legal risk; quality erosion. | Baseline in CI/manual audit; keyboard matrix; no color-only status. | Design + frontend | Audit failures; keyboard gaps. |
| R-16 | Prototype mistaken for product. | False commitments; mis-scoped sales. | Status labels; appendix A; no mock on the paid path. | Product | Demo claims outpace implementation. |
| R-17 | Stale/rerun scope incorrect. | Wrong content in the deck; cost leakage. | Matrix tests; stage nav markers; cascade metric. | Frontend + backend | Cascade factor divergence; user reports stale pages. |

---

## 16. Open questions and decisions
All BM §12 and SRC §7 items are included. New PRD decisions are marked PRD-xx. "Blocking" means the decision must be made before the named stage; it does not mean the feature ships in that stage. IDs are stable; missing numbers are decisions removed from v1 scope.

| ID | Question / decision | Options / recommendation | Owner | Stage | Blocking |
| --- | --- | --- | --- | --- | --- |
| BM-1 | Beachhead segment | Pre-sales/bidding; product/marketing; founders; broad knowledge workers. Recommendation: pre-sales + product/marketing `[ASSUMPTION]`. | Founder | Before paid pilot | Yes |
| BM-2 | Revenue model | Pure subscription; pure credits; hybrid. Recommendation: hybrid subscription + allowance `[ASSUMPTION]`. | Founder + finance | Before paid pilot | No (M2) |
| BM-3 | Free-tier boundary | PPTX with caps; PPTX gated; watermark. Recommendation: capped PPTX, no watermark. | Founder + product | Before paid pilot | No (M2) |
| BM-4 | Price points | Set after cost telemetry and pilot conversion. | Founder + finance | After paid pilot | No |
| BM-5 | Premium model tier | Same model; paid high-quality model. Recommendation: Pro/add-on option. | Product | M2 | No |
| BM-6 | Team/enterprise timing | Now; after collaboration/admin; never. Recommendation: after capabilities exist. | Founder | M3 | No |
| BM-7 | Data policy | Training opt-in; no training; region-specific. Recommendation: no training by default; explicit retention. | Legal + founder | Before paid pilot | Yes |
| BM-8 | Launch region and vendors | Decide before search/payment/compliance work. | Founder | Before paid pilot | Yes |
| BM-9 | Collaboration scope | Comments; real-time co-editing; shared libraries. Recommendation: shared libraries and brand kits first. | Product | M3 | No |
| BM-10 | Style marketplace | Built-in only; third-party marketplace. Recommendation: built-in first. | Product | Post-M2 | No |
| BM-11 | Font/image licensing | Bundled licensed assets; user-supplied only. Recommendation: bundled licensed + user responsibility terms. | Legal | Before paid launch | Yes |
| BM-12 | Paid support/SLA | Community; email; SLA. Recommendation: email at M2; SLA Enterprise. | Founder | M2 | No |
| TBD-BE-1 | Supported file types and parsing limits | Candidates: docx/pdf/xlsx/pptx/md/txt/images. Freeze list and size/page limits. | Backend | Before development | Yes |
| TBD-BE-2 | URL fetch degradation for login walls/anti-scraping | Recommendation: failure + paste-body suggestion; keep other sources. | Backend | Before development | Yes |
| TBD-BE-3 | Material sufficiency and gap suggestion logic | Digest → judge → 3 gaps with reasons → user confirm → targeted search. | Backend | Before development | Yes |
| TBD-UX-1 | Material chip limit and oversized-file messaging | Prototype 6; real default and messages. | Design | Visual design | Yes |
| TBD-UX-2 | Material preview form | Summary line; expandable source text. Recommendation: summary at M1; expansion P2 (R5). | Design | Visual design | No |
| TBD-UX-3 | Gap default selection and display order | 3 suggestions; recommended pre-checked. Confirm ordering and edge cases. | Design | Visual design | No |
| TBD-FE-1 | Re-search after profile | Interaction for changing gaps and updating the profile. Recommendation: P1 (FR-2.18); M1 fallback restart. | Frontend | Before development | No |
| PRD-01 | M1 pilot commercial onboarding | Manual contract/invoice vs early billing. Recommendation: manual `[ASSUMPTION]`. | Founder | M1 | Yes |
| PRD-02 | Activation threshold N pages | Define N for "activated". | Founder | Before paid launch | No (M2) |
| PRD-03 | Export with incomplete pages | Block export vs partial export with explicit scope. Recommendation: block success; offer explicit partial scope only after validation. | Product + UX | M1 | Yes |
| PRD-04 | Mode switching mid-project | Fixed at start vs switchable. Recommendation: fixed for M1. | UX | M1 | No |
| PRD-05 | UI and deck locale | Single locale vs i18n. Recommendation: single UI locale for M1; deck language follows user input `[ASSUMPTION]`. | Product | M1 | No |
| PRD-06 | Browser support matrix | Define supported browsers/versions. | Frontend | M1 | Yes |
| PRD-07 | PPTX fidelity acceptance bar | Define PowerPoint versions, editability checks, font-substitution tolerance. | Product + engineering | M1 | Yes |
| PRD-08 | Analytics consent and retention | Define lawful basis, retention, and redaction review. | Legal + product | M1 | Yes |
| PRD-09 | Project list/rename/duplicate | Not in FLOW. Define M2 workspace behavior. | Product + backend | M2 | No |
| PRD-10 | Source/search caps | Define cap values by plan and the user-facing notice. | Product + engineering | M1 | Yes |
| PRD-11 | Queue timeout/cancel defaults | Define per-stage timeout, retry limit, cancellation semantics. | Backend | M1 | Yes |
| PRD-15 | Terms/privacy page ownership | Who writes, reviews, and publishes. | Legal + founder | M1 | Yes |
| PRD-17 | Interview skip / optional expert mode | Keep mandatory interview vs optional expert path. Recommendation: mandatory for M1; revisit if pilots skip it. | Product | Post-pilot | No |
| PRD-18 | Page count caps by plan | Define caps; do not hard-code prototype counts. | Product | M2 | No |
| PRD-19 | OCR for images/scans | Required at M1 vs later. Depends on TBD-BE-1. | Backend | M1 | No |
| PRD-22 | Stage 2 auto-advance in fully automatic mode | Keep explicit profile gate vs auto-advance after profile. Recommendation: keep gate (C-2). | UX | M1 | No |
| PRD-23 | Roving tabindex / arrow keys for radio groups (UX R8) | Current Tab+Space works; add standard roving tabindex. | Frontend | M1 hardening | No |
| PRD-24 | Mobile canvas fit / 100% toggle (UX R9) | Keep 680px horizontal scroll vs add a fit toggle. | Design | Visual design | No |
| PRD-25 | Global cross-project version history (UX R6) | Per-page history only vs global history. | Product | Post-M1 | No |

---

## 17. Traceability
### 17.1 Requirement group → source → acceptance evidence
| Requirement group | Primary source sections | Acceptance evidence |
| --- | --- | --- |
| FR-1 Material intake | FLOW §2 stage 1, §6; SRC §1, §4.2, §5; UX 1.x, R4 | FR-1 acceptance bullets; parse success by type; URL degradation test; M1 checklist #1/#9. |
| FR-2 Research + interview | FLOW §2 stage 2, §3.2, §6; SRC §2.3, §4.2, §5; UX 2.x | Profile/completion metrics; gap decision tests; conflict-priority review; M1 checklist #3. |
| FR-3 Outline | FLOW §2 stage 3, §3.4, §7.1; UX 3.x | Keyboard/drag tests; deviation warning; seven-row stale matrix; countdown tests. |
| FR-4 Plan draft | FLOW §2 stage 4; UX 4.x | Completion gate; re-plan scope; skeleton/status tests; error retry. |
| FR-5 Style selection | FLOW §2 stage 5; UX 5.x | Radiogroup keyboard test; confirm gating; style-change invalidation. |
| FR-6 Design draft and export | FLOW §2 stage 6, §6, §7.2; EXTRACT §II.3, §IV; UX 6.x, R7 | Per-page history; single-layout protection; export scope; PowerPoint fidelity matrix; failure recovery. |
| FR-7 Cross-cutting | FLOW §1, §3.4, §6, §7; UX §5; BM §10.1 | Stage reachability; stale matrix; 13 failure contracts; keyboard matrix; breakpoints; persistence/background tests. |
| FR-8 Project lifecycle | FLOW §1; BM §6.2, §10.1 | Project name; deletion test; M2 workspace decision. |
| CR-1 to CR-7 Content/output | SRC §1–§5; EXTRACT §III, §IV; BM §10.3 | Source-channel coverage; gap logic; conflict priority; format fidelity; licensing review. |
| §10 Business rules | BM §5.1, §6, §6.3, §6.4, §12 | Packaging review; free-loop test; no-paywall audit; no hard-coded limits. |
| §11 Analytics | FLOW §3.2; BM §7, §8.2, §11.2 | Event schema audit; cost ledger reconciliation; no-PII review. |
| §12 NFRs | FLOW §7; UX §5/§7; BM §7, §11.1 | Audit reports; load tests; export matrix; accessibility audit; cost dashboards. |
| §14 Release gates | BM §0, §11.3; UX §5 | M1 go/no-go checklist; design-partner log; unit-cost report; fidelity sign-off. |

### 17.2 PRD ↔ architecture handoff
The following items need architectural design. This PRD defines behavior and acceptance, not implementation. All items are `[TBD-INFRA · architecture stage]` or `[TBD-BE · tech implementation]`.

| Area | Why architecture is needed | Requirements | Owner / stage |
| --- | --- | --- | --- |
| Long-task job model and queue | Background continuation, cancellation, reconnect, idempotency, and page-level concurrency cannot be solved in the client. | FR-7.4, FR-7.5, NFR-REL-3/4, NFR-SCALE-1 | `[TBD-INFRA · architecture stage]` |
| Incremental rerun and caching | The stale matrix must translate into a dependency graph and input-keyed cache; otherwise rerun costs explode. | FR-7.3, NFR-COST-3/4 | `[TBD-BE · architecture stage]` |
| Metering and cost attribution | Stage/page cost, quota, and billing require a usage ledger and reconciliation with provider invoices. | §11, NFR-COST-1/2, NFR-OBS-1 | `[TBD-INFRA · architecture stage]` |
| Export pipeline | SVG composition, font embedding/substitution, Office compatibility, validation, and artifact storage are core engineering. | FR-6.12–6.18, NFR-COMPAT-4/5, NFR-MAINT-3 | `[TBD-BE · export implementation]` |
| Tenancy and isolation | Materials and artifacts are confidential; project/account boundaries and signed access are required before paid use. | NFR-SEC-1, NFR-PRIV-1 | `[TBD-INFRA · architecture stage]` |
| Project persistence and state versioning | Autosave, refresh recovery, stale flags, and history require a durable project schema with migrations. | FR-7.9, NFR-MAINT-1 | `[TBD-BE · tech implementation]` |
| Streaming transport | Research/outline/plan/design streaming and reconnect semantics need a transport contract. | NFR-PERF-3, FR-2.1–2.9, FR-3.1 | `[TBD-INFRA · architecture stage]` |
| Model gateway, prompt registry, and real search | Real generation and search must replace demo content; structured output, model routing, retries, provider portability, and per-call metering are not client concerns. | FR-2.20, FR-7.18, NFR-MAINT-2, NFR-COST-1 | `[TBD-BE · tech implementation]` |
| Ingestion pipeline | Parsing, OCR, URL extraction, and degradation paths need a pipeline with per-material status. | FR-1.8–1.10, FR-2.10 | `[TBD-BE · tech implementation]` |
| Billing and quota (M2) | Plans, allowances, overage, and quota enforcement need account/billing architecture. | §11 quota events, BR-3/4, BR-12 | `[TBD-BE · M2]` |
| Connectors (M3) | Organizational knowledge ingestion needs authorization, sync, and governance. | Out of M1; SRC §4.3 | `[TBD-BIZ · M3]` |

---

## 18. Change log
| Version | Date | Change |
| --- | --- | --- |
| v1 | 2026-11-18 | Initial PRD. Translates business model v1 and interaction flow v3 into M1/M2/M3 product requirements; adds requirement IDs, acceptance criteria, stale/failure/accessibility tables, metrics, NFRs, dependencies, risks, open questions, traceability, and prototype-vs-product appendix. |

---

## Appendix A. Prototype vs product
The current prototype is a single-file clickable demo with built-in mock data and a timer-sliced streaming simulator. It makes no network requests and does not produce real artifacts [FLOW §5]. Do not treat the following demo behaviors as requirements.

| Capability | Prototype behavior | Production requirement | Status |
| --- | --- | --- | --- |
| Model generation | Timer-sliced typewriter over built-in `MOCK` content; no network. | Real model pipeline with streaming, token accounting, per-page errors, and retries. | Missing (FR-7.18; R1, R3) |
| Material parsing | Files record name/type/size only; content is not parsed. | Real parsing for supported types, failure isolation, and paste fallback. | Missing (R4) |
| URL ingestion | URL format validated; content is not fetched. | Real fetch/extraction; login-wall/anti-scraping degradation. | Missing (R4) |
| Web search | Mock source list; no network. | Real search API; targeted per gap; zero-results handling; source caps. | Missing (FR-2.20) |
| Plan/design generation | Static `MOCK` variants rendered with CSS Grid; six Bento compositions. | Model-generated plan/design; real content; style application; per-page variants/history. | Missing |
| Export | Mock progress and success; no files. | Real PPTX/HTML/PDF; pre-export validation; fidelity matrix; downloadable artifacts. | Missing (R7) |
| Persistence | In-memory JS state; refresh resets. | Server persistence, autosave, reconnect, background jobs. | Missing |
| Analytics | Client-side event simulator; no network. | Server-side events for cost, quota, billing, and product analytics. | Missing |
| Error states | `error` status reserved; not simulated. | 13 failure/recovery contracts; retry; no dead ends. | Contract only (R1) |
| Accounts/billing | None. | M2 accounts, billing, quotas, admin. | M2 |
| Style memory | `localStorage`. | Account-scoped preference after accounts exist `[TBD-BE]`. | Prototype (mock) |
| Stale propagation | Client state flags and amber dots; no real rerun jobs. | Server-side dependency tracking and incremental rerun. | Prototype (state only) |
| Accessibility | Keyboard matrix, focus ring, reduced motion, live regions; P2 gaps (roving tabindex, mobile fit toggle). | WCAG 2.2 AA baseline; complete keyboard matrix; no pointer-only core action. | Prototype baseline |
| Material limit | 6-item demo constraint. | Configurable real default `[TBD-UX]`; no packaging hard-coded to 6. | Prototype (demo) |
| Content | Fixed "Dify company introduction" mock. | User topic and sources; grounding rubric; no fabricated facts. | Prototype (mock) |

---
