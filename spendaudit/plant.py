"""Planted misuse (spec §5): inject labeled fake incidents into a copy of the real data, then
measure how many each rule finds. Planted rows look like real rows — same columns, real cards,
real merchants, amounts from the real distribution — and are told apart only by `planted_type`,
which no rule and no investigator prompt ever reads."""

import math
from datetime import date, timedelta
from typing import Any

import numpy as np
import polars as pl

from spendaudit.rules import exempt_expr, load_policy, multi_unit_expr, prohibited_expr, run_all

TYPES = ("split", "duplicate", "prohibited", "personal")
PLANT_ROW_BASE = 900_000  # real files have < 100k rows a month, so these ids never collide


def _pick(rng: np.random.Generator, frame: pl.DataFrame) -> dict[str, Any]:
    return frame.row(int(rng.integers(frame.height)), named=True)


def plant(
    df: pl.DataFrame,
    seed: int,
    n_per_type: int = 200,
    policy: dict[str, Any] | None = None,
    min_card_txns: int = 40,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Returns (df + planted rows with `planted_type`/`incident_id` columns, labels).

    labels: incident_id, type, txn_ids, card_key, dollars."""
    policy = policy or load_policy()
    rng = np.random.default_rng(seed)
    limit = float(policy["single_purchase_limit"])
    first, last = df["date"].min(), df["date"].max()
    assert isinstance(first, date) and isinstance(last, date)
    # Plants land after the first 60 days so cards already have a history to compare against.
    start = first + timedelta(days=60)
    span = (last - start).days

    pos = df.filter(pl.col("amount") > 0)
    card_n = pos.group_by("card_key").agg(n=pl.len(), agency=pl.col("agency").first())
    # Sorted so sampling by row index is reproducible (group_by/join order is not).
    active = card_n.filter(pl.col("n") >= min_card_txns).sort("card_key")
    # Ordinary buying: no exempt, multi-unit, prohibited or consumer categories.
    consumer = pl.col("mcc").fill_null("").str.contains(policy["consumer_categories"])
    ordinary = (
        pos.filter(
            prohibited_expr(policy).is_null()
            & ~exempt_expr(policy)
            & ~multi_unit_expr(policy)
            & ~consumer
            & (pl.col("amount") >= 25)
            & (pl.col("amount") < limit)
        )
        .join(active.select("card_key"), on="card_key")
        .sort("txn_id")
    )

    by_cat: dict[str, pl.DataFrame] = {}
    for p in policy["prohibited"]:
        hit = pl.col(p["field"]).fill_null("").str.to_uppercase().str.contains(p["pattern"])
        rows_ = pos.filter(hit & (pl.col("amount") < limit)).sort("txn_id")
        if rows_.height:  # a small slice may lack a category; plant from the ones present
            by_cat[p["id"]] = rows_
    consumer_rows = pos.filter(consumer & (pl.col("amount") < limit)).sort("txn_id")
    if not (active.height and ordinary.height and by_cat and consumer_rows.height):
        raise ValueError("not enough history to plant every misuse type")
    used_mcc = pos.select("card_key", "mcc").unique()

    rows: list[dict[str, Any]] = []
    labels: list[dict[str, Any]] = []
    counter = 0

    def add(
        template: dict[str, Any],
        d: date,
        amount: float,
        card: str,
        agency: str,
        kind: str,
        incident: str,
        **over: Any,
    ) -> str:
        nonlocal counter
        counter += 1
        tid = f"T{d:%Y%m}{PLANT_ROW_BASE + counter:06d}"
        rows.append(
            {
                **{k: template[k] for k in df.columns if k in template},
                "txn_id": tid,
                "date": d,
                "post_date": d + timedelta(days=int(rng.integers(1, 4))),
                "amount": round(amount, 2),
                "card_key": card,
                "agency": agency,
                **over,
                "planted_type": kind,
                "incident_id": incident,
            }
        )
        return tid

    for kind in TYPES:
        for i in range(n_per_type):
            inc = f"{kind}-{seed}-{i:04d}"
            d0 = start + timedelta(days=int(rng.integers(span - 5)))
            if kind == "split":
                t = _pick(rng, ordinary)
                total = limit * float(rng.uniform(1.2, 3.0))
                k = int(rng.integers(max(2, math.ceil(total / (0.95 * limit))), 5))
                while True:
                    parts = rng.dirichlet(np.full(k, 4.0)) * total
                    if parts.max() < limit and parts.min() >= 50:
                        break
                spread = int(rng.integers(0, 3))  # parts over 0–2 days
                ids = [
                    add(
                        t,
                        d0 + timedelta(days=int(rng.integers(spread + 1))),
                        float(a),
                        t["card_key"],
                        t["agency"],
                        kind,
                        inc,
                    )
                    for a in parts
                ]
                dollars = float(sum(round(float(a), 2) for a in parts))
            elif kind == "duplicate":
                t = _pick(rng, ordinary)
                d = t["date"] + timedelta(days=int(rng.integers(0, 3)))
                ids = [add(t, d, t["amount"], t["card_key"], t["agency"], kind, inc)]
                dollars = t["amount"]
            elif kind == "prohibited":
                cat = list(by_cat)[i % len(by_cat)]
                t = _pick(rng, by_cat[cat])
                c = _pick(rng, active)
                ids = [add(t, d0, t["amount"], c["card_key"], c["agency"], kind, inc)]
                dollars = t["amount"]
            else:  # personal: a consumer category this card has never used
                t = _pick(rng, consumer_rows)
                while True:
                    c = _pick(rng, active)
                    seen = used_mcc.filter(
                        (pl.col("card_key") == c["card_key"]) & (pl.col("mcc") == t["mcc"])
                    )
                    if seen.is_empty():
                        break
                ids = [add(t, d0, t["amount"], c["card_key"], c["agency"], kind, inc)]
                dollars = t["amount"]
            labels.append(
                {
                    "incident_id": inc,
                    "type": kind,
                    "txn_ids": ids,
                    "card_key": rows[-1]["card_key"],
                    "dollars": round(dollars, 2),
                }
            )

    base = df.with_columns(
        planted_type=pl.lit(None, dtype=pl.String), incident_id=pl.lit(None, dtype=pl.String)
    )
    planted = pl.DataFrame(rows).select(base.columns).cast(dict(base.schema))  # type: ignore[arg-type]
    out = pl.concat([base, planted]).sort("date", "txn_id")
    return out, pl.DataFrame(labels)


def recall(flags: pl.DataFrame, labels: pl.DataFrame) -> pl.DataFrame:
    """Per planted type: share of incidents with ≥1 txn in any flag."""
    flagged = flags.select("rule", txn_id=pl.col("txn_ids")).explode("txn_id").unique("txn_id")
    hit = (
        labels.explode("txn_ids")
        .join(flagged, left_on="txn_ids", right_on="txn_id", how="left")
        .group_by("incident_id", "type")
        .agg(caught=pl.col("rule").is_not_null().any(), by=pl.col("rule").drop_nulls().first())
    )
    return (
        hit.group_by("type")
        .agg(incidents=pl.len(), caught=pl.col("caught").sum())
        .with_columns(recall=pl.col("caught") / pl.col("incidents"))
        .sort("type")
    )


def measure(df: pl.DataFrame, seeds: range = range(5), n_per_type: int = 200) -> dict[str, Any]:
    """Recall per type across seeds (mean, min, max) and real flag volume per 10k txns."""
    policy = load_policy()
    per_seed = []
    for s in seeds:
        planted, labels = plant(df, s, n_per_type, policy)
        r = recall(run_all(planted, policy), labels).with_columns(seed=pl.lit(s))
        per_seed.append(r)
    allr = pl.concat(per_seed)
    summary = (
        allr.group_by("type")
        .agg(
            mean=pl.col("recall").mean(),
            min=pl.col("recall").min(),
            max=pl.col("recall").max(),
            incidents=pl.col("incidents").sum(),
        )
        .sort("type")
    )
    overall = allr.group_by("seed").agg(r=pl.col("caught").sum() / pl.col("incidents").sum())
    return {
        "by_type": summary.to_dicts(),
        "overall_mean": float(overall["r"].mean()),  # type: ignore[arg-type]
        "overall_min": float(overall["r"].min()),  # type: ignore[arg-type]
        "overall_max": float(overall["r"].max()),  # type: ignore[arg-type]
        "seeds": list(seeds),
        "n_per_type": n_per_type,
    }
