# Bound PPT · UX review (v2 → v3)

> Review targets: `docs/ppt-agent-interaction-flow.md` (v2), `docs/ppt-content-sources.md` (v2), `prototype/ppt-agent-prototype.html` (v2 implementation)
> Review date: 2026-11-18
> Method: stage-by-stage walkthrough + hands-on prototype use + targeted ui-ux-pro-max research (AI-Native / Bento Grid, wizard forms, undo and confirmation, drag keyboard alternatives, modal focus, contrast, empty and loading states, responsive)
> Conclusion: v2's information architecture holds; there is no need to overturn the main axis "materials → interview → sticky notes → plan → style → design". The problems cluster in **boundary states** — failure recovery, undoability, predictability, accessibility. v3 has landed the interaction-side P0/P1 items in the prototype; implementation items such as failure recovery, real parsing, and task queues still need to be completed, listed in §5.

---

## 1. Conclusion summary

Ordered by harm to user experience, the six v2 issues that most needed attention:

1. **The interview was laid out all at once, and wrong answers could not be corrected.** 5 question cards appeared simultaneously, creating high cognitive load; in the v2 prototype every single-select click ran `answerCount++`, so changing an answer corrupted the count, and the profile might appear early or never; after profile generation there was also no edit entry.
2. **Gaps were guessed by the user, conflicting with the content source design.** `ppt-content-sources.md` §2.3 says "Agent digests materials → judges sufficiency → lists gaps", but the prototype made the user self-report gaps from 4 hardcoded options. This pushed back onto the user the judgment that most belonged to the Agent.
3. **Auto-advance was neither visible nor pausable.** Fully automatic mode jumped 1.2 seconds after the outline streaming animation ended, with no countdown and no pause; users editing a title were also cut off.
4. **Downstream invalidation was only written in the docs, not built into the state machine.** The v2 docs said "mark for rerun after downstream data changes", but the data structure had no `stale`, and the prototype did not rerun; after editing the outline and entering the plan draft, users still saw the old wireframe.
5. **"Regenerate" had no way back.** Single-page regeneration overwrote directly; after the user was satisfied with a page, one more click permanently lost it; cover/TOC/end had only one layout yet still displayed "switched to V2", which is fake feedback.
6. **Accessibility and mobile were systemic gaps.** Emoji used as structural icons, no visible focus ring, no keyboard alternative for drag, no focus trap in modals, insufficient contrast on small gray text, mobile stage nav disappearing, and the design canvas too small to read.

---

## 2. Stage-by-stage check

Criterion: **Pass** = design covered and prototype verifiable; **Fail** = missing, conflicting, or inoperable; **N/A** = not applicable to the current version. Evidence only cites reviewable behavior or document paragraphs.

### 2.1 Stage 1 · New project

| # | Check item | v2 verdict | Evidence | v3 handling |
| --- | --- | --- | --- | --- |
| 1.1 | Clear feedback when topic is empty | Fail | Prototype silently falls back to `MOCK.topic`; user thinks their topic was submitted | Empty topic blocks submission and focuses the input |
| 1.2 | Material count has a visible limit | Fail | Over 6 only shows a toast; count invisible; button not disabled | Show `0 / 6`; disable entry at full |
| 1.3 | Link format validation | Fail | Any string accepted after prefixing `https://` | Inline error if `URL` parsing fails |
| 1.4 | Drag has discoverability | Pass | Dashed slot + drag highlight | Keep, and add empty-state description |
| 1.5 | Restart has confirmation | Fail | Top button immediately clears everything | Confirm modal, default focus on "Cancel" |
| 1.6 | Structural icons do not rely on emoji | Fail | 📦 / 📝 / 📎 / 🔗 / 🚀 / 🧭 are all emoji | Replace all with line SVG icons |

### 2.2 Stage 2 · Research

| # | Check item | v2 verdict | Evidence | v3 handling |
| --- | --- | --- | --- | --- |
| 2.1 | Questions appear one at a time, reducing cognitive load | Fail | 4-5 question cards laid out at once | Sequential Q&A; collapse to summary after answering; "Edit" reopens |
| 2.2 | Changing answers does not break the flow | Fail | Single-select increments `answerCount` on every click; changing an answer inflates the count | Use the `answers` map as source of truth; changing an answer overwrites only that item |
| 2.3 | Profile is editable | Fail | Profile card is read-only; after changing answers, "Generate outline" is still clickable | "Edit requirements answers" + "Update profile"; block outline until updated |
| 2.4 | Gaps judged by the Agent | Fail | Gap card has 4 hardcoded options, user self-reports | Material digest summary + Agent gap suggestions (reason + pre-selected + recommended badge) |
| 2.5 | Timing of material digestion and questions is understandable | Fail | Question cards appear first; tool cards asynchronously appended after; order inverted | Digestion and questions run in parallel; gap card only after digestion; digest card explains each material |
| 2.6 | Chat area scrolls independently and auto-follows | Fail | `.chat` only has `min-height`; long conversations stretch the page; `scrollTop` ineffective | Desktop fixed-height scroll container + immediate follow; natural flow on mobile |
| 2.7 | Source panel has empty/loading states | Fail | Web group only has an empty list; no skeleton during search | Grouped empty copy + 3 skeleton rows + item-by-item lighting |
| 2.8 | Conflict priority is visible | Pass | Right panel footnote says "first-party materials first" | Keep, and repeat in the profile strategy row |
| 2.9 | Skipping web has a clear result | Pass | After choosing "not needed", copy explains the material-based basis | Keep, and write "no web" in the profile "Web" row |

### 2.3 Stage 3 · Outline sticky notes

| # | Check item | v2 verdict | Evidence | v3 handling |
| --- | --- | --- | --- | --- |
| 3.1 | Drag has keyboard/button alternatives | Fail | Only "←/→" buttons, whose direction semantics mismatch vertical sections; cross-section moves are drag-only | ↑/↓ buttons + `Alt + ↑/↓` + `Shift + Alt + ←/→` across sections |
| 3.2 | Delete has undo or confirmation | Fail | Clicking "×" deletes immediately with no recovery | **Unfinished**, see §5 R2 |
| 3.3 | Page count deviation has a warning | Fail | Docs say "warn if difference >2 pages"; prototype does not implement it | Compare with the agreed page count; show warning over the threshold |
| 3.4 | Auto-advance is visible and pausable | Fail | Silent jump after 1.2 seconds | 3-second countdown + pause button; editing/structure changes auto-pause |
| 3.5 | Edits invalidate downstream | Fail | `done.plan` remains true; plan draft does not rerun | `stale` marker + top nav dot + rerun on entry |
| 3.6 | Invalidation scope distinguishes title/structure/order | Fail | Never invalidates | Title and order invalidate design only; add/delete/cross-section invalidate plan + design |
| 3.7 | Insert page directly within a section | Pass | Note "+" inserts after that page | Keep, and add "+" at the section's top-right |

### 2.4 Stage 4 · Plan draft

| # | Check item | v2 verdict | Evidence | v3 handling |
| --- | --- | --- | --- | --- |
| 4.1 | Cannot confirm before completion | Fail | Confirm button always enabled | Enabled only after all pages complete |
| 4.2 | Page status not conveyed by color alone | Fail | Only an 8px color dot, no text/icon semantics | Color dot + clock/spinner/check icon + `aria-label` |
| 4.3 | Unplanned pages have a clear placeholder | Fail | Shows the final wireframe directly, looking complete | Skeleton placeholder + `aria-busy` |
| 4.4 | Re-plan invalidates design | Fail | Plan variant changes, but design still marked complete | Trigger design `stale` |
| 4.5 | Tweaks affect only the current page | Pass | Docs and prototype consistent | Keep, and add error prompt and keyboard Enter |

### 2.5 Stage 5 · Style

| # | Check item | v2 verdict | Evidence | v3 handling |
| --- | --- | --- | --- | --- |
| 5.1 | "Remember preference" matches the docs | Fail | Docs describe it; prototype does not have it | Checkbox + `localStorage`; auto-select on entering the style page |
| 5.2 | Style cards are keyboard-selectable | Fail | Click only; no `role/aria-checked` | `radiogroup` + arrow keys + `aria-checked` |
| 5.3 | Changing style invalidates generated design | Fail | Design still considered complete | Compare `styleApplied` on confirm; invalidate design |

### 2.6 Stage 6 · Design draft

| # | Check item | v2 verdict | Evidence | v3 handling |
| --- | --- | --- | --- | --- |
| 6.1 | Single-page regeneration is undoable | Fail | Variant overwritten directly; old version lost | Per-page `history` stack + "Previous version" |
| 6.2 | Single-layout pages do not fake regeneration | Fail | Cover/TOC/end still show V2 after "Regenerate"; visuals unchanged | Single-layout pages prompt to use tweaks; no variant increment |
| 6.3 | Can freely view generated pages during generation | Fail | After clicking a thumbnail, the generation loop steals the current page back | `pinned` flag: stop following after the user selects a page |
| 6.4 | Page-level status during generation | Fail | Only one line "rendering" | Top progress + thumbnail spinner/check |
| 6.5 | Export has a scope summary | Fail | Modal only has three format buttons | Page count, style, and rendered page count summary |
| 6.6 | Export meets modal accessibility | Fail | No `role=dialog`, no focus trap, Esc does not close | Focus trap + Esc + focus return + progress `aria-valuenow` |
| 6.7 | Export failure is recoverable | Fail | Success path only | **Unfinished**, see §5 R1/R7 |

### 2.7 Global experience

| # | Check item | v2 verdict | Evidence | v3 handling |
| --- | --- | --- | --- | --- |
| G1 | Visible focus ring | Fail | No global `:focus-visible` rule | 2px brand focus ring + 2px offset |
| G2 | Keyboard can complete the main flow | Fail | Gaps in drag, style, and modals | Completed and documented in the §7 keyboard matrix |
| G3 | Skip to main content | Fail | No skip link | Add skip link |
| G4 | Motion respects reduced motion | Fail | Typewriter/fly-in/pulse have no fallback | `prefers-reduced-motion` + typewriter outputs full text |
| G5 | Body contrast ≥ 4.5:1 | Fail | `#9aa2b8` small text on light background is about 2.4:1 | Unify to `#566079` / `#626c82`, measured ≥ 4.7:1 |
| G6 | Mobile stage nav is usable | Fail | `@media (max-width:1100px)` sets `display:none` | Switch to native `<select>` at ≤920px |
| G7 | Mobile canvas is readable | Fail | 16:9 canvas shrinks to 335px; cqi text about 5px | ≤720px canvas 680px + container horizontal scroll + hint |
| G8 | Long tasks are predictable | Partial | Progress bar exists, but no ETA/cancel | Progress and page status added; cancel/background continue in §5 R3 |
| G9 | Failure paths are complete | Fail | The whole flow only has the happy path | In §5 R1; v3 only defines contracts |

---

## 3. Key problem deep dives

### 3.1 Why the "gap card" must be asked by the Agent

v2 wrote gaps as a multi-select of four: "competitor comparison / industry and market data / customer cases / not needed". It had three problems:

- **Contradicts product positioning**: the product promises "research like a professional consultant", but gap judgment is handed to the user, who must first know "what is missing".
- **Contradicts the content source doc**: `ppt-content-sources.md` §2.3 explicitly says the Agent judges material sufficiency first, then lists gaps.
- **No reason means no basis for judgment**: the user sees "competitor comparison" and does not know why to select it.

v3 approach: first give a **material digest summary** (what each material yielded), then **gap suggestions** (each with a reason, recommended badge, and pre-checked), and the user only confirms and chooses. Choosing "not needed" clears the other items to avoid semantic conflict.

### 3.2 Why auto-advance needs a "visible 3 seconds"

The value of fully automatic mode is ease of mind, but "ease of mind" does not mean "jumping the gun". v2 silently jumped after the outline animation; if the user was editing a title, the edit was interrupted. v3:

- The countdown bar explicitly says "Entering plan draft in 3 seconds".
- The "Pause" button is always available.
- Any title edit, add/delete, or sort auto-pauses and explains why.
- When the countdown reaches zero, if focus is in an input/editable area, auto-pause instead of jumping.

### 3.3 Stale propagation matrix

| Change | Affected artifacts | v3 behavior |
| --- | --- | --- |
| Edit page title | Plan page header, design page header | Design marked stale; plan only needs a static re-render, no layout rerun |
| Reorder within section | Design order/thumbnails | Design marked stale |
| Move across sections | Plan grouping, design order | Plan + design marked stale |
| Add/delete page | Plan, design | Plan + design marked stale; deleting a page also clears its plan/slide |
| Re-plan/tweak single page | That page's design | Design marked stale |
| Change style | All design drafts | Design marked stale |

The prototype implements this as `S.stale.plan` / `S.stale.design`; the top stage nav shows an amber dot + `aria-label="needs rerun"`.

### 3.4 Why the design draft must have a "previous version"

Single-page "Regenerate" is a high-frequency and high-risk operation. Users often click once more after "this version is already fine". Without a history stack, that click is irreversible. v3 maintains `history: number[]` per page, pushes the current variant before each regenerate/tweak, and "Previous version" pops and restores it. Cover/TOC/end with a single layout do not increment variants and directly prompt the user to use tweaks, avoiding a fake "V2".

---

## 4. v3 changes already landed (in user-perceivable order)

1. **Visual system**: indigo primary + sticky-note amber secondary; unified 4/8/12/16/24 spacing, radii, shadows, focus ring; all structural icons replaced with line SVG; home page uses a more restrained "highlight marker" instead of gradient text.
2. **Material slot**: count `0/6`, disabled at full, URL format validation, paste `Cmd/Ctrl+Enter`, file type hints, empty-state description, removal feedback.
3. **Interview**: sequential Q&A, collapse to summary after answering, any question editable, profile editable and blocked from outline when dirty; material digest summary card; Agent gap suggestion card.
4. **Outline**: ↑/↓ buttons + keyboard sorting + cross-section keyboard moves; section-level insertion; page count deviation warning; auto-advance countdown/pause/edit-auto-pause; stale propagation.
5. **Plan draft**: per-page status icons, skeleton placeholder, confirmation blocked before completion, `aria-busy`, re-plan triggers design invalidation, tweak error prompt.
6. **Style**: remember preference (`localStorage`), arrow-key selection, `radiogroup` semantics, style change triggers design invalidation.
7. **Design draft**: user-selected page no longer stolen back by the generation loop; per-page version history and "Previous version"; single-layout page protection; export summary/progress/success; modal focus trap and Esc.
8. **Global**: skip link, `:focus-visible`, `aria-live` status announcements, `role=log`, `aria-current`, `prefers-reduced-motion`, mobile stage `<select>`, mobile page strip, mobile canvas horizontal scroll, contrast fixes.

---

## 5. Still uncovered / follow-ups

| ID | Item | Priority | Current state | Owner / stage |
| --- | --- | --- | --- | --- |
| R1 | Failure and recovery: material parsing failure, URL fetch failure, zero search results, single-page generation failure, export failure | P0 | v3 only defines contracts (interaction doc §6); prototype does not simulate failures | Frontend + backend · before development |
| R2 | Outline delete undo: single-page delete, section delete | P1 | Currently deletes immediately, no undo | Frontend · before development |
| R3 | Long-task cancel/background continue/reconnect recovery | P1 | Navigating aborts (via `runSeq` token); no background task | Backend · architecture stage |
| R4 | Real material parsing and URL fetching (size, page count, login walls, anti-scraping) | P0 | Prototype only records name/size, no parsing | Backend · see content sources §4.2 |
| R5 | Material digest expandable to view source text/locate | P2 | Prototype only shows the summary line | Design · visual design stage |
| R6 | Global version history (cross-page, cross-style) | P2 | Only per-page variant history | Product · next version |
| R7 | Real pre-export validation (missing fonts, out-of-bounds images, empty pages) | P1 | Prototype only shows "rendered X/Y" | Frontend · export implementation |
| R8 | Standard roving tabindex for radio groups | P2 | Tab + Space currently works; arrow keys not implemented | Frontend · accessibility completion |
| R9 | Mobile canvas "fit/100%" toggle | P2 | Currently 680px horizontal swipe + hint | Design · visual design stage |

> Do not describe the unfinished items above as "supported". The v3 docs and prototype are only responsible for the changes listed in §4.

---

## 6. Validation log (2026-11-18)

- **No-material path**: topic → 4 sequential questions → 12 web sources → profile → outline → 16 plan pages → style → 16 design pages → regenerate → previous version → tweak → export in three formats; no console errors.
- **With-material path**: paste + URL + file (3 items) → material tool cards complete one by one → suggested gaps (2 pre-selected) → "not needed" clears the others → profile "no web" → outline. No console errors.
- **Keyboard**: sticky notes `Alt + ↑/↓` reorder, `Shift + Alt + →` cross-section; design draft `←/→` paging; modal `Esc` closes and returns focus.
- **Stale propagation**: add a page after design completes; both plan and design stages show the "needs rerun" dot and `aria-label`.
- **Responsive**: 1440 / 1180 / 920 / 720 / 390 walkthrough; at 390px stage nav switches to `<select>`, page list is a horizontal strip, canvas 680px horizontally scrollable.
- **Contrast**: primary text `#161c2d` / `#566079` / `#626c82` on `#ffffff` and `#f5f6fa` all ≥ 4.5:1; white button text on `#4f46e5` is 6.29:1.
- **Reduced motion**: under `prefers-reduced-motion: reduce`, animation durations approach zero and the typewriter outputs full text.

---

## 7. Accessibility and responsive baseline (for reuse in implementation)

### 7.1 Keyboard matrix

| Area | Key | Behavior |
| --- | --- | --- |
| Global | `Tab` / `Shift+Tab` | Move in visual order; cycle within modals |
| Global | `Esc` | Close the current modal; focus returns to the trigger |
| Home mode | `←` / `→` / `↑` / `↓` | Switch between "fully automatic / expert copilot" |
| Interview | `Tab` + `Space` / `Enter` | Select an option; confirm multi-select items individually |
| Sticky notes | `Alt + ↑/↓` | Move up/down within the section |
| Sticky notes | `Shift + Alt + ←/→` | Move to the end of an adjacent section |
| Sticky notes | `Enter` | Finish title editing and save |
| Style | `←` / `→` / `↑` / `↓` | Switch and select style cards |
| Design draft | `←` / `→` | Previous/next page |

### 7.2 Semantics and states

- Conversation container `role="log"`, `aria-live="off"`; milestones are announced through a separate `role="status"` region to avoid per-token chatter.
- Question options `role="radio"` / `role="checkbox"` + `aria-checked`; gaps use native checkboxes.
- Canvas `role="img"` + `aria-label`; thumbnails are decorative with `aria-hidden="true"`.
- Generation container `aria-busy`; progress bar `role="progressbar"` + `aria-valuenow`.
- Current stage `aria-current="step"`; needs-rerun stated explicitly in `aria-label`.

### 7.3 Breakpoints

| Breakpoint | Layout |
| --- | --- |
| ≥1180 | Full three- or two-column layout for research/plan/design |
| ≤1180 | Right panel moves below; design draft order "canvas → actions → thumbnails" |
| ≤920 | Top stage nav switches to native `<select>` |
| ≤720 | Home single column, survey full-width, page list horizontal strip, canvas 680px with horizontal scroll |
| ≤480 | Trim brand and example chips; keep core actions |
