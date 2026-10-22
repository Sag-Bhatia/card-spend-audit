"""Planting and prevention replay: determinism, detectability, no look-ahead, monotonic curve."""

from datetime import date

import polars as pl
import pytest

from spendaudit import plant as P
from spendaudit import replay as R
from spendaudit.rules import load_policy, run_all

SLICE = "tests/fixtures/txns_slice.parquet"


@pytest.fixture(scope="module")
def real() -> pl.DataFrame:
    return pl.read_parquet(SLICE)


@pytest.fixture(scope="module")
def planted(real: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    return P.plant(real, seed=0, n_per_type=20)


def test_plant_is_deterministic(real: pl.DataFrame) -> None:
    a, la = P.plant(real, seed=3, n_per_type=10)
    b, lb = P.plant(real, seed=3, n_per_type=10)
    assert a.equals(b) and la.equals(lb)
    c, _ = P.plant(real, seed=4, n_per_type=10)
    assert not a.equals(c)


def test_plant_shapes(real: pl.DataFrame, planted: tuple[pl.DataFrame, pl.DataFrame]) -> None:
    df, labels = planted
    assert labels.group_by("type").len().sort("type")["len"].to_list() == [20, 20, 20, 20]
    new = df.filter(pl.col("planted_type").is_not_null())
    assert set(new["txn_id"]) == set(labels.explode("txn_ids")["txn_ids"])
    assert not set(new["txn_id"]) & set(real["txn_id"])  # ids never collide with real rows
    assert set(new["card_key"]) <= set(real["card_key"])  # real cards only
    assert (
        df.filter(pl.col("planted_type").is_null())
        .drop("planted_type", "incident_id")
        .sort("txn_id")
        .equals(real.sort("txn_id"))
    )
    limit = load_policy()["single_purchase_limit"]
    splits = new.filter(pl.col("planted_type") == "split")
    assert (splits["amount"] < limit).all()
    sums = splits.group_by("incident_id").agg(pl.col("amount").sum())["amount"]
    assert (sums > limit).all()


def test_every_type_detectable(planted: tuple[pl.DataFrame, pl.DataFrame]) -> None:
    df, labels = planted
    r = P.recall(run_all(df), labels)
    assert r.height == 4
    assert r.filter(pl.col("type") != "personal")["recall"].min() > 0.8
    assert r.filter(pl.col("type") == "personal")["recall"].item() > 0


def test_rules_never_read_planted_type(planted: tuple[pl.DataFrame, pl.DataFrame]) -> None:
    df, _ = planted
    a = run_all(df).sort("rule", "evidence")
    b = run_all(df.drop("planted_type", "incident_id")).sort("rule", "evidence")
    assert a.equals(b)


def _decisions(df: pl.DataFrame, s: float) -> dict[str, str]:
    f = R.features(df).filter(pl.col("amount") > 0)
    return dict(zip(f["txn_id"], R.decide(f, s), strict=True))


@pytest.mark.parametrize("s", [0.0, 0.3, 0.65, 1.0])
def test_replay_never_looks_ahead(planted: tuple[pl.DataFrame, pl.DataFrame], s: float) -> None:
    df, _ = planted
    cut = date(2025, 11, 1)
    full = _decisions(df, s)
    # Change the future: drop half of it, inflate the rest. Past decisions must not move.
    future = df.filter(pl.col("date") >= cut)
    altered = pl.concat(
        [
            df.filter(pl.col("date") < cut),
            future.filter(pl.int_range(pl.len()) % 2 == 0).with_columns(pl.col("amount") * 7),
        ]
    )
    part = _decisions(altered, s)
    past = df.filter((pl.col("date") < cut) & (pl.col("amount") > 0))["txn_id"]
    assert all(full[t] == part[t] for t in past)


def test_curve_is_monotonic(planted: tuple[pl.DataFrame, pl.DataFrame]) -> None:
    df, _ = planted
    f = R.features(df)
    pos = f.filter(pl.col("amount") > 0)
    prev: set[str] = set()
    for s in R.GRID:
        declined = set(pos.filter(R.decide(pos, s) != "")["txn_id"])
        assert prev <= declined, f"decline set shrank at s={s}"
        prev = declined
    pts = R.curve(f, set(), examples=2)
    keys = (
        "legit_dollars_declined_pct",
        "planted_dollars_blocked_pct",
        "planted_incidents_stopped",
    )
    for key in keys:
        vals = [p[key] for p in pts]
        assert vals == sorted(vals), key
        assert all(0 <= v <= 1 for v in vals)


def test_s0_blocks_only_prohibited(planted: tuple[pl.DataFrame, pl.DataFrame]) -> None:
    df, _ = planted
    f = R.features(df).filter(pl.col("amount") > 0)
    reasons = set(R.decide(f, 0.0)) - {""}
    assert reasons <= {"prohibited category"}


def test_split_guard_declines_crossing_part() -> None:
    policy = load_policy()
    rows = [
        ("T1", date(2025, 1, 2), 3000.0),
        ("T2", date(2025, 1, 2), 3000.0),  # crosses $5,000 → declined at high strictness
        ("T3", date(2025, 1, 20), 100.0),  # outside even the 7-day window
    ]
    df = pl.DataFrame(
        {
            "txn_id": [r[0] for r in rows],
            "date": [r[1] for r in rows],
            "post_date": [r[1] for r in rows],
            "amount": [r[2] for r in rows],
            "merchant_raw": ["GRAINGER"] * 3,
            "mcc": ["INDUSTRIAL SUPPLIES NOT ESLEWHERE CLASSI"] * 3,
            "agency": ["A"] * 3,
            "card_key": ["c1"] * 3,
            "description": ["GENERAL PURCHASE"] * 3,
            "merchant_norm": ["GRAINGER"] * 3,
        }
    )
    f = R.features(df, policy)
    assert list(R.decide(f, 1.0)) == ["", "split guard", ""]
    assert list(R.decide(f, 0.0)) == ["", "", ""]


def test_headline_picks_strictest_within_budget() -> None:
    pts = [
        {"s": 0.0, "legit_dollars_declined_pct": 0.001},
        {"s": 0.5, "legit_dollars_declined_pct": 0.009},
        {"s": 1.0, "legit_dollars_declined_pct": 0.03},
    ]
    assert R.headline(pts, 0.01)["s"] == 0.5
