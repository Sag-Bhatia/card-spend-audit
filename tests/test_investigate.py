"""AI investigator: case selection, prompt blinding, validation and retry — offline, fake runner."""

import json
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from spendaudit import investigate as I
from spendaudit import tools as T
from spendaudit.plant import plant
from spendaudit.rules import run_all

SLICE = "tests/fixtures/txns_slice.parquet"
RAW = Path("tests/fixtures/claude_raw.json")


@pytest.fixture(scope="module")
def world() -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    planted, labels = plant(pl.read_parquet(SLICE), seed=0, n_per_type=20)
    return planted, labels, run_all(planted)


def _good(ids: list[str], verdict: str = "needs_review") -> dict[str, Any]:
    return {
        "structured_output": {
            "verdict": verdict,
            "confidence": 0.6,
            "explanation": "x",
            "evidence_txn_ids": ids,
            "policy_clause": "c",
            "innocent_explanation": "y",
            "dollars_at_issue": 10.0,
        },
        "total_cost_usd": 0.05,
        "usage": {"input_tokens": 10, "output_tokens": 20},
    }


def test_select_cases_mix_and_blinding(
    world: tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame],
) -> None:
    planted, labels, flags = world
    cases = I.select_cases(planted, labels, flags)
    assert cases == I.select_cases(planted, labels, flags)  # deterministic
    assert [c["case_id"] for c in cases] == [f"C{i + 1:02d}" for i in range(len(cases))]
    truths = [c["truth"] for c in cases if c["truth"]]
    assert truths and all(t in I.PLANTED_MIX for t in truths)
    controls = [c for c in cases if c["control"]]
    assert controls and all(c["rule"] == "spot_check" and not c["truth"] for c in controls)
    assert len({c["card_key"] for c in controls}) == len(controls)
    flagged = set(flags["txn_ids"].explode())
    assert all(
        t["txn_id"] not in flagged and t["amount"] >= I.CONTROL_MIN
        for c in controls
        for t in c["txns"]
    )
    for c in cases:
        p = I.prompt_for(c)
        assert "truth" not in p and "planted" not in p.lower() and c["card_key"] in p
        assert '"control"' not in p
        assert all(t["txn_id"] in p for t in c["txns"])


def test_parse_accepts_structured_output_and_rejects_unknown_ids() -> None:
    v = I.parse(_good(["T1"]), {"T1"})
    assert v.verdict == "needs_review"
    with pytest.raises(ValueError, match="not in the data"):
        I.parse(_good(["T999"]), {"T1"})
    text = {
        "result": 'Here: {"verdict": "likely_ok", "confidence": 1, "explanation": "", '
        '"evidence_txn_ids": [], "policy_clause": "", "innocent_explanation": "", '
        '"dollars_at_issue": 0}'
    }
    assert I.parse(text, set()).verdict == "likely_ok"


def test_bad_answer_is_retried_once_with_the_error(tmp_path: Path) -> None:
    case = {"case_id": "C01", "card_key": "k", "txns": [{"txn_id": "T1"}], "truth": None}
    prompts: list[str] = []
    answers = [_good(["T404"]), _good(["T1"], "likely_ok")]

    def runner(prompt: str, cwd: Path) -> dict[str, Any]:
        prompts.append(prompt)
        return answers[len(prompts) - 1]

    out = I.investigate_one(case, {"T1"}, runner, tmp_path)
    assert out["result"]["verdict"] == "likely_ok" and out["attempts"] == 2
    assert "rejected" in prompts[1] and "T404" in prompts[1]
    assert out["cost_usd"] == pytest.approx(0.10)
    assert out["usage"]["output_tokens"] == 40


def test_two_bad_answers_give_an_error_verdict(tmp_path: Path) -> None:
    case = {"case_id": "C02", "card_key": "k", "txns": [], "truth": None}
    out = I.investigate_one(case, set(), lambda p, c: _good(["nope"]), tmp_path)
    assert out["result"]["verdict"] == "error" and "nope" in out["result"]["error"]


@pytest.mark.skipif(not RAW.exists(), reason="no recorded claude -p response")
def test_recorded_claude_response_parses() -> None:
    rec = json.loads(RAW.read_text())
    ids = {t["txn_id"] for t in rec["case"]["txns"]} | set(
        rec["raw"]["structured_output"]["evidence_txn_ids"]
    )
    v = I.parse(rec["raw"], ids)
    assert v.verdict in ("likely_misuse", "needs_review", "likely_ok")
    assert rec["raw"]["total_cost_usd"] > 0


def test_runner_drops_api_key_and_nesting_marker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen: dict[str, Any] = {}

    class P:
        returncode = 0
        stdout = json.dumps(_good([]))
        stderr = ""

    def fake_run(cmd: list[str], **kw: Any) -> P:
        seen.update(cmd=cmd, **kw)
        return P()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setattr(I.subprocess, "run", fake_run)
    I.claude_runner("hi", tmp_path)
    assert "ANTHROPIC_API_KEY" not in seen["env"] and "CLAUDECODE" not in seen["env"]
    assert seen["cwd"] == tmp_path
    assert "Bash(./audit-tool:*)" in seen["cmd"] and "--json-schema" in seen["cmd"]


def test_tools_read_only_lookups(world: tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]) -> None:
    planted, _, _ = world
    df = planted.drop("planted_type", "incident_id")
    card = df["card_key"][0]
    out = T.card_history(df, card, df["date"][0], 10)
    assert card in out and "Transactions" in out
    assert "No card" in T.card_history(df, "nope", None, 10)
    m = df["merchant_norm"][0]
    assert m in T.merchant(df, m)
    assert "No merchant" in T.merchant(df, "NOT A MERCHANT")
    assert "$5,000" in T.policy("limit") or "5,000" in T.policy("limit")
    assert "[split]" in T.policy(None)
    assert "cards" in T.peer_spend(df, df["agency"][0], m)


def test_cache_file_never_holds_card_keys(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(I, "CASES", tmp_path / "cases.json")
    case = {"case_id": "C01", "card_key": "abc123def456", "txns": [], "truth": None}
    I._save([case], {"C01:x": {"case_id": "C01"}})
    text = (tmp_path / "cases.json").read_text()
    assert "abc123def456" not in text and "card_key" not in text and "C01:x" in text
