"""Card Spend Audit: swipe-time card controls and an AI investigator on public P-card data."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
TXNS = DATA / "txns.parquet"
OUT = ROOT / "out"
WEB_DATA = ROOT / "web" / "public" / "data"
POLICY = ROOT / "policy.yaml"
