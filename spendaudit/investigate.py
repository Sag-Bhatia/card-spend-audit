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
PER_RULE = 10
PLANTED_MIX = {"split": 3, "duplicate": 2, "prohibited": 2, "personal": 3}
MODEL = "sonnet"
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

PROMPT = """You are a careful purchase-card reviewer for the State of Oklahoma. An automated rule
flagged the case below. Decide whether it is likely misuse, needs human review, or is likely fine.

Investigate before deciding. You can run these read-only commands with Bash (at most 8 calls):
  ./audit-tool card-history CARD [--around YYYY-MM-DD] [--days N]   the card's history
  ./audit-tool merchant "MERCHANT NAME"                             who buys there, typical amounts
  ./audit-tool policy [limit|split|prohibited|personal|food]        the policy text
  ./audit-tool peer-spend "AGENCY" "MERCHANT NAME"                  the agency's use of the merchant
Use CARD = {card} and MERCHANT NAME exactly as given. Run nothing else.

Guidance:
- Split purchasing requires intent to divide a known quantity; repeated routine buying from a
  regular supplier is not by itself a split. Several exemptions have no limit at all.
- A double charge is a billing error rather than cardholder misconduct, but the money should
  still be recovered, so a likely double charge needs review.
- Gift cards are allowed for employee recognition programs; fuel may be for non-state vehicles.
- Weigh how normal this purchase is for this card, this agency and this merchant.
- Never name or guess a person. Base every claim on data you saw.

Case:
{case}

Verdicts:
- likely_misuse: the purchase probably breaks the card policy.
- needs_review: a person should check it. This includes billing errors with money to recover.
- likely_ok: nothing to question and nothing to recover.

Reply with the structured result. explanation: at most 80 words. evidence_txn_ids: only ids
that appear in the case or in tool output. dollars_at_issue: the amount you think is actually at
issue (0 if none). confidence: 0 to 1."""


def build_world(df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Real + seed-0 planted rows, renumbered, and the label-free world the tools read.

    Planted rows are created with ids from 900000 up, which no real file reaches; a model
    noticed the gap ("out of sequence with neighboring IDs"). So every row gets a fresh id in a
    neutral order — month, agency, card, date — and planted rows sit among their card's real
    rows with ordinary ids."""
    planted, labels = plant(df, 0)
    month = pl.col("txn_id").str.slice(1, 6)
    ids = (
        planted.select("txn_id", "agency", "card_key", "date")
        .with_columns(month=month)
        .sort("month", "agency", "card_key", "date", "txn_id")
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
    world.write_parquet(WORLD)
    return planted, labels, run_all(planted)


def select_cases(
    planted: pl.DataFrame, labels: pl.DataFrame, flags: pl.DataFrame
) -> list[dict[str, Any]]:
    """Top real flags per rule (deduped per card+merchant) plus a blind sample of flagged planted
    incidents, shuffled together with a fixed seed."""
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
    for rule in ("split", "duplicate", "prohibited", "unusual"):
        top = (
            real.filter(pl.col("rule") == rule)
            .sort("dollars_at_stake", "evidence", descending=True)
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
    order = np.random.default_rng(0).permutation(len(chosen))
    cases = []
    for i, j in enumerate(order):
        c = chosen[int(j)]
        txns = planted.filter(pl.col("txn_id").is_in(c["txn_ids"])).sort("date", "txn_id")
        cases.append(
            {
                "case_id": f"C{i + 1:02d}",
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
            }
        )
    return cases


def prompt_for(case: dict[str, Any]) -> str:
    public = {k: v for k, v in case.items() if k not in ("truth", "case_id")}
    return PROMPT.format(card=case["card_key"], case=json.dumps(public, indent=1))


def _key(case: dict[str, Any]) -> str:
    return case["case_id"] + ":" + hashlib.sha256(prompt_for(case).encode()).hexdigest()[:16]


def _workdir() -> Path:
    """A temp folder outside the project holding only the `audit-tool` wrapper."""
    d = Path(tempfile.mkdtemp(prefix="spendaudit-inv-"))
    tool = d / "audit-tool"
    tool.write_text(f'#!/bin/sh\ncd "{ROOT}" && exec "{sys.executable}" -m spendaudit.tools "$@"\n')
    tool.chmod(0o755)
    return d


def claude_runner(prompt: str, cwd: Path) -> dict[str, Any]:
    """One headless Claude Code call. Returns the parsed --output-format json object."""
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "CLAUDECODE")}
    cmd = [
        shutil.which("claude") or "claude",
        "-p",
        prompt,
        "--output-format",
        "json",
        "--model",
        MODEL,
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
    case: dict[str, Any], known_ids: set[str], runner: Runner, cwd: Path
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
        "model": MODEL,
    }


def run(
    df: pl.DataFrame, runner: Runner = claude_runner, workers: int = 4, limit: int | None = None
) -> dict[str, Any]:
    """Investigate every case not already cached in out/cases.json; returns the full file."""
    planted, labels, flags = build_world(df)
    cases = select_cases(planted, labels, flags)
    known = set(planted["txn_id"])
    cached = json.loads(CASES.read_text()) if CASES.exists() else {"cases": [], "runs": {}}
    runs: dict[str, Any] = cached.get("runs", {})
    pending = [c for c in cases if _key(c) not in runs]
    todo = pending[:limit]
    cwd = _workdir()
    print(
        f"investigate: {len(cases)} cases, {len(cases) - len(pending)} cached, running {len(todo)}"
    )
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for res in pool.map(lambda c: investigate_one(c, known, runner, cwd), todo):
            runs[res["key"]] = res
            print(f"  {res['case_id']}: {res['result']['verdict']} ({res['seconds']}s)")
            out = {"cases": cases, "runs": runs}
            CASES.write_text(json.dumps(out, indent=1, default=str))  # save as we go
    shutil.rmtree(cwd, ignore_errors=True)
    live = {_key(c) for c in cases}  # drop answers to cases that no longer exist
    out = {"cases": cases, "runs": {k: v for k, v in runs.items() if k in live}}
    CASES.write_text(json.dumps(out, indent=1, default=str))
    return out


def results(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Cases joined to their current run (by key), for export."""
    return [{**c, "run": data["runs"].get(_key(c))} for c in data["cases"]]
