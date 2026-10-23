"""Export (spec §8): pipeline outputs -> web/public/data/*.json and REPORT.md.

Every number on the site and in REPORT.md comes from here. Nothing is typed by hand."""

import json
from datetime import date, timedelta
from typing import Any

import polars as pl

from spendaudit import OUT, ROOT, WEB_DATA
from spendaudit.investigate import (
    EXPERIMENTS,
    FIRST_PASS,
    LAST_PASS,
    MODEL,
    PER_RULE,
    load_cases,
    set_metrics,
)
from spendaudit.merchants import top_clusters
from spendaudit.rules import load_policy
from spendaudit.tools import WORLD
from spendaudit.writeup import tuning_log, write_writeup

RULE_LABELS = {
    "split": "Split purchase",
    "duplicate": "Possible double charge",
    "prohibited": "Prohibited category",
    "unusual": "Unusual for this card",
    "spot_check": "Random spot check",
}
TIMELINE_MAX = 160
TXNS_MAX = 60
VERDICTS = ("likely_misuse", "needs_review", "likely_ok", "error")


def _read(name: str) -> Any:
    return json.loads((OUT / name).read_text())


def _write(name: str, obj: Any) -> None:
    WEB_DATA.mkdir(parents=True, exist_ok=True)
    (WEB_DATA / name).write_text(json.dumps(obj, default=str, separators=(",", ":")))


def rules_summary(txns: pl.DataFrame, flags: pl.DataFrame) -> dict[str, Any]:
    gross = txns.filter(pl.col("amount") > 0)
    by_rule = (
        flags.group_by("rule")
        .agg(
            flags=pl.len(),
            dollars=pl.col("dollars_at_stake").sum().round(2),
            txns=pl.col("txn_ids").list.len().sum(),
        )
        .sort("dollars", descending=True)
    )
    spend = gross.group_by("agency").agg(
        spend=pl.col("amount").sum().round(2), cards=pl.col("card_key").n_unique()
    )
    fa = flags.group_by("agency").agg(
        flags=pl.len(), flagged=pl.col("dollars_at_stake").sum().round(2)
    )
    agencies = (
        spend.join(fa, on="agency", how="left")
        .fill_null(0)
        .with_columns(
            flags_per_million=pl.col("flags") / (pl.col("spend") / 1e6),
            flagged_share=pl.col("flagged") / pl.col("spend"),
        )
        .sort("spend", descending=True)
        .head(25)
    )
    return {
        "by_rule": [{**r, "label": RULE_LABELS[r["rule"]]} for r in by_rule.to_dicts()],
        "total_flags": flags.height,
        "flags_per_10k": flags.height / txns.height * 10_000,
        "flagged_txns": flags.explode("txn_ids")["txn_ids"].n_unique(),
        "agencies": agencies.to_dicts(),
    }


def case_payload(world: pl.DataFrame, cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cases for the inbox. Cards are renamed Card A, B, … — no card_key leaves this function."""
    alias: dict[str, str] = {}
    out = []
    for c in cases:
        alias.setdefault(c["card_key"], f"Card {chr(65 + len(alias) % 26)}{len(alias) // 26 or ''}")
        d = date.fromisoformat(c["txns"][0]["date"])
        tl = (
            world.filter(
                (pl.col("card_key") == c["card_key"])
                & pl.col("date").is_between(d - timedelta(days=30), d + timedelta(days=30))
            )
            .sort("date", "txn_id")
            .select("txn_id", "date", "amount", "merchant_norm")
            .with_columns(
                pl.col("date").cast(pl.String),
                flagged=pl.col("txn_id").is_in([t["txn_id"] for t in c["txns"]]),
            )
        )
        # Busy cards make hundreds of purchases a month: keep every flagged one and an even
        # sample of the rest so the chart stays readable and the file small.
        rest = tl.filter(~pl.col("flagged"))
        if rest.height > TIMELINE_MAX:
            rest = rest.gather_every(-(-rest.height // TIMELINE_MAX))
        tl = pl.concat([rest, tl.filter("flagged")]).sort("date", "txn_id")
        run = c.get("run") or {}
        res = run.get("result") or {"verdict": "pending"}
        out.append(
            {
                "case_id": c["case_id"],
                "rule": c["rule"],
                "rule_label": RULE_LABELS[c["rule"]],
                "card": alias[c["card_key"]],
                "agency": c["agency"],
                "merchant": c["merchant_norm"],
                "dollars_at_stake": c["dollars_at_stake"],
                "evidence": c["evidence"],
                "clause": c["clause"],
                "txns": c["txns"][:TXNS_MAX],
                "txn_count": len(c["txns"]),
                "timeline": tl.to_dicts(),
                "planted": c["truth"],
                "control": c["control"],
                "ai": res,
                "ai_meta": {
                    k: run.get(k) for k in ("cost_usd", "seconds", "attempts", "model", "usage")
                },
            }
        )
    return out


def ai_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    runs = [c["ai_meta"] for c in cases if c["ai"]["verdict"] != "pending"]
    real = [c for c in cases if not c["planted"] and not c["control"]]
    planted = [c for c in cases if c["planted"]]
    controls = [c for c in cases if c["control"]]

    def mix(cs: list[dict[str, Any]]) -> dict[str, int]:
        return {v: sum(c["ai"]["verdict"] == v for c in cs) for v in VERDICTS}

    def flagged(cs: list[dict[str, Any]]) -> int:
        return sum(c["ai"]["verdict"] in ("likely_misuse", "needs_review") for c in cs)

    tokens = sum(sum((r.get("usage") or {}).values()) for r in runs)
    cost = sum(r.get("cost_usd") or 0 for r in runs)
    return {
        "cases": len(cases),
        "investigated": len(runs),
        "real_cases": len(real),
        "planted_cases": len(planted),
        "control_cases": len(controls),
        "real_verdicts": mix(real),
        "planted_verdicts": mix(planted),
        "control_verdicts": mix(controls),
        "planted_flagged_by_ai": flagged(planted),
        "controls_flagged_by_ai": flagged(controls),
        "planted_by_type": {
            t: {
                "n": len(of_t := [c for c in planted if c["planted"] == t]),
                "caught": flagged(of_t),
                "misuse": mix(of_t)["likely_misuse"],
            }
            for t in sorted({c["planted"] for c in planted})
        },
        "cost_usd": round(cost, 2),
        "cost_per_case_usd": round(cost / len(runs), 3) if runs else None,
        "tokens": tokens,
        "seconds_mean": round(sum(r.get("seconds") or 0 for r in runs) / len(runs), 1)
        if runs
        else None,
        "model": f"{FIRST_PASS}, then {MODEL}, then {LAST_PASS} when unsure",
        # which model gave the final answer, e.g. {"haiku": 23, "sonnet": 3, "opus": 54}
        "settled_by": {
            m: sum(str(r.get("model") or "").split(", then ")[-1] == m for r in runs)
            for m in (FIRST_PASS, MODEL, LAST_PASS)
        },
        "per_rule": PER_RULE,
    }


def export() -> dict[str, Any]:
    txns = pl.read_parquet(ROOT / "data" / "txns.parquet")
    flags = pl.read_parquet(OUT / "flags.parquet")
    profile, recall, curve = _read("profile.json"), _read("recall.json"), _read("curve.json")
    loaded = load_cases(txns)  # builds out/world.parquet, which a fresh clone doesn't have yet
    cases = case_payload(pl.read_parquet(WORLD), loaded)
    rules = rules_summary(txns, flags)
    ai = ai_summary(cases)
    ai_sets = {"dev": set_metrics(loaded), "test": set_metrics(load_cases(txns, "test"))}
    experiments = json.loads(EXPERIMENTS.read_text()) if EXPERIMENTS.exists() else []
    policy = load_policy()
    h1 = curve["headline"]["0.01"]
    summary = {
        "generated": date.today().isoformat(),
        "source": profile["source"],
        "profile": {k: v for k, v in profile.items() if k != "null_rates"},
        "policy": {
            "limit": policy["single_purchase_limit"],
            "limit_clause": policy["limit_clause"],
            "split_window_days": policy["split_window_days"],
            "duplicate_window_days": policy["duplicate_window_days"],
            "anomaly_multiple": policy["anomaly_multiple"],
            "anomaly_min_history": policy["anomaly_min_history"],
            "sources": policy["sources"],
            "prohibited": [
                {"label": p["label"], "clause": p["clause"]} for p in policy["prohibited"]
            ],
        },
        "headline": {
            "rules_recall": recall["overall_mean"],
            "rules_recall_range": [recall["overall_min"], recall["overall_max"]],
            "replay_stopped": h1["planted_incidents_stopped"],
            "replay_stopped_range": h1["seed_range"],
            "replay_legit_declined": h1["legit_dollars_declined_pct"],
            "replay_budget": h1["max_legit"],
            "replay_s": h1["s"],
            "dollars_audited": profile["dollars_positive"],
            "txns_audited": profile["rows"],
            "ai_cost_usd": ai["cost_usd"],
            "ai_cases": ai["investigated"],
        },
        "replay_headlines": curve["headline"],
        "replay_seconds": curve["seconds"],
        "replay_rows": curve["rows"],
        "rules": {k: v for k, v in rules.items() if k != "agencies"},
        "ai": ai,
        "ai_sets": ai_sets,
        "ai_experiments": experiments,
        "ai_tuning": [
            {
                "label": r["label"],
                "dev_score": r["dev"]["score"] if "dev" in r else None,
                "test_score": r["test"]["score"] if "test" in r else None,
                "test_cost_per_case_usd": r["test"]["cost_per_case_usd"] if "test" in r else None,
                "kept": r["kept"],
            }
            for r in tuning_log(experiments)
        ],
    }
    _write("summary.json", summary)
    _write("curve.json", curve["points"])
    _write("recall.json", recall)
    _write("rules.json", rules)
    _write("cases.json", cases)
    merchants = {
        "raw_descriptors": txns["merchant_raw"].n_unique(),
        "merchants": txns["merchant_norm"].n_unique(),
        "top": top_clusters(txns).to_dicts(),
    }
    _write("merchants.json", merchants)
    write_report(summary, recall, curve, rules, cases)
    write_writeup(summary, recall, curve, cases, merchants)
    return summary


def _usd(x: float | None) -> str:
    return "n/a" if x is None else f"${x:.3f}"


def _pct(x: float | None, d: int = 1) -> str:
    return "n/a" if x is None else f"{x * 100:.{d}f}%"


def write_report(
    summary: dict[str, Any],
    recall: dict[str, Any],
    curve: dict[str, Any],
    rules: dict[str, Any],
    cases: list[dict[str, Any]],
) -> None:
    p, h, ai = summary["profile"], summary["headline"], summary["ai"]
    L = [
        "# REPORT.md — every number in Card Spend Audit",
        "",
        f"_Generated by `python -m spendaudit export` on {summary['generated']}. Do not edit by hand._",
        "",
        "## Data",
        f"- Source: {summary['source']}",
        f"- {p['rows']:,} transactions, {p['first_date']} to {p['last_date']} ({p['months']} months)",
        f"- Gross purchases ${p['dollars_positive']:,.2f}; net ${p['dollars']:,.2f}; {p['refunds']:,} refunds",
        f"- {p['agencies']} agencies, {p['cards']:,} cards (agency + surname + initial, hashed)",
        "",
        "## Rule flags on real data",
        "| Rule | Flags | Transactions | $ at stake |",
        "|---|---:|---:|---:|",
        *[
            f"| {r['label']} | {r['flags']:,} | {r['txns']:,} | ${r['dollars']:,.2f} |"
            for r in rules["by_rule"]
        ],
        f"| **All** | {rules['total_flags']:,} | {rules['flagged_txns']:,} distinct | |",
        "",
        f"Flag volume: {rules['flags_per_10k']:.1f} flags per 10,000 transactions. Precision on real data is unknown: "
        "a flag is a transaction worth reviewing, not a finding of misuse.",
        "",
        f"## Planted misuse: rule recall ({recall['n_per_type']} incidents per type × seeds {recall['seeds']})",
        "| Type | Recall (mean) | Min | Max | Incidents |",
        "|---|---:|---:|---:|---:|",
        *[
            f"| {r['type']} | {_pct(r['mean'])} | {_pct(r['min'])} | {_pct(r['max'])} | {r['incidents']:,} |"
            for r in recall["by_type"]
        ],
        f"| **all types** | {_pct(recall['overall_mean'])} | {_pct(recall['overall_min'])} | {_pct(recall['overall_max'])} | |",
        "",
        "Recall measures only the planted patterns, which the rules were designed around.",
        "",
        f"## Prevention replay ({curve['rows']:,} rows incl. seed-0 plants, {curve['seconds']} s)",
        "| Strictness | Legit $ declined | Legit txns declined | Planted incidents stopped | Planted $ blocked | Flagged real $ blocked |",
        "|---:|---:|---:|---:|---:|---:|",
        *[
            f"| {q['s']:.2f} | {_pct(q['legit_dollars_declined_pct'], 2)} | {_pct(q['legit_txns_declined_pct'], 2)} | "
            f"{_pct(q['planted_incidents_stopped'])} | {_pct(q['planted_dollars_blocked_pct'])} | {_pct(q['flagged_dollars_blocked_pct'])} |"
            for q in curve["points"]
        ],
        "",
        "Planted incidents stopped, by type, at each budget:",
        "",
        "| Legit $ budget | Strictness | Legit $ declined | Stopped (all) | "
        + " | ".join(sorted(curve["points"][0]["planted_incidents_stopped_by_type"]))
        + " |",
        "|---:|---:|---:|---:|"
        + "---:|" * len(curve["points"][0]["planted_incidents_stopped_by_type"]),
        *[
            f"| ≤{_pct(float(b), 1)} | {hh['s']:.2f} | {_pct(hh['legit_dollars_declined_pct'], 2)} | {_pct(hh['planted_incidents_stopped'])} | "
            + " | ".join(
                _pct(v) for _, v in sorted(hh["planted_incidents_stopped_by_type"].items())
            )
            + " |"
            for b, hh in curve["headline"].items()
        ],
        "",
        f"Headline (≤1% legit $ declined): {_pct(h['replay_stopped'])} of planted incidents stopped; across seeds 0–4 "
        f"{_pct(h['replay_stopped_range'][0])}–{_pct(h['replay_stopped_range'][1])}. Legit $ declined is an upper bound: "
        "every real transaction is treated as legitimate.",
        "",
        f"## AI investigator (headless Claude Code: {ai['model']})",
        "- Final answer given by: "
        + ", ".join(f"{m} {n}" for m, n in ai["settled_by"].items())
        + " (Haiku answers first; a needs_review, an error or confidence under 0.8 goes up a tier).",
        f"- Cases: {ai['cases']} ({ai['real_cases']} real top flags, {ai['planted_cases']} planted, {ai['control_cases']} controls; "
        f"planted and controls blind); investigated: {ai['investigated']}",
        "- Controls are real purchases of $500+ that no rule flagged, one per card, sent as random spot checks.",
        *[
            f"- {name} verdicts: " + ", ".join(f"{k} {v}" for k, v in ai[key].items())
            for name, key in (
                ("Real-case", "real_verdicts"),
                ("Planted", "planted_verdicts"),
                ("Control", "control_verdicts"),
            )
        ],
        f"- Planted cases rated likely_misuse or needs_review: {ai['planted_flagged_by_ai']} of {ai['planted_cases']} — "
        + ", ".join(f"{t} {v['caught']}/{v['n']}" for t, v in ai["planted_by_type"].items()),
        f"- Controls rated likely_misuse or needs_review (false alarms): {ai['controls_flagged_by_ai']} of {ai['control_cases']}",
        f"- Cost (API-equivalent; paid by the Claude plan): ${ai['cost_usd']:.2f} total, ${ai['cost_per_case_usd'] or 0:.3f} per case; "
        f"{ai['tokens']:,} tokens; {ai['seconds_mean']} s per case",
        "- Real-case verdicts are the model's judgment and are unverified.",
        "",
        "### Answer-key score: dev set vs held-out test set",
        "Dev = the planted cases and controls above (planting seed 0, controls from seed 1), used for "
        "tuning. Test = 20 planted cases from planting seed 1 and 20 controls from seed 2, used only "
        "to score changes that had already improved dev. Score = planted caught rate − controls "
        "false-alarm rate (caught = likely_misuse or needs_review).",
        "",
        "| Set | Planted caught | Called likely_misuse | Controls flagged | Errors | Score | $ per case | s per case |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        *[
            f"| {name} | {m['planted_caught']}/{m['planted']} | {m['planted_misuse']}/{m['planted']} | "
            f"{m['controls_flagged']}/{m['controls']} | {m['errors']} | {m['score']:+.2f} | "
            f"{_usd(m['cost_per_case_usd'])} | {m['seconds_per_case']} |"
            for name, m in summary["ai_sets"].items()
        ],
        "",
        "Confidence bands on dev (right = flagged a planted case or cleared a control): "
        + "; ".join(
            f"{b} {v['right']}/{v['n']}"
            for b, v in summary["ai_sets"]["dev"]["confidence_bands"].items()
        )
        + " (high ≥ 0.8, medium ≥ 0.6).",
        "",
        "### Tuning log (every run, from out/experiments.json)",
        "| # | Change | Set | Planted caught | Controls flagged | Errors | Score | $ per case |",
        "|---:|---|---|---:|---:|---:|---:|---:|",
        *[
            f"| {i + 1} | {e['label']} | {e['set']} | {e['planted_caught']}/{e['planted']} | "
            f"{e['controls_flagged']}/{e['controls']} | {e['errors']} | {e['score']:+.2f} | "
            f"{_usd(e['cost_per_case_usd'])} |"
            for i, e in enumerate(summary["ai_experiments"])
        ],
        "",
        "| Case | Rule | Agency | Merchant | $ at stake | Planted / control | AI verdict | Confidence |",
        "|---|---|---|---|---:|---|---|---:|",
        *[
            f"| {c['case_id']} | {c['rule_label']} | {c['agency']} | {c['merchant']} | ${c['dollars_at_stake']:,.2f} | "
            f"{c['planted'] or ('control' if c['control'] else '')} | {c['ai']['verdict']} | {c['ai'].get('confidence', '')} |"
            for c in cases
        ],
        "",
    ]
    (ROOT / "REPORT.md").write_text("\n".join(L) + "\n")
