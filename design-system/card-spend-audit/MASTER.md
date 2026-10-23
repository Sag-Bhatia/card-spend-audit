# Card Spend Audit: design system (MASTER)

Generated with ui-ux-pro-max (`"audit review dashboard financial report" --design-system --density 7`),
then taste-checked with frontend-design. **This file is the single design source of truth** for `web/`.
Page files in `pages/` override it where they exist (none yet).

## What changed in the taste check

| Generated pick | Kept / swapped | Why |
|---|---|---|
| Pattern "Enterprise Gateway" (mega menu, Contact Sales) | Swapped | This is a data story plus a review tool, not a sales site. Nothing to sell. |
| Style "Dark Mode (OLED)", light not recommended | Swapped | Light and dark are both required. A dark page with one acid-green accent is the most common generated look. |
| Navy `#0F172A` + green `#22C55E` | Swapped | Green means "approved" in card UIs; as the only accent it fights the verdict colors. |
| Fira Code headings + Fira Sans body | Swapped | Monospace headings read as a code tool. The subject is money and policy, not code. |
| Density 7, 4.5:1 contrast, visible focus, reduced motion, 375px | Kept | All required anyway. |

## The idea

**The moment of the swipe.** Every purchase is either approved or declined at the register, and the
project asks what a stricter card would have declined. The visual world is a card statement under
review: cool statement-white paper, graphite ink, Oklahoma's flag sky blue for ordinary approved spend,
and a decline red for what gets stopped. The state flag's buckskin tan marks the planted test cases.

The one loud element is the **strictness dial** on the Findings page. Everything else is quiet and
precise: this is Operate mode on Case review and Read mode on Findings and Method.

## Color

Semantic tokens live in `web/src/styles.css` as CSS variables, with light values on `:root`, dark
values under `prefers-color-scheme: dark` (guarded by `:root:not([data-theme="light"])`) and again under
`:root[data-theme="dark"]`. Components never use raw hex.

| Token | Light | Dark | Role |
|---|---|---|---|
| `--paper` | `#F4F6F9` | `#0F1621` | Page background (statement white / night statement) |
| `--paper-2` | `#E8ECF2` | `#172131` | Hover, quiet fills, table stripes |
| `--surface` | `#FFFFFF` | `#18233A` | Raised panels: the dial, case detail |
| `--ink` | `#151B24` | `#E9EEF5` | Primary text |
| `--ink-2` | `#495567` | `#B0BCCB` | Secondary text |
| `--ink-3` | `#5F6B7C` | `#8E9BAD` | Tertiary text, axis labels (still 4.5:1 on paper) |
| `--rule` | `#D5DCE5` | `#28354A` | Hairlines |
| `--rule-strong` | `#A9B5C4` | `#41516A` | Input borders, emphasized rules |
| `--series-1` (sky) | `#1D6AB0` | `#5B9BE0` | Approved / ordinary spend, links, focus |
| `--series-2` (decline) | `#C7362B` | `#F06A5C` | Declined / flagged / stopped |
| `--buckskin` | `#8A6431` | `#D2A96E` | Planted test cases only |
| `--good` | `#1C7348` | `#4FBF88` | Verdict: likely fine |
| `--warn` | `#8A5300` | `#E5A640` | Verdict: needs review |
| `--bad` | `#B42318` | `#F37365` | Verdict: likely misuse |

Rules:
- Verdicts always ship with an icon and a label, never color alone.
- Sky and decline are the only two chart series. A third meaning gets a shape or dash, not a color.
- Buckskin is for planted cases only; controls use sky.

## Typography

One family: **Archivo** (Google Fonts, variable: weight 100–900, width 62–125). The width axis
gives two clearly distinct roles from one family:

| Role | Setting | Size |
|---|---|---|
| Display (page titles, hero) | `font-stretch: 118%`, weight 800, tracking −0.02em, line-height 1.02 | clamp(2.4rem, 6vw, 4.6rem) |
| Section heading | `font-stretch: 112%`, weight 750 | 1.75rem (1.5rem on phones) |
| Big figures | `font-stretch: 112%`, weight 800, tabular | 2.75–3.5rem |
| Body | `font-stretch: 100%`, weight 400, line-height 1.6 | 1.0625rem; long reading text 1.125rem at 64ch |
| UI / labels | weight 500–600 | 0.875rem; never below 0.75rem |

- All numbers use tabular lining figures (`tnum`, `lnum`).
- Sentence case everywhere. No all-caps eyebrow labels, no monospace data labels, no `→` on links.

## Spacing and shape

- Spacing on a 4px grid; sections 80px apart on desktop, 56px on phones.
- Radius by hierarchy: 4px controls and badges, 8px panels, 12px the dial panel only.
- No drop shadows except the dial panel (`0 1px 0 var(--rule-strong)`), which sits like a terminal on paper.
- Content left-aligned; max width 72rem; reading text 64ch.

## Components (shadcn/ui, themed by these tokens)

shadcn components in `web/src/components/ui/` are themed only through the CSS variables above, mapped
to shadcn's names in `@theme inline` (`--background` → paper, `--foreground` → ink, `--primary` → ink,
`--muted-foreground` → ink-2, `--border`/`--input` → rule/rule-strong, `--ring` → series-1,
`--destructive` → bad).

| Need | Component |
|---|---|
| Strictness dial | `Slider` (Radix: keyboard, aria-valuetext) |
| Case filters | `Select`, `Checkbox`, `Label` |
| Dismiss / escalate, theme toggle | `Button` (variants: default, outline, ghost) |
| Planted / control / rule tags | `Badge` |

Charts stay hand-written SVG (Curve, Timeline): no chart library.

## Interaction and motion

- Hover and press feedback 150–200ms, color and opacity only.
- One orchestrated moment: example declines stamp in when the dial moves. Nothing else animates on its own.
- `prefers-reduced-motion` turns the stamp off.
- Touch targets at least 44×44px on phones.

## Anti-patterns (do not use)

- Dark-only themes, acid-green accents, cream backgrounds with terracotta accents
- Identical rounded cards with soft grey shadows; gradient washes
- All-caps eyebrows, middle-dot meta strings, monospace labels, arrows appended to links
- Emoji as icons; color as the only signal
- Horizontal scroll at 375px

## Pre-delivery checklist

- [ ] Light and dark: text 4.5:1, large text and chart marks 3:1
- [ ] Visible focus on every control; keyboard reaches the dial, filters and buttons
- [ ] 375, 768, 1024, 1440px: no horizontal scroll
- [ ] Reduced motion respected
- [ ] Empty, loading and error states read as directions, not moods
