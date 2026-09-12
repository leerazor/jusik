import hashlib
import json
from decimal import Decimal, getcontext
from pathlib import Path
from typing import Any, cast

import pytest

import jusik.research_portfolio_concentration as module
from jusik.research_entry_attribution import PERIODS


def _fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    capital: str = "100000000",
    symbol_c: str = "10",
    symbol_v: str = "8",
    pair_c: str | None = None,
    pair_v: str | None = None,
    extra_c: str = "0",
    extra_v: str = "0",
) -> dict[str, Any]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    evaluations = []
    for period in PERIODS:
        for _arm, label in (("control", "b2"), ("variant", "variant")):
            for cost in (1, 2):
                evaluations.append(
                    {
                        "artifact": f"{period}-{label}_c{cost}.json",
                        "initial_equity_krw": capital,
                    }
                )
    body = (json.dumps({"evaluations": evaluations}) + "\n").encode()
    (tmp_path / "results.json").write_bytes(body)
    monkeypatch.setattr(module, "RESULTS_SHA256", hashlib.sha256(body).hexdigest())
    pair_c = symbol_c if pair_c is None else pair_c
    pair_v = symbol_v if pair_v is None else pair_v
    pairs = [
        {
            "period": p,
            "cost_multiplier": c,
            "control_final_equity": str(Decimal("100000000") + Decimal(pair_c)),
            "variant_final_equity": str(Decimal("100000000") + Decimal(pair_v)),
            "delta_pnl": str(Decimal(pair_v) - Decimal(pair_c)),
        }
        for p in PERIODS
        for c in (1, 2)
    ]
    symbols = []
    for p in PERIODS:
        for c in (1, 2):
            symbols.extend(
                [
                    {
                        "period": p,
                        "cost_multiplier": c,
                        "symbol": "000660",
                        "control_net_pnl": symbol_c,
                        "variant_net_pnl": symbol_v,
                        "delta_net_pnl": str(Decimal(symbol_v) - Decimal(symbol_c)),
                    },
                    {
                        "period": p,
                        "cost_multiplier": c,
                        "symbol": "AMD",
                        "control_net_pnl": extra_c,
                        "variant_net_pnl": extra_v,
                        "delta_net_pnl": str(Decimal(extra_v) - Decimal(extra_c)),
                    },
                ]
            )
    fresh = {
        "input": {},
        "pairs": pairs,
        "symbol_rows": symbols,
        "monthly_rows": [],
        "residuals": {},
        "source_hashes": {},
    }
    monkeypatch.setattr(module, "entry_analyze", lambda _path: fresh)
    saved = {
        "formula": (
            "signed_raw_notional - transaction_cost - fx_cost + terminal + "
            "split_cash_in_lieu; equivalent to signed_execution_notional - fee "
            "- fx_cost + terminal + split_cash_in_lieu"
        ),
        **fresh,
    }
    saved_body = (json.dumps(saved) + "\n").encode()
    saved_path = tmp_path / "saved.json"
    saved_path.write_bytes(saved_body)
    monkeypatch.setattr(
        module, "ATTRIBUTION_SHA256", hashlib.sha256(saved_body).hexdigest()
    )
    return module.analyze(tmp_path, saved_path)


def test_full_arithmetic_padding_and_tie_transition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _fixture(tmp_path, monkeypatch)
    assert len(result["symbol_rows"]) == 256
    row = next(r for r in result["symbol_rows"] if r["symbol"] == "000660")
    assert row["control_remaining_pnl"] == 0
    assert row["variant_remaining_ratio"] == Decimal("0")
    absent = next(r for r in result["symbol_rows"] if r["symbol"] == "ARM")
    assert absent["control_symbol_net_pnl"] == 0 and not absent["source_symbol_present"]
    assert row["advantage_transition"] == "to_tie"


def test_negative_cancellation_and_strict_flip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _fixture(
        tmp_path,
        monkeypatch,
        symbol_c="5",
        symbol_v="-5",
        pair_c="10",
        pair_v="5",
        extra_c="5",
        extra_v="10",
    )
    row = next(r for r in result["symbol_rows"] if r["symbol"] == "000660")
    assert row["delta_symbol_net_pnl"] == -10
    assert row["advantage_transition"] == "strict_flip"


@pytest.mark.parametrize("capital", ["0", "-1", "NaN", "100000001"])
def test_invalid_fixed_capital_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capital: str
) -> None:
    with pytest.raises(ValueError, match="initial (capital|equity)|non-finite"):
        _fixture(tmp_path, monkeypatch, capital=capital)


def test_precision_independent_output_and_nonempty_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _fixture(tmp_path / "one", monkeypatch)
    old = getcontext().prec
    try:
        getcontext().prec = 6
        other = module.analyze(tmp_path / "one", tmp_path / "one" / "saved.json")
    finally:
        getcontext().prec = old
    assert result["symbol_rows"] == other["symbol_rows"]
    output = tmp_path / "output"
    module.write_outputs(result, output)
    with pytest.raises(ValueError, match="new or empty"):
        module.write_outputs(result, output)


def test_saved_tamper_and_missing_input_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fixture(tmp_path / "valid", monkeypatch)
    saved = tmp_path / "valid" / "saved.json"
    original_saved = saved.read_bytes()
    saved.write_text(
        saved.read_text().replace('"input": {}', '"input": {"tampered": true}')
    )
    with pytest.raises(ValueError, match="hash mismatch"):
        module.analyze(tmp_path / "valid", saved)
    saved.write_bytes(original_saved)
    with pytest.raises(FileNotFoundError):
        module.analyze(tmp_path / "missing", saved)


@pytest.mark.parametrize("field", ["pairs", "symbol_rows"])
def test_missing_or_duplicate_upstream_rows_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    _fixture(tmp_path, monkeypatch)
    original = getattr(module, "entry_analyze")

    def altered(_path: Path) -> dict[str, Any]:
        value = original(_path)
        value[field] = (
            value[field][:-1] if field == "pairs" else value[field] + [value[field][0]]
        )
        return cast(dict[str, Any], value)

    monkeypatch.setattr(module, "entry_analyze", altered)
    with pytest.raises(
        ValueError, match="(pair set|duplicate source|saved attribution)"
    ):
        module.analyze(tmp_path, tmp_path / "saved.json")


def test_zero_and_negative_total_pnl_are_preserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _fixture(
        tmp_path,
        monkeypatch,
        symbol_c="-5",
        symbol_v="5",
        pair_c="0",
        pair_v="0",
        extra_c="5",
        extra_v="-5",
    )
    row = next(r for r in result["symbol_rows"] if r["symbol"] == "000660")
    assert row["control_total_pnl"] == 0 and row["variant_total_pnl"] == 0
    assert row["control_symbol_net_pnl"] < 0 and row["variant_symbol_net_pnl"] > 0
    assert row["advantage_transition"] == "from_tie"
