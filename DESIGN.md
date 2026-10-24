---
name: Card Spend Audit
description: A purchase-card audit set as a Swiss annual report; the measured numbers are the typography.
colors:
  paper: "#ffffff"
  paper-2: "#f0f0f0"
  ink: "#0a0a0a"
  ink-2: "#3d3d3d"
  ink-3: "#5c5c5c"
  rule: "#d4d4d4"
  signal-red: "#e30613"
  night-paper-2: "#1c1c1c"
  night-ink: "#f5f5f5"
  night-ink-2: "#c8c8c8"
  night-ink-3: "#a3a3a3"
  night-rule: "#333333"
  night-signal-red: "#ff4436"
typography:
  figure:
    fontFamily: "Hanken Grotesk, ui-sans-serif, system-ui, sans-serif"
    fontSize: "clamp(3.25rem, 9vw, 8.25rem)"
    fontWeight: 800
    lineHeight: 0.88
    letterSpacing: "-0.05em"
    fontFeature: "\"tnum\" 1, \"lnum\" 1"
  display:
    fontFamily: "Hanken Grotesk, ui-sans-serif, system-ui, sans-serif"
    fontSize: "clamp(2.25rem, 4.3vw, 3.6rem)"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "-0.03em"
  headline:
    fontFamily: "Hanken Grotesk, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.75rem"
    fontWeight: 800
    lineHeight: 1.1
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Hanken Grotesk, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 800
    lineHeight: 1.6
  body:
    fontFamily: "Hanken Grotesk, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 400
    lineHeight: 1.6
    fontFeature: "\"tnum\" 1, \"lnum\" 1"
  body-read:
    fontFamily: "Hanken Grotesk, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 400
    lineHeight: 1.65
  label:
    fontFamily: "Hanken Grotesk, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 600
    lineHeight: 1.45
  caption:
    fontFamily: "Hanken Grotesk, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 400
    lineHeight: 1.35
rounded:
  none: "0"
spacing:
  row: "12px"
  gutter: "24px"
  block: "40px"
  section: "80px"
  page-x-phone: "16px"
  page-x: "24px"
  container: "1152px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "8px 24px"
    height: "44px"
  button-outline:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "8px 24px"
    height: "44px"
  button-outline-hover:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
  button-ghost:
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    height: "44px"
  select-trigger:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "8px 12px"
    height: "44px"
  stamp:
    textColor: "{colors.ink}"
    typography: "{typography.caption}"
    rounded: "{rounded.none}"
    padding: "0 0.45em"
  stamp-stopped:
    textColor: "{colors.signal-red}"
  stamp-cost:
    textColor: "{colors.ink-2}"
  tag:
    textColor: "{colors.ink}"
    typography: "{typography.caption}"
    rounded: "{rounded.none}"
    padding: "2px 8px"
  select-option:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "8px 32px 8px 8px"
    height: "44px"
  tooltip:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.caption}"
    rounded: "{rounded.none}"
    padding: "8px 12px"
  scale-flag:
    backgroundColor: "{colors.signal-red}"
    width: "14px"
    height: "44px"
---

# Design System: Card Spend Audit

## Overview

**Creative North Star: "The Annual Report"**

The audit is set as a Swiss International Style annual report. The measured numbers are the typography: two figures near 130px carry the first screen, and everything else is ruled, numbered and set in one neo-grotesk on a 12-column grid. White paper, black ink, one grey, one signal red. Nothing is boxed, tinted or lifted; 2px black rules divide the page, and sections, figures and notes carry numbers the way a printed report does.

Density is that of a report, not a dashboard: generous vertical spacing between numbered sections, tight ruled rows within them. The world refuses the SaaS KPI-card page (tinted stat tiles, rounded cards, shadows) and the cream editorial data story. State is shown by a mark (a flag, a stamp, a tick, a strike, a dashed border) and never by a hue alone.

The dark theme is the same report inverted: black paper, white ink, a brighter red. It follows the OS until the reader picks one with the toggle.

**Key Characteristics:**
- One family (Hanken Grotesk), extrabold for anything that leads, tabular lining numerals everywhere.
- 2px ink rules as the only dividers of consequence; 1px grey rules between rows.
- Square corners on every surface and control.
- Flat: no shadows, no tinted card fills.
- Numbered sections, figures and notes; the number hangs in column 1.
- Red is a signal, not a palette colour.

## Colors

A monochrome press palette with a single signal red; the grey exists for secondary text and hairline rules only.

### Primary
- **Signal Red** (`signal-red`; night: `night-signal-red`): misuse stopped (the stopped figure, "stopped" bars and the scale's upper ticks, the Declined stamp on a stopped purchase, the strictness flag), and the report's own marks: section and note numbers, the logo square, the focus outline. It is never used for a category, a cost, a flagged purchase on a card's timeline, or an AI error.

### Neutral
- **Paper** (`paper`): the page and every surface, including tooltips and the select trigger. Night: `ink` becomes paper.
- **Pale Press Grey** (`paper-2`; night: `night-paper-2`): row hover in lists and the shaded "no more misuse stopped" region of the curve. Never a card fill.
- **Ink** (`ink`; night: `night-ink`): text, 2px rules, the primary button, the curve line, the 1% budget rule. The legacy aliases `--good`, `--warn`, `--buckskin` and `--series-1` all resolve to ink; they are not separate colours.
- **Ink 2** (`ink-2`; night: `night-ink-2`): secondary text, ledes, cost stamps.
- **Ink 3** (`ink-3`; night: `night-ink-3`): captions, axis labels, dates, keyboard hints, and the small dots for a card's unflagged purchases on the case timeline.
- **Hairline** (`rule`; night: `night-rule`): 1px row dividers and chart gridlines.

### Named Rules
**The Signal Rule.** Red marks what was stopped and the report's own numbering; a legitimate purchase declined is a cost and is stamped in ink-2, never red.

**The Mark Not Hue Rule.** Every state reads without colour: verdicts are an icon plus a label in ink, planted cases are a solid-bordered tag, control cases a dashed one, the current setting is a flag, a flagged purchase on the timeline is a square among dots.

## Typography

**Display Font:** Hanken Grotesk (with ui-sans-serif, system-ui)
**Body Font:** Hanken Grotesk
**Label/Mono Font:** none distinct; labels are the same family at 600-800.

**Character:** One neo-grotesk at few sizes, with weight carrying the hierarchy: 800 for figures, titles and captions that lead, 400 for reading. Numerals are tabular and lining site-wide, so columns of money align.

### Hierarchy
- **Figure** (800, clamp(3.25rem, 9vw, 8.25rem), 0.88, -0.05em): the headline measurements only, each with a ruled caption beneath (capped at 14vw on phones). Within 0.1 point of the 1% budget the declined figure prints two decimals, so it never reads "1.0%" beside "over the budget". Smaller figure cells (2rem) set the summary table.
- **Display** (800, clamp(2.25rem, 4.3vw, 3.6rem), 1, -0.03em, balanced): the page question on Findings and the Method title.
- **Headline** (800, 1.75rem / 1.5rem on phones, 1.1, -0.02em): numbered section titles; Method notes at 1.375rem; Case review title at 2rem.
- **Title** (800, 1rem): figure captions ("Figure 2. ..."), small sub-heads at 0.875rem.
- **Body** (400, 1.0625rem, 1.6): default text. Reading passages use body-read (1.125rem, 1.65) capped at 64ch; ledes and Method's notes cap at 62ch (70ch below lg).
- **Label** (600, 0.875rem): table headers, figure captions under numbers, nav links, buttons (700).
- **Caption** (400, 0.75rem): axis ticks, dates, hints; stamps use it at 800.

### Named Rules
**The Numbers Are The Type Rule.** The largest thing on a page is a measured number, never a word or an illustration.

## Layout

A 12-column grid (24px gutter) inside a 1152px container with 24px side margins (16px on phones). Sections are separated by 80px and open on a 2px ink rule; the section number hangs in column 1 and the content is set from column 2. On phones the number moves inline before the heading. Findings' first viewport puts the question in columns 2-7, the two figures in columns 8-12 with the answer-key note under them (on phones the note follows the figures, before the scale), the lede in 2-7, and the strictness scale ruled full width beneath. The decline figure's caption carries an "Over the 1% budget." line that is always laid out and only shown past the budget, so nothing below moves. Method indents its notes to column 2 at a 56rem block, with paragraphs and lists at 62ch and two-column key/value tables at 40rem. Case review is a two-pane schedule at lg (22rem list, detail) and a single list that opens into detail on phones; filters collapse behind a toggle under 640px. Rows inside lists and tables sit on 12px vertical padding. Every tap target is at least 44px.

## Elevation & Depth

Flat. Depth is never conveyed by shadow; hierarchy comes from rule weight (1px grey, 2px ink, 3px ink for the budget line on the curve, 4px dashed ink for it on the scale), type weight and position. Floating things (chart tooltips) are a paper box with a 2px ink border; the select popover is a paper box with a 1px ink border and no shadow.

### Named Rules
**The Ruled Not Lifted Rule.** If something needs separating, rule it; never shadow it, tint it or round it.

## Shapes

Every radius token is 0; corners are square throughout, including buttons, inputs, select options, checkboxes, tags, the slider thumb and tooltips. Nothing is a pill. Borders are ink at 2px for structure and controls (1px for the select trigger and answer-key note), grey at 1px between rows. Chart points are the only circles; on a card's timeline the flagged purchases are 12px ink squares among 3.5px ink-3 dots. The strictness flag is a 14 x 44px red bar standing on a 2px ink track.

## Components

### Buttons
Blunt, printed controls.
- **Shape:** square (0), 44px tall in use, 700 weight 0.875rem.
- **Primary:** ink fill, paper text, 2px ink border; marks a chosen decision ("Escalated").
- **Outline:** paper with a 2px ink border; hover fills with ink and inverts the text.
- **Ghost:** text with a 2px underline at 4px offset; hover turns the underline red. Used for "Next case", "Clear filters", "Back to the reported setting" and the theme toggle.
- **Focus:** 2px signal-red outline at 2px offset (site-wide), plus the shadcn ring on buttons.

### Tags
- **Style:** square, 1px ink outline, ink text, 0.75rem 700, 2px 8px padding; never a pill. Planted cases take a solid border, control cases a dashed one: the difference is the mark, not a colour.
- **Answer-key result:** on planted and control rows in the case list, the AI's result against the answer key follows the tags. A right call ("AI caught it", "AI cleared it") is plain ink-2 text; a wrong one ("AI missed it", "AI wrongly flagged it") is an ink stamp. An answer-key summary line (0.875rem 600) sits above the list.
- **Blind review:** a checkbox under the summary line ("Review blind", kept in the URL as `?blind=1`). While on, an undecided case shows no verdict, no Planted/Control tag, no answer-key result and no "cited by AI" marks; its detail replaces them with a ruled "Reviewing blind." note, and the AI verdict filter is removed. Deciding a case reveals all of it, and a second line under the summary tallies your calls on the planted and control cases you have decided. Findings links to it ("review them blind and see how your calls compare").

### Inputs / Fields
- **Select trigger:** paper, 1px ink border, square, 44px, with a muted chevron; label above in ink-2 at 0.875rem. Untinted in dark mode.
- **Select options:** 44px rows in a paper popover with a 1px ink border and no shadow; the focused option takes paper-2.
- **Checkbox:** 16px square, 2px ink border, ink fill with paper tick when checked.

### Navigation
A running head: the name with a 16px red square at left, Findings / Case review / Method at right in 0.875rem 600 ink-2, then the theme toggle; the whole head sits on a 2px ink rule. The active link goes 800 ink with a 2px ink underline. On phones the nav wraps to a second line under the name. A "Skip to content" link is the first focus stop.

### Stamp
A swipe-time decision as a ruled label: 2px border in currentColor, 0.75rem 800, no rotation, no fill. Red when it stopped planted misuse, ink-2 when it is the cost of a legitimate purchase declined, ink for an approval and for the AI's misses and false alarms against the answer key.

### Verdict
The AI reviewer's call: a 14px (18px large) stroked icon plus a label, always both, in ink (ink-3 for no answer / not reviewed).

### Strictness Scale (signature)
Figure 1 on Findings. The caption line carries the current strictness and a ghost "Back to the reported setting" button, always laid out and invisible at the reported setting so the scale never shifts; a 0.75rem ink-2 key line (max 34rem) sits under the title. A "Reported" label with a short ink stem marks the quoted setting above the ticks. Above the 2px track, red ticks for planted misuse stopped at each setting (60px for 100%; current one solid, others at 70%); below, ink ticks for legitimate spend declined at 16px per 1% (current solid, others at 50%), clipped at 3% with a paper break across the tick. The 1% budget is a 4px dashed ink rule labelled "1% budget". The red flag thumb is 14 x 44px to the eye with a 44px-wide hit area; its wrapper eases `left` over 220ms (cubic-bezier(0.16, 1, 0.3, 1)) when motion is allowed, and the slider root is `touch-action: pan-y` so a vertical swipe still scrolls. The same setting drives the trade-off curve and the cost list, so one control registers in three places.

### Charts
Hand-written SVG: ink line and points, 1px grey gridlines, 12px ink-3 tick labels, a 3px ink vertical rule for the 1% budget, paper-2 shading where nothing more is gained, one red point for the current setting. A card's timeline (log scale) sets flagged purchases as 12px ink squares and its other purchases as 3.5px ink-3 dots; no red. Tooltips are 2px-ink-bordered paper boxes.

### States
Inside the report, never a bare error: "No such page" (2rem heading on a 2px ink rule, ink-2 explanation at 62ch, an underlined "Back to Findings") for unknown routes and render errors, and "No case X" in the case pane with the valid range and "Back to all cases". An AI case with no valid answer states it in an ink 600 line, never red.

## Do's and Don'ts

### Do:
- **Do** divide with 2px ink rules and number sections, figures (Figure N.) and notes (Note N.).
- **Do** let a measured number be the largest element on the page, set in figure style with a ruled caption.
- **Do** keep every corner square and every surface flat and untinted.
- **Do** show state with a mark (flag, stamp, icon + label, solid vs dashed border) that survives greyscale.
- **Do** keep numerals tabular and lining, and money columns right-aligned.

### Don't:
- **Don't** use signal red for anything except misuse stopped and the report's own marks (numbers, logo square, current setting, focus).
- **Don't** stamp or colour a legitimate purchase declined in red; it is a cost, set in ink-2.
- **Don't** use shadows, rounded corners, pills or tinted card fills.
- **Don't** introduce a second typeface or a monospace for display.
- **Don't** set KPI tiles or stat cards; figures stand on rules in the grid.
