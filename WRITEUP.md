# If Oklahoma's state cards could say no at the register, what would they stop?

_Card Spend Audit. Numbers generated 2026-10-23 by `python -m spendaudit export`._

**Swipe-time card controls would have stopped 24% of the misuse I planted in two years of Oklahoma's real purchase-card data, while declining 0.73% of legitimate spend. After-the-fact rules caught 88%. An AI reviewer worked 80 cases for $3.92 at API prices.**

## Why

Most public card programs find problems after the money is gone: a monthly reconciliation, an annual audit. Corporate card platforms like Ramp argue the opposite: put the policy on the card so the bad purchase never clears. I wanted to test that claim on real data, with the cost attached, because every control that stops misuse also stops some purchases people needed to make.

## The data

Oklahoma publishes every state purchase-card transaction. I used 24 months of statements (2024-07 to 2026-06): 843,229 transactions, $366.5M of purchases, 119 agencies and 7,530 cards. The policy is the state's own: a $5,000 single-purchase limit set by statute (74 O.S. § 85.5a), a ban on splitting purchases to get under it, and banned categories including cash, gift cards and motor fuel. The files have no card numbers, so a card is an agency plus a cardholder's surname and initial, hashed on load. No names are kept.

## What I built

1. **Merchant cleanup.** 276,892 raw card descriptors ("SQ  CORNER COPY", "AMAZON MKTPL PL8PX4N33") collapse to 40,341 merchants.
2. **Rule checks** for split purchases, double charges, prohibited categories, and purchases unusual for the card. On the real data they raise 14,030 flags, 166 per 10,000 purchases.
3. **A planted answer key.** Real data has no labels, so for 5 random seeds I planted 200 incidents of each kind of misuse, using real cards, merchants and amounts.
4. **A swipe-time replay** that walks every transaction in order and approves or declines it using only what came before, and only what a card network sees at authorization.
5. **An AI reviewer**: Claude running headless with four read-only lookups, asked to clear or escalate each flag and cite the transactions it relied on.

## The curve

One strictness setting turns the controls on and tightens them in order of precision. No step stops less misuse or declines less legitimate spend than the one before (the replay is built so it can't, and a test checks it):

| Legitimate spend declined (at most) | Planted misuse stopped |
|---:|---:|
| 0.50% | 18% |
| 1.0% | 24% |
| 2.0% | 47% |
| 7.4% (strictest) | 81% |

Two steps on the curve show the range. At strictness 0.30 the replay starts blocking a card's first purchase in a consumer category, such as a bar or a sporting-goods store; that step (in which the split and amount guards also tighten a notch) stopped 16% more of the planted misuse for 0.29% more legitimate spend declined. At 0.60 it starts blocking identical same-day charges; that step stopped 9% more for 1.1% more declined: at the swipe, a double charge looks exactly like buying several of the same item. Gift cards can't be stopped at the swipe at all, because the network sees the store's category, not the item. They show up only in the item description afterward.

## What the AI found

On the 10 largest real flags under each rule (40 in all), the reviewer called 15 likely fine, 16 worth a human look and 9 likely misuse. Of the 20 planted cases, which it wasn't told about, it called 5 likely misuse and sent 10 to a human, catching 15 in all. To check it wasn't simply flagging everything, I also gave it 20 controls: real purchases of $500 or more that no rule flagged, presented as random spot checks. It cleared 19 of them and wrongly flagged 1.

A typical clearance: a split purchase flag at STANDLEY SYSTEMS ($23,333). The reviewer's reasoning: "Standley Systems is a regular supplier for this card: 80 purchases, median $3,240.72, the card's second-largest merchant. The seven charges carry different invoice numbers (INV1801374, INV1801418, etc.) tied to contracts 16, 17, 19 and 20. That looks like routine per-contract invoice billing, not one need split to evade the $5,000 limit. No single known quantity is shown."

What it missed: a planted case (prohibited categories) at CS QUIKTRIP GC that it called likely fine: "The $10 QuikTrip "GC" funding charge is a prepaid or gift-card load, which §V.B.1.b and §V.B.1.d would prohibit. But it is routine for this agency: 114 purchases, $2,020 across many cards, median $10. This card also regularly buys Tango Card gift cards, which fits an employee-recognition exception. It is not cash or an ATM withdrawal, and the amount is tiny. Only a recognition-program record could confirm." Planted misuse is built from real purchases, so some of it looks legitimate on the evidence available.

Three things I fixed along the way are worth saying out loud. First, the reviewer noticed that planted transactions had out-of-sequence ids. I renumbered every transaction so planted rows look like their neighbors, and reran every case. Second, my first prompt never defined the verdicts, so the reviewer called a planted double charge "likely fine" (no misconduct) while still putting the money at issue. I defined the verdicts and reran. Third, that version hedged: it never once said "likely misuse", and with no clean purchases to test against, sending everything to review looked like perfect recall. So I added the controls, doubled the planted cases, required "needs review" to name the document that would settle it, and reran every case once, without tuning the prompt to the answer key.

## How I measured

| Kind of planted misuse | Caught after the fact (mean, range over seeds) | Stopped at the swipe at ≤1% legit declined |
|---|---:|---:|
| Double charges | 97% (96%–98%) | 2% |
| Personal purchases | 57% (55%–58%) | 0% |
| Prohibited categories | 100% (100%–100%) | 66% |
| Split purchases | 98% (98%–100%) | 30% |

The ≤1% setting was chosen on seed 0. Replayed with the same setting on all 5 planting seeds, it stopped 24.4% to 25.6% of planted incidents.

## Limitations

- Recall only measures the kinds of misuse I planted, and the rules were designed with those kinds in mind.
- "Legitimate spend declined" treats every real purchase as legitimate, so it is an upper bound on the cost.
- The AI's verdicts on real cases are its judgment; no one has checked them. 20 planted cases and 20 controls are small samples, and a control may itself be misuse no rule caught.
- One state. No card numbers, and purchases under statewide contracts (no limit) can't be told apart.
- Every flag is a purchase worth reviewing, not an accusation against anyone.
- 6,014 purchases fall in prohibited categories; gift cards are allowed for employee recognition, so many will be fine.

## Next

- Replay published state audit reports: would these controls have caught what auditors found, and how much earlier?
- Run the same pipeline on a second state.
- Publish the merchant-name cleanup as a labeled benchmark.
- Pit an agent that tries to evade the controls against the reviewer, round by round.
