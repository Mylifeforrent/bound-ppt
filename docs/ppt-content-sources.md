# Bound PPT · Content source design (v2.1)

> Version: v2.1 · 2026-11-18 (aligned with interaction flow v3: gaps are suggested by the Agent and confirmed by the user)
> Question it answers: where does Bound PPT's presentation content come from? How is each source type ingested and digested by the Agent?
> Related docs: interaction flow v3 (`docs/ppt-agent-interaction-flow.md`, stages 1/2 updated per this document); UX review (`docs/ppt-agent-ux-review.md`).

---

## 0. Background and problem definition

The v1 entry point was "user provides a topic → Agent searches the web": stage 1 only accepted a topic, and stage 2's Agent behavior was hard-coded as `web_search(...)`. That treated "web search" as the default main ingredient.

In real work, users in most PPT scenarios **already have material**: project reports use BI data and weekly reports, pre-sales proposals use client RFPs and internal case libraries, tech talks use code repositories and design docs — only competitive analysis truly relies on web search as the main ingredient (see the scenario matrix in §3). So v2 explicitly models content sources as five channels and upgrades the entry point from "topic → web research" to "topic + materials → material digestion + gap filling".

**Core principle: first-party materials come first; web search is downgraded to a gap-filling tool.**

---

## 1. Content source landscape (five channels)

### 1.1 Your own work output (first-party material, highest credibility)

| Subcategory | Specific sources |
| --- | --- |
| Documents and reports | PRD / proposals / design docs (Word, Feishu Docs, Yuque, Notion, Confluence, Markdown), weekly / monthly / quarterly / annual summaries, retrospectives, meeting notes |
| Communication records | Email threads, IM discussions (WeCom / Feishu / Slack / WeChat groups), iteration records in ticket systems (Jira / Linear / TAPD) |
| Data | Excel / CSV business tables, BI reports and dashboards, database query results, survey results, A/B experiment and telemetry data |
| Visual and product assets | Figma designs, product UI screenshots, demo recordings, whiteboard exports (Miro / FigJam), mind maps (XMind), hand-drawn sketches / whiteboard photos |
| Reusable historical assets | Old PPTs (same topic / same client), company templates and brand guidelines, chart/image asset libraries, case libraries / bid document libraries |
| Verbal material | Voice memos, meeting recordings and transcripts, your own customer / expert interview notes |

### 1.2 Organizational knowledge (team assets)

Internal wikis and knowledge bases (Confluence / Yuque / Feishu Knowledge Base / SharePoint), policies and standards, historical training decks, internal competitive and industry intelligence briefs, CRM customer data, finance / operations system exports.

The difference from 1.1 is **ingestion**: personal output comes through "drag-and-drop files", organizational assets through "account authorization connections".

### 1.3 External public information (the only category v1 covered)

Search engines and encyclopedias, news media, industry reports / white papers, public company financials and prospectuses, academic papers, competitor public materials (official website, launch events, pricing pages, job descriptions), communities and social media (linux.do, Zhihu, WeChat public accounts, X, Reddit, Bilibili).

### 1.4 Interpersonal and offline materials (external, but not searchable)

Files sent by others (client RFP / tender, quotes, email attachments, group files), interview and conference-call recordings/transcripts, digitization of physical items (trade-show materials, brochures, book photos, scans), audio/video content (podcasts, launch recordings, course videos transcribed into text/images).

### 1.5 In-head and conversation (zero-material starting point + immediate expression)

A one-sentence topic, a few keywords, spoken ideas (speech-to-text), a short outline, a hand-drawn page sketch, and **the interview Q&A itself** — stage 2 answers are both constraints and content sources, injected into outline generation along with the requirements profile.

---

## 2. Three dimensions that determine ingestion design

### 2.1 Structure level → Agent processing strategy

| Material form | Example | Processing strategy |
| --- | --- | --- |
| Finished | Complete documents, old PPTs | Extract, compress, rewrite; research barely needed |
| Fragmented | Notes, chat logs, dictation | Summarize and integrate + fill gaps |
| Data | Spreadsheets, reports, BI screenshots | Data storytelling + charting |
| Blank | Only a topic | Interview + web search (v1 behavior) |

### 2.2 Medium and accessibility

Zero barrier (paste text, drag files) → low barrier (URL fetch) → high barrier (authorized connections to Feishu / Notion, etc.). Accessibility determines MVP trade-offs (see §4).

### 2.3 Material sufficiency (v2 core mechanism)

The Agent first digests existing material and judges "is it enough to support the outline"; if not, it lists a **gap list** (missing data, cases, competitor comparison), then decides whether to ask the user to add more or fill via web search. That is, `web_search` is downgraded from "default first action" to "gap-filling tool".

---

## 3. Scenario × primary source matrix

| High-frequency scenario | Primary sources | Role of web search |
| --- | --- | --- |
| Project / quarterly report | BI data, weekly reports, ticket records | Almost none |
| Product launch | Internal docs + business data | Fill industry benchmarks |
| Fundraising roadshow | Business data | Fill market size, competitors, industry reports |
| Pre-sales / bidding | Client RFP + internal case library | Fill qualifications and industry trends |
| Tech sharing | Code repository, design docs, README | Fill community and ecosystem news |
| Training deck | Internal standards + old decks | Basically none |
| Competitive analysis | Competitor public materials | **Primary** |
| Thesis / graduation defense | Your thesis + experiment data | None |

Across the eight high-frequency scenarios, only competitive analysis truly relies on web search as the primary source — direct evidence of the limits of a single search entry point.

---

## 4. Ingestion priority and v2 scope

### 4.1 Priority order

**Paste text / drag files → URL fetch** → (later) speech transcription → (later) authorized access to internal systems (Feishu / Notion, etc.; highest value but most engineering).

### 4.2 v2 scope (already reflected in the interaction flow and prototype)

| Capability | Behavior | Tool card |
| --- | --- | --- |
| Paste text | Stage 1 material slot paste → material chip | `read_paste_text` |
| Drag / select files | Stage 1 material slot drop or click to select | `ingest_file(filename)` |
| URL fetch | Stage 1 material slot add link | `fetch_url(url)` |
| Material grouping | Stage 2 content-source panel splits "Your materials / Web supplements" | `source.origin` |
| Material digest | After stage 2 material digestion, show "what was extracted" per item | `digest` event |
| Gap suggestions | After the digest, the Agent proposes 3 gaps (with reasons and a "suggested" badge; recommended ones pre-checked) | `gap_suggest` |
| Gap confirmation | User adds/removes gaps, or chooses "Not needed — just use my materials"; choosing "not needed" clears the others | `gap_decision`; skipping web means the outline is entirely material-based |

The prototype is a mock: files only record name / type / size and are not actually parsed; URLs are not actually fetched. Real implementation scope **[TBD-BE]**:

- The list of supported file types (candidates: docx / pdf / xlsx / pptx / md / txt / images) and parsing size/page limits — frozen by the backend before development based on parser availability.
- Degradation strategy when URL fetching hits a login wall / anti-scraping — confirmed by the backend before development.

### 4.3 Later roadmap (out of v2 scope)

Speech transcription (meeting recordings / dictation); authorized access to organizational assets (Feishu / Notion / Confluence OAuth); old PPT parsing and reuse; IM / email record import.

---

## 5. Data contracts (aligned with interaction flow v2 §3.1)

```ts
interface Material { id: string; kind: 'paste' | 'file' | 'url'; title: string; meta: string; }
interface Source   { title: string; summary: string; origin: 'provided' | 'web'; }
interface GapSuggestion { label: string; reason: string; recommended: boolean; } // Agent suggestion
interface GapDecision   { label: string; selected: boolean; }                    // User confirmation
```

Rules:

- Material chip limit is 6 (prototype demo constraint; the real product's default limit **[TBD-UX]**, confirmed by design at the visual design stage).
- Source conflict priority: **first-party materials > organizational assets > web supplements**; the outline generation prompt must state this priority.
- Interview answers themselves are also counted as content sources (semantic extension of `origin: 'provided'`), injected into outline generation along with the requirements profile.
- **Gaps must be proposed by the Agent**: digest materials and output a summary first, then give suggestions with reasons; the user only confirms and chooses, and is not responsible for figuring out "what is missing".
- Gap confirmation is a material strategy and cannot be modified at the profile stage; a real product should support "re-search and update the profile" (`[TBD-FE]`).

---

## 6. Impact on the interaction flow (summary)

1. Stage 1 is upgraded to "topic + material entry"; when the material slot is empty, the v1 web-only path remains (backward compatible).
2. Stage 2 changes from "web research" to "material digestion + Agent gap suggestions + user confirmation"; the content-source panel is split into two groups, with material digests and skeleton/empty states added.
3. The requirements profile card adds "Materials" and "Web" rows; the profile can be edited, and after answers change the profile must be updated before entering the outline.
4. The gap card becomes "Agent suggestion + reason + recommended badge + pre-selected"; the user only confirms and chooses; choosing "not needed" clears the other items.
5. Detailed interactions in `docs/ppt-agent-interaction-flow.md` §2 stage 1 / stage 2; review conclusions in `docs/ppt-agent-ux-review.md`.

---

## 7. Open questions

| ID | Item | Owner / confirmation stage |
| --- | --- | --- |
| TBD-BE-1 | List of file types supported by v2 and parsing limits | Backend · frozen before development |
| TBD-BE-2 | URL fetch degradation strategy for login walls / anti-scraping (e.g. prompt the user to paste the body text) | Backend · before development |
| TBD-BE-3 | Prompt / rules for "material sufficiency" judgment and gap suggestions | Backend · before development |
| TBD-UX-1 | Material chip count limit and user messaging for oversized files | Design · visual design stage |
| TBD-UX-2 | Material preview form (show parsing summary? expandable source text?) | Design · visual design stage |
| TBD-UX-3 | Default selection strategy and display order of gap suggestions | Design · visual design stage |
| TBD-FE-1 | Interaction for "re-search and update gaps" after the profile is generated | Frontend · before development |

---

## 8. Version history

- **v2.1 (2026-11-18)**: aligned with interaction flow v3. Gaps changed from "user self-reported" to "Agent suggestion + reason + recommendation + user confirmation"; added material digest, gap decision data contracts, profile dirty-data gate, and re-search TBD.
- **v2 (2026-11-16)**: initial content source system (five channels, ingestion priority, data contracts), paired with interaction flow v2.
