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


def test_cache_file_never_holds_card_keys(tmp_path: Path) -> None:
    case = {"case_id": "C01", "card_key": "abc123def456", "txns": [], "truth": None}
    I._save(tmp_path / "cases.json", [case], {"C01:x": {"case_id": "C01"}})
    text = (tmp_path / "cases.json").read_text()
    assert "abc123def456" not in text and "card_key" not in text and "C01:x" in text


def test_held_out_set_has_no_real_flags_and_other_controls(
    world: tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame],
) -> None:
    planted, labels, flags = world
    dev = I.select_cases(planted, labels, flags)
    test = I.select_cases(planted, labels, flags, control_seed=2, real_flags=False, prefix="T")
    assert all(c["truth"] or c["control"] for c in test)
    assert [c["case_id"] for c in test] == [f"T{i + 1:02d}" for i in range(len(test))]
    ctl = {c["txns"][0]["txn_id"] for c in dev if c["control"]}
    assert ctl != {c["txns"][0]["txn_id"] for c in test if c["control"]}
    assert I.SETS["dev"]["file"] != I.SETS["test"]["file"]
    assert I.SETS["dev"]["plant_seed"] != I.SETS["test"]["plant_seed"]


def _case(
    truth: str | None, control: bool, verdict: str | None, conf: float = 0.9
) -> dict[str, Any]:
    run = None
    if verdict:
        res = (
            {"verdict": verdict} if verdict == "error" else {"verdict": verdict, "confidence": conf}
        )
        run = {"result": res, "cost_usd": 0.1, "seconds": 10}
    return {"truth": truth, "control": control, "run": run}


def test_set_metrics_score_is_caught_minus_false_alarms() -> None:
    cases = [
        _case("split", False, "likely_misuse"),
        _case("duplicate", False, "needs_review", 0.5),
        _case("personal", False, "likely_ok", 0.7),
        _case("prohibited", False, "error"),
        _case(None, True, "likely_ok"),
        _case(None, True, "needs_review", 0.65),
        _case(None, False, "likely_misuse"),  # real flag: no answer key, ignored
        _case(None, True, None),  # not investigated yet
    ]
    m = I.set_metrics(cases)
    assert (m["planted_caught"], m["planted_misuse"], m["controls_flagged"]) == (2, 1, 1)
    assert m["errors"] == 1 and m["investigated"] == 6
    assert m["score"] == pytest.approx(2 / 4 - 1 / 3, abs=1e-4)
    assert m["cost_per_case_usd"] == pytest.approx(0.1)
    assert m["confidence_bands"]["high"] == {"n": 2, "right": 2}
    assert m["confidence_bands"]["medium"] == {"n": 2, "right": 0}


def test_experiment_log_appends(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(I, "EXPERIMENTS", tmp_path / "experiments.json")
    I.log_experiment("baseline", "dev", {"score": 0.7})
    I.log_experiment("checklists", "test", {"score": 0.8})
    log = json.loads((tmp_path / "experiments.json").read_text())
    assert [(e["label"], e["set"], e["score"]) for e in log] == [
        ("baseline", "dev", 0.7),
        ("checklists", "test", 0.8),
    ]


def test_tools_read_the_world_named_by_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pl.DataFrame({"x": [1]}).write_parquet(tmp_path / "w.parquet")
    monkeypatch.setenv("SPENDAUDIT_WORLD", str(tmp_path / "w.parquet"))
    assert T._world().height == 1
    assert 'SPENDAUDIT_WORLD="' + str(tmp_path) in (I._workdir(tmp_path) / "audit-tool").read_text()


def test_tiered_escalates_only_unsure_first_answers(tmp_path: Path) -> None:
    case = {"case_id": "C01", "card_key": "k", "txns": [{"txn_id": "T1"}], "truth": None}
    calls: list[str] = []

    def runner(prompt: str, cwd: Path, model: str = I.MODEL) -> dict[str, Any]:
        calls.append(model)
        if model == I.FIRST_PASS:
            return _good(["T1"], first)
        sure = _good(["T1"], "likely_misuse")
        sure["structured_output"]["confidence"] = 0.9
        return sure

    first = "likely_ok"  # _good's confidence is 0.6, below ESCALATE_BELOW
    out = I.investigate_tiered(case, {"T1"}, runner, tmp_path)
    assert calls == [I.FIRST_PASS, I.MODEL] and out["result"]["verdict"] == "likely_misuse"
    assert out["cost_usd"] == pytest.approx(0.10) and out["first_pass"]["verdict"] == "likely_ok"
    assert out["model"] == f"{I.FIRST_PASS}, then {I.MODEL}"
    calls.clear()
    out = I.investigate_tiered(
        case, {"T1"}, lambda p, c, model=I.MODEL: calls.append(model) or _good(["T1"]), tmp_path
    )
    assert calls == [I.FIRST_PASS, I.MODEL, I.LAST_PASS]  # still unsure after the last pass
    assert out["result"]["verdict"] == "needs_review" and out["cost_usd"] == pytest.approx(0.15)
    calls.clear()
    sure = _good(["T1"], "likely_ok")
    sure["structured_output"]["confidence"] = 0.9
    out = I.investigate_tiered(case, {"T1"}, lambda p, c, model=I.MODEL: sure, tmp_path)
    assert out["model"] == I.FIRST_PASS and out["cost_usd"] == pytest.approx(0.05)
