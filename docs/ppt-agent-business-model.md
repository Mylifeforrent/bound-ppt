# Bound PPT · Business model (v1)

> Version: v1 · 2026-11-18
> Basis: interaction flow v3 (`docs/ppt-agent-interaction-flow.md`), content source design v2.1 (`docs/ppt-content-sources.md`), UX review follow-ups (`docs/ppt-agent-ux-review.md` §5), post extract (`docs/linux-do-1782304-ppt-agent-extract.md`).
> Scope: how Bound PPT creates, delivers, and captures value. This is a **business-model design document**, not a financial forecast, a market-sizing study, or a pricing commitment.
> Evidence rule: product facts cite the source section. Unverified business hypotheses are marked `[ASSUMPTION]`. Decisions not yet made are marked `[TBD-BIZ]` with owner and confirmation stage. No price, market size, or competitor figure is asserted without a source.
> Known boundary: the interaction flow defines the user experience, not accounts, billing, admin, collaboration, or data policy. Those are business-model prerequisites and are listed in §10.1.

---

## 0. One-page summary

Bound PPT is an "expert team–style" PPT Agent: the user supplies a topic and any existing materials, and the Agent runs a researcher → planner → designer pipeline while the user makes a few high-leverage confirmations at checkpoints [FLOW §0]. The six stages are material intake, research + interview, sticky-note outline, plan draft, style selection, and design draft / export [FLOW §1].

**Business thesis.** The product is not competing with "faster template filling". It sells an agency-like first draft that is grounded in the user's own materials, controllable before expensive design work, and exportable as an editable deliverable. The users most likely to pay are professionals with material-rich, deadline-driven, high-stakes decks (pre-sales/bidding, product and marketing launches, founder fundraising), and later teams that need brand consistency and knowledge reuse.

**Three bets** `[ASSUMPTION]`:

1. Material-rich users will pay for relevance and control, not only generation speed.
2. Editable output (SVG-composited PPTX) supports a price premium over image-based or rigid-template output.
3. The six-stage workflow, material ingestion, and reliability features (undo, stale detection, failure recovery) create switching costs that a generic chat model does not.

**Recommended starting model** `[ASSUMPTION]`: freemium subscription with an included monthly generation allowance, overage credits, and later team/enterprise tiers. Charge for capacity, quality, and collaboration — never for undo, history, accessibility, or error recovery.

**Cost engine.** Per-deck LLM inference across research, plan, and design pages dominates variable cost; regeneration, tweaks, and stale reruns multiply it. Regeneration and rerun policy is therefore the primary unit-economics lever (§5, §7).

**Readiness.** The current artifact is a clickable prototype with mock parsing, mock search, mock design generation, and mock export [FLOW §5, §6]. Paid launch is blocked by real material parsing/URL fetch, failure recovery, background task execution, and real export validation (`R1`, `R3`, `R4`, `R7` in the UX review §5). The interaction flow defines contracts for these, not implementations [FLOW §6].

**What must be true before a paid launch:**

| # | Condition | Current status | Evidence needed |
| --- | --- | --- | --- |
| 1 | Material ingestion works reliably for common formats and URLs | Mock only; parsing limits are `[TBD-BE · backend, before development]` [SRC §4.2] | Parsing success rate by file type, URL degradation path |
| 2 | Export produces an Office-usable, editable PPTX | Mock only; export failure path undefined [FLOW §6] | Export fidelity review in PowerPoint, font/asset handling |
| 3 | Users perceive the interview and gap confirmation as value, not friction | Designed but unvalidated [FLOW §2 stage 2] | Completion rate, time-to-profile, edit rate |
| 4 | Variable cost per exported deck leaves room for gross margin | No instrumentation | Stage-level token/search/parse cost telemetry |
| 5 | Users produce more than one deck per quarter | Unknown | Repeat project rate, cohort retention |
| 6 | Some segment shows willingness to pay above free-tier limits | Unknown | Paid pilot conversion, willingness-to-pay interviews |

---

## 1. Product value and business thesis

### 1.1 What the customer actually buys

| Business problem | Product mechanism | Customer value | Source |
| --- | --- | --- | --- |
| One-click tools produce generic decks from a topic | Sequential interview plus Agent gap suggestions before the outline | A targeted deck with fewer rewrites; the user only confirms, does not diagnose what is missing | FLOW §0.1 #1, §2 stage 2; UX review §3.1 |
| Company knowledge is ignored by web-only research | Material slot (paste/file/link) + per-material digest + targeted gap filling | Accurate, first-party content; less dependence on public search; confidential material can stay inside | FLOW §0.1 #8, §2 stage 2; SRC §0, §5 |
| Design changes are expensive, so users over-invest in reviewing finished slides | Sticky-note outline + grayscale plan draft before style is applied | Cheap structural edits at the right abstraction level; fewer expensive design reruns | FLOW §2 stages 3–4; extract §II.3 |
| AI output is not usable in Office or is not editable | Full-page SVG composition; export as PPTX / HTML / PDF | A deliverable that can be opened, edited, and presented in the tools the customer already uses | FLOW §0.1 #6, §2 stage 6; extract §IV |
| AI behavior is unpredictable, so users do not trust it with important work | Per-page history and undo, no fake variants, stale markers, "needs rerun" propagation | Recoverability and predictability; fewer support requests and less rework | FLOW §2 stage 6, §3.4; UX review §3.4 |
| Automation is one-speed: either too slow or too uncontrollable | Fully automatic mode plus expert copilot; pausable auto-advance; per-page ops | Serves both "pour a coffee" and "important board deck" occasions with one product | FLOW §1, §2 stages 3–4 |

### 1.2 Positioning against alternative categories

| Alternative | What it optimizes | Limitation Bound PPT targets | Bound PPT counter |
| --- | --- | --- | --- |
| Template-based AI PPT generators | Speed from a topic to outline + template | Generic content, template lock-in, weak use of first-party material ("force it into a template", per the post's criticism) | Research + interview first, material-first content, Bento layout vocabulary instead of a fixed template |
| Image-generation slide tools | Visual polish | Output pages are images; edits require regeneration or external tools | SVG-composited, fully editable pages and Office-compatible export |
| General chat assistants | Flexible text generation | User must assemble structure, layout, and export manually; no state machine, undo, or stale handling | End-to-end six-stage workflow with checkpoints and recovery |
| Design agencies / freelancers | Quality and accountability | High cost and turnaround time; especially for routine decks | Agency-like first draft at software cost and speed; human review only where it matters |
| Manual PowerPoint / Keynote | Full control | Time-consuming; most effort goes into structure and layout before content polish | AI draft plus per-page control and editable output |

> The competitive descriptions above are category-level and are not a vendor comparison. Vendor-specific claims require a dated competitive review `[TBD-BIZ · product, before paid launch]`.

### 1.3 Defensibility hypothesis

The post calls the Bento layout prompts "one of the project's core moats" [extract §II.4]. For business purposes, prompts alone are copyable; the durable layers are expected to be:

1. **Workflow and state quality** — interview logic, gates, undo, stale propagation, failure recovery. Easy to describe, hard to make coherent.
2. **Material ingestion** — real parsing, URL degradation, and later connectors to organizational knowledge. Operationally heavy and trust-sensitive.
3. **Design system and evaluation set** — layout vocabulary, style library, and a repeatable quality bar.
4. **Export fidelity** — SVG composition, font handling, Office compatibility. Engineering depth that affects the core promise.
5. **Distribution and community** — the product originates from a public linux.do breakdown, which supports build-in-public and practitioner credibility.

All five are `[ASSUMPTION]`; none is validated as a moat until win/loss and retention data exist.

---

## 2. Customer segments and jobs

### 2.1 Primary users [FLOW §0.2]

| Segment | Core job | Trigger | Material richness | Repeat use | Value that matters most | WTP hypothesis |
| --- | --- | --- | --- | --- | --- | --- |
| Product managers | Product launch, roadmap review, quarterly report | Release cadence, review cycles | High (PRDs, data, tickets) | High | Accuracy, speed, editable output | Medium-high `[ASSUMPTION]` |
| Marketing | Campaign, launch, brand and event decks | Campaign calendar | Medium-high (briefs, assets, past decks) | High | Visual quality, brand consistency, speed | Medium-high `[ASSUMPTION]` |
| Pre-sales / solutions | Client proposal, bid/tender, solution defense | RFP deadlines | Very high (RFP, case library, pricing) | High and deadline-driven | Relevance to the client, reuse of cases, editable output | High `[ASSUMPTION]` |
| Founders / executives | Fundraising, board, company introduction | Fundraising rounds, board meetings | Medium-high (metrics, narrative, old decks) | Episodic but high stakes | Polish, narrative, confidentiality | High per deck `[ASSUMPTION]` |

### 2.2 Scenario demand [SRC §3]

| Scenario | Primary sources | Role of web search | Fit for material-first positioning |
| --- | --- | --- | --- |
| Project / quarterly report | BI data, weekly reports, tickets | Almost none | **Strong** — little public information can substitute |
| Product launch | Internal docs + business data | Fill industry benchmarks | **Strong** |
| Fundraising roadshow | Business data | Market size, competitors, industry reports | Medium-strong — web supplements matter |
| Pre-sales / bidding | Client RFP + internal case library | Qualifications and industry trends | **Strong** — high value, deadline-driven |
| Tech sharing | Code repository, design docs, README | Community and ecosystem news | Medium |
| Training deck | Internal standards + old decks | Basically none | **Strong** for organizations |
| Competitive analysis | Competitor public materials | Primary source | Weak — web-first; less differentiated |
| Thesis / graduation defense | Thesis + experiment data | None | Weak as a business segment — low willingness to pay |

### 2.3 Beachhead recommendation `[ASSUMPTION]`

Start with **pre-sales/bidding** and **product/marketing launch** decks inside material-rich organizations. Rationale:

- The user already has the raw material that v2/v3 is designed to exploit [SRC §0].
- The cost of a poor deck is high and the deadline is real, so quality and reliability outrank price.
- Decks recur, which supports subscription rather than one-off purchase.
- The output must be edited by the user or a designer afterward, so editable export is a purchase requirement rather than a nice-to-have.

Validate with 10–15 problem interviews and 5 paid pilots before freezing the segment `[TBD-BIZ · founder, before paid pilot]`.

**Deliberately later:** students and one-off users (low willingness to pay, high support volume), pure template buyers, and competitive-analysis-only users (web-first, weakest differentiation).

### 2.4 User versus buyer

For individual plans, the deck maker is the buyer. For team and enterprise plans, the user is the deck maker but the economic buyer is a team lead, enablement owner, or IT/security. The buyer cares about brand consistency, shared case/material libraries, seat administration, data governance, and invoiceability — capabilities not designed in the v3 flow. Team and enterprise packaging therefore depends on roadmap items in §10.1, not merely a pricing page.

---

## 3. Value proposition by segment

| Segment | Pain | Promise | Proof the product must show |
| --- | --- | --- | --- |
| Individual professional | "I spend hours on structure and layout before the content is right" | A targeted first draft in one sitting, with control at outline and plan | Time to first exported deck; edit effort per page |
| Pre-sales / bid team | "Every proposal starts from zero even though we have cases and past bids" | Reuse first-party material, fill only the real gaps, output an editable client deck | Case reuse rate; gap acceptance rate; export fidelity |
| Marketing / brand owner | "AI decks do not follow our brand" | Consistent style system, shared brand kits (team tier), editable output | Brand-consistent sample decks; shared style adoption |
| Founder / executive | "This deck is important and I cannot send something generic" | Agency-like quality with per-page control and undo | Before/after quality review; recovery behavior |
| Team / enterprise buyer | "We cannot let confidential material go to arbitrary tools" | Material-first flow, governance, connectors, retention controls | Security review pack; data-flow diagram; deletion policy |

---

## 4. Business Model Canvas

| Block | Design | Status |
| --- | --- | --- |
| Customer segments | Individual knowledge workers (PM, marketing, pre-sales, founders); teams with brand and case assets; enterprises with internal knowledge systems | Primary segments sourced from FLOW §0.2; team/enterprise requires undesigned features |
| Value propositions | Agency-like draft grounded in first-party material; control before expensive design; editable export; recoverable and predictable AI | Product mechanisms exist in flow; willingness to pay unvalidated `[ASSUMPTION]` |
| Channels | Product-led web app; community and build-in-public (linux.do origin); scenario landing pages and showcase decks; partnerships; bottom-up enterprise entry | `[ASSUMPTION]`; channel economics `[TBD-BIZ · founder, before paid launch]` |
| Customer relationships | Self-serve with in-product guidance; community support; paid support/SLA later; enterprise success and security review | Support model `[TBD-BIZ · founder, before paid launch]` |
| Revenue streams | Freemium subscription; generation/overage credits; team seats; enterprise contracts; possible premium model and brand services | Hypothesis only; see §6 |
| Key resources | Six-stage workflow and prompts; Bento layout vocabulary and SVG renderer; style library; parsing and export pipeline; evaluation set; community credibility | Extract calls the layout methodology a moat [extract §II.4]; durability `[ASSUMPTION]` |
| Key activities | Model orchestration; material ingestion and digest; render/export fidelity; quality evaluation; cost governance; support | Ingestion and export are mock today [FLOW §5, §6] |
| Key partners | Model provider(s); search API; document parsing/OCR; payment; cloud; font/image licensors; template or brand partners | Vendors and commercial terms `[TBD-BIZ · founder, before paid launch]` |
| Cost structure | Variable: LLM inference, search, parsing, storage/egress, export compute. Fixed: engineering, design, infrastructure baseline, support, compliance | Structure is known; magnitudes require instrumentation §7 |

**Value and money flow (conceptual):**

```
topic + first-party materials
        │
        ▼
research & interview → outline → plan → style → design → export
        │              │         │                │
        └── LLM + search + parsing cost ──────────┘
                                                       │
                     charge at: export / capacity / quality / collaboration
                     never at: undo, history, accessibility, error recovery
```

---

## 5. Cost structure and the six-stage value chain

The interaction flow is also the cost model: every stage that calls a model has a per-deck variable cost, and every user-visible retry is a paid generation.

| Stage | Agent work [FLOW §2] | Primary cost driver | What makes it vary | Business lever |
| --- | --- | --- | --- | --- |
| 1 · Material intake | Material chips, type/size validation, limit of 6 in the prototype | Parsing/OCR, storage | Number, size, type, page count of materials | Supported-type list, material caps by plan, paid higher caps |
| 2 · Research + interview | One tool call per material, digest, Agent gap suggestions, targeted searches; no-material path uses 4 searches / 12 sources | LLM input tokens, search API | Material volume, gap count, whether web is skipped | Digest caching; source caps; targeted search is already cheaper than blanket search; free tier can default to the web-only path |
| 3 · Outline | Streamed outline JSON; if the requirements profile changes after generation, the outline is marked unconfirmed and plan/design rerun after re-confirmation [FLOW §3.4] | LLM output, rerun | Page count, edit/rerun frequency | Outline edits are cheap compared with design; keep the profile-dirty gate; limit regeneration to the affected scope |
| 4 · Plan draft | One plan per page plus per-page re-plan and tweaks | LLM output per page | Page count, re-plan rate | Cheaper model tier for plan; limit plan variants; reuse unchanged pages |
| 5 · Style | Style selection; preference memory | Negligible inference | — | Premium style packs and brand kits; style is a packaging dimension, not a cost center |
| 6 · Design draft | One design per page, per-page regenerate/tweak, per-page history | LLM output per page per variant, export compute | Page count, regeneration rate, variant depth, export format | Regeneration allowance; undo protects retention; premium model; pre-export validation |
| Cross-cutting · Stale rerun | Automatic rerun of stale downstream stages on entry | Cascading LLM calls | Change type from the stale matrix [FLOW §3.4] | **Incremental rerun by affected page**, not full-deck; strict stale scope; cost telemetry |
| Cross-cutting · Long tasks | Background generation, page locking, cancellation contract | Infrastructure, retries | Concurrency, deck size, failure rate | Queue priority as a paid lever; timeouts; idempotent retries |

### 5.1 Cost-governance rules (proposed)

1. **Rerun must be incremental.** The stale matrix already distinguishes title/order changes (design only) from structural changes (plan + design) [FLOW §3.4]. A full-deck rerun after a one-title edit would make the unit economics unpredictable; page-level incremental rerun is a business requirement, not only an optimization. `[TBD-BE · architecture stage]`
2. **Cache by input.** Reuse the research digest, plan, and design output for pages whose inputs did not change. Regeneration must not silently regenerate the whole deck.
3. **Route models by stage.** The post recommends Gemini 3 Flash for cost/quality balance and 3.1 Pro when budget allows [extract §VI #8]. Use a cheaper tier for digest/plan and reserve premium inference for design or a paid "high-quality" option. `[ASSUMPTION]`
4. **Cap the expensive dimensions.** Materials, page count, and regenerations are the three dimensions that scale cost; expose them as plan limits rather than hiding them.
5. **Validate before export.** A failed export that forces regeneration is pure cost and trust loss; pre-export validation is a margin protection feature (`R7`, UX review §5).
6. **Instrument before pricing.** No price should be set before per-stage cost telemetry exists (§7).
7. **Never charge for trust features.** Undo, previous version, stale markers, and error recovery reduce churn and support cost; paywalling them damages the product promise [FLOW §2 stage 6; UX review §3.4].

---

## 6. Revenue model and packaging

### 6.1 Principles

- Charge for delivered value: exportable decks, capacity, quality, collaboration, governance — not for tokens.
- The free tier must complete one full loop (materials → interview → outline → plan → style → design → export) so the user can verify the core promise.
- Usage overage should track marginal cost; subscriptions should not subsidize unbounded regeneration.
- Team and enterprise tiers require capabilities that do not exist in the v3 flow; do not sell them before the product can support them.

### 6.2 Packaging hypothesis `[ASSUMPTION]`

| Plan | Target | Included value | Limits | Price | Status |
| --- | --- | --- | --- | --- | --- |
| Free | Individual evaluation | Full six-stage flow; web path; limited materials; PDF/HTML and capped PPTX export; undo/history | 1 active project, capped pages, low regeneration allowance, 2 styles | 0 | Recommended to prove the core loop |
| Pro | Individual professional | Higher project/page limits; all styles; full PPTX/SVG export; larger regeneration allowance; priority queue | Fair-use generation allowance | `[TBD-BIZ]`, monthly/yearly | Core revenue hypothesis |
| Team | Marketing, pre-sales, enablement | Shared brand styles, shared material/case library, seats, admin, shared version history | Seat-based; shared quotas | `[TBD-BIZ]`, per seat | **Blocked** on collaboration/admin features not in v3 |
| Enterprise | Large organizations | SSO, private/VPC deployment, retention and deletion controls, connectors to Feishu/Notion/Confluence, audit, custom styles | Contractual | `[TBD-BIZ]`, annual | **Blocked** on connectors [SRC §4.3] and security work |
| Add-ons | All paid plans | Extra generation credits; premium model; brand-kit setup; onboarding/training | — | `[TBD-BIZ]` | Hypothesis |

Notes:

- Gate the *volume and quality* dimensions, not the core proof. Free users should be able to export an editable deck; otherwise they cannot verify the central claim that separates Bound PPT from image-based tools.
- Regeneration is the most natural usage metric but also the most anxiety-inducing. Prefer a stated allowance with graceful degradation ("you can still edit and export; extra regenerations next cycle") over hard paywalls mid-deck.
- The prototype's 6-material limit is a demo constraint; the real default limit is `[TBD-UX · design, visual design stage]` [SRC §4.2]. Do not hard-code packaging around 6 before design freezes it.
- All price cells above inherit the price-setting work in §6.3: `[TBD-BIZ · founder + finance, after paid pilot]`.

### 6.3 Value metric and price-setting framework

**Candidate value metrics:** active projects, pages designed, exported decks, regenerations. **Recommendation:** a hybrid — subscription with an included monthly allowance measured primarily in designed pages, expressed to users as "decks up to N pages", with regeneration allowances and overage credits. This aligns price with the dominant cost driver while remaining understandable.

**Anchors:**

- High end: the post reports that top domestic PPT design firms quote 10k+ RMB per page for a planner-led process [extract §II.3]. This is a high-end anchor for high-stakes decks, not a mass-market price point.
- Low end: template sites and generic AI tools anchor near zero for speed and templates.
- The product should be priced between DIY tools and agencies, and justify the gap with material grounding, control, and editable output.

**Price research before launch** `[TBD-BIZ · founder + finance, before paid launch]`: willingness-to-pay interviews by segment, a fake-door test for the Pro plan, and a paid pilot with 5–10 design partners. Do not publish price points until cost telemetry and pilot conversion exist.

### 6.4 What is not monetized

Undo and version history, stale detection, accessibility, failure recovery, and basic export are product-trust features. They may differ in depth across plans (for example, cross-project global history later, `R6`), but the core recovery loop stays available to every user.

---

## 7. Unit-economics framework

No numbers are asserted here; the goal is to define what must be measured before pricing.

| Metric | Definition | Why it matters |
| --- | --- | --- |
| `cost_per_research` | LLM input + search + parsing cost per project through the profile gate | Determines whether a free trial is affordable |
| `cost_per_plan_page` | Inference cost to plan one page | Scales directly with deck length |
| `cost_per_design_page` | Inference cost to render one design page, including style application | Largest per-page cost driver |
| `regeneration_intensity` | Regenerated pages ÷ designed pages | Measures both user dissatisfaction and cost leakage |
| `rerun_cascade_factor` | Pages rerun ÷ pages actually changed | Must approach 1.0; exposes full-deck rerun behavior |
| `cost_per_exported_deck` | Total variable cost ÷ successful exports | The core unit-cost number for pricing |
| `gross_margin_per_deck` | (Revenue − variable cost) ÷ Revenue | Subscription viability |
| `export_success_rate` | Successful exports ÷ export attempts | Failure costs generation and trust |
| `free_to_paid_conversion` | Paying accounts ÷ activated free accounts | Validates the free-tier boundary |
| `decks_per_paid_account` | Exported decks per paid account per period | Tests whether usage supports subscription |
| `cac_payback_months` | CAC ÷ monthly contribution margin | Channel viability |

**Formulas:**

```
variable_cost_per_deck =
    research + Σ(plan_page) + Σ(design_page)
  + Σ(regeneration) + search + parsing + storage + export_compute

contribution_margin = ARPU − variable_cost_per_deck
```

Targets (gross margin, cascade factor, regeneration intensity, payback) are `[TBD-BIZ · founder + finance, after paid pilot]`. Instrumentation must be server-side; the prototype's simulator events are client-side only [FLOW §3.2].

---

## 8. Go-to-market

### 8.1 Wedge and proof assets

- **Message:** "Bring your materials; get an editable, on-message deck — with the structure you can still control."
- **Proof assets:** a real PPTX opened and edited in PowerPoint (not a video of the app), before/after material-to-deck walkthroughs, and a time-to-first-draft comparison.
- **Showcase scenarios:** one pre-sales/bid deck, one product launch, one quarterly report, one fundraising deck. These match the high-fit scenarios in §2.2.

### 8.2 Funnel mapped to the six-stage flow

| Funnel stage | User action | Business event | Metric | Lever |
| --- | --- | --- | --- | --- |
| Acquisition | Lands on a scenario page or community post | Visit / sign-up | Traffic → sign-up | Scenario landing pages, community credibility |
| Activation | Adds topic and materials, completes interview | `question_answer`, `digest`, `gap_decision`, `profile_ready` | Interview completion rate, time to profile | Sequential questions, Agent gap suggestions, skip-web path |
| First value | Confirms outline and sees plan/design | `outline_done`, `page_done` | Time to first design page, outline edit rate | Sticky-note board, pausable auto-advance |
| Conversion moment | Attempts export | `export` | Export attempt → paid conversion | Editable export, scope summary, export success |
| Habit | Starts a second project | New project | Second-deck rate within 30 days | Style memory, reusable brand/material setup |
| Referral | Shares a deck or recommends the tool | Referral / invite | Referred sign-ups | Opt-in sharing only; confidential materials must not leak |

Recommended activation definition `[ASSUMPTION]`: a completed first export of a deck with at least N pages; N is `[TBD-BIZ · founder, before paid launch]`.

### 8.3 Channels

1. **Community and build-in-public.** The product originates from a public linux.do teardown; continue with transparent design notes, failure write-ups, and practitioner case studies. `[ASSUMPTION]`
2. **Scenario SEO and content.** Landing pages for fundraising, bid/tender, quarterly report, and product launch; free style samples and outline templates.
3. **Product-led sharing.** Exported decks and read-only preview links can carry opt-in attribution; never expose material content by default.
4. **Partnerships.** Sales-enablement consultancies, incubators/accelerators, and brand/template agencies. `[TBD-BIZ · founder, after paid pilot]`
5. **Bottom-up enterprise.** Pro users bring the product into pre-sales and marketing teams; convert to Team when shared libraries and admin exist.

### 8.4 Trust as a channel

Material-first positioning means the product handles client RFPs, internal data, and unreleased plans. A public data-handling page, a no-training-on-customer-data commitment, deletion/retention controls, and regional processing options are prerequisites for enterprise conversations `[TBD-BIZ · legal, before paid launch]`. Trust is also a differentiator against web-only tools, which cannot promise that confidential material stays out of public search paths.

---

## 9. Competitive position and threats

| Threat | Why it matters | Mitigation |
| --- | --- | --- |
| Model providers ship native slide generation | The workflow can be absorbed into a general assistant | Compete on material ingestion, structured control, export fidelity, and distribution; keep model portability |
| Template incumbents add AI | They own distribution and brand familiarity | Compete on content quality and first-party grounding, not template count |
| Image-based AI slide tools improve | Visual quality may be "good enough" for low-stakes decks | Emphasize editability and Office compatibility for high-stakes work |
| Price war | Free tools anchor expectations near zero | Segment focus, cost discipline via model routing and incremental rerun, paid value in capacity/quality |
| Prompt copycats | The published post already exposes the methodology | Build operational depth (parsing, export, recovery, evaluation) and community trust |
| Export fidelity failure | One bad PPTX damages the core promise | Pre-export validation, sample matrix, fast repair (`R7`) |

---

## 10. Risks, dependencies, and compliance

### 10.1 Product dependencies before charging

| Dependency | Why the business needs it | Source | Status |
| --- | --- | --- | --- |
| Real material parsing and URL fetching | Paid promise: "use your own material" | `R4`; SRC §4.2 | Mock only |
| Failure and recovery UX | Paid reliability: parse/search/generation/export failures | `R1`; FLOW §6 | Contracts only |
| Background tasks, cancellation, reconnect | Long decks cannot abort when the user navigates away | `R3`; FLOW §1, §6 | Prototype aborts |
| Real export validation and fidelity | The deliverable is the product | `R7`; FLOW §6 | Mock progress only |
| Accounts, billing, quotas, admin | Required for any paid plan | Not in FLOW | Undesigned `[TBD-BE · architecture stage]` |
| Collaboration and shared libraries | Required for the Team tier | Not in FLOW | Undesigned |
| Organizational connectors | Required for the Enterprise tier | SRC §4.3 | Roadmap |
| Server-side analytics and cost telemetry | Required for pricing and margin control | FLOW §3.2 is client-side only | Not built |

### 10.2 Business risks

| Risk | Impact | Mitigation | Owner / stage |
| --- | --- | --- | --- |
| Inference cost or provider pricing changes | Gross margin erosion | Model routing, caching, incremental rerun, usage allowances | `[TBD-BIZ · founder + engineering, before pricing]` |
| Regeneration and rerun cost blowout | Unpredictable unit economics | Regeneration allowance, cascade-factor target, incremental rerun | `[TBD-BIZ · product + engineering, architecture stage]` |
| Low willingness to pay versus free chat tools | Conversion failure | Beachhead segment with high-stakes decks; prove export and material reuse | `[TBD-BIZ · founder, paid pilot]` |
| Confidential material exposure | Enterprise disqualification and reputational harm | No-training policy, retention/deletion, regional options, least-privilege connectors | `[TBD-BIZ · legal + security, before paid launch]` |
| Copyright and font/image licensing in generated decks | Legal exposure for users and the product | Clear user responsibility terms, licensed font/image sources, export warnings | `[TBD-BIZ · legal, before paid launch]` |
| Hallucinated or unsupported content | Trust damage in high-stakes decks | Material-first priority, source list, visible conflict rule | Product already specifies material priority [SRC §5]; validation needed |
| Model-provider dependency | Quality or price shock | Abstraction layer, evaluation set, multi-provider option | `[TBD-BE · architecture stage]` |
| Team/enterprise scope creep | Engineering diverted before product-market fit | Freeze Team tier until collaboration/admin exists; focus on Pro | `[TBD-BIZ · founder, after paid pilot]` |
| Region-specific search, payment, and compliance | Launch blocked in the chosen market | Decide region before vendor and pricing work | `[TBD-BIZ · founder, before paid pilot]` |

### 10.3 Compliance questions `[TBD-BIZ · legal, before paid launch]`

- Data retention, deletion, subprocessors, and regional processing for uploaded materials.
- Whether customer material or generated output may be used for model improvement (recommended default: no).
- Ownership of generated decks and responsibility for user-supplied third-party content.
- Font, image, and icon licensing for SVG-composited exports.
- Invoicing, tax, and payment requirements in the launch region.

---

## 11. Metrics and milestones

### 11.1 North star and guardrails

**North star (proposal)** `[ASSUMPTION]`: exported decks per active account per month. Because acceptance is hard to observe directly, pair it with regeneration intensity and export success rate as quality guardrails.

**Guardrails:** cost per exported deck, p95 time to first design page, generation failure rate, export failure rate, support contacts per 100 decks.

### 11.2 Instrumentation map from the interaction flow

| Flow event [FLOW §3.2] | Business meaning |
| --- | --- |
| `tool` / `source` | Material and research cost, ingestion success rate |
| `question` / `question_answer` | Interview completion and drop-off |
| `digest` / `gap_suggest` / `gap_decision` | Gap acceptance rate, web-skip rate, material sufficiency |
| `profile_ready` | Activation milestone |
| `outline_delta` / `outline_done` | Outline generation time and edit intensity |
| `page_start` / `page_done` (plan/design) | Throughput, per-page cost, failure rate |
| `history_push` / `history_pop` | Regeneration and undo behavior |
| `export` | Conversion moment and export success |
| Stale/rerun (new server-side event) | Rerun cascade factor and cost leakage |

The real product needs server-side events for billing, quota enforcement, and cost attribution; the prototype's event sequence is a client-side simulator [FLOW §3.2]. `[TBD-BE · architecture stage]`

### 11.3 Milestones and exit criteria

| Milestone | Scope | Exit criteria |
| --- | --- | --- |
| M0 · Prototype (current) | Interaction flow validated in a clickable mock | Flow walkthrough complete; known gaps listed in UX review §5 |
| M1 · Paid pilot readiness | Real parsing/URL fetch, failure recovery, real export validation, cost telemetry, terms and privacy page | 5–10 design partners complete real decks; export fidelity sign-off; unit cost measured |
| M2 · Self-serve paid launch | Accounts, billing, quotas, support runbook, scenario landing pages | Conversion and margin targets met on a small cohort `[TBD-BIZ · founder, before M2]` |
| M3 · Team / Enterprise | Collaboration, shared libraries, admin, connectors, security review | First team contract; security questionnaire passed |

Dates and revenue targets: `[TBD-BIZ · founder, after paid pilot]`.

### 11.4 Pivot criteria `[ASSUMPTION]`

- If activated users rarely export a second deck within 30 days, narrow the segment rather than broadened the feature set.
- If `cost_per_exported_deck` exceeds the planned share of price, fix model routing and rerun behavior before raising prices.
- If users consistently skip the interview and gap steps, reposition them as an optional "expert mode" rather than removing the differentiation.
- If PPTX export fidelity cannot reach an acceptable bar, pivot the paid promise toward HTML/PDF delivery for personal use, as the post itself suggests for non-editable use cases [extract §IV].

Thresholds: `[TBD-BIZ · founder + finance, before paid launch]`.

---

## 12. Open business decisions

| ID | Decision | Options | Recommendation | Owner / stage |
| --- | --- | --- | --- | --- |
| BM-1 | Beachhead segment | Pre-sales/bidding; product/marketing; founders; broad knowledge workers | Pre-sales + product/marketing `[ASSUMPTION]` | Founder · before paid pilot |
| BM-2 | Revenue model | Pure subscription; pure credits; hybrid | Hybrid subscription + allowance `[ASSUMPTION]` | Founder + finance · before paid pilot |
| BM-3 | Free-tier boundary | PPTX included with caps; PPTX gated; watermark | Include PPTX with page/regeneration caps; no watermark | Founder + product · before paid pilot |
| BM-4 | Price points | — | Do not set before cost telemetry and pilots | Founder + finance · after paid pilot |
| BM-5 | Premium model tier | Same model for all; paid high-quality model | Offer as Pro/add-on option | Product · M2 |
| BM-6 | Team/enterprise timing | Now; after collaboration/admin; never | After collaboration/admin exists | Founder · M3 |
| BM-7 | Data policy | Training opt-in; no training; region-specific | No training by default; explicit retention policy | Legal + founder · before paid pilot |
| BM-8 | Launch region and vendors | — | Decide before search/payment/compliance work | Founder · before paid pilot |
| BM-9 | Collaboration scope | Comments; real-time co-editing; shared libraries only | Start with shared libraries and brand kits | Product · M3 |
| BM-10 | Style marketplace | Built-in styles only; third-party marketplace | Built-in first; marketplace only after creator demand | Product · post-M2 |
| BM-11 | Licensing policy for fonts/images | Bundled licensed assets; user-supplied only | Bundled licensed set plus user responsibility terms | Legal · before paid launch |
| BM-12 | Paid support/SLA | Community only; email; SLA | Email support at M2; SLA only for Enterprise | Founder · M2 |

---

## 13. Version history

- **v1 (2026-11-18)**: initial business model document, derived from interaction flow v3. Covers value proposition, segments, Business Model Canvas, six-stage cost map, packaging hypothesis, unit-economics framework, GTM funnel mapped to flow stages, risks and dependencies, metrics, and open business decisions. All prices, market sizes, and competitor figures deliberately left as `[TBD-BIZ]`; no financial forecast is asserted.
