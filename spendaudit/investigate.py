"""AI investigator (spec §7): headless Claude Code reviews flagged cases with read-only tools.

Runs on the user's Claude plan: the subprocess env drops ANTHROPIC_API_KEY (so Claude Code uses
the signed-in plan, not API credits) and CLAUDECODE (so it can start inside another session).
It runs from a temp folder outside the project so it never loads this project's CLAUDE.md."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from typing import Any, Literal

import numpy as np
import polars as pl
from pydantic import BaseModel, Field, ValidationError

from spendaudit import OUT, ROOT
from spendaudit.plant import plant
from spendaudit.rules import run_all
from spendaudit.tools import WORLD

CASES = OUT / "cases.json"
EXPERIMENTS = OUT / "experiments.json"
# Dev cases are what the reviewer is tuned on; the held-out test set is built the same way from
# other seeds and only ever scores a change that already improved dev. Real flags have no answer
# key, so the test set is planted + controls only.
SETS: dict[str, dict[str, Any]] = {
    "dev": {
        "plant_seed": 0,
        "control_seed": 1,
        "real": True,
        "prefix": "C",
        "file": CASES,
        "world": WORLD,
    },
    "test": {
        "plant_seed": 1,
        "control_seed": 2,
        "real": False,
        "prefix": "T",
        "file": OUT / "cases-test.json",
        "world": OUT / "world-test.parquet",
    },
}
FLAGGED = ("likely_misuse", "needs_review")
PER_RULE = 10
PLANTED_MIX = {"split": 5, "duplicate": 5, "prohibited": 5, "personal": 5}
CONTROLS = 20  # real purchases no rule flagged, sent as random spot checks
CONTROL_MIN = 500.0  # material purchases, comparable to the flags
MODEL = "sonnet"
FIRST_PASS = "haiku"  # answers first; MODEL redoes the cases it isn't sure of
LAST_PASS = "opus"  # and redoes the cases MODEL still isn't sure of
ESCALATE_BELOW = 0.8
TIMEOUT_S = 420
USAGE_KEYS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)


class Verdict(BaseModel):
    verdict: Literal["likely_misuse", "needs_review", "likely_ok"]
    confidence: float = Field(ge=0, le=1)
    explanation: str
    evidence_txn_ids: list[str]
    policy_clause: str
    innocent_explanation: str
    dollars_at_issue: float = Field(ge=0)


SCHEMA = Verdict.model_json_schema()

PROMPT = """You are a careful purchase-card reviewer for the State of Oklahoma. The case below was
either flagged by an automated rule or picked at random for a routine spot check. Decide what
should happen to it.

Investigate before deciding. You can run these read-only commands with Bash (at most 8 calls):
  ./audit-tool card-history CARD [--around YYYY-MM-DD] [--days N]   the card's history
  ./audit-tool merchant "MERCHANT NAME"                             who buys there, typical amounts
  ./audit-tool policy [limit|split|prohibited|personal|food]        the policy text
  ./audit-tool peer-spend "AGENCY" "MERCHANT NAME"                  the agency's use of the merchant
Use CARD = {card} and MERCHANT NAME exactly as given. Run nothing else.

The problems to look for:
- Split purchase: one need bought in parts on the same card at the same merchant within a day or
  two, so each part stays under the single-purchase limit while the total exceeds it. Routine
  repeat buying from a regular supplier, or a vendor exempt from the limit, is not a split.
- Double charge: the same card, merchant and amount charged again within a few days, with no
  refund and nothing in the history suggesting a second, separate order.
- Prohibited purchase: cash, gift cards or another category the policy prohibits, unless the data
  shows an allowed exception (gift cards for employee recognition, fuel for non-state vehicles).
- Personal purchase: a consumer purchase that doesn't fit what this card and agency normally buy.

How to settle each kind (check these against the card history around the date):
- Split: do the parts share a description, order or invoice reference? One reference billed in
  parts is evidence of one order split up, not of routine billing. Is the combined total over the
  limit while each part is under it? Routine buying means the card's history shows similar-size
  charges at this merchant at a steady cadence, not a one-off cluster of large ones.
- Double charge: an identical description or order reference with the same amount is what a
  double charge looks like; it is not evidence of two items. It is innocent only if a refund or
  credit follows, or the history shows this exact amount recurring at a steady interval (weekly,
  monthly) that the two charges fit. Two equal charges days apart at a merchant the card normally
  pays once a month or less is a likely double charge.
- Prohibited: is the category on the policy's prohibited list? An exception counts only if this
  card's own history shows it (for example a recognition program). Other cards or agencies doing
  the same thing does not make it allowed.
- Personal: has this card ever bought this kind of thing before? A consumer category this card has
  never used, with no business reason visible in what the card normally buys, points to personal
  use; other cards buying from the merchant does not clear it.
- Spot check (no rule fired): flag only a specific problem from the list above. A business
  purchase that is merely new for the card is not one.
A rule firing is not evidence by itself, and neither is being picked for a spot check. Weigh how
normal the purchase is for this card, this agency and this merchant. Never name or guess a
person. Base every claim on data you saw.

Case:
{case}

Verdicts. Choose the one the evidence supports; do not default to the middle one:
- likely_misuse: the data shows one of the problems above and no innocent explanation in the
  data fits as well. A likely double charge counts: the money should be recovered.
- likely_ok: the purchase fits the normal pattern for this card, agency and merchant, or the data
  shows an innocent explanation.
- needs_review: you found specific evidence pointing both ways, and only a document outside this
  data (a receipt, a contract, an approval) could settle it. Say which document in explanation.

Before you answer, check your draft verdict against the list above:
- Clearing a flagged case as likely_ok: name the specific fact in this card's own history that
  clears it (a refund, a steady interval the charges fit, an earlier purchase of the same kind, an
  exception the card has used before). If you can't name one, it is not likely_ok.
- needs_review: name the evidence on each side. If every sign on the checklist is present and
  nothing in the data explains it, the verdict is likely_misuse.
- Spot check: likely_ok unless you found a specific problem from the list.

Reply with the structured result. explanation: at most 80 words. evidence_txn_ids: only ids
that appear in the case or in tool output. dollars_at_issue: the amount you think is actually at
issue (0 if none). confidence: 0 to 1."""


def build_world(
    df: pl.DataFrame, seed: int = 0, world_path: Path = WORLD
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Real + planted rows (seed 0 for dev), renumbered, and the label-free world the tools read.

    Planted rows are created with ids from 900000 up, which no real file reaches; a model
    noticed the gap ("out of sequence with neighboring IDs"). So every row gets a fresh id in a
    neutral order — month, agency, card, date — and planted rows sit among their card's real
    rows with ordinary ids."""
    planted, labels = plant(df, seed)
    month = pl.col("txn_id").str.slice(1, 6)
    ids = (
        planted.select("txn_id", "agency", "card_key", "date")
        .with_columns(month=month, card_first=pl.col("txn_id").min().over("card_key"))
        .sort("month", "agency", "card_first", "date", "txn_id")  # salt-independent order
        .with_columns(
            new=pl.format(
                "T{}{}",
                pl.col("month"),
                pl.int_range(pl.len()).over("month").cast(pl.String).str.zfill(6),
            )
        )
    )
    mapping = dict(ids.select("txn_id", "new").iter_rows())
    planted = planted.with_columns(pl.col("txn_id").replace_strict(mapping)).sort("date", "txn_id")
    labels = labels.with_columns(
        pl.col("txn_ids").list.eval(pl.element().replace_strict(mapping, return_dtype=pl.String))
    )
    world = planted.drop("planted_type", "incident_id")
    OUT.mkdir(exist_ok=True)
    world.write_parquet(world_path)
    return planted, labels, run_all(planted)


def select_cases(
    planted: pl.DataFrame,
    labels: pl.DataFrame,
    flags: pl.DataFrame,
    control_seed: int = 1,
    real_flags: bool = True,
    prefix: str = "C",
) -> list[dict[str, Any]]:
    """Top real flags per rule (deduped per card+merchant), a blind sample of flagged planted
    incidents, and controls: real purchases no rule flagged, presented as random spot checks.
    Shuffled together with a fixed seed. Without controls, a reviewer that sends everything to
    review would look perfect on the planted cases."""
    plant_of = dict(labels.explode("txn_ids").select("txn_ids", "incident_id").iter_rows())
    type_of = dict(labels.select("incident_id", "type").iter_rows())
    flags = flags.with_columns(
        incident=pl.col("txn_ids")
        .list.eval(pl.element().replace_strict(plant_of, default=None))
        .list.drop_nulls()
        .list.first()
    )
    real = flags.filter(pl.col("incident").is_null())
    chosen: list[dict[str, Any]] = []
    for rule in ("split", "duplicate", "prohibited", "unusual") if real_flags else ():
        top = (
            real.filter(pl.col("rule") == rule)
            .with_columns(first_txn=pl.col("txn_ids").list.first())
            .sort(["dollars_at_stake", "evidence", "first_txn"], descending=[True, True, False])
            .unique(["card_key", "merchant_norm"], keep="first", maintain_order=True)
            .head(PER_RULE)
        )
        chosen += [{**r, "truth": None} for r in top.iter_rows(named=True)]
    fake = flags.filter(pl.col("incident").is_not_null()).with_columns(
        ptype=pl.col("incident").replace_strict(type_of)
    )
    for kind, n in PLANTED_MIX.items():
        pick = (
            fake.filter(pl.col("ptype") == kind)
            .unique("incident", keep="first", maintain_order=True)
            .sort("incident")
            .head(n)
        )
        chosen += [{**r, "truth": kind} for r in pick.iter_rows(named=True)]
    flagged_ids = flags["txn_ids"].explode()
    pool = (
        planted.filter(
            pl.col("planted_type").is_null()
            & ~pl.col("txn_id").is_in(flagged_ids.implode())
            & (pl.col("amount") >= CONTROL_MIN)
            & ~pl.col("card_key").is_in(pl.Series([c["card_key"] for c in chosen]).implode())
        )
        .sort("txn_id")
        .unique("card_key", keep="first", maintain_order=True)  # one per card
    )
    rows = np.random.default_rng(control_seed).choice(
        pool.height, min(CONTROLS, pool.height), replace=False
    )
    chosen += [
        {
            "rule": "spot_check",
            "txn_ids": [r["txn_id"]],
            "card_key": r["card_key"],
            "agency": r["agency"],
            "merchant_norm": r["merchant_norm"],
            "dollars_at_stake": r["amount"],
            "evidence": "Picked at random for a routine spot check; no rule fired.",
            "clause": "",
            "truth": None,
            "control": True,
        }
        for r in pool[sorted(rows.tolist())].iter_rows(named=True)
    ]
    order = np.random.default_rng(0).permutation(len(chosen))
    cases = []
    for i, j in enumerate(order):
        c = chosen[int(j)]
        txns = planted.filter(pl.col("txn_id").is_in(c["txn_ids"])).sort("date", "txn_id")
        cases.append(
            {
                "case_id": f"{prefix}{i + 1:02d}",
                "rule": c["rule"],
                "evidence": c["evidence"],
                "clause": c["clause"],
                "card_key": c["card_key"],
                "agency": c["agency"],
                "merchant_norm": c["merchant_norm"],
                "dollars_at_stake": c["dollars_at_stake"],
                "txns": txns.select(
                    "txn_id", "date", "amount", "merchant_raw", "mcc", "description"
                )
                .with_columns(pl.col("date").cast(pl.String))
                .to_dicts(),
                "truth": c["truth"],  # never sent to the model
                "control": c.get("control", False),  # nor this
            }
        )
    return cases


def prompt_for(case: dict[str, Any]) -> str:
    public = {k: v for k, v in case.items() if k not in ("truth", "control", "case_id")}
    return PROMPT.format(card=case["card_key"], case=json.dumps(public, indent=1))


def _key(case: dict[str, Any]) -> str:
    """Cache key: the prompt with the card's salted hash masked, so the committed cache matches
    in a fresh clone (which makes its own salt)."""
    prompt = (
        prompt_for(case).replace(case["card_key"], "CARD") + f"|{FIRST_PASS}>{MODEL}>{LAST_PASS}"
    )
    return case["case_id"] + ":" + hashlib.sha256(prompt.encode()).hexdigest()[:16]


def _workdir(world: Path = WORLD) -> Path:
    """A temp folder outside the project holding only the `audit-tool` wrapper."""
    d = Path(tempfile.mkdtemp(prefix="spendaudit-inv-"))
    tool = d / "audit-tool"
    tool.write_text(
        f'#!/bin/sh\ncd "{ROOT}" && SPENDAUDIT_WORLD="{world}" '
        f'exec "{sys.executable}" -m spendaudit.tools "$@"\n'
    )
    tool.chmod(0o755)
    return d


def claude_runner(prompt: str, cwd: Path, model: str = MODEL) -> dict[str, Any]:
    """One headless Claude Code call. Returns the parsed --output-format json object."""
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "CLAUDECODE")}
    cmd = [
        shutil.which("claude") or "claude",
        "-p",
        prompt,
        "--output-format",
        "json",
        "--model",
        model,
        "--json-schema",
        json.dumps(SCHEMA),
        "--tools",
        "Bash",
        "--allowedTools",
        "Bash(./audit-tool:*)",
        "--strict-mcp-config",
        "--no-session-persistence",
    ]
    proc = subprocess.run(
        cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=TIMEOUT_S, check=False
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"claude exited {proc.returncode}: {(proc.stderr or proc.stdout)[-500:]}"
        )
    out: dict[str, Any] = json.loads(proc.stdout)
    return out


Runner = Callable[[str, Path], dict[str, Any]]


def parse(raw: dict[str, Any], known_ids: set[str]) -> Verdict:
    """Validate the model's structured output; reject txn ids that don't exist."""
    data = raw.get("structured_output")
    if data is None:
        text = str(raw.get("result", "")).strip()
        text = text[text.find("{") : text.rfind("}") + 1]
        data = json.loads(text)
    v = Verdict.model_validate(data)
    unknown = [t for t in v.evidence_txn_ids if t not in known_ids]
    if unknown:
        raise ValueError(f"evidence_txn_ids not in the data: {unknown}")
    return v


def investigate_one(
    case: dict[str, Any], known_ids: set[str], runner: Runner, cwd: Path, model: str = MODEL
) -> dict[str, Any]:
    prompt = prompt_for(case)
    t0 = time.time()
    usage = dict.fromkeys(USAGE_KEYS, 0)
    cost, attempts, error = 0.0, 0, None
    verdict: Verdict | None = None
    for _ in range(2):  # one retry, told what was wrong
        attempts += 1
        raw: dict[str, Any] | None = None
        for backoff in (0, 20, 60):
            time.sleep(backoff)
            try:
                raw = runner(prompt, cwd)
                break
            except (RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
                error = str(e)
        if raw is None:
            break
        cost += float(raw.get("total_cost_usd") or 0)
        for k in usage:
            usage[k] += int((raw.get("usage") or {}).get(k) or 0)
        try:
            verdict = parse(raw, known_ids)
            error = None
            break
        except (ValidationError, ValueError, json.JSONDecodeError) as e:
            error = str(e)[:300]
            prompt = prompt_for(case) + f"\n\nYour previous answer was rejected: {error}. Fix it."
    return {
        "key": _key(case),
        "case_id": case["case_id"],
        "result": verdict.model_dump() if verdict else {"verdict": "error", "error": error},
        "cost_usd": round(cost, 4),
        "usage": usage,
        "seconds": round(time.time() - t0, 1),
        "attempts": attempts,
        "model": model,
    }


def _unsure(res: dict[str, Any]) -> bool:
    return res["verdict"] in ("needs_review", "error") or res["confidence"] < ESCALATE_BELOW


def investigate_tiered(
    case: dict[str, Any], known_ids: set[str], runner: Callable[..., dict[str, Any]], cwd: Path
) -> dict[str, Any]:
    """FIRST_PASS answers; MODEL, then LAST_PASS, redo needs_review, errors and answers below
    ESCALATE_BELOW. Cost, time and tokens add up over every pass."""
    passes: list[dict[str, Any]] = []
    for model in (FIRST_PASS, MODEL, LAST_PASS):
        passes.append(investigate_one(case, known_ids, partial(runner, model=model), cwd, model))
        if not _unsure(passes[-1]["result"]):
            break
    if len(passes) == 1:
        return passes[0]
    return {
        **passes[-1],
        "cost_usd": round(sum(p["cost_usd"] for p in passes), 4),
        "usage": {k: sum(p["usage"][k] for p in passes) for k in USAGE_KEYS},
        "seconds": round(sum(p["seconds"] for p in passes), 1),
        "attempts": sum(p["attempts"] for p in passes),
        "model": ", then ".join(p["model"] for p in passes),
        "first_pass": passes[0]["result"],
    }


def _cases_for(df: pl.DataFrame, name: str) -> tuple[list[dict[str, Any]], set[str]]:
    cfg = SETS[name]
    planted, labels, flags = build_world(df, cfg["plant_seed"], cfg["world"])
    cases = select_cases(planted, labels, flags, cfg["control_seed"], cfg["real"], cfg["prefix"])
    return cases, set(planted["txn_id"])


def run(
    df: pl.DataFrame,
    runner: Callable[..., dict[str, Any]] = claude_runner,
    workers: int = 4,
    limit: int | None = None,
    set_name: str = "dev",
    labeled_only: bool = False,
) -> dict[str, Any]:
    """Investigate every case of a set not already cached in its file; returns the full file.
    labeled_only skips the real flags (no answer key), for tuning runs on dev."""
    cfg = SETS[set_name]
    cases, known = _cases_for(df, set_name)
    path: Path = cfg["file"]
    cached = json.loads(path.read_text()) if path.exists() else {"cases": [], "runs": {}}
    runs: dict[str, Any] = cached.get("runs", {})
    pending = [
        c for c in cases if _key(c) not in runs and (c["truth"] or c["control"] or not labeled_only)
    ]
    todo = pending[:limit]
    cwd = _workdir(cfg["world"])
    print(
        f"investigate {set_name}: {len(cases)} cases, {len(cases) - len(pending)} cached, "
        f"running {len(todo)}"
    )
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for res in pool.map(lambda c: investigate_tiered(c, known, runner, cwd), todo):
            runs[res["key"]] = res
            print(f"  {res['case_id']}: {res['result']['verdict']} ({res['seconds']}s)")
            _save(path, cases, runs)  # save as we go
    shutil.rmtree(cwd, ignore_errors=True)
    live = {_key(c) for c in cases}  # drop answers to cases that no longer exist
    runs = {k: v for k, v in runs.items() if k in live}
    _save(path, cases, runs)
    return {"cases": cases, "runs": runs}


def _save(path: Path, cases: list[dict[str, Any]], runs: dict[str, Any]) -> None:
    """The case files are committed, so the hashed card_key is left out: cases are rebuilt from
    the data (deterministically) whenever they are needed, and runs are keyed by prompt hash."""
    public = [{k: v for k, v in c.items() if k != "card_key"} for c in cases]
    text = json.dumps({"cases": public, "runs": runs}, indent=1, default=str)
    for c in cases:  # the model sometimes echoes the card's hash in its explanation
        text = text.replace(c["card_key"], "this card")
    path.write_text(text)


def load_cases(df: pl.DataFrame, set_name: str = "dev") -> list[dict[str, Any]]:
    """The set's cases, each joined to its cached run (None if not investigated yet)."""
    path: Path = SETS[set_name]["file"]
    cases, _ = _cases_for(df, set_name)
    runs = json.loads(path.read_text())["runs"] if path.exists() else {}
    return [{**c, "run": runs.get(_key(c))} for c in cases]


def set_metrics(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Answer-key metrics over a set's planted cases and controls (cases joined to their runs).
    score = planted caught rate - controls false-alarm rate."""

    def verdict(c: dict[str, Any]) -> str:
        return str(((c.get("run") or {}).get("result") or {}).get("verdict", "pending"))

    planted = [c for c in cases if c["truth"]]
    controls = [c for c in cases if c["control"]]
    labeled = [c for c in planted + controls if c.get("run")]
    caught = sum(verdict(c) in FLAGGED for c in planted)
    false_alarms = sum(verdict(c) in FLAGGED for c in controls)
    cost = sum(c["run"].get("cost_usd") or 0 for c in labeled)
    caught_rate = caught / len(planted) if planted else 0.0
    false_rate = false_alarms / len(controls) if controls else 0.0
    by_band: dict[str, list[int]] = {}
    for c in planted + controls:
        res = (c.get("run") or {}).get("result") or {}
        if "confidence" not in res:
            continue
        band = (
            "high" if res["confidence"] >= 0.8 else "medium" if res["confidence"] >= 0.6 else "low"
        )
        right = (verdict(c) in FLAGGED) == bool(c["truth"])
        by_band.setdefault(band, []).append(int(right))
    return {
        "planted": len(planted),
        "controls": len(controls),
        "investigated": len(labeled),
        "planted_caught": caught,
        "planted_misuse": sum(verdict(c) == "likely_misuse" for c in planted),
        "controls_flagged": false_alarms,
        "errors": sum(verdict(c) == "error" for c in planted + controls),
        "caught_rate": round(caught_rate, 4),
        "false_alarm_rate": round(false_rate, 4),
        "score": round(caught_rate - false_rate, 4),
        "cost_per_case_usd": round(cost / len(labeled), 4) if labeled else None,
        "seconds_per_case": round(
            sum(c["run"].get("seconds") or 0 for c in labeled) / len(labeled), 1
        )
        if labeled
        else None,
        "confidence_bands": {b: {"n": len(v), "right": sum(v)} for b, v in sorted(by_band.items())},
    }


def log_experiment(label: str, set_name: str, metrics: dict[str, Any]) -> None:
    """Append one tuning run's metrics to out/experiments.json (committed; export reads it)."""
    log = json.loads(EXPERIMENTS.read_text()) if EXPERIMENTS.exists() else []
    log.append({"label": label, "set": set_name, "date": time.strftime("%Y-%m-%d"), **metrics})
    EXPERIMENTS.write_text(json.dumps(log, indent=1))
