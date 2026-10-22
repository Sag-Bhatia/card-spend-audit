"""After-the-fact rule checks (spec §4). Rules return flags and never read `planted_type`."""

from datetime import timedelta
from functools import cache
from pathlib import Path
from typing import Any

import polars as pl
import yaml

from spendaudit import POLICY

FLAG_SCHEMA: dict[str, Any] = {
    "rule": pl.String,
    "txn_ids": pl.List(pl.String),
    "card_key": pl.String,
    "agency": pl.String,
    "merchant_norm": pl.String,
    "dollars_at_stake": pl.Float64,
    "evidence": pl.String,
    "clause": pl.String,
}


@cache
def load_policy(path: Path = POLICY) -> dict[str, Any]:
    policy: dict[str, Any] = yaml.safe_load(path.read_text())
    return policy


def exempt_expr(policy: dict[str, Any]) -> pl.Expr:
    """No single-purchase limit (§IV.D): exempt categories and State Use contract vendors."""
    pattern = "|".join(c["pattern"] for c in policy["limit_exempt_categories"])
    merchant = pl.col("merchant_norm").fill_null("")
    return (
        pl.col("mcc").fill_null("").str.contains(pattern)
        | merchant.str.contains(policy["statewide_contract_merchants"])
        | merchant.str.contains(policy["not_purchases"])
    )


def multi_unit_expr(policy: dict[str, Any]) -> pl.Expr:
    """Categories where identical repeated charges are normal (fares, rooms, fees). Checks the
    merchant too: some airlines' categories are just their brand name ("DELTA")."""
    pattern = policy["multi_unit_categories"]
    return pl.col("mcc").fill_null("").str.contains(pattern) | pl.col("merchant_norm").fill_null(
        ""
    ).str.contains(pattern)


def prohibited_expr(
    policy: dict[str, Any], fields: tuple[str, ...] = ("mcc", "description")
) -> pl.Expr:
    """String id of the prohibited category a txn falls in, else null. `fields` limits which
    columns may be used (the swipe-time replay only sees `mcc`)."""
    expr: pl.Expr = pl.lit(None, dtype=pl.String)
    for p in reversed(policy["prohibited"]):
        if p["field"] in fields:
            hit = pl.col(p["field"]).fill_null("").str.to_uppercase().str.contains(p["pattern"])
            expr = pl.when(hit & (pl.col("amount") > 0)).then(pl.lit(p["id"])).otherwise(expr)
    return expr


def _flags(rows: list[dict[str, Any]]) -> pl.DataFrame:
    return pl.DataFrame(rows, schema=FLAG_SCHEMA)


def split_purchases(df: pl.DataFrame, policy: dict[str, Any]) -> pl.DataFrame:
    """≥2 purchases, each under the limit, same card + merchant within `split_window_days`,
    together over the limit. Overlapping windows on one card+merchant merge into one flag."""
    limit = float(policy["single_purchase_limit"])
    window = int(policy["split_window_days"])
    cand = (
        df.filter(
            (pl.col("amount") > 0)
            & (pl.col("amount") < limit)
            & ~exempt_expr(policy)
            & ~multi_unit_expr(policy)
        )
        .select("txn_id", "date", "amount", "card_key", "merchant_norm", "agency")
        .sort("card_key", "merchant_norm", "date", "txn_id")
        .with_row_index("idx")
    )
    agg = cand.rolling("date", period=f"{window + 1}d", group_by=["card_key", "merchant_norm"]).agg(
        win_sum=pl.col("amount").sum(), win_n=pl.len(), idx=pl.col("idx").last()
    )
    trig = (
        cand.join(agg.select("idx", "win_sum", "win_n"), on="idx")
        .filter((pl.col("win_sum") > limit) & (pl.col("win_n") >= 2))
        .select("card_key", "merchant_norm", "date")
    )
    groups = trig.select("card_key", "merchant_norm").unique()
    sub = cand.join(groups, on=["card_key", "merchant_norm"])
    trig_dates: dict[tuple[str, str], list[Any]] = {}
    for c, m, d in trig.iter_rows():
        trig_dates.setdefault((c, m), []).append(d)
    rows = []
    for (c, m), g in sub.group_by(["card_key", "merchant_norm"], maintain_order=True):
        assert isinstance(c, str) and isinstance(m, str)
        ends = sorted(set(trig_dates[(c, m)]))
        # union of trigger windows [end - window, end], split into connected runs
        spans: list[list[Any]] = []
        for e in ends:
            s = e - timedelta(days=window)
            if spans and s <= spans[-1][1]:
                spans[-1][1] = e
            else:
                spans.append([s, e])
        for s, e in spans:
            part = g.filter(pl.col("date").is_between(s, e))
            total = float(part["amount"].sum())
            rows.append(
                {
                    "rule": "split",
                    "txn_ids": part["txn_id"].to_list(),
                    "card_key": c,
                    "agency": part["agency"][0],
                    "merchant_norm": m,
                    "dollars_at_stake": round(total, 2),
                    "evidence": (
                        f"{part.height} purchases at {m} between {s:%Y-%m-%d} and {e:%Y-%m-%d}, "
                        f"each under ${limit:,.0f}, totalling ${total:,.2f}"
                    ),
                    "clause": policy["split_clause"],
                }
            )
    return _flags(rows)


def duplicates(df: pl.DataFrame, policy: dict[str, Any]) -> pl.DataFrame:
    """Exactly two identical charges (card, raw descriptor, amount) within
    `duplicate_window_days` — a double-post. Three or more look like a multi-unit purchase.
    Skips multi-unit categories and pairs reversed by a matching refund within 45 days."""
    window = int(policy["duplicate_window_days"])
    keys = ["card_key", "merchant_raw", "amount"]
    pos = (
        df.filter(
            (pl.col("amount") >= float(policy["duplicate_min_amount"])) & ~multi_unit_expr(policy)
        )
        .sort("date", "txn_id")
        .with_columns(gap=(pl.col("date") - pl.col("date").shift(1)).dt.total_days().over(keys))
        .with_columns(
            cl=(pl.col("gap").is_null() | (pl.col("gap") > window))
            .cast(pl.Int32)
            .cum_sum()
            .over(keys)
        )
    )
    pairs = (
        pos.group_by([*keys, "cl"])
        .agg(
            n=pl.len(),
            txn_ids=pl.col("txn_id"),
            first=pl.col("date").min(),
            second=pl.col("date").max(),
            agency=pl.col("agency").first(),
            merchant_norm=pl.col("merchant_norm").first(),
        )
        .filter(pl.col("n") == 2)
    )
    refunds = df.filter(pl.col("amount") < 0).select(
        "card_key", "merchant_norm", amount=-pl.col("amount"), refund_date=pl.col("date")
    )
    reversed_ = (
        pairs.join(refunds, on=["card_key", "merchant_norm", "amount"])
        .filter(
            (pl.col("refund_date") >= pl.col("first"))
            & ((pl.col("refund_date") - pl.col("second")).dt.total_days() <= 45)
        )
        .select(*keys, "cl")
        .unique()
    )
    pairs = pairs.join(reversed_, on=[*keys, "cl"], how="anti").sort("first", "card_key")
    rows = [
        {
            "rule": "duplicate",
            "txn_ids": r["txn_ids"],
            "card_key": r["card_key"],
            "agency": r["agency"],
            "merchant_norm": r["merchant_norm"],
            "dollars_at_stake": r["amount"],
            "evidence": (
                f"${r['amount']:,.2f} at {r['merchant_raw']} on {r['first']:%Y-%m-%d} and again "
                f"on {r['second']:%Y-%m-%d}, with no matching refund"
            ),
            "clause": "Possible double charge: a billing error to recover, not a policy breach",
        }
        for r in pairs.iter_rows(named=True)
    ]
    return _flags(rows)


def prohibited(df: pl.DataFrame, policy: dict[str, Any]) -> pl.DataFrame:
    """One flag per txn in a prohibited category (cash, gift cards, motor fuel)."""
    by_id = {p["id"]: p for p in policy["prohibited"]}
    hits = df.with_columns(cat=prohibited_expr(policy)).filter(pl.col("cat").is_not_null())
    rows = [
        {
            "rule": "prohibited",
            "txn_ids": [r["txn_id"]],
            "card_key": r["card_key"],
            "agency": r["agency"],
            "merchant_norm": r["merchant_norm"],
            "dollars_at_stake": r["amount"],
            "evidence": (
                f"{by_id[r['cat']]['label']}: ${r['amount']:,.2f} at {r['merchant_raw']} "
                f"({r['mcc']}) on {r['date']:%Y-%m-%d}"
            ),
            "clause": by_id[r["cat"]]["clause"],
        }
        for r in hits.iter_rows(named=True)
    ]
    return _flags(rows)


def card_history_features(df: pl.DataFrame, policy: dict[str, Any]) -> pl.DataFrame:
    """Per-txn features from the card's *earlier* purchases only: count, max amount, and whether
    this consumer-type category is new for the card. Used by the soft rule and the replay."""
    consumer = pl.col("mcc").fill_null("").str.contains(policy["consumer_categories"])
    return df.sort("date", "txn_id").with_columns(
        is_consumer=consumer,
        prior_n=(pl.col("amount") > 0).cast(pl.Int32).cum_sum().over("card_key")
        - (pl.col("amount") > 0).cast(pl.Int32),
        prior_max=pl.col("amount").clip(lower_bound=0).cum_max().shift(1).over("card_key"),
        prior_same_mcc=pl.int_range(pl.len()).over(["card_key", "mcc"]),
    )


def unusual_for_card(df: pl.DataFrame, policy: dict[str, Any]) -> pl.DataFrame:
    """Soft rule: far above the card's prior max, or a consumer category the card never used."""
    k = float(policy["anomaly_multiple"])
    hist = int(policy["anomaly_min_history"])
    f = card_history_features(df, policy)
    big = (pl.col("amount") > pl.col("prior_max") * k) & ~exempt_expr(policy)
    new_consumer = pl.col("is_consumer") & (pl.col("prior_same_mcc") == 0)
    hits = f.filter((pl.col("prior_n") >= hist) & (pl.col("amount") > 0) & (big | new_consumer))
    rows = []
    for r in hits.iter_rows(named=True):
        if r["amount"] > (r["prior_max"] or 0) * k and not r["is_consumer"]:
            ev = (
                f"${r['amount']:,.2f} at {r['merchant_raw']} is over {k:g}× this card's largest "
                f"earlier purchase (${r['prior_max']:,.2f} across {r['prior_n']} purchases)"
            )
        else:
            ev = (
                f"First-ever {r['mcc'].lower()} purchase on a card with {r['prior_n']} earlier "
                f"purchases: ${r['amount']:,.2f} at {r['merchant_raw']}"
            )
        rows.append(
            {
                "rule": "unusual",
                "txn_ids": [r["txn_id"]],
                "card_key": r["card_key"],
                "agency": r["agency"],
                "merchant_norm": r["merchant_norm"],
                "dollars_at_stake": r["amount"],
                "evidence": ev,
                "clause": policy["personal_use_clause"],
            }
        )
    return _flags(rows)


RULES = {
    "split": split_purchases,
    "duplicate": duplicates,
    "prohibited": prohibited,
    "unusual": unusual_for_card,
}


def run_all(df: pl.DataFrame, policy: dict[str, Any] | None = None) -> pl.DataFrame:
    policy = policy or load_policy()
    return pl.concat([fn(df, policy) for fn in RULES.values()])
