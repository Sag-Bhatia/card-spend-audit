"""Prevention replay (spec §6): re-run history in order with swipe-time card controls.

Each transaction is approved or declined using only the policy and transactions that came
before it (earlier dates, or the same date with a smaller txn_id). Controls see only what a
card network sees at authorization: amount, merchant, merchant category — not item descriptions.

Every control's decline set only grows with strictness `s`, so the curve is monotonic. To keep
that guarantee, declined attempts still count toward later rolling sums (an issuer sees the
attempt either way)."""

from typing import Any

import numpy as np
import polars as pl

from spendaudit.rules import (
    card_history_features,
    exempt_expr,
    load_policy,
    multi_unit_expr,
    prohibited_expr,
)

GRID: list[float] = [round(float(x), 2) for x in np.linspace(0, 1, 21)]
TICK = 1_000_000  # order index: days * TICK + rank within the day


# At s=0 only prohibited categories are blocked; each guard switches on loose and tightens.
def split_window(s: float) -> int:
    return 1 + round(6 * s)


def split_multiple(s: float) -> float | None:
    """Rolling card+merchant total must exceed limit × this to decline (None = guard off)."""
    return None if s == 0 else 3 - 2 * s


CONSUMER_ON = 0.3
DUP_ON = 0.6  # last: at swipe time a double-post looks like buying several identical items


def dup_window(s: float) -> int | None:
    return None if s < DUP_ON else round(5 * (s - DUP_ON))


def anomaly_multiple(s: float) -> float | None:
    return None if s == 0 else 10 - 8 * s


def features(df: pl.DataFrame, policy: dict[str, Any] | None = None) -> pl.DataFrame:
    """Everything the controls need, computed once, backward-looking only."""
    policy = policy or load_policy()
    limit = float(policy["single_purchase_limit"])
    f = card_history_features(df, policy).sort("date", "txn_id")
    f = f.with_columns(
        order=(pl.col("date").cast(pl.Int64) * TICK + pl.int_range(pl.len()).over("date")),
        prohibited=prohibited_expr(policy, fields=("mcc",)),
        exempt=exempt_expr(policy),
        multi_unit=multi_unit_expr(policy),
    )
    split_cand = (
        (pl.col("amount") > 0)
        & (pl.col("amount") < limit)
        & ~pl.col("exempt")
        & ~pl.col("multi_unit")
    )
    f = f.with_columns(split_cand=split_cand)
    # Rolling card+merchant sums of split candidates for every window the grid uses.
    cand = f.filter("split_cand").select("txn_id", "order", "card_key", "merchant_norm", "amount")
    cand = cand.sort("card_key", "merchant_norm", "order")
    for w in sorted({split_window(s) for s in GRID}):
        r = cand.rolling(
            "order", period=f"{(w + 1) * TICK}i", group_by=["card_key", "merchant_norm"]
        ).agg(
            txn_id=pl.col("txn_id").last(), **{f"sum{w}": pl.col("amount").sum(), f"n{w}": pl.len()}
        )
        f = f.join(r.select("txn_id", f"sum{w}", f"n{w}"), on="txn_id", how="left")
    # Days since the previous identical charge (card, raw descriptor, amount), by order.
    keys = ["card_key", "merchant_raw", "amount"]
    f = f.sort("order").with_columns(
        dup_gap=pl.when(
            (pl.col("amount") >= float(policy["duplicate_min_amount"])) & ~pl.col("multi_unit")
        )
        .then((pl.col("date") - pl.col("date").shift(1).over(keys)).dt.total_days())
        .otherwise(None)
    )
    return f


def decide(f: pl.DataFrame, s: float, policy: dict[str, Any] | None = None) -> pl.Series:
    """Reason a txn is declined at strictness s ('' = approved). First matching control wins."""
    policy = policy or load_policy()
    limit = float(policy["single_purchase_limit"])
    hist = int(policy["anomaly_min_history"])
    w = split_window(s)
    sm = split_multiple(s)
    split = (
        pl.lit(False)
        if sm is None
        else pl.col("split_cand") & (pl.col(f"n{w}") >= 2) & (pl.col(f"sum{w}") > limit * sm)
    )
    dw = dup_window(s)
    dup = (
        pl.lit(False) if dw is None else pl.col("dup_gap").is_not_null() & (pl.col("dup_gap") <= dw)
    )
    am = anomaly_multiple(s)
    big = (
        pl.lit(False)
        if am is None
        else (pl.col("prior_n") >= hist)
        & ~pl.col("exempt")
        & (pl.col("amount") > pl.col("prior_max") * am)
    )
    consumer = (
        pl.lit(s >= CONSUMER_ON)
        & pl.col("is_consumer")
        & (pl.col("prior_same_mcc") == 0)
        & (pl.col("prior_n") >= hist)
    )
    reason = (
        pl.when(pl.col("amount") <= 0)
        .then(pl.lit(""))
        .when(pl.col("prohibited").is_not_null())
        .then(pl.lit("prohibited category"))
        .when(split)
        .then(pl.lit("split guard"))
        .when(dup)
        .then(pl.lit("duplicate guard"))
        .when(big)
        .then(pl.lit("unusual amount for card"))
        .when(consumer)
        .then(pl.lit("first consumer purchase on card"))
        .otherwise(pl.lit(""))
    )
    return f.select(reason.fill_null("").alias("reason"))["reason"]


def curve(
    f: pl.DataFrame,
    flagged_ids: set[str] | None = None,
    grid: list[float] = GRID,
    examples: int = 10,
) -> list[dict[str, Any]]:
    """One point per strictness: legit $ declined, planted $ blocked (overall and per type),
    after-the-fact-flagged real $ blocked, and example declines."""
    policy = load_policy()
    pos = f.filter(pl.col("amount") > 0)
    is_planted = (
        pl.col("planted_type").is_not_null() if "planted_type" in f.columns else pl.lit(False)
    )
    flagged = pl.col("txn_id").is_in(list(flagged_ids or set()))
    real_total = float(pos.filter(~is_planted)["amount"].sum())
    real_n = pos.filter(~is_planted).height
    flagged_total = float(pos.filter(~is_planted & flagged)["amount"].sum())
    points = []
    for s in grid:
        d = pos.with_columns(reason=decide(pos, s, policy)).with_columns(
            declined=pl.col("reason") != ""
        )
        real = d.filter(~is_planted)
        point: dict[str, Any] = {
            "s": s,
            "split_window_days": split_window(s),
            "split_multiple": split_multiple(s),
            "duplicate_window_days": dup_window(s),
            "anomaly_multiple": anomaly_multiple(s),
            "consumer_guard": s >= CONSUMER_ON,
            "legit_dollars_declined_pct": float(real.filter("declined")["amount"].sum())
            / real_total,
            "legit_txns_declined_pct": real.filter("declined").height / real_n,
            "flagged_dollars_blocked_pct": (
                float(real.filter(pl.col("declined") & flagged)["amount"].sum()) / flagged_total
                if flagged_total
                else None
            ),
            "by_reason": {
                r: float(v)
                for r, v in real.filter("declined")
                .group_by("reason")
                .agg(pl.col("amount").sum())
                .iter_rows()
            },
        }
        if "planted_type" in d.columns:
            pl_rows = d.filter(is_planted)
            tot = float(pl_rows["amount"].sum())
            point["planted_dollars_blocked_pct"] = (
                float(pl_rows.filter("declined")["amount"].sum()) / tot
            )
            inc = pl_rows.group_by("incident_id", "planted_type").agg(
                stopped=pl.col("declined").any()
            )
            by_type = (
                inc.group_by("planted_type").agg(pl.col("stopped").mean()).sort("planted_type")
            )
            point["planted_incidents_stopped_by_type"] = dict(by_type.iter_rows())
            point["planted_incidents_stopped"] = float(by_type["stopped"].mean())  # type: ignore[arg-type]
            point["planted_by_type"] = {
                t: float(b) / float(a)
                for t, a, b in pl_rows.group_by("planted_type")
                .agg(
                    a=pl.col("amount").sum(),
                    b=pl.col("amount").filter(pl.col("declined")).sum(),
                )
                .sort("planted_type")
                .iter_rows()
            }
        ex = real.filter("declined").sort("amount", descending=True).head(examples)
        point["examples"] = (
            ex.select("txn_id", "date", "amount", "merchant_norm", "mcc", "agency", "reason")
            .with_columns(pl.col("date").cast(pl.String))
            .to_dicts()
        )
        points.append(point)
    return points


def headline(points: list[dict[str, Any]], max_legit: float = 0.01) -> dict[str, Any]:
    """The strictest setting whose legit $ declined stays ≤ max_legit."""
    ok = [p for p in points if p["legit_dollars_declined_pct"] <= max_legit]
    best = max(ok, key=lambda p: p["s"]) if ok else points[0]
    return {
        "s": best["s"],
        "max_legit": max_legit,
        "legit_dollars_declined_pct": best["legit_dollars_declined_pct"],
        "planted_dollars_blocked_pct": best.get("planted_dollars_blocked_pct"),
        "planted_incidents_stopped": best.get("planted_incidents_stopped"),
        "planted_incidents_stopped_by_type": best.get("planted_incidents_stopped_by_type"),
        "planted_by_type": best.get("planted_by_type"),
    }
