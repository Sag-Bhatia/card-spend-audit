# Card Spend Audit — spec

**The design spec, written before the build.** A few details changed while building (for example, the strictness
knob and the AI case mix); WRITEUP.md and REPORT.md describe what was actually built and measured.

## 1. What it is
A portfolio project for fintech (Ramp-style) audiences. It takes **real public government
purchase-card transactions**, runs swipe-time card controls and an AI investigator over them, and
proves every claim with generated numbers. Four core pieces:

1. **Rule checks**: split purchases, duplicates, prohibited categories (+ one soft anomaly rule).
2. **Planted-misuse measurement**: inject labeled fake misuse into real data, then measure recall.
3. **Prevention replay** (centerpiece): re-run history chronologically with swipe-time controls;
   a curve of misuse $ blocked vs legit $ declined as strictness rises.
4. **AI investigator**: headless Claude Code reviews the top flags with read-only tools.

Plus a polished static web app and a write-up. Out of scope (listed as "next" in the write-up):
replaying published state audits, cross-state comparison, a public merchant-name benchmark,
fraudster-vs-auditor agents, live hosting.

## 2. Data sources (chosen at the M1 gate, in this order)
1. **Oklahoma** purchase-card transactions (data.ok.gov / OMES open data).
2. **Delaware** state employee credit card transactions (data.delaware.gov).
3. **UK local council** procurement-card files (pick one large council with consistent monthly CSVs).

The URLs and field names are unconfirmed. The `researcher` subagent confirms them before
`sources.py` is written. The policy source is that government's published purchase-card
policy/manual (PDF or page) and is required for `policy.yaml`.

**Go criteria** (all required): ≥100k transactions, ≥2 years, fields for amount, date, merchant,
agency, and something that identifies the card or cardholder. MCC is strongly preferred; without
it, `prohibited_mcc` falls back to merchant-name keywords (logged). Use the first source that
passes. Record why the others failed in NOTES.md.

**Common schema** (polars, one parquet in `data/`):
`txn_id: str` (stable hash of the source row), `date: Date`, `amount: Float64` (refunds
negative; keep them), `merchant_raw: str`, `mcc: str | null`, `agency: str`, `card_key: str`
(salted SHA-256 of the cardholder/card field; the salt lives in gitignored `data/salt`),
`description: str | null`. **Names never survive `sources.py`.**

## 3. Merchant normalization (`merchants.py`)
`normalize(raw: str) -> str`:
- uppercase
- strip processor prefixes (`SQ *`, `TST*`, `PAYPAL *`, `SP *`, `PY *`, `AMZN MKTP US*…`,
  `AMAZON.COM*…`)
- strip trailing store numbers, city/state, phone numbers and reference codes
- collapse whitespace

Then cluster near-duplicates per first token with rapidfuzz (`token_sort_ratio ≥ 92`) into
`merchant_norm`. Also produce a table of the 30 largest clusters with sample raw strings, for the
Method page and for the user to spot-check.

## 4. Policy and rules
`policy.yaml`:
- `single_purchase_limit`
- `prohibited_mccs: [{mcc, label, clause, url}]`
- `split_window_days`, `duplicate_window_days`

Every value cites the published policy. A guessed value carries `# placeholder: <what to check>`
and is listed in NOTES.md.

`rules.py` → `list[Flag]`, where `Flag = {rule, txn_ids, card_key, agency, merchant_norm,
dollars_at_stake, evidence: str}`:
- **split**: same `card_key` + `merchant_norm`, ≥2 txns within `split_window_days`, each
  < limit, sum > limit.
- **duplicate**: same card + merchant + amount (≥ $5) within `duplicate_window_days`.
- **prohibited_mcc**: MCC (or keyword fallback) in the prohibited list.
- **unusual_for_card** (soft): amount > card's prior p99 × 3 with ≥20 prior txns, *or* a
  consumer-type MCC (streaming, dating, games, clothing) the card has never used.

## 5. Planted misuse (`plant.py`)
`plant(df, seed, n_per_type=200) -> (df_with_plants, labels)`. Each plant is an *incident* of one
or more new rows, marked by a hidden `planted_type` column that the rules never read. It uses
real `card_key`s, real merchants, and amounts sampled from the real distribution for that
merchant/MCC.

| Type | How it's planted |
|---|---|
| `split` | One purchase of 1.2–3× the limit, split into 2–4 parts under the limit, 0–N days apart |
| `duplicate` | A real txn re-posted 0–2 days later |
| `prohibited` | Gift card / cash / liquor-type MCC or merchant |
| `personal` | One consumer merchant that is out of pattern for the card; only the soft rule and investigator can catch it |

Run seeds 0–4.

Metrics:
- **recall per type**: incidents with ≥1 row flagged / incidents. Report the mean and min–max
  across seeds.
- **flag volume** per 10k real txns.

Precision on real data is unknown. Say so.

## 6. Prevention replay (`replay.py`)
Process txns in date order (ties broken by `txn_id`). Each txn is approved or declined **using
only earlier txns** plus the policy. Declined txns don't count toward later rolling sums.

Controls are parameterized by `strictness s ∈ [0,1]` (21 points). Each control's decline set
must only grow as `s` rises, so the curve is monotonic:
- prohibited MCC: always on.
- split guard: decline if the rolling card+merchant sum over the last `1+round(6s)` days
  (including this txn) exceeds the limit.
- duplicate guard: decline the same card+merchant+amount within `round(3s)` days (off at `s=0`).
- anomaly guard: decline if amount > prior p99 × `(4 − 3s)`, once the card has ≥20 prior txns.

Output, per `s`:
- `legit_dollars_declined_pct`: non-planted $ declined / non-planted $. This is an *upper
  bound*: some real txns are misuse.
- `planted_dollars_blocked_pct` overall and per type.
- 10 example declines.

**Headline:** planted $ blocked at the largest `s` where legit $ declined ≤ 1%.

Must be vectorized or use a per-card loop. A full year must run in < 60 s.

## 7. AI investigator (`investigate.py`, `tools.py`)
**Case set:** the top 40 real flags by `dollars_at_stake` (deduped per card+merchant), plus 10
planted incidents from seed 0 (at least 2 per type; blind, their labels never reach the model).
Each case gets a `case_id`.

**Runner:**
- One subprocess per case:
  `claude -p <prompt> --output-format json --model sonnet --allowedTools "Bash(uv run python -m spendaudit.tools:*)" --max-turns 12`
- The env copy removes `ANTHROPIC_API_KEY` and `CLAUDECODE`, so it uses the user's Claude
  plan, not API credits.
- 4 run concurrently, with exponential backoff on failure.

**Tools** (`python -m spendaudit.tools …`, read-only, output capped at 4 KB):
- `card-history <card_key> [--around DATE --days N]`
- `merchant <merchant_norm>` (spend by agency, typical amounts, MCCs)
- `policy [clause]`
- `peer-spend <agency> <merchant_norm>`

**Prompt:** the role is a careful purchase-card reviewer. It gets the flag evidence and the
policy, is told to investigate with the tools, and must reply with **only** a JSON object:
`{verdict: likely_misuse|needs_review|likely_ok, confidence: 0–1, explanation (≤80 words),
evidence_txn_ids: [..], policy_clause, innocent_explanation, dollars_at_issue}`.

**Validation** (pydantic):
- Any `evidence_txn_ids` not in the data → reject and retry once with the error. A second
  failure → `verdict: error`.

**Caching and cost:**
- Results cached in committed `out/cases.json` keyed by `case_id` + prompt hash. Re-runs skip
  cached cases.
- Record `usage` tokens, `total_cost_usd` (API-equivalent; the plan pays) and wall time from
  the JSON output.

**Metrics:** on the planted cases, the share rated `likely_misuse` or `needs_review`. Report the
verdict mix on real cases. State that real-case verdicts are unverified.

**Fallback:** if a nested `claude -p` fails inside the build session, keep the runner, test it
with recorded fixtures, and tell the user to run `uv run python -m spendaudit investigate` once
from Terminal. Log this in NOTES.md.

## 8. Export (`export.py`)
Writes `web/public/data/`:
- `summary.json` (headline numbers, data profile, run date)
- `curve.json`
- `recall.json`
- `rules.json` (counts, $ by rule, by agency per $1M spend)
- `cases.json` (case + evidence txns + ±30-day card timeline + AI result; cards shown as
  "Card A/B…", no `card_key`)
- `merchants.json` (top clusters)

Also generates `REPORT.md`: every number in the project, with sample sizes, seeds and date.
**No number anywhere is typed by hand.**

## 9. Web app (`web/`, static; React 19 + Vite + Tailwind v4, no backend)
Load the `frontend-design` and `dataviz` skills before building. Its own design system: a
serious fintech feel (think a controller's tool), not a copy of the fantasy app. Design tokens
are CSS variables in `web/src/styles.css`, with light + dark themes. Charts are hand-written
SVG components. It works at 375 px wide.

- **Story** (`/`): the write-up as a page.
  - Hero with 3 headline numbers from `summary.json`:
    - planted misuse caught by rules
    - planted $ blocked at ≤1% legit $ declined
    - $ audited, plus what the AI review cost
  - **Trade-off curve with a strictness slider** (keyboard-accessible). Moving it updates the
    two percentages and lists example declines at that setting.
  - 3 example AI cases (one `likely_misuse`, one `needs_review`, one `likely_ok` where
    possible), method in brief, limitations, next steps.
- **Inbox** (`/cases`):
  - Filters: rule, verdict, agency, $.
  - List + detail pane with a timeline chart of the card's spend ±30 days with flagged txns
    highlighted, an evidence table, the policy clause, the AI explanation and innocent
    explanation, and confidence.
  - Dismiss/escalate are stored in localStorage (wrapped in try/catch).
- **Method** (`/method`): data profile, merchant clusters, recall table per type (mean,
  min–max), flag volume, replay details, investigator cost/tokens, limitations.

## 10. Write-up (`WRITEUP.md`)
Around 800 words, built from `summary.json`/`REPORT.md` numbers only. Structure:
1. Headline
2. Why (Ramp's thesis: controls at the swipe beat audits after the fact)
3. Data
4. What I built
5. The curve
6. What the AI found
7. How I measured
8. Limitations
9. Next

Limitations must say:
- recall measures known planted patterns only
- legit-declined is an upper bound
- real-case AI verdicts are unverified
- one jurisdiction only
- findings are "worth reviewing", not accusations

The user reviews it before anything is shared.

## 11. CLI
`uv run python -m spendaudit {gate,build,plant,replay,investigate,export,all}`. `all` runs every
step except `investigate`, which uses the cache and runs only on request.
