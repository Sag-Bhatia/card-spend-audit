"""Read-only lookups for the AI investigator (spec §7). Output is plain text, capped at 4 KB.

    python -m spendaudit.tools card-history CARD [--around YYYY-MM-DD] [--days N]
    python -m spendaudit.tools merchant "MERCHANT NAME"
    python -m spendaudit.tools policy [topic]
    python -m spendaudit.tools peer-spend "AGENCY" "MERCHANT NAME"

The data is the investigation world (`out/world.parquet`): real transactions plus the planted
ones, with no column that says which is which."""

import argparse
import sys
from datetime import date, timedelta

import polars as pl
import yaml

from spendaudit import OUT, POLICY

WORLD = OUT / "world.parquet"
CAP = 4000
COLS = ["date", "txn_id", "amount", "merchant_raw", "mcc", "description"]


def _num(x: object) -> float:
    return float(x) if isinstance(x, int | float) else 0.0


def _world() -> pl.DataFrame:
    return pl.read_parquet(WORLD)


def _table(df: pl.DataFrame) -> str:
    lines = []
    for r in df.select(COLS).iter_rows(named=True):
        desc = (r["description"] or "")[:40]
        lines.append(
            f"{r['date']} {r['txn_id']} ${r['amount']:>10,.2f}  {r['merchant_raw'][:25]:<25} "
            f"| {(r['mcc'] or '')[:32]} | {desc}"
        )
    return "\n".join(lines)


def card_history(df: pl.DataFrame, card: str, around: date | None, days: int) -> str:
    c = df.filter(pl.col("card_key") == card).sort("date", "txn_id")
    if c.is_empty():
        return f"No card {card}."
    pos = c.filter(pl.col("amount") > 0)
    first, last = str(c["date"].min()), str(c["date"].max())
    out = [
        f"Card {card} — agency {c['agency'][0]}",
        f"{c.height} transactions {first} to {last}; median purchase "
        f"${_num(pos['amount'].median()):,.2f}; largest ${_num(pos['amount'].max()):,.2f}",
        "Top merchants: "
        + ", ".join(
            f"{m} ({n})"
            for m, n in pos.group_by("merchant_norm")
            .len()
            .sort("len", descending=True)
            .head(8)
            .iter_rows()
        ),
        "Top categories: "
        + ", ".join(
            f"{m} ({n})"
            for m, n in pos.group_by("mcc").len().sort("len", descending=True).head(6).iter_rows()
        ),
    ]
    if around:
        win = c.filter(
            pl.col("date").is_between(around - timedelta(days=days), around + timedelta(days=days))
        )
        out.append(
            f"Transactions {around - timedelta(days=days)} to {around + timedelta(days=days)}:"
        )
        out.append(_table(win.head(60)))
    else:
        out.append("Most recent 30 transactions:")
        out.append(_table(c.tail(30)))
    return "\n".join(out)


def merchant(df: pl.DataFrame, name: str) -> str:
    m = df.filter((pl.col("merchant_norm") == name.upper()) & (pl.col("amount") > 0))
    if m.is_empty():
        return f"No merchant {name!r}. Use the merchant name exactly as shown in the case."
    out = [
        f"{name.upper()}: {m.height:,} purchases, ${_num(m['amount'].sum()):,.2f} total, "
        f"{m['card_key'].n_unique():,} cards, {m['agency'].n_unique()} agencies",
        f"Amounts: median ${_num(m['amount'].median()):,.2f}, "
        f"90th pct ${_num(m['amount'].quantile(0.9)):,.2f}, max ${_num(m['amount'].max()):,.2f}",
        "Categories: "
        + ", ".join(
            f"{c} ({n})"
            for c, n in m.group_by("mcc").len().sort("len", descending=True).head(4).iter_rows()
        ),
        "Top agencies by spend:",
    ]
    by_agency = (
        m.group_by("agency").agg(pl.col("amount").sum(), pl.len()).sort("amount", descending=True)
    )
    out += [f"  {a}: ${s:,.2f} ({n})" for a, s, n in by_agency.head(8).iter_rows()]
    return "\n".join(out)


def policy(topic: str | None) -> str:
    p = yaml.safe_load(POLICY.read_text())
    parts = {
        "limit": f"{p['limit_clause']}. Exempt from the limit: "
        + "; ".join(c["clause"] for c in p["limit_exempt_categories"])
        + ". Qualified State Use vendors are treated as statewide contracts.",
        "split": p["split_clause"]
        + ". OMES FAQ: 'Known quantity' and 'intent' are key; separate purchases not known at the "
        "time of the first are compliant.",
        "prohibited": "; ".join(f"{x['label']}: {x['clause']}" for x in p["prohibited"]),
        "personal": p["personal_use_clause"],
        "food": "§V.B.2: food and entertainment need agency director approval in advance; light "
        "refreshments for public meetings are allowed (Statewide Accounting Manual 8.34.4).",
    }
    if topic and topic.lower() in parts:
        return parts[topic.lower()]
    return "\n".join(f"[{k}] {v}" for k, v in parts.items())


def peer_spend(df: pl.DataFrame, agency: str, name: str) -> str:
    a = df.filter((pl.col("agency") == agency.upper()) & (pl.col("amount") > 0))
    if a.is_empty():
        return f"No agency {agency!r}."
    m = a.filter(pl.col("merchant_norm") == name.upper())
    return "\n".join(
        [
            f"{agency.upper()}: {a['card_key'].n_unique():,} cards, {a.height:,} purchases.",
            f"At {name.upper()}: {m['card_key'].n_unique()} of those cards, {m.height} purchases, "
            f"${_num(m['amount'].sum()):,.2f}"
            + (f", median ${_num(m['amount'].median()):,.2f}" if m.height else ""),
        ]
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="audit-tool")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ch = sub.add_parser("card-history")
    ch.add_argument("card")
    ch.add_argument("--around", type=date.fromisoformat)
    ch.add_argument("--days", type=int, default=30)
    sub.add_parser("merchant").add_argument("name")
    sub.add_parser("policy").add_argument("topic", nargs="?")
    ps = sub.add_parser("peer-spend")
    ps.add_argument("agency")
    ps.add_argument("name")
    a = ap.parse_args(argv)
    if a.cmd == "policy":
        text = policy(a.topic)
    else:
        df = _world()
        if a.cmd == "card-history":
            text = card_history(df, a.card, a.around, min(a.days, 90))
        elif a.cmd == "merchant":
            text = merchant(df, a.name)
        else:
            text = peer_spend(df, a.agency, a.name)
    sys.stdout.write(text[:CAP] + ("\n…(truncated)" if len(text) > CAP else "") + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
