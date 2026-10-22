"""Download Oklahoma's public P-card files and load them into the common schema (spec §2).

Cardholder names are hashed into `card_key` here and never leave this module.
"""

import hashlib
import secrets
import time
from pathlib import Path

import httpx
import polars as pl

from spendaudit import DATA, RAW

CKAN = "https://data.ok.gov/api/3/action/package_show"
# Fiscal years 2025 and 2026: July 2024 through June 2026.
DATASETS = ["purchase-card-pcard-fiscal-year-2025", "purchase-card-pcard-fiscal-year-2026"]
SOURCE_NAME = "State of Oklahoma Purchase Card (PCard), data.ok.gov"

SCHEMA = {
    "txn_id": pl.String,
    "date": pl.Date,
    "post_date": pl.Date,
    "amount": pl.Float64,
    "merchant_raw": pl.String,
    "mcc": pl.String,
    "agency": pl.String,
    "card_key": pl.String,
    "description": pl.String,
}


def download(raw_dir: Path = RAW) -> list[Path]:
    """Fetch every CSV resource of the configured datasets once (≤1 req/s); return local paths."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    with httpx.Client(timeout=180, follow_redirects=True) as client:
        n = 0
        for ds in DATASETS:
            resources = client.get(CKAN, params={"id": ds}).raise_for_status().json()["result"]
            for res in resources["resources"]:
                if (res.get("format") or "").upper() != "CSV":
                    continue
                n += 1
                path = raw_dir / f"ok_{n:02d}_{res['url'].rsplit('/', 1)[-1]}"
                if not path.exists() or path.stat().st_size == 0:
                    time.sleep(1)
                    path.write_bytes(client.get(res["url"]).raise_for_status().content)
                paths.append(path)
    return paths


def _salt(data_dir: Path = DATA) -> str:
    path = data_dir / "salt"
    if not path.exists():
        data_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(secrets.token_hex(16))
    return path.read_text().strip()


def card_key(salt: str, agency_nbr: str, last: str, first: str) -> str:
    # shortcut: the files have no card number, so two same-surname/same-initial cardholders in one
    # agency share a key; upgrade if the state ever publishes a card or employee id.
    raw = f"{salt}|{agency_nbr.strip()}|{last.strip().upper()}|{first.strip().upper()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def parse_amount(col: pl.Expr) -> pl.Expr:
    """'1,234.50' -> 1234.5, ' $(121.52)' -> -121.52."""
    s = col.str.strip_chars().str.replace_all(r"[\s$,]", "")
    neg = s.str.starts_with("(") & s.str.ends_with(")")
    num = s.str.strip_chars("()").cast(pl.Float64, strict=False)
    return pl.when(neg).then(-num).otherwise(num)


def read_file(path: Path, salt: str) -> pl.DataFrame:
    """One raw monthly CSV -> common schema. The month is read from the rows, not the filename
    (several files on the portal are misnamed)."""
    df = pl.read_csv(path, infer_schema=False, encoding="utf8-lossy")
    df = df.rename({c: c.strip().lstrip("﻿") for c in df.columns})
    keys = [
        card_key(salt, a, ln, fi)
        for a, ln, fi in zip(
            df["AGENCYNBR"].fill_null(""),
            df["LAST_NAME"].fill_null(""),
            df["FIRST_INITIAL"].fill_null(""),
            strict=True,
        )
    ]
    month = f"{df['CALENDAR_YEAR'][0]}{int(df['CALENDAR_MONTH'][0]):02d}"
    out = df.select(
        pl.format(
            "T{}{}", pl.lit(month), pl.int_range(pl.len()).cast(pl.String).str.zfill(6)
        ).alias("txn_id"),
        pl.col("TRANSACTION_DATE")
        .str.strip_chars()
        .str.to_date("%d-%b-%y", strict=False)
        .alias("date"),
        pl.col("POST_DATE")
        .str.strip_chars()
        .str.to_date("%d-%b-%y", strict=False)
        .alias("post_date"),
        parse_amount(pl.col("AMOUNT")).alias("amount"),
        pl.col("MERCHANT").str.strip_chars().alias("merchant_raw"),
        pl.col("MCC_DESCRIPTION").str.strip_chars().alias("mcc"),
        pl.col("AGENCYNAME").str.strip_chars().alias("agency"),
        pl.Series("card_key", keys),
        pl.col("ITEM_DESCR").str.strip_chars().alias("description"),
    )
    return out.cast(SCHEMA)  # type: ignore[arg-type]


def load(paths: list[Path], salt: str | None = None) -> pl.DataFrame:
    """All files -> one frame, unfiltered (the gate counts unparseable rows; `build` drops them).
    If two files hold the same month, the later one wins."""
    salt = salt if salt is not None else _salt()
    frames: dict[str, pl.DataFrame] = {}
    for p in sorted(paths):
        df = read_file(p, salt)
        frames[df["txn_id"][0][1:7]] = df
    return pl.concat(frames[m] for m in sorted(frames)).sort("date", "txn_id")


def load_all(raw_dir: Path = RAW) -> pl.DataFrame:
    """Download (once) and load every configured file."""
    return load(sorted(raw_dir.glob("ok_*.csv")) or download(raw_dir))
