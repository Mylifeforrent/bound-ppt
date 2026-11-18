# Bound PPT · PPT Agent

A productization repo based on the linux.do post ["Probably the strongest PPT Agent right now, with a full breakdown of the approach"](https://linux.do/t/topic/1782304). Current design version: **v3** (sequential interview, Agent gap suggestions, undoable single-page edits, stale-propagation reruns, accessibility improvements).

## Repository layout

- `docs/linux-do-1782304-ppt-agent-extract.md` — post extract (design rationale + original prompts)
- `docs/ppt-content-sources.md` — content-source design (v2.1: five source channels, ingestion priority, data contracts, Agent gap suggestions)
- `docs/ppt-agent-interaction-flow.md` — product interaction flow v3 (six-stage flow, state machine, stale propagation, error contracts, accessibility baseline)
- `docs/ppt-agent-ux-review.md` — UX review (v2 → v3 issue list, validation log, remaining items)
- `docs/images/` — key workflow screenshots from the post
- `prototype/ppt-agent-prototype.html` — clickable interaction prototype (single file, built-in mock LLM streaming)

## Running the prototype

```bash
cd prototype && python3 -m http.server 8931
# open http://127.0.0.1:8931/ppt-agent-prototype.html
```

Or open `prototype/ppt-agent-prototype.html` directly in a browser.

## Workflow (v3)

Material intake (paste text / drag files / URL, optional) → research (material digestion + Agent gap suggestions + sequential interview + editable profile) → sticky-note outline (drag / buttons / keyboard, auto-advance pausable) → plan draft (Bento wireframe, confirm only after completion) → design draft (lock pages while generating, single-page variant switching with undo, tweaks, export)

> Principle: first-party materials come first; web search is downgraded to a gap-filling tool. When the material slot is empty, fall back to the v1 web-only research path.
