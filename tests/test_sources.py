from pathlib import Path

import polars as pl

from spendaudit.sources import SCHEMA, card_key, load, parse_amount, read_file

RAW = Path(__file__).parent / "fixtures" / "raw_month.csv"


def _parse(values):
    df = pl.DataFrame({"a": values}, schema={"a": pl.String})
    return df.select(parse_amount(pl.col("a")))["a"].to_list()


def test_parse_amount():
    got = _parse(["34.930000000000000000", " $(121.52) ", " 1,250.00 ", ""])
    assert got == [34.93, -121.52, 1250.0, None]


def test_read_file_schema_ids_dates():
    df = read_file(RAW, "x")
    assert df.schema == SCHEMA
    assert df.columns == list(SCHEMA)
    assert df["txn_id"].to_list() == [f"T2025090{i:05d}" for i in range(5)]
    assert df["txn_id"][0] == "T202509000000"
    assert df["date"].null_count() == 0
    assert df["date"][1].isoformat() == "2025-09-02"  # single-digit day parses
    assert df["amount"].to_list() == [34.93, -121.52, 1250.0, 145.0, None]


def test_card_key_groups_by_agency_and_name_case():
    df = read_file(RAW, "x")
    k = df["card_key"].to_list()
    assert k[0] == k[1]  # Doe,J and DOE,J in the same agency
    assert k[3] != k[0]  # same name, other agency
    assert len(set(k)) == 4


def test_names_never_leave_sources():
    df = read_file(RAW, "x")
    for col in df.columns:
        if df[col].dtype == pl.String:
            joined = " ".join(df[col].drop_nulls().to_list())
            assert "Doe" not in joined and "Roe" not in joined


def test_card_key_salt():
    assert card_key("s", "01000", "Doe", "J") == card_key("s", " 01000", "DOE ", "j")
    assert card_key("s", "01000", "Doe", "J") != card_key("t", "01000", "Doe", "J")
    assert read_file(RAW, "x")["card_key"].to_list() == read_file(RAW, "x")["card_key"].to_list()
    assert read_file(RAW, "x")["card_key"][0] != read_file(RAW, "y")["card_key"][0]


def test_load_with_salt():
    df = load([RAW], salt="x")
    assert df.height == 5
    assert df.schema == SCHEMA
    assert df["date"].is_sorted()
