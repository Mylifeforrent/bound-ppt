# Post extract: Probably the strongest PPT Agent right now, with a full breakdown of the approach

> This document is a complete extraction and structured summary of the linux.do post, for product design and development reference.

- **Source**: <https://linux.do/t/topic/1782304>
- **Author**: sandun (title "A New Beginning"; 7 years of PPT teaching / 3 years of AI product experience)
- **Published**: 2026-03-19 (the post shows Mar 19)
- **Category / tags**: Development tuning · Artificial intelligence / Software development / Featured post
- **Community traction**: 4,931 likes · 59.3k views · 1,097 replies · 5.8k likes
- **Extraction method**: browser (extracted 2026-11-16, including the full body text and 3 prompt code blocks verbatim)
- **Key screenshots**: downloaded to this repo's `docs/images/` (the originals are linux.do CDN links; see the appendix at the end)

---

## I. Product definition: one-paragraph summary

Give AI a topic (for example, "Dify company introduction"), and it runs the whole pipeline automatically like a real expert team:

**Research → material gathering → outline planning → plan draft → design draft**

The final output is a complete presentation design that can be used directly. The author's project uses **Gemini 3 Flash** (the author recommends **Gemini 3.1 Pro** if available).

> ⚠️ Note: the author did not publish the full prompts for the research and material-gathering stages (the post only shows screenshots of the UI).

---

## II. Four core design ideas (in the original post's order)

### 1. Forget "one-click generation" and start with "questions" (research)

- The common flaw of almost every AI PPT tool on the market: **it immediately spits out a rough outline + an off-the-shelf template as soon as you enter a topic**.
- The original post's core claim: **"The soul of a PPT is the content, not the skin."**
- The real process of making a PPT by hand starts by clarifying: **Who is it for? What is it about? What should it achieve?**
- So the first thing the AI should do is **"research" like a professional consultant**: search the web for relevant material, then ask the user a few key questions in a professional way, so the real requirements come out.
- Only after the requirements are fully discussed does the AI generate an outline that is genuinely **targeted**, using the material it collected.

**Supporting methodology — the sticky-note method (digital sticky notes)**:

- The author's long-standing habit for complex PPTs: write each page's core content on sticky notes and cover a wall with them, so the logical structure is obvious at a glance; tear off the bad ones and reorder the rest.
- The original post turns this method into a product: **"Every page is a 'digital sticky note', so you can see clearly and adjust confidently."**
- Role-play instruction for the outline stage: ask the AI to play your "PPT planner".

**Images**: research UI ([survey-ui](images/survey-ui.webp)), digital sticky-note UI (the original post's GIF "1").

### 2. Retrieve a large amount of material

- "The outline is only the skeleton; the flesh needs real, accurate information."
- For engineering reasons, the author's project uses a **domestic Chinese search API**.
- DIY recommendation: **Grok** — in the author's view "the strongest AI for search and information summarization right now, bar none".
- Usage: "Take the outline headings generated in the previous step and feed them to Grok one by one; it will collect and organize the material you need neatly."

**Images**: search UI ([search-ui](images/search-ui.webp)), Grok research example ([research-grok](images/research-grok.png)).

### 3. PPTs have a plan draft too? (two stages: plan first, design second)

- Industry backing: top domestic PPT design firms (quoting 10k+ RMB/page) have a dedicated **planner** role — research, material retrieval, and outline planning are all done by planners.
- The planner ultimately produces a **PPT draft** for the designer: **what element goes where on each page, which layout to use — all fixed in advance**.
- The AI equivalent:
  1. **First have the AI generate a "plan draft"**: a simple, clean **page draft** without complex effects (layout only);
  2. **Then have the AI add design effects to the draft** (style, color, decoration).
- The author's team, after extensive testing: "This human-expert workflow is fully understandable by AI! The planning part handles layout, the design part handles style, and the results are excellent."
- User-side strategy: ordinary PPTs can run fully automatically and be usable; **for especially important PPTs, fine-tune the content manually at the plan-draft stage, then let the AI run the final design**, "maximizing both efficiency and polish".

**Images**: planner role ([planner-role](images/planner-role.webp)), plan-draft example ([planning-draft](images/planning-draft.webp)), page draft ([draft-page](images/draft-page.webp)), after design effects ([designed-page](images/designed-page.webp)).

### 4. Use "card layout (Bento Grid)" to drive AI design

- "Card layout" = the style commonly seen at Apple keynotes: put content into individual cards.
- Three benefits:
  1. **Capacity**: a single page can clearly carry a large amount of information;
  2. **Flexibility**: card count, size, and position can be combined freely, yielding endless layouts;
  3. **AI can understand it (most important)**: "Cards are the design language that AI understands and masters most easily."
- The author wrote this methodology into precise instructions telling the AI how to think about layout like a top designer, and calls it "one of the project's core moats" (see prompts 2/3 in section III).

**Images**: Apple keynote card layout ([card-layout-apple](images/card-layout-apple.webp)), card-layout example ([card-layout](images/card-layout.webp)).

---

## III. Original prompts (3, all production versions used by the author's project)

> The content below is the **verbatim text** of the post's code blocks (browser extraction, original formatting preserved). `{{PAGE_REQUIREMENTS}}` is the page-count requirement template variable used in the author's project. The Chinese prompt text has been translated into English for this edition.

### Prompt 1: Top-tier PPT structure architect (outline generation · Context-Aware)

```text
# Role: Top-tier PPT structure architect

## Profile
- Version: 2.0 (Context-Aware)
- Specialty: PPT logical structure design
- Strength: Apply the Pyramid Principle together with **background research (Context)** to build clear presentation logic

## Goals
Based on the **PPT topic** and **background research (Context)** provided by the user, design a logically rigorous, clearly layered PPT outline.

## Core Methodology: Pyramid Principle
1. Conclusion first: open each section with the core point
2. Summarize from above: upper-level points summarize lower-level content
3. Group by category: content at the same level belongs to the same logical category
4. Logical progression: unfold content in a deliberate logical order

## Important: use the research
You will receive search summaries about the topic. Be sure to reference them when planning the outline so it matches current market reality or technical facts rather than inventing things.
For example: if the research shows "a technology is outdated", do not present it as a core recommendation.

## Output specification
Strictly output in the following JSON format, wrapped in [PPT_OUTLINE] and [/PPT_OUTLINE]:

[PPT_OUTLINE]
{
  "ppt_outline": {
    "cover": {
      "title": "A catchy main title",
      "sub_title": "Subtitle",
      "content": []
    },
    "table_of_contents": {
      "title": "Table of contents",
      "content": ["Part 1 title", "Part 2 title", "..."]
    },
    "parts": [
      {
        "part_title": "Part 1: Section title",
        "pages": [
          { "title": "Page title 1", "content": [] },
          { "title": "Page title 2", "content": [] }
        ]
      }
    ],
    "end_page": {
      "title": "Summary and outlook",
      "content": []
    }
  }
}
[/PPT_OUTLINE]

## Constraints
1. Must strictly follow the JSON format.
2. **Page count requirement**: {{PAGE_REQUIREMENTS}}
```

### Prompt 2: Bento Grid layout methodology (the author calls it the "core moat")

```text
Bento Grid layout for content pages
This is a flexible grid system whose layout should be driven by the needs of the content itself, not by a rigid template. Combine cards of different sizes to create dynamic and visually interesting layouts.
- Core principles:
    - Flexibility: the number of cards is not fixed. It can be 1, 2, 3, 4, 5 or more, depending on how best to present the information.
    - Hierarchy: use card size to establish visual hierarchy. Put the most important information in the largest card.
    - White space: keep at least 20px of spacing between all cards.
- Layout combination examples:
    - Single focus: one large card covering most of the area (w=1200, h=580). Suitable for a single, powerful message or a detailed chart.
    - Two-column layout:
        - 50/50 symmetric: two equal-width cards.
        - Asymmetric: one wider card (e.g. 2/3 width) for the main content and one narrower card (1/3 width) for supporting information, data, or images.
    - Three-column layout: three equal-width cards, suitable for comparing three items side by side.
    - Primary + secondary: one large centered card with a small vertical card on each side.
    - Top hero: a wide "hero" card at the top, with a grid of 2-4 smaller equal-width cards below.
    - Mixed grid (most freedom): freely mix cards of various sizes, e.g. one medium square, two small horizontal rectangles, and one vertical rectangle. This adapts extremely well to different content needs.
```

### Prompt 3: SVG page generation (content → design draft · concatenation usage)

> Usage note from the original post: append the previous version (the content organized by Grok) at the end of the prompt after "My content is:" and send. Author's recommended model: Gemini 3 Flash (3.1 Pro if available).

```text
As an expert in information architecture and SVG coding, your task is to turn complete text content into a high-quality, structured SVG presentation page with a premium, clean, and professional feel. Requirements:

1. Canvas: the SVG viewBox must be 0 0 1280 720.

2. Bento Grid layout for content pages
This is a flexible grid system whose layout should be driven by the needs of the content itself, not by a rigid template. Combine cards of different sizes to create dynamic and visually interesting layouts.
- Core principles:
    - Flexibility: the number of cards is not fixed. It can be 1, 2, 3, 4, 5 or more, depending on how best to present the information.
    - Hierarchy: use card size to establish visual hierarchy. Put the most important information in the largest card.
    - White space: keep at least 20px of spacing between all cards.
- Layout combination examples:
    - Single focus: one large card covering most of the area (w=1200, h=580). Suitable for a single, powerful message or a detailed chart.
    - Two-column layout:
        - 50/50 symmetric: two equal-width cards.
        - Asymmetric: one wider card (e.g. 2/3 width) for the main content and one narrower card (1/3 width) for supporting information, data, or images.
    - Three-column layout: three equal-width cards, suitable for comparing three items side by side.
    - Primary + secondary: one large centered card with a small vertical card on each side.
    - Top hero: a wide "hero" card at the top, with a grid of 2-4 smaller equal-width cards below.
    - Mixed grid (most freedom): freely mix cards of various sizes, e.g. one medium square, two small horizontal rectangles, and one vertical rectangle. This adapts extremely well to different content needs.


Please output SVG code based on my content. My content is:
```

**Images**: Gemini generating SVG code ([gemini-svg-code](images/gemini-svg-code.png)), the resulting full-page SVG ([svg-result](images/svg-result.jpeg)).

---

## IV. Technical choice: why generate a "full-page SVG"

- Most AI PPT tools on the market call Banana (image generation) or generate HTML; the author's team generates a **full-page SVG**.
- Reasons for SVG:
  - **Best PPT compatibility**: SVG code can be dragged directly into Office 2016 and later;
  - **Fully editable**, supported by all major design tools;
  - **Scales infinitely without quality loss**, preserving sharpness.
- Cost: "Over three months we spent a lot of time on SVG, because nobody had done it before; everything had to be figured out from scratch."
- Advice for individual users: if you do not need editability, **generating HTML with AI is more recommended** (the relevant prompt is in the author's earlier article "Turning Xiaomi's 379-page annual report into a visual web page, with the complete prompt" <https://linux.do/t/topic/604327>).

**Image**: an example of an AI-generated finished piece — the cover ([cover-sample](images/cover-sample.jpeg)).

---

## V. Author motivation (implications for product positioning)

- Author's self-assessment: "What I'm building now only scratches about 5% of AI's PPT capability."
- Criticism of market tools: "Their developers don't understand PPT at all. They take an outline and force it into a template."
- Product belief: "AI is capable of changing the way we create and present information — and it already is."

---

## VI. Reusable design checklist (distilled)

1. **Research first, generate later**: build the "requirements interview" into the flow; use questions to clarify audience/purpose/page count/style instead of producing an outline straight from the topic.
2. **Ground the outline in real material**: retrieve first (Context), then generate the outline; explicitly require the prompt to cite research and avoid fabrication.
3. **Sticky-note outline**: visualize the outline as "one page per sticky note", supporting drag-to-reorder and page insertion/deletion.
4. **Two-stage generation**: plan draft (pure layout, structured, restrained styling) → confirm/fine-tune → design draft (add style effects). Important PPTs get manual fine-tuning at the plan-draft stage.
5. **Card/Bento Grid layout language**: constrain layout with the design language AI understands best; provide plenty of layout combination examples instead of a rigid template.
6. **Fixed canvas + structured output**: SVG viewBox 0 0 1280 720 (or 1920×1080); wrap JSON in parseable delimiters such as `[PPT_OUTLINE]`.
7. **Choose the format by need**: editable/Office-bound → SVG; personal use without editing → HTML.
8. **Model choice**: Gemini 3 Flash balances cost and quality; use 3.1 Pro when budget allows.

---

## Appendix: image index from the original post (original CDN links)

| Purpose | Original image URL |
| --- | --- |
| Finished example · cover | <https://cdn3.ldstatic.com/original/4X/c/a/7/ca785958d37aba2c5e234af1f4d969945ae87b2f.jpeg> |
| Finished example · layered architecture design | <https://cdn3.ldstatic.com/original/4X/2/b/9/2b9fbeb40ca978629c4986e994c2abc701f00121.jpeg> |
| Finished example · core hardware | <https://cdn3.ldstatic.com/original/4X/a/a/f/aaf137fb6a7a4ddff3c818a7c07cd5cb44562aea.jpeg> |
| Finished example · other style 1 | <https://cdn3.ldstatic.com/original/4X/1/1/8/1181834e44162e2c873288ee999a8184e54380ad.jpeg> |
| Finished example · other style 2 | <https://cdn3.ldstatic.com/original/4X/c/f/d/cfdbb2954d1b93ffc430c8a5652b3ef34f92dc5b.jpeg> |
| Full-workflow demo GIF | <https://cdn3.ldstatic.com/original/4X/2/7/3/273349036183b47dd6873ff8a6fc4b7a269bc974.gif> |
| Full-design demo GIF | <https://cdn3.ldstatic.com/original/4X/f/1/a/f1aab7cf304e037dc060a30e2f22555a06a83a24.gif> |
| Research UI | <https://cdn3.ldstatic.com/original/4X/f/4/5/f45478b3c2c96c726e50d357f2b776f372267dfc.webp> |
| Sticky-note UI GIF | <https://cdn3.ldstatic.com/original/4X/1/c/e/1cec102727d58958c25d6da46a1955e063b95199.gif> |
| Material search UI | <https://cdn3.ldstatic.com/original/4X/6/2/a/62a898a2d1178c85985ece017fc7ec2f166280c4.webp> |
| Grok research example | <https://cdn3.ldstatic.com/original/4X/6/3/0/6305c980802f3a1ddff840e44a71c842a9d9ea88.png> |
| Planner role introduction | <https://cdn3.ldstatic.com/original/4X/6/b/f/6bffcac7dd291641b6cdfa71cce3538a58248974.webp> |
| Plan-draft example | <https://cdn3.ldstatic.com/original/4X/b/6/3/b6318bdc47fbfd9d7466fdbb944ad839d6154158.webp> |
| Page draft (no design effects) | <https://cdn3.ldstatic.com/original/4X/5/1/9/519bbc1c6824983966ca86882578e0c752288d66.webp> |
| After design effects | <https://cdn3.ldstatic.com/original/4X/b/c/8/bc840a42bada631399f6d5c0504b9b11990210a7.webp> |
| Apple keynote card layout | <https://cdn3.ldstatic.com/original/4X/2/8/d/28d75c58237d2ea179ddd772da651aae0ac455ce.webp> |
| Card layout example | <https://cdn3.ldstatic.com/original/4X/c/7/a/c7a44935dcb61e2bc0421e6e8b2a35343a044806.webp> |
| Gemini generating SVG code | <https://cdn3.ldstatic.com/original/4X/c/7/4/c74bd996a229c7abf44d1ad0a6ff9d1dd37d78bc.png> |
| Resulting full-page SVG | <https://cdn3.ldstatic.com/original/4X/2/6/f/26f3fcb9890f2b0727180c9ef98a18cc01900137.jpeg> |

> Note: the OP did not add new prompts in the reply section (27 direct replies + the hot-post digest); the author said the full "research" prompt was not disclosed because of the commercial project, and the post only shows the product UI in screenshots.
