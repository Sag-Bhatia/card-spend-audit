import polars as pl
import pytest

from spendaudit.merchants import add_merchant_norm, cluster, normalize


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        ("LOWES #00907", "LOWES"),
        ("AMAZON MKTPL PL8PX4N33", "AMAZON"),
        ("Amazon.com RC7JH1UW0", "AMAZON"),
        ("AMZN Mktp US*2K4L", "AMAZON"),
        ("FEDEX57680723", "FEDEX"),
        ("SOUTHWES    5267089063530", "SOUTHWEST AIRLINES"),
        ("SQ *BLUE BOTTLE", "BLUE BOTTLE"),
        ("SYSCO CORP", "SYSCO"),
        ("FASTENAL COMPANY 01OKALT", "FASTENAL"),
    ],
)
def test_normalize(raw, want):
    assert normalize(raw) == want


def test_southwest_medical_is_not_the_airline():
    assert normalize("IN  SOUTHWEST MEDICAL EQU") != "SOUTHWEST AIRLINES"


def _names(d):
    return pl.DataFrame({"name": list(d), "n": list(d.values())})


def test_cluster_merges_truncated_name():
    m = cluster(_names({"SOUTH CENTRAL INDUSTRIES": 10, "SOUTH CENTRAL INDUSTRIE": 3}))
    full = "SOUTH CENTRAL INDUSTRIES"
    assert m["SOUTH CENTRAL INDUSTRIE"] == m[full] == full


def test_cluster_keeps_distinct_prefix_names_apart():
    m = cluster(_names({"UNITED": 10, "UNITED RENTALS": 5}))
    assert m["UNITED RENTALS"] == "UNITED RENTALS"
    assert m["UNITED"] == "UNITED"


def test_add_merchant_norm_keeps_rows():
    raw = ["LOWES #1", "LOWES #1", "LOWES #22", "SQ *BLUE BOTTLE"]
    df = pl.DataFrame({"merchant_raw": raw, "amount": [1.0] * 4})
    out = add_merchant_norm(df)
    assert out.height == df.height
    assert "merchant_norm" in out.columns
    assert sorted(out["merchant_norm"].to_list()) == ["BLUE BOTTLE", "LOWES", "LOWES", "LOWES"]
