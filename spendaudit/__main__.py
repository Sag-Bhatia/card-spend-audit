"""CLI: uv run python -m spendaudit {gate,build,rules,plant,replay,investigate,export,all}."""

import argparse
import json
import time
from typing import Any

import polars as pl

from spendaudit import OUT, ROOT, TXNS


def build() -> pl.DataFrame:
    from spendaudit import gate, merchants, sources

    df = sources.load_all()
    prof = gate.profile(df)
    gate.write_data_md(prof, sources.SOURCE_NAME)
    _dump("profile.json", {**prof, "source": sources.SOURCE_NAME})
    print(
        f"gate: {'GO' if prof['go'] else 'NO-GO'} — {prof['rows']:,} txns, ${prof['dollars']:,.0f}"
    )
    if not prof["go"]:
        print("  failed checks:", [k for k, v in prof["checks"].items() if not v])
    df = df.filter(pl.col("amount").is_not_null() & pl.col("date").is_not_null())
    df = merchants.add_merchant_norm(df)
    TXNS.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(TXNS)
    print(
        f"build: {df['merchant_raw'].n_unique():,} raw descriptors -> "
        f"{df['merchant_norm'].n_unique():,} merchants"
    )
    return df


def txns() -> pl.DataFrame:
    return pl.read_parquet(TXNS) if TXNS.exists() else build()


def rules() -> pl.DataFrame:
    from spendaudit import rules as r

    flags = r.run_all(txns())
    OUT.mkdir(exist_ok=True)
    flags.write_parquet(OUT / "flags.parquet")
    print(flags.group_by("rule").agg(n=pl.len(), dollars=pl.col("dollars_at_stake").sum()))
    return flags


def _dump(name: str, obj: Any) -> None:
    OUT.mkdir(exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, indent=1, default=str))


def plant() -> dict[str, Any]:
    from spendaudit import plant as p

    result = p.measure(txns())
    _dump("recall.json", result)
    for r in result["by_type"]:
        print(f"  {r['type']:<10} recall {r['mean']:.1%} (seeds {r['min']:.1%}–{r['max']:.1%})")
    return result


def replay() -> dict[str, Any]:
    from spendaudit import plant as p
    from spendaudit import replay as r

    df = txns()
    flags = pl.read_parquet(OUT / "flags.parquet") if (OUT / "flags.parquet").exists() else rules()
    flagged = set(flags.explode("txn_ids")["txn_ids"].to_list())
    t0 = time.time()
    planted, labels = p.plant(df, 0)
    points = r.curve(r.features(planted), flagged)
    seconds = time.time() - t0
    heads = {str(m): r.headline(points, m) for m in (0.005, 0.01, 0.02)}
    # Headline stability: the same setting replayed on the other planting seeds.
    s1 = heads["0.01"]["s"]
    other = []
    for seed in range(1, 5):
        pl_df, _ = p.plant(df, seed)
        pt = r.curve(r.features(pl_df), flagged, grid=[s1], examples=0)[0]
        other.append(pt["planted_incidents_stopped"])
    heads["0.01"]["seed_range"] = [
        min(other + [heads["0.01"]["planted_incidents_stopped"]]),
        max(other + [heads["0.01"]["planted_incidents_stopped"]]),
    ]
    result = {
        "points": points,
        "headline": heads,
        "seconds": round(seconds, 1),
        "rows": planted.height,
        "seed": 0,
    }
    _dump("curve.json", result)
    h = heads["0.01"]
    print(
        f"  at ≤1% legit $ declined (s={h['s']}): {h['planted_incidents_stopped']:.1%} of planted "
        f"incidents stopped (seeds {h['seed_range'][0]:.1%}–{h['seed_range'][1]:.1%})"
    )
    return result


def investigate(set_name: str = "dev", labeled: bool = False, label: str | None = None) -> None:
    from spendaudit import investigate as inv

    df = txns()
    inv.run(df, set_name=set_name, labeled_only=labeled)
    m = inv.set_metrics(inv.load_cases(df, set_name))
    print(
        f"  {set_name}: planted caught {m['planted_caught']}/{m['planted']}, controls flagged "
        f"{m['controls_flagged']}/{m['controls']}, errors {m['errors']}, score {m['score']:+.2f}, "
        f"${m['cost_per_case_usd'] or 0:.3f} and {m['seconds_per_case']} s per case"
    )
    if label:
        inv.log_experiment(label, set_name, m)


def export() -> None:
    from spendaudit import export as ex

    h = ex.export()["headline"]
    print(
        f"  export: rules recall {h['rules_recall']:.1%}, replay stopped {h['replay_stopped']:.1%} "
        f"at ≤{h['replay_budget']:.0%} legit declined; "
        f"AI ${h['ai_cost_usd']:.2f} for {h['ai_cases']} cases"
    )


def serve(port: int = 8000) -> None:
    """Serve the built site (web/dist) — no Node needed."""
    import functools
    import http.server

    dist = ROOT / "web" / "dist"
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(dist))
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        print(f"Card Spend Audit: open http://localhost:{port}  (Ctrl+C to stop)", flush=True)
        httpd.serve_forever()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="spendaudit")
    ap.add_argument(
        "step",
        choices=[
            "gate",
            "build",
            "rules",
            "plant",
            "replay",
            "investigate",
            "export",
            "all",
            "serve",
        ],
    )
    ap.add_argument("--set", default="dev", choices=["dev", "test"], help="investigate only")
    ap.add_argument("--labeled", action="store_true", help="investigate: skip real flags")
    ap.add_argument("--label", help="investigate: log this run to out/experiments.json")
    args = ap.parse_args(argv)
    t0 = time.time()
    steps = {
        "gate": build,
        "build": build,
        "rules": rules,
        "plant": plant,
        "replay": replay,
        "investigate": investigate,
        "export": export,
        "serve": serve,
    }
    if args.step == "all":
        for name in ("build", "rules", "plant", "replay", "export"):
            if name in steps:
                steps[name]()
    elif args.step == "investigate":
        investigate(args.set, args.labeled, args.label)
    else:
        steps[args.step]()
    print(f"done in {time.time() - t0:.1f}s  ({ROOT.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
