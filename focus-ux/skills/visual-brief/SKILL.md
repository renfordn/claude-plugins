---
name: visual-brief
description: Present big or many-part information visually, as a diagram, timeline, flow, comparison matrix, progress map, or chart with a short headline, so a visual thinker with ADHD can take it in at a glance and remember it. Use this whenever you're about to deliver research findings, a review or audit result, an investigation or debugging conclusion, a plan or roadmap, a comparison of options, a multi-phase recap, or an explanation with several moving parts. Also use it when the user says "show me", "visualize", "diagram", "timeline", "map it out", "draw", "picture", "overview", "summarize visually", or "I'm lost". Use it even when they didn't ask for a visual, if the reply would otherwise run past about 15 lines of prose or bullets.
---

# Visual Brief

The reader thinks in pictures and has ADHD. A wall of text gets skimmed and forgotten. One good
picture with a one-line headline gets understood and remembered. Your job is to find the
**shape** of the information, draw that shape, and keep the words to what the picture can't
carry.

## 1. Find the shape

Before drawing anything, name what kind of thing it is. The shape decides the form, and a wrong
form (a flowchart of things that don't flow) is worse than a list.

| The content is… | Draw a… |
|---|---|
| Events or steps in time order, history, a plan's phases | **Timeline** (horizontal, milestones labelled) |
| A process with branches, decisions, or loops | **Flow diagram** |
| Parts and what talks to or depends on what | **Structure / box-and-arrow map** |
| A hierarchy, like a folder tree, an org, or a taxonomy | **Tree** |
| Options judged on criteria | **Comparison matrix** with a verdict row |
| A change | **Before → after**, side by side |
| Status of many items (tasks, slices, checks) | **Progress map / checklist grid** |
| Quantities, trends, or proportions | **Chart**: follow the `dataviz` skill for the form and colours |
| Findings with severity or priority | **Ranked cards** (most important first) plus a small severity strip |

Two shapes in one set of findings (say, a structure *and* a sequence) means two pictures. Don't
cram both into one. More than two pictures means you need to cut something.

`references/patterns.md` has a ready-to-adapt ASCII template for each shape.

## 2. Split: the chat always carries the summary; the page is extra

Every brief has a **text summary in chat**: the headline, the picture drawn inline, the top 3
points, and what's next. That alone should be enough to act on. Build an **Artifact page** on top
of it only when the page adds something the chat can't:

- the user will **come back to it** (a plan, a tracker, a report they'll share), or
- it has **more than about 7 findings or rows**, a **real chart**, or a **flow with branches**
  that ASCII can't draw cleanly, or
- the user **asked** for a page or visual.

Otherwise, stay inline and end with a one-line offer: `Want this as a page? (plan + timeline)`.
Building a page costs about 30 seconds and 15K tokens, so it has to earn that.

In the terminal CLI, where there's no Artifact tool, stay inline at any size. When an inline
picture gets large, split it into several small ones.

### Building the page cheaply: the bundled template

Don't hand-write the HTML. Write the brief as a small JSON file and render it with the bundled
script. The template is already designed (both themes, phone width, accessible type), so
there's nothing to design each time, and every brief shares one layout the reader learns once.

1. Write `brief.json` to the scratchpad. The script's docstring documents the shape. It supports
   `progress`, `points`, and sections of type `findings`, `timeline`, `matrix`, `bars`,
   `diagram` (mermaid, which Artifacts render natively), `text`, `list`, and `details`.
2. `python3 <skill dir>/scripts/build_brief.py brief.json brief.html`
3. Publish `brief.html` with the Artifact tool. Pass a one-sentence `description`, and
   `icon: "chart"` on the first publish. The Artifact tool asks you to load `artifact-design`
   before publishing, so do that. Skip `artifact-diagramming` and `dataviz`, because the template
   already covers them.

Hand-build a page (with those skills) only when the template really can't show the shape, such
as an interactive tool or a chart type the template lacks. The inline widget (`show_widget`) is
rarely worth it: its guide is very large, so reach for it only for a one-off rich picture the
user explicitly wants in chat.

## 3. Structure of a brief

Whatever the medium, the reader should hit these in this order:

1. **Headline**: one sentence with the conclusion. It is not a title. "Nelly's cache misses
   because summaries are keyed by absolute path" beats "Cache analysis".
2. **The picture**: the one diagram or chart that carries the shape.
3. **Key points**: 3 to 5 at most, each tied to a spot in the picture with a numbered callout
   (①②③) and followed by its "so what" in a few words.
4. **What's next**: the decision or action it leads to, with your recommendation.
5. **Details** go last. In an Artifact, put them in collapsible sections. In chat, leave them out
   unless asked.

If the brief is part of multi-step work, add a small progress strip at the top showing where
this sits (`Phase 2/4 ▸ Step 3/5`). Name what each finished phase actually produced
("entry type + write path merged"), not just that it's done. Seeing concrete results is what
makes progress feel real and easy to recall later. A bare ✅ gives the reader nothing to hold on
to.

## 4. Make it memorable

These choices are what make a picture stick instead of blur:

- **Label on the picture.** Put names on the nodes and arrows themselves rather than in a legend
  the eye has to shuttle to.
- **Keep one meaning per colour for the whole brief.** Pick a colour for each concept (say, done
  green, current blue, risk amber) and never reuse it for anything else. Colour always backs up a
  label or icon and never stands in for one.
- **Chunk to about 7.** Group anything bigger into named clusters.
- **Read in one direction.** Time and flow go left to right or top to bottom, never both at once.
- **Mark "you are here" and "the problem".** One highlighted node or row tells the eye where to
  land first.
- **Use concrete labels:** real file names, real numbers, real dates. "~40% of lookups miss" beats
  "many misses".
- **Draw comparisons in chat as a markdown table, not ASCII.** A table reflows to a narrow
  chat panel, while a wide ASCII grid wraps into noise. Keep ASCII for shapes a table can't show
  (timelines, flows, trees) and keep those under about 80 characters wide.
- **Put words in matrix cells, not symbols.** Rating dots (●●○) or bare ✅/❌ show *that* an
  option loses without saying *why*, so the reader has to hunt for the reason somewhere else. Use
  a short verdict word plus a reason of a few words ("❌ corrupts over iCloud"). Save pure symbols
  for status grids, where the meaning is just done / not done.

## 5. Deliver it

- **Chat (always):** the headline, then the inline picture, then the **top 3 key points** in a
  line each, then the decision needed with your recommendation. Keep it to about 20 lines.
  Readers often never open a link, so the chat has to stand on its own.
- **Page (when earned):** add the link on its own line under the key points. Don't repeat the
  page's full detail in chat. Without a page, end with the one-line offer instead.
- Every key point must also exist in plain words, because the picture supports the text rather
  than replacing it. That matters for screen readers, for the terminal, and for the moment the
  picture doesn't load.

## Don't

- Don't draw decoration. If a picture doesn't show a real relationship, order, or comparison,
  use a short list instead.
- Don't add a diagram of one box, or a chart of one number. Say it in a sentence.
- Don't restate the whole picture in prose underneath it.
