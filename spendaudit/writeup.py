"""WRITEUP.md (spec §10): the prose is fixed; every number is filled in from export output."""

from typing import Any

from spendaudit import ROOT
from spendaudit.replay import CONSUMER_ON, DUP_ON

TYPE = {
    "split": "split purchases",
    "duplicate": "double charges",
    "prohibited": "prohibited categories",
    "personal": "personal purchases",
}


def _p(x: float, d: int = 0) -> str:
    return f"{x * 100:.{d}f}%"


def _ps(x: float) -> str:
    return _p(x, 2 if x < 0.01 else 1 if x < 0.1 else 0)


def _step(points: list[dict[str, Any]], s_on: float) -> tuple[float, float]:
    """Change in (planted stopped, legit $ declined) when a guard switches on at s_on."""
    i = next(i for i, p in enumerate(points) if p["s"] >= s_on)
    a, b = points[i - 1], points[i]
    return (
        b["planted_incidents_stopped"] - a["planted_incidents_stopped"],
        b["legit_dollars_declined_pct"] - a["legit_dollars_declined_pct"],
    )


def write_writeup(
    summary: dict[str, Any],
    recall: dict[str, Any],
    curve: dict[str, Any],
    cases: list[dict[str, Any]],
    merchants: dict[str, Any],
) -> str:
    h, pr, ai = summary["headline"], summary["profile"], summary["ai"]
    h05, h1, h2 = (curve["headline"][k] for k in ("0.005", "0.01", "0.02"))
    by_type = {r["type"]: r for r in recall["by_type"]}
    rules = {r["rule"]: r for r in summary["rules"]["by_rule"]}
    top = curve["points"][-1]
    ok = [c for c in cases if not c["planted"] and c["ai"]["verdict"] == "likely_ok"]
    ok_example = max(ok, key=lambda c: c["ai"].get("confidence", 0)) if ok else None
    missed = [c for c in cases if c["planted"] and c["ai"]["verdict"] == "likely_ok"]
    gift = rules.get("prohibited")
    cons, dup = _step(curve["points"], CONSUMER_ON), _step(curve["points"], DUP_ON)

    lines = [
        "# If Oklahoma's state cards could say no at the register, what would they stop?",
        "",
        f"_Card Spend Audit. Numbers generated {summary['generated']} by `python -m spendaudit export`._",
        "",
        f"**Swipe-time card controls would have stopped {_p(h1['planted_incidents_stopped'])} of the misuse I planted "
        f"in two years of Oklahoma's real purchase-card data, while declining {_ps(h1['legit_dollars_declined_pct'])} "
        f"of legitimate spend. After-the-fact rules caught {_p(h['rules_recall'])}. An AI reviewer worked {ai['investigated']} "
        f"flagged cases for {'$'}{ai['cost_usd']:.2f} at API prices.**",
        "",
        "## Why",
        "",
        "Most public card programs find problems after the money is gone: a monthly reconciliation, an annual audit. "
        "Corporate card platforms like Ramp argue the opposite: put the policy on the card so the bad purchase never clears. "
        "I wanted to test that claim on real data, with the cost attached, because every control that stops misuse also "
        "stops some purchases people needed to make.",
        "",
        "## The data",
        "",
        f"Oklahoma publishes every state purchase-card transaction. I used {pr['months']} months of statements "
        f"({pr['first_month']} to {pr['last_month']}): {pr['rows']:,} transactions, {'$'}{pr['dollars_positive'] / 1e6:,.1f}M "
        f"of purchases, {pr['agencies']} agencies and {pr['cards']:,} cards. The policy is the state's own: a "
        f"{'$'}{summary['policy']['limit']:,} single-purchase limit set by statute (74 O.S. § 85.5a), a ban on splitting "
        "purchases to get under it, and banned categories including cash, gift cards and motor fuel. The files have no card "
        "numbers, so a card is an agency plus a cardholder's surname and initial, hashed on load. No names are kept.",
        "",
        "## What I built",
        "",
        f'1. **Merchant cleanup.** {merchants["raw_descriptors"]:,} raw card descriptors ("SQ  CORNER COPY", '
        f'"AMAZON MKTPL PL8PX4N33") collapse to {merchants["merchants"]:,} merchants.',
        "2. **Rule checks** for split purchases, double charges, prohibited categories, and purchases unusual for the card. "
        f"On the real data they raise {summary['rules']['total_flags']:,} flags, {summary['rules']['flags_per_10k']:.0f} per "
        "10,000 purchases.",
        f"3. **A planted answer key.** Real data has no labels, so for {len(recall['seeds'])} random seeds I planted "
        f"{recall['n_per_type']} incidents of each kind of misuse, using real cards, merchants and amounts.",
        "4. **A swipe-time replay** that walks every transaction in order and approves or declines it using only what came "
        "before, and only what a card network sees at authorization.",
        "5. **An AI reviewer**: Claude running headless with four read-only lookups, asked to clear or escalate each flag "
        "and cite the transactions it relied on.",
        "",
        "## The curve",
        "",
        "One strictness setting turns the controls on and tightens them in order of precision. No step stops less "
        "misuse or declines less legitimate spend than the one before (the replay is built so it can't, and a test checks it):",
        "",
        "| Legitimate spend declined (at most) | Planted misuse stopped |",
        "|---:|---:|",
        *[
            f"| {_ps(x['max_legit'])} | {_p(x['planted_incidents_stopped'])} |"
            for x in (h05, h1, h2)
        ],
        f"| {_ps(top['legit_dollars_declined_pct'])} (strictest) | {_p(top['planted_incidents_stopped'])} |",
        "",
        f"Two steps on the curve show the range. At strictness {CONSUMER_ON:.2f} the replay starts blocking a card's first "
        f"purchase in a consumer category, such as a bar or a sporting-goods store; that step (in which the split and amount "
        f"guards also tighten a notch) stopped {_p(cons[0])} more of the planted misuse for {_ps(cons[1])} more legitimate "
        f"spend declined. At {DUP_ON:.2f} it starts blocking identical same-day charges; that step stopped {_p(dup[0])} more "
        f"for {_ps(dup[1])} more declined: at the "
        "swipe, a double charge looks exactly like buying several of the same item. Gift cards can't be stopped at the swipe "
        "at all, because the "
        "network sees the store's category, not the item. They show up only in the item description afterward.",
        "",
        "## What the AI found",
        "",
        f"On the {ai['per_rule']} largest real flags under each rule ({ai['real_cases']} in all), the reviewer called {ai['real_verdicts']['likely_ok']} likely fine, "
        f"{ai['real_verdicts']['needs_review']} worth a human look and {ai['real_verdicts']['likely_misuse']} likely misuse. "
        f"It sent {ai['planted_flagged_by_ai']} of the {ai['planted_cases']} planted cases, which it wasn't told about, "
        "to review.",
        "",
    ]
    if ok_example:
        lines += [
            f"A typical clearance: a {ok_example['rule_label'].lower()} flag at {ok_example['merchant']} "
            f'({"$"}{ok_example["dollars_at_stake"]:,.0f}). The reviewer\'s reasoning: "{ok_example["ai"].get("explanation", "")}"',
            "",
        ]
    if missed:
        m = missed[0]
        lines += [
            f"What it missed: a planted case ({TYPE[m['planted']]}) at {m['merchant']} that it called likely fine: "
            f'"{m["ai"].get("explanation", "")}" Planted misuse is built from real purchases, so some of it looks '
            "legitimate on the evidence available.",
            "",
        ]
    lines += [
        "Two things I fixed along the way are worth saying out loud. First, the reviewer noticed that planted transactions "
        "had out-of-sequence ids. I renumbered every transaction so planted rows look like their neighbors, and reran "
        "every case. Second, my first prompt never defined the verdicts, so the reviewer called a planted double charge "
        '"likely fine" (no misconduct) while still putting the money at issue. I defined the verdicts once and reran.',
        "",
        "## How I measured",
        "",
        "| Kind of planted misuse | Caught after the fact (mean, range over seeds) | Stopped at the swipe at ≤1% legit declined |",
        "|---|---:|---:|",
        *[
            f"| {TYPE[t].capitalize()} | {_p(by_type[t]['mean'])} ({_p(by_type[t]['min'])}–{_p(by_type[t]['max'])}) | "
            f"{_p(h1['planted_incidents_stopped_by_type'][t])} |"
            for t in sorted(by_type)
        ],
        "",
        f"The ≤1% setting was chosen on seed 0. Replayed with the same setting on all {len(recall['seeds'])} planting seeds, "
        f"it stopped {_p(h1['seed_range'][0], 1)} to {_p(h1['seed_range'][1], 1)} of planted incidents.",
        "",
        "## Limitations",
        "",
        "- Recall only measures the kinds of misuse I planted, and the rules were designed with those kinds in mind.",
        '- "Legitimate spend declined" treats every real purchase as legitimate, so it is an upper bound on the cost.',
        f"- The AI's verdicts on real cases are its judgment; no one has checked them. {ai['planted_cases']} planted cases is a small sample.",
        "- One state. No card numbers, and purchases under statewide contracts (no limit) can't be told apart.",
        "- Every flag is a purchase worth reviewing, not an accusation against anyone.",
    ]
    if gift:
        lines.append(
            f"- {gift['flags']:,} purchases fall in prohibited categories; gift cards are allowed for employee recognition, "
            "so many will be fine."
        )
    lines += [
        "",
        "## Next",
        "",
        "- Replay published state audit reports: would these controls have caught what auditors found, and how much earlier?",
        "- Run the same pipeline on a second state.",
        "- Publish the merchant-name cleanup as a labeled benchmark.",
        "- Pit an agent that tries to evade the controls against the reviewer, round by round.",
        "",
    ]
    text = "\n".join(lines)
    (ROOT / "WRITEUP.md").write_text(text)
    return text
