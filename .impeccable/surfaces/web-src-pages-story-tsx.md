---
version: 1
slug: "web-src-pages-story-tsx"
primary_target: "web/src/pages/Story.tsx"
related_targets: ["web/src/pages/Cases.tsx","web/src/pages/Method.tsx"]
---

# Findings, Case review, Method (Card Spend Audit site)

Scope: the whole static site; Findings (`#/`) is the first surface and sets the world. Mode: read (Findings, Method); Case review is operate inside the same world.
Audience and job: fintech hiring reviewers skimming a portfolio link; they must believe within one screen that the result was measured, then find the evidence.
Constraints: look and layout only; pages, copy and numbers stay as generated. Light and dark, 375px up, hand-written SVG charts, no metric logic in the browser.

## Direction contract

THESIS: The audit set as a Swiss annual report: the measured numbers are the typography, on a strict 12-column grid with numbered figures and notes. It refuses the SaaS KPI-card page and the cream editorial data story.

OWN-WORLD: White paper, black ink, one signal red for misuse stopped, one grey; dark theme inverts to black paper and white ink. One neo-grotesk (Hanken Grotesk) at few sizes, numerals tabular. 2px black rules divide everything; square corners, no shadows, no tinted card fills. Figures and notes are numbered. State is a mark (flag, tick, strike), never a hue.

STORY: The reviewer reads the answer and its answer key before scrolling, believes it was measured, moves the scale to price the trade-off, then audits cases in a ruled schedule.

FIRST VIEWPORT: Running head on a 2px rule, name left, nav right. Red section number in column 1; the question as title in columns 2-7 near 58px; 24% (red) and 0.73% (black) as figures near 130px in columns 8-12 with ruled captions; lede columns 2-6; answer-key note under the figures; the strictness scale ruled full width at the fold, red flag at the setting, the 1% budget as a heavy rule. The scale is the primary action.

FORM: Swiss International Typographic Style annual report, candidate 4 of 7. seed:1a5f020333643e03. Raises: state as marks (cutting bench), one calibrated scale registering dial, curve and cost list (emission rail), the 1% budget as a hard capacity rule (cassette J-card).

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
