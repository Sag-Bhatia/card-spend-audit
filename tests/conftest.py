from datetime import date, timedelta
from pathlib import Path

import polars as pl
import pytest

FIXTURES = Path(__file__).parent / "fixtures"

COLS = {
    "txn_id": pl.String,
    "date": pl.Date,
    "amount": pl.Float64,
    "merchant_raw": pl.String,
    "mcc": pl.String,
    "agency": pl.String,
    "card_key": pl.String,
    "description": pl.String,
    "merchant_norm": pl.String,
}


@pytest.fixture
def mk():
    """Build a small txns frame from (offset_days, amount, **overrides) tuples."""

    def make(rows):
        out = []
        for i, (day, amount, kw) in enumerate(rows):
            r = {
                "txn_id": f"t{i}",
                "date": date(2025, 9, 1) + timedelta(days=day),
                "amount": float(amount),
                "merchant_raw": "ACME SUPPLY",
                "mcc": "OFFICE SUPPLIES",
                "agency": "AGENCY A",
                "card_key": "card1",
                "description": "GENERAL PURCHASE",
                "merchant_norm": "ACME SUPPLY",
            }
            r.update(kw)
            out.append(r)
        return pl.DataFrame(out, schema=COLS)

    return make
