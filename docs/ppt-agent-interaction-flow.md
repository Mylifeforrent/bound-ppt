# Bound PPT Agent — Interaction flow design (v3)

> Version: v3 (2026-11-18). Review conclusions and remaining items in `docs/ppt-agent-ux-review.md`.
> Content source system in `docs/ppt-content-sources.md` (v2.1, aligned with stages 1/2 here).
> Companion clickable HTML prototype: `prototype/ppt-agent-prototype.html` (pure static single file, built-in mock LLM streaming).

---

## 0. Product positioning

**Bound PPT**: an "expert team–style" PPT Agent. The user provides a topic (and any existing materials), and the Agent runs the full pipeline like a real PPT company's "researcher → planner → designer" assembly line, while the user makes **few, high-leverage confirmations and adjustments** at key checkpoints.

### 0.1 Original post ideas → product implementation (mapping)

| # | Original post idea | Product implementation |
| --- | --- | --- |
| 1 | Forget "one-click generation", start with questions; AI does research like a professional consultant | **Stage 2 sequential interview**: first digest materials / retrieve information, then ask 4 key questions one at a time (plus 1 gap confirmation card when materials exist), producing an editable "requirements profile" |
| 2 | Retrieve a large amount of material first; the outline must be based on research | **Stage 2 content source panel**: two groups, "Your materials" and "Web supplements"; material + web summaries both feed outline generation |
| 3 | Sticky-note method: one page per sticky note, cover a wall | **Stage 3 sticky-note board**: outline presented as "digital sticky notes", with drag, button, and keyboard sorting, and per-section page insertion |
| 4 | Separate plan draft (layout planning) from design draft (style) | **Stage 4 plan draft** (grayscale Bento wireframe) and **Stage 6 design draft** (style applied) as two stages; plan supports per-page rerun and tweaks |
| 5 | Card layout (Bento Grid) is the design language AI understands most easily | Plan draft's **layout vocabulary** and design draft's **renderer** both use the six Bento compositions; the prototype's visual system itself uses a Bento-style modular layout |
| 6 | SVG goes directly into Office and is fully editable; HTML for personal use | **Export menu**: PPTX (SVG-composited) / HTML / PDF; before export, show a summary of page count, style, and render completeness |
| 7 | Fully automatic plus manual fine-tuning for important occasions | **Two modes**: fully automatic (confirm all the way to the design draft; the outline stage has a 3-second pausable countdown) / expert copilot (stop for confirmation at each stage); any page can be individually regenerated and undone |
| 8 | (v2 extension) Content sources are not limited to web search | **Stage 1 material slot** + **Stage 2 material digestion and gap filling**: first-party materials first, web search downgraded to gap filling |
| 9 | (v3 extension) Agent products must be recoverable, undoable, and predictable | **Gaps suggested by the Agent, auto-advance pausable, downstream stale markers, per-page version history, failure/empty-state contracts** (see §6) |

### 0.2 Users and scenarios

- Primary users: professionals who need high-quality external presentation materials (product / marketing / pre-sales / founders).
- Core scenario: enter a topic (optionally drop in documents, data, links) → pour a coffee → receive a deliverable design draft; for important PPTs, spend 5 minutes fine-tuning at the sticky-note / plan-draft checkpoints.
- New v3 scenarios: when the user repeatedly regenerates individual pages, they can step back to the previous version at any time; after leaving the page and returning, they can see which downstream artifacts need reruns.

---

## 1. Interaction overview

```
┌────────────────┐   ┌───────────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────────────┐
│ Stage 1        │   │ Stage 2           │   │ Stage 3      │   │ Stage 4      │   │ Stage 5      │   │ Stage 6              │
│ New project    │ → │ Research+interview│ → │ Outline·notes│ → │ Plan·wireframe│ → │ Style select │ → │ Design·preview/export│
│ Topic input    │   │ Digest+gap filling│   │ Drag/btn/kbd │   │ Per-page Bento│   │ Gallery+memory│   │ Rerun/undo/tweak/exp │
│ +material slot │   │ Sequential Q&A    │   │ +count warning│  │ +completion gate│ │              │   │ +lock pages while gen│
└────────────────┘   └───────────────────┘   └──────────────┘   └──────────────┘   └──────────────┘   └──────────────────────┘
                     ↑______________________ Back (top stage nav can jump to any reachable stage) _______________________↑
```

- **Global top bar**: logo, project name, stage nav (completed stages clickable, stale stages with an amber dot), mode badge (fully automatic / expert copilot).
- **Auto-advance**: in fully automatic mode, after stage 2 interview → stage 3 sticky notes stream in → **3-second countdown (pausable; editing auto-pauses)** → stage 4 auto-completes → pauses at the style page. In expert copilot mode, every stage ends at a "confirm button".
- **Back navigation**: any stage can click the top nav to return to a reachable stage; after changing the outline/plan/style, affected downstream stages are marked "needs rerun" and rerun automatically on entry.
- **Long tasks**: the prototype uses incrementing tokens to abort old flows; a real product needs a task queue, explicit cancellation, and background continuation (see §6 `[TBD-BE]`).

---

## 2. Stage details

### Stage 1 · New project (Home)

| Item | Design |
| --- | --- |
| Interface | Centered Hero: big title + topic input + scenario shortcut chips + **material slot** (paste text / upload or drag files / add link; added materials shown as chips, removable, count `N / 6`) + mode selection (default fully automatic) |
| User actions | Enter topic (example "Dify company introduction") → (optional) add materials → click "Start generating" |
| Agent behavior | None (enter stage 2) |
| Boundaries | Empty topic blocks submission and focuses the input; **empty material slot = v1 web-only research path**; prototype material limit 6, entry disabled at full; files only record name/type/size and are not actually parsed; URL format validated but not actually fetched |

### Stage 2 · Research + interview (v3: material digestion + Agent gap suggestions + sequential Q&A)

| Item | Design |
| --- | --- |
| Interface | Left **conversation stream** (Agent messages + tool-call cards + per-question cards + material digest card + gap card + profile card); on desktop it is an independent scroll container, on mobile it scrolls with the page. Right **content source panel** in two groups: "Your materials" (appears when materials exist, with a "material" badge) and "Web supplements", with empty and skeleton loading states |
| Agent behavior (streaming) | ① Opening script branches on materials (with materials: "I'll digest your materials first, then fill gaps online"; without: v1's "I'll search the web first"); ② **Material digestion**: one tool card per material (`read_paste_text` / `ingest_file(filename)` / `fetch_url(url)`), each completes and the material enters the right "Your materials" group; ③ **Sequential questions**: 4 basic single-choice questions appear one at a time, collapsing into a "Recorded: X · Edit" summary after answering; ④ **Material digest**: with materials, output a "Material digestion complete" card explaining what was extracted per item; ⑤ **Gap suggestions**: with materials, the 5th card gives 3 Agent suggestions (each with a reason and a "suggested" badge; recommended ones pre-checked), and the user can add/remove or choose "Not needed — just use my materials"; ⑥ **Targeted web search per gap**: user checks gaps → targeted `web_search("supplemental search · competitor comparison")` etc., right web group lights up item by item; if the user chooses only "not needed" → skip web; no materials → v1 default 4 searches + 12 sources; ⑦ Output "requirements profile" confirmation card (including **Materials** and **Web** rows) |
| User actions | Answer each question → (with materials) confirm gaps → click "Generate requirements profile" → review profile → can click "Edit requirements answers" to change any basic question and "Update profile" → click "Requirements look good, generate outline" |
| Boundaries | All basic questions must be answered to generate the profile; when the profile is `profileDirty` due to answer changes, entering the outline is blocked; **when first-party materials conflict with web information, user materials win** (outline generation prompt constraint, see `docs/ppt-content-sources.md` §5); gap confirmation is a material strategy and cannot be modified at the profile stage; changing gaps requires restarting research (v3 prototype behavior; a real product should offer "re-search", `[TBD-FE]`) |

### Stage 3 · Outline (digital sticky notes)

| Item | Design |
| --- | --- |
| Interface | **Sticky-note board**: cover/TOC/end are independent notes (fixed position, titles editable); body grouped by "section", one note per page (page number, title, key content keywords); insert-page button at the top-right of each section; top-right stats "N pages · M sections", warning when >2 pages off from the agreed count |
| Agent behavior (streaming) | Streams `[PPT_OUTLINE]` JSON in chunks; notes **fly in one by one** on the board (matching the original post's GIF effect) |
| User actions | ① Click a note title for inline editing (Enter to save); ② note "Move up / Move down / Insert / Delete" within its section; ③ **drag** notes across sections or reorder; ④ keyboard focus a note: `Alt + ↑/↓` move within section, `Shift + Alt + ←/→` move to adjacent section; ⑤ confirm "Outline looks good, generate plan draft" |
| Boundaries | Cover/TOC/end cannot be deleted but titles can be edited; warn when page count differs by >2 from the agreed count; in fully automatic mode, a 3-second countdown and "Pause" button appear after generation, and any edit/sort auto-pauses; outline changes invalidate downstream per the §3.4 matrix |

### Stage 4 · Plan draft (layout planning)

| Item | Design |
| --- | --- |
| Interface | Left page list (grouped by section, per-page status: pending / planning / done); main area **16:9 grayscale Bento wireframe** (each card labeled "what goes here"); completion progress bar at top; unplanned pages show a skeleton placeholder |
| Agent behavior (streaming) | Plan page by page: choose Bento layout (six-combination vocabulary) → output card list (content source page points + suggested size weights + suggested element types) → wireframe animates open |
| User actions | ① switch pages in the left list to inspect; ② per-page "Re-plan" (new layout variant); ③ natural-language tweak (example: "make the data card on page 2 larger, move the case to the right") → Agent re-renders that page's wireframe; ④ "Confirm plan draft, choose style" |
| Boundaries | Confirm button is enabled only after all pages complete; tweaks affect the current page only; re-plan/tweak marks the generated design draft as stale; ungenerated pages show a skeleton rather than a "final wireframe" |

### Stage 5 · Style selection

| Item | Design |
| --- | --- |
| Interface | Style gallery cards (4): each with a real "company intro" page mini preview + palette dots + use-case description; arrow-key switching and `aria-checked`; bottom "Remember my preference" checkbox |
| User actions | Single-select a style (mouse/keyboard) → (optional) check remember preference → "Start generating design draft" |
| Boundaries | Confirm button disabled until a style is selected; preference written to `localStorage` (prototype), auto-selected and shown as "last used" next time; changing style marks the generated design draft as stale |

### Stage 6 · Design draft (generate, preview, edit, export)

| Item | Design |
| --- | --- |
| Interface | **Three-column workbench**: left thumbnail column (grouped by section, per-page generation status); center large canvas preview of the current page (16:9, Bento card final); right current-page action panel (regenerate / previous version / tweak input / layout description / variant and history counts / export) |
| Agent behavior (streaming) | Generate the design page by page: the message stream shows "Applying style "X" to page N…"; the right layout description updates in sync; if the user clicks a thumbnail during generation, the **current page is locked** and the remaining pages continue generating in the background |
| User actions | ① page through (thumbnails/arrows/`←` `→`); ② unhappy with a page → "Regenerate" (variant rotation) or enter a tweak instruction; ③ "Previous version" to undo to the previous variant; ④ "Export" → export modal (PPTX (SVG-composited, recommended) / HTML / PDF) → review page count/style/render completeness summary → mock progress → success state |
| Boundaries | Regenerate/tweak affect a single page only; cover/TOC/end have only one layout, so prompt the user to use tweaks instead and do not fake a variant increment; page-level actions during generation show "please wait"; export is a mock demo (the prototype does not generate real files); export failure path in §6 |

---

## 3. State machine and data flow

### 3.1 Frontend project state (a JS object in the prototype)

```ts
type Stage = 'home' | 'research' | 'outline' | 'plan' | 'style' | 'design';
type JobStatus = 'idle' | 'streaming' | 'done' | 'error';

interface Material { id: string; kind: 'paste' | 'file' | 'url'; title: string; meta: string; }
interface Source   { title: string; summary: string; origin: 'provided' | 'web'; }

interface GapSuggestion { label: string; reason: string; recommended: boolean; }
interface GapDecision   { label: string; selected: boolean; }
interface QuestionAnswer { label: string; }

interface PlanState {
  variant: number;
  status: JobStatus;          // error is reserved for the real implementation; the prototype never triggers it
}

interface SlideState {
  variant: number;
  history: number[];          // stack of variants before regenerate/tweak
  status: JobStatus;          // error is reserved for the real implementation
}

interface ProjectState {
  topic: string;
  mode: 'auto' | 'guided';
  stage: Stage;
  materials: Material[];      // v3: stage 1 material slot, max 6
  qTotal: number;             // 4 or 5 (includes the gap card when materials exist)
  answers: Record<number, QuestionAnswer>;
  profileDirty: boolean;      // profile has been shown but answers were changed
  gaps: GapSuggestion[];      // Agent suggestions
  gapDecision: GapDecision[]; // user confirmation result
  webSkipped: boolean;
  outline: { cover: PageRef; toc: PageRef; parts: { title: string; pages: PageRef[] }[]; end: PageRef };
  plans: Record<pageId, PlanState>;
  styleId?: string;
  styleApplied?: string;      // style actually used by the current design draft
  rememberStyle: boolean;
  slides: Record<pageId, SlideState>;
  stale: { plan: boolean; design: boolean };
  autoPaused: boolean;
  pinned: boolean;            // user manually locked the page during generation
  curPlanPage?: string;
  curDesignPage?: string;
  done: { research: boolean; outline: boolean; plan: boolean; style: boolean; design: boolean };
}
```

### 3.2 Mock LLM return contract (prototype's built-in streaming simulator, matching the prompts)

| Stage | Simulator | Event sequence (SSE-style) |
| --- | --- | --- |
| Research | `startResearchFlow()` | `{type:'message',delta}` → (with materials) `{type:'tool',name:'read_paste_text'\|'ingest_file'\|'fetch_url',target}` ×N + `{type:'source',origin:'provided'}` ×N → `{type:'question',index,total,multi:false}` (one at a time) → `{type:'question_answer'}` (client) → `{type:'digest',items}` → `{type:'gap_suggest',items:[{label,reason,recommended}]}` → `{type:'gap_decision'}` (client) → per gap `{type:'tool',name:'web_search',query}` ×M + `{type:'source',origin:'web'}` ×M (skip the entire segment if "not needed"; if no materials, fixed 4 searches + 12 sources) → `{type:'message',delta}` → `{type:'profile_ready'}` |
| Outline | `runOutlineStage()` | `{type:'outline_delta',chunk}` (simulates `[PPT_OUTLINE]` JSON chunks, incrementally renders notes) → `{type:'outline_done'}` → (auto mode) `{type:'auto_advance',seconds:3,pausable:true}` |
| Plan/design | `runPlanStage(page)` / `runDesignStage(page,variant)` | `{type:'page_start',pageId}` → `{type:'card_delta',...}` → `{type:'page_done'}` |
| Single-page ops | `redesignCurrent()` / `tweakCurrent()` / `undoDesign()` | `{type:'history_push',variant}` → `{type:'page_start',pageId}` → `{type:'page_done'}` / `{type:'history_pop',variant}` |

> All "typewriter" effects in the prototype are implemented as timer slices, simulating a real LLM token stream; no network requests are made.

### 3.3 Structured conventions borrowed from the prompts

- The outline JSON structure follows prompt 1's `ppt_outline` (cover / table_of_contents / parts / end_page); its "background research (Context)" is extended in v3 to **user materials + web supplements**, and states that first-party materials take precedence over web information.
- Plan and design layout vocabulary follows prompts 2/3's six Bento Grid combinations; the design canvas is fixed at 16:9 (the prototype uses CSS grid + `cqi` to simulate 1280×720 viewBox semantics).

### 3.4 Stale propagation matrix

| Change | Plan draft | Design draft | Notes |
| --- | --- | --- | --- |
| Edit page title | Keep (re-render page header) | Needs rerun | Layout unchanged; design page header needs re-rendering |
| Reorder within section | Keep | Needs rerun | Plan content unchanged; order affects the final deck |
| Move across sections | Needs rerun | Needs rerun | Grouping structure changes |
| Add / delete page | Needs rerun | Needs rerun | Deleting a page also clears its plan/slide |
| Re-plan / tweak single page | That page complete | Needs rerun | Layout change requires re-applying the style |
| Change style | Unchanged | Needs rerun | Affects the design draft only |
| Update requirements profile (outline already generated) | Needs reconfirmation | Needs rerun | Prototype marks the outline unconfirmed; after re-confirming the outline, rerun plan/design |

The top stage nav shows an amber dot + `aria-label="needs rerun"`; entering the stage automatically reruns missing/stale artifacts.

---

## 4. Prototype feature map (acceptance checklist)

| Interaction | Clickable location in the prototype | Expected result |
| --- | --- | --- |
| Empty-topic validation | Home "Start generating" | No navigation, toast + focus input |
| Enter topic to start | Home input + start button | Enter stage 2, start mock research |
| Scenario chips | Home 4 chips | Fill an example topic |
| **Add pasted material** | Home material slot "Paste text" | Expand textarea → creates a material chip, removable; count `N/6` |
| **Drag/select files** | Home material slot drop files or click "Upload file" | Chip shows filename + type/size; over 6 prompts and adds only the remaining quota |
| **Add link** | Home material slot "Add link" | Auto-prefix `https://`; invalid format shows an inline error; chip shows host + path |
| **Material limit** | Add a 7th item | Entry disabled + toast |
| Mode switch | Home two mode cards | Affects whether later stages auto-advance |
| **Answer interview sequentially** | Stage 2 current question card | After selection it collapses into a "Recorded" summary; next question appears |
| **Edit answer** | Stage 2 answered question card "Edit" | Reopens options; updates the answer; marks `profileDirty` if the profile was already generated |
| **View material digestion** | Stage 2 material digest card | Shows the extraction result per material |
| **Agent gap suggestions** | Stage 2 5th card | 3 suggestions with reasons and a "suggested" badge; recommended ones pre-checked |
| **Not needed** | Gap card "Not needed — just use my materials" | Clears the other items; skips web after confirmation |
| View materials and sources | Stage 2 right content source panel | Two groups light up separately; empty/skeleton/count |
| **Edit profile** | Profile card "Edit requirements answers" | Opens edit mode; blocks outline until the profile is updated |
| **Pause auto-advance** | Outline confirm bar countdown | 3-second countdown; pause button; editing/sorting auto-pauses |
| Sticky-note editing | Stage 3 notes | Inline title edit (Enter saves) / move up / move down / insert / delete |
| Sticky-note drag | Stage 3 notes | Cross-section drag; dropping on a note inserts before it |
| **Sticky-note keyboard** | Focus a note | `Alt+↑/↓` within section; `Shift+Alt+←/→` across sections |
| **Page count deviation** | Stage 3 bottom stats | Warning if >2 off the agreed count |
| Outline confirm | "Generate plan draft" | Enter stage 4; wireframes stream in page by page |
| Per-page plan view | Stage 4 left page list | Switch wireframe; status icons distinguish pending/planning/done |
| Re-plan page | Stage 4 "Re-plan this page" | Wireframe switches variant; design marked stale |
| Tweak plan | Stage 4 input + "Tweak" | Re-layouts the current page only; empty instruction shows inline error |
| **Plan completion gate** | Stage 4 confirm button | Enabled only after all pages complete |
| Select style | Stage 5 style cards | Selected highlight + `aria-checked`; arrow keys switch |
| **Remember preference** | Stage 5 checkbox | Writes `localStorage`; auto-selected next time |
| Page through preview | Stage 6 thumbnails/arrows/`←` `→` | Canvas switches pages; clicking during generation locks the current page |
| Single-page regenerate | Stage 6 "Regenerate" | Page re-renders streaming (variant rotation); single-layout pages prompt to use tweaks |
| **Undo regenerate** | Stage 6 "Previous version" | Restores the previous variant from the history stack |
| Tweak instruction | Stage 6 tweak input | Mock "adjusted per instruction" re-render; empty instruction shows field error |
| Export | "Export" button | Modal with three options + scope summary + mock progress + success; Esc/focus trap |
| **Restart** | Top "Restart" | Confirm modal (default focus on cancel) |
| Stage jump back | Top stage nav | Jump to a reachable stage; stale stages show a dot |
| **Mobile stage nav** | ≤920px top `<select>` | Equivalent to desktop stage nav |
| **Mobile page list** | Stage 4 horizontal page strip | Saves vertical space; canvas 680px horizontal scroll |

---

## 5. Prototype implementation notes

- Single file `prototype/ppt-agent-prototype.html`: pure HTML/CSS/JS, no build, no external dependencies, no network requests; about 3,000 lines.
- Design system: indigo primary + sticky-note amber secondary; unified spacing/radius/shadow/focus ring; all structural icons are inline SVG line icons (no emoji); supports `prefers-reduced-motion`.
- Mock data is built into the `MOCK` constant (topic, research sources, interview questions, gap suggestions, outline JSON, plan and design variants, page notes), corresponding to the example topic "Dify company introduction".
- Streaming simulator: `typeInto(el, text, token, speed)` timer-sliced typewriter; generation stages use a stage-granular scheduler that advances serially; the `runSeq` token aborts old flows on stage changes, and the `opSeq` token aborts expired single-page operations.
- **Material slot is mock**: files only read filename/type/size (content not parsed), URLs are format-validated but not actually fetched; gap confirmation connects to the background research stream via a Promise — "gaps selected → search by gap" and "not needed → skip web" are both demo logic.
- The content source panel renders grouped by `origin`; without materials it shows only the web group (consistent with v1 behavior); a skeleton is shown before web research, and material digestion lights up item by item.
- Design draft rendering: a CSS Grid Bento layout renderer (`single / 2col / 3col / hero / async / mix`), with four style themes switched via CSS variables; cover/TOC/end use dedicated compositions; the plan draft uses a degraded wireframe renderer.
- State: `S` holds all project state; `stale` records downstream invalidation; `slides[pageId].history` holds the per-page version stack; `localStorage` holds the style preference.
- Viewports: desktop-first (three columns at ≥1180px); single column at ≤1180px; stage nav switches to a native `<select>` at ≤920px; page list becomes a horizontal strip and the canvas is 680px with horizontal scrolling at ≤720px; brand and example chips are trimmed at ≤480px.
- Accessibility: `:focus-visible` focus ring, skip link, `role=log/status/dialog`, `aria-checked/current/busy/valuenow`, modal focus trap and Esc, focus moves to the heading on stage change, keyboard sorting and paging.

---

## 6. Errors, recovery, and uncovered items

> The table below is the v3 **contract**, not a list of implemented features. The prototype only covers the "happy path + a few gates"; items marked `[TBD]` must be completed before the real implementation.

| Scenario | Trigger | Expected interaction | v3 prototype | Owner |
| --- | --- | --- | --- | --- |
| Material parsing failure | Corrupted file / unsupported type | Tool card red state + mark that material "not digested" + allow removal/replacement; do not block other materials | Not simulated | `[TBD-FE]` / `[TBD-BE]` |
| URL fetch failure | Login wall / anti-scraping / 404 | Tool card failure state + suggest pasting the body text instead; keep other sources | Not simulated | `[TBD-BE]` |
| Zero search results | Gap too narrow / query returns nothing | Keep the question card, prompt "not found; continue/adjust gaps"; do not silently skip | Not simulated | `[TBD-FE]` |
| Single-page generation failure | Timeout / model error | Page status `error` + "Retry this page"; other pages continue | Not simulated | `[TBD-FE]` |
| Export failure | Missing font / out-of-bounds asset / write failure | Failure reason + "Retry" + "Try another format"; do not close the modal | Not simulated | `[TBD-FE]` |
| Leaving the page | Stage switch / refresh | Prototype aborts the current flow; a real product should continue in the background and restore on return | Aborts | `[TBD-BE]` |
| Concurrent operations | Single-page action during generation | Prompt "generating, please wait"; forbid writing the same page concurrently | Prevented | — |
| Profile dirty data | Answers changed after profile generation without update | Block entering outline; prompt to update profile first | Implemented | — |
| Downstream stale | Outline/plan/style change | Stage nav shows "needs rerun"; rerun on entry | Implemented | — |
| Delete page | Note "Delete" | Immediate delete (prototype); a real product should offer toast undo or confirmation | No undo | `[TBD-FE]` |
| Auto-advance | Fully automatic + editing | Detect editing and auto-pause; do not steal focus | Implemented | — |
| Material over limit | 7th item | Entry disabled + limit hint | Implemented (6-item demo constraint) | `[TBD-UX]` |
| User changes gap decision | Wants to change web scope after profile | A real product should support "re-search and update profile" | Not supported; must restart research | `[TBD-FE]` |

---

## 7. Accessibility and responsive baseline

### 7.1 Keyboard matrix

| Area | Key | Behavior |
| --- | --- | --- |
| Global | `Tab` / `Shift+Tab` | Move in visual order; cycle within modals |
| Global | `Esc` | Close the current modal; focus returns to the trigger |
| Home mode | `←` / `→` / `↑` / `↓` | Switch between "fully automatic / expert copilot" |
| Interview | `Tab` + `Space` / `Enter` | Select an option; check gap items individually then confirm |
| Sticky notes | `Alt + ↑/↓` | Move up/down within the section |
| Sticky notes | `Shift + Alt + ←/→` | Move to the end of an adjacent section |
| Sticky notes | `Enter` | Finish title editing and save |
| Style | `←` / `→` / `↑` / `↓` | Switch and select style cards |
| Design draft | `←` / `→` | Previous/next page |
| Export modal | `Tab` / `Shift+Tab` / `Esc` | Focus trap / close and return focus |

### 7.2 Semantics and states

- Conversation container `role="log"`, `aria-live="off"`; milestones (question answered, material digested, research complete, profile generated, export complete) are announced through a separate `role="status"` region to avoid per-token chatter.
- Question options `role="radio"` / `role="checkbox"` + `aria-checked`; gaps use native checkboxes; style cards `role="radio"`.
- Canvas `role="img"` + `aria-label`; thumbnails are decorative with `aria-hidden="true"`.
- Generation container `aria-busy`; progress bar `role="progressbar"` + `aria-valuenow`.
- Current stage `aria-current="step"`; needs-rerun stated explicitly in `aria-label`.
- Focus: `:focus-visible` 2px brand color + 2px offset; focus moves to `h1` on stage change; closing a modal restores focus to the trigger.

### 7.3 Breakpoints

| Breakpoint | Layout |
| --- | --- |
| ≥1180 | Full two- or three-column research/plan/design |
| ≤1180 | Right panel moves below; design draft order "canvas → actions → thumbnails" |
| ≤920 | Top stage nav switches to native `<select>` |
| ≤720 | Home single column, survey full-width, page list horizontal strip, canvas 680px with horizontal scroll |
| ≤480 | Trim brand and example chips; keep core actions |

### 7.4 Motion and contrast

- `prefers-reduced-motion: reduce`: CSS animation/transition durations approach zero; the typewriter outputs the full text immediately.
- Body and secondary text are ≥ 4.5:1 on `#ffffff` / `#f5f6fa`; white text on the `#4f46e5` primary button is 6.29:1; sticky-note text `#3c3410` on `#fdf6d8` is > 10:1.

---

## 8. Version history

- **v3 (2026-11-18)**: sequential Q&A with answer editing; material digest summary + Agent gap suggestions; profile dirty-data gate; auto-advance countdown/pause/edit-auto-pause; stale propagation and needs-rerun markers; per-page version history and "previous version"; single-layout page protection; page locking during generation; export scope summary and modal accessibility; style preference memory; mobile stage `<select>`, page strip, scrollable canvas; full SVG icon set, focus ring, reduced motion, and contrast fixes. Review and remaining items in `docs/ppt-agent-ux-review.md`.
- **v2 (2026-11-16)**: added the content source system (`docs/ppt-content-sources.md`); stage 1 gained the material slot (paste text / drag files / add link); stage 2 changed from "web research" to "material digestion + gap filling", with web search downgraded to gap filling; data structures gained `materials` and `source.origin`; the v1 web-only path remains the default when materials are empty.
- **v1**: initial six-stage flow (productization inspired by the linux.do post).
