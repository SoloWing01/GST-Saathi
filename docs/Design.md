# Design — UI/UX

## Principle
The merchant is anxious when they land here. The design job is to lower
panic, not add more dense text. Calm, plain, short sentences, generous
whitespace. This is a compliance tool, not a dashboard — resist the urge to
cram in charts.

## Screens

### 1. Upload screen
- One clear action: upload a notice (drag-drop or file picker), or a "paste
  text instead" option.
- Short reassuring copy: what happens next, that nothing is sent anywhere
  permanent, roughly how long it takes.
- No sign-up friction for the demo — keep it to one screen, one action.

### 2. Processing state
- Show the audit trail live as it happens (parsing → matching transactions →
  checking rules → reasoning) — this doubles as a trust-building UI moment
  and a demo highlight. A simple step list with checkmarks appearing in
  order is enough; no need for animation polish.

### 3. Results screen
Four clearly separated sections, in this order:
1. **What this means** — one or two plain-language sentences.
2. **Why you likely got it** — tied to specific transaction IDs, shown as a
   small reference list, not buried in prose.
3. **What to do next** — a short actionable checklist, not a paragraph.
4. **Confidence** — a visible badge (high / medium / low). Low confidence
   swaps the tone of the whole card: a distinct visual treatment (not just
   red text) plus a clear "here's what to check with a CA" line.

Every factual sentence carries a small inline citation marker (rule
reference or transaction ID) that expands to show the source on click/hover.
A collapsed "full audit trail" section at the bottom for anyone who wants
the detail.

## Visual tone
- Plain, sans-serif, high contrast, generous line height — legible for a
  non-technical, possibly stressed reader.
- Color used sparingly and meaningfully: neutral for informational, a single
  distinct treatment for low-confidence/escalation — not a rainbow of
  status colors.
- No jargon in headings. "What this means," not "Notice classification."

## What NOT to do
- Don't make it look like a legal document — that increases anxiety, not
  trust.
- Don't hide the confidence level or audit trail to make the app "look more
  confident" — the honesty is the point of this product.
- Don't over-build the frontend before the pipeline (Phases 0–6) works.
  Design polish is Phase 7, not Phase 1.
