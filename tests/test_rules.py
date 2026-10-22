from pathlib import Path

import polars as pl
import pytest

from spendaudit.rules import (
    FLAG_SCHEMA,
    duplicates,
    load_policy,
    prohibited,
    run_all,
    split_purchases,
    unusual_for_card,
)

SLICE = Path(__file__).parent / "fixtures" / "txns_slice.parquet"


@pytest.fixture(scope="module")
def policy():
    return load_policy()


# ---- split ----
def test_split_pair_same_day(mk, policy):
    f = split_purchases(mk([(0, 3000, {}), (0, 3000, {})]), policy)
    assert f.height == 1
    assert sorted(f["txn_ids"][0]) == ["t0", "t1"]
    assert f["rule"][0] == "split" and f["dollars_at_stake"][0] == 6000.0


def test_split_consecutive_days_flags(mk, policy):
    assert split_purchases(mk([(0, 3000, {}), (1, 3000, {})]), policy).height == 1


def test_split_two_days_apart_no_flag(mk, policy):
    assert split_purchases(mk([(0, 3000, {}), (2, 3000, {})]), policy).height == 0


def test_split_sum_exactly_limit_no_flag(mk, policy):
    assert split_purchases(mk([(0, 2500, {}), (0, 2500, {})]), policy).height == 0


def test_split_single_big_purchase_no_flag(mk, policy):
    assert split_purchases(mk([(0, 6000, {})]), policy).height == 0


@pytest.mark.parametrize(
    "kw",
    [
        {"mcc": "UTILITIES-ELEC/GAS/HEAT OIL/SANITARY/WTR"},
        {"merchant_norm": "WORKQUEST OKLAHOMA"},
        {"merchant_norm": "DELTA AIR LINES"},
    ],
)
def test_split_exempt_no_flag(mk, policy, kw):
    assert split_purchases(mk([(0, 3000, kw), (0, 3000, kw)]), policy).height == 0


def test_split_different_card_or_merchant_no_flag(mk, policy):
    other = [{"card_key": "card2"}, {"merchant_norm": "OTHER"}]
    df = mk([(0, 3000, {}), *[(0, 3000, o) for o in other]])
    assert split_purchases(df, policy).height == 0


def test_split_overlapping_windows_merge(mk, policy):
    f = split_purchases(mk([(0, 3000, {}), (1, 3000, {}), (2, 3000, {})]), policy)
    assert f.height == 1
    assert sorted(f["txn_ids"][0]) == ["t0", "t1", "t2"]


# ---- duplicates ----
def test_duplicate_pair_same_day(mk, policy):
    f = duplicates(mk([(0, 80, {}), (0, 80, {})]), policy)
    assert f.height == 1 and sorted(f["txn_ids"][0]) == ["t0", "t1"]
    assert f["dollars_at_stake"][0] == 80.0


def test_duplicate_three_identical_no_flag(mk, policy):
    assert duplicates(mk([(0, 80, {}), (0, 80, {}), (0, 80, {})]), policy).height == 0


def test_duplicate_pair_with_refund_no_flag(mk, policy):
    df = mk([(0, 80, {}), (0, 80, {}), (20, -80, {})])
    assert duplicates(df, policy).height == 0


def test_duplicate_pair_far_apart_no_flag(mk, policy):
    assert duplicates(mk([(0, 80, {}), (3, 80, {})]), policy).height == 0


def test_duplicate_pair_within_window_flags(mk, policy):
    assert duplicates(mk([(0, 80, {}), (2, 80, {})]), policy).height == 1


def test_duplicate_hotel_no_flag(mk, policy):
    kw = {"merchant_raw": "HOLIDAY INNS", "merchant_norm": "HOLIDAY INN", "mcc": "HOLIDAY INNS"}
    assert duplicates(mk([(0, 150, kw), (0, 150, kw)]), policy).height == 0


def test_duplicate_tiny_amount_no_flag(mk, policy):
    assert duplicates(mk([(0, 4.99, {}), (0, 4.99, {})]), policy).height == 0


# ---- prohibited ----
@pytest.mark.parametrize(
    ("kw", "clause_part"),
    [
        ({"mcc": "AUTOMATED FUEL DISPENSERS"}, "Motor Fuel"),
        ({"description": "Visa Gift Card EACH"}, "Gift"),
        ({"mcc": "POI FUNDING TRANSACTIONS EXCLUDING MONEYSEND"}, "Cash"),
    ],
)
def test_prohibited_flags(mk, policy, kw, clause_part):
    f = prohibited(mk([(0, 100, kw)]), policy)
    assert f.height == 1 and f["rule"][0] == "prohibited"
    assert clause_part in f["clause"][0]


@pytest.mark.parametrize(
    "kw",
    [
        {"mcc": "AUTOMATED FUEL DISPENSERS"},
        {"description": "Visa Gift Card EACH"},
        {"mcc": "POI FUNDING TRANSACTIONS EXCLUDING MONEYSEND"},
    ],
)
def test_prohibited_refund_not_flagged(mk, policy, kw):
    assert prohibited(mk([(0, -100, kw)]), policy).height == 0


def test_prohibited_ordinary_purchase_not_flagged(mk, policy):
    assert prohibited(mk([(0, 100, {})]), policy).height == 0


# ---- unusual_for_card ----
def _history(n, amount=100):
    return [(i, amount - (i % 3), {}) for i in range(n)]  # max stays <= 100


def test_unusual_big_purchase_flagged(mk, policy):
    f = unusual_for_card(mk([*_history(20), (30, 400, {})]), policy)
    assert f["txn_ids"].to_list() == [["t20"]]


def test_unusual_moderate_purchase_not_flagged(mk, policy):
    assert unusual_for_card(mk([*_history(20), (30, 250, {})]), policy).height == 0


def test_unusual_new_consumer_category_flagged(mk, policy):
    bar = {"mcc": "DRINKING PLACES (ALCOHOLIC BEV.)-BARS TA"}
    f = unusual_for_card(mk([*_history(20), (30, 20, bar)]), policy)
    assert f["txn_ids"].to_list() == [["t20"]]


def test_unusual_needs_history(mk, policy):
    bar = {"mcc": "DRINKING PLACES (ALCOHOLIC BEV.)-BARS TA"}
    assert unusual_for_card(mk([*_history(5), (30, 20, bar)]), policy).height == 0
    assert unusual_for_card(mk([*_history(5), (30, 400, {})]), policy).height == 0


def test_unusual_repeat_consumer_category_not_flagged(mk, policy):
    bar = {"mcc": "DRINKING PLACES (ALCOHOLIC BEV.)-BARS TA"}
    f = unusual_for_card(mk([*_history(20), (30, 20, bar), (31, 20, bar)]), policy)
    assert f["txn_ids"].to_list() == [["t20"]]


# ---- run_all on real slice ----
def test_run_all_on_slice(policy):
    df = pl.read_parquet(SLICE)
    flags = run_all(df, policy)
    assert flags.schema == FLAG_SCHEMA
    ids = set(df["txn_id"])
    flagged = {t for lst in flags["txn_ids"] for t in lst}
    assert flagged <= ids
    assert flags.height > 0
    assert set(flags["rule"]) <= {"split", "duplicate", "prohibited", "unusual"}
    assert all(len(lst) >= 1 for lst in flags["txn_ids"])
