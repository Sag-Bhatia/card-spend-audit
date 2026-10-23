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
    seen: set[str] = set()
    for p in pts:  # examples are new at their step, never repeats from an earlier one
        ids = {e["txn_id"] for e in p["examples"]}
        assert not ids & seen
        seen |= ids
    assert (
        any(p["past_plateau"] for p in pts)
        or pts[-1]["planted_incidents_stopped"] > pts[-2]["planted_incidents_stopped"]
    )
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


def _frame(rows: list[tuple[str, date, float]]) -> pl.DataFrame:
    n = len(rows)
    return pl.DataFrame(
        {
            "txn_id": [r[0] for r in rows],
            "date": [r[1] for r in rows],
            "post_date": [r[1] for r in rows],
            "amount": [r[2] for r in rows],
            "merchant_raw": ["GRAINGER"] * n,
            "mcc": ["INDUSTRIAL SUPPLIES NOT ESLEWHERE CLASSI"] * n,
            "agency": ["A"] * n,
            "card_key": ["c1"] * n,
            "description": ["GENERAL PURCHASE"] * n,
            "merchant_norm": ["GRAINGER"] * n,
        }
    )


def test_split_window_is_calendar_days() -> None:
    # At s=1 the window is 7 days: [d-7, d]. A purchase 7 days back counts, 8 days back does not.
    assert R.split_window(1.0) == 7
    inside = _frame([("T1", date(2025, 1, 1), 3000.0), ("T2", date(2025, 1, 8), 3000.0)])
    outside = _frame([("T1", date(2025, 1, 1), 3000.0), ("T2", date(2025, 1, 9), 3000.0)])
    assert list(R.decide(R.features(inside), 1.0)) == ["", "split guard"]
    assert list(R.decide(R.features(outside), 1.0)) == ["", ""]


def test_same_day_later_txns_do_not_count() -> None:
    # T1 and T2 share a day; T1 comes first by txn_id. Adding a later same-day purchase (T3)
    # must not change T1's or T2's decision.
    base = [("T1", date(2025, 1, 1), 3000.0), ("T2", date(2025, 1, 1), 1000.0)]
    a = R.decide(R.features(_frame(base)), 1.0).to_list()
    b = R.decide(R.features(_frame([*base, ("T3", date(2025, 1, 1), 4000.0)])), 1.0).to_list()
    assert a == ["", ""] and b[:2] == a and b[2] == "split guard"


def test_serve_serves_the_built_site(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import threading
    import urllib.request

    import spendaudit.__main__ as cli

    dist = tmp_path / "web" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<title>Card Spend Audit</title>")
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    import http.server

    servers: list[http.server.ThreadingHTTPServer] = []
    real = http.server.ThreadingHTTPServer

    class Capture(real):  # type: ignore[misc,valid-type]
        def __init__(self, *a, **k) -> None:  # type: ignore[no-untyped-def]
            super().__init__(*a, **k)
            servers.append(self)

    monkeypatch.setattr(http.server, "ThreadingHTTPServer", Capture)
    t = threading.Thread(target=cli.serve, kwargs={"port": 0}, daemon=True)
    t.start()
    while not servers:
        pass
    port = servers[0].server_address[1]
    body = urllib.request.urlopen(f"http://127.0.0.1:{port}/").read().decode()
    servers[0].shutdown()
    assert "Card Spend Audit" in body


def test_planting_does_not_depend_on_the_salt(real: pl.DataFrame) -> None:
    # A fresh clone hashes cardholders with its own salt, so card_key values differ. Relabelling
    # every card must give the same plants on the same cards.
    import hashlib

    relabel = {k: hashlib.sha256(k.encode()).hexdigest()[:12] for k in real["card_key"].unique()}
    other = real.with_columns(pl.col("card_key").replace_strict(relabel))
    a, la = P.plant(real, seed=1, n_per_type=10)
    b, lb = P.plant(other, seed=1, n_per_type=10)
    a = a.with_columns(pl.col("card_key").replace_strict(relabel))
    la = la.with_columns(pl.col("card_key").replace_strict(relabel))
    assert a.sort("txn_id").equals(b.sort("txn_id")) and la.equals(lb)
