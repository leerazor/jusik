import hashlib
import json
from decimal import Decimal, getcontext

import pytest

import jusik.research_portfolio_concentration as module


def _fixture(
    tmp_path,
    monkeypatch,
    *,
    capital="100000000",
    symbol_c="10",
    symbol_v="8",
    pair_c=None,
    pair_v=None,
    extra_c="0",
    extra_v="0",
):
    tmp_path.mkdir(parents=True, exist_ok=True)
    evaluations = []
    for period in module.PERIODS:
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
        for p in module.PERIODS
        for c in (1, 2)
    ]
    symbols = []
    for p in module.PERIODS:
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
    formula = (
        "signed_raw_notional - transaction_cost - fx_cost + terminal + "
        "split_cash_in_lieu; equivalent to signed_execution_notional - fee "
        "- fx_cost + terminal + split_cash_in_lieu"
    )
    monkeypatch.setattr(
        module, "_read_saved", lambda _path: {"formula": formula, **fresh}
    )
    return module.analyze(tmp_path, tmp_path / "saved.json")


def test_full_arithmetic_padding_and_tie_transition(tmp_path, monkeypatch):
    result = _fixture(tmp_path, monkeypatch)
    assert len(result["symbol_rows"]) == 256
    row = next(r for r in result["symbol_rows"] if r["symbol"] == "000660")
    assert row["control_remaining_pnl"] == 0
    assert row["variant_remaining_ratio"] == Decimal("0")
    absent = next(r for r in result["symbol_rows"] if r["symbol"] == "ARM")
    assert absent["control_symbol_net_pnl"] == 0 and not absent["source_symbol_present"]
    assert row["advantage_transition"] == "to_tie"


def test_negative_cancellation_and_strict_flip(tmp_path, monkeypatch):
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
def test_invalid_fixed_capital_rejected(tmp_path, monkeypatch, capital):
    with pytest.raises(ValueError, match="initial (capital|equity)|non-finite"):
        _fixture(tmp_path, monkeypatch, capital=capital)


def test_precision_independent_output_and_nonempty_refusal(tmp_path, monkeypatch):
    result = _fixture(tmp_path / "one", monkeypatch)
    old = getcontext().prec
    try:
        getcontext().prec = 6
        other = module.analyze(tmp_path / "one", tmp_path / "saved.json")
    finally:
        getcontext().prec = old
    assert result["symbol_rows"] == other["symbol_rows"]
    output = tmp_path / "output"
    module.write_outputs(result, output)
    with pytest.raises(ValueError, match="new or empty"):
        module.write_outputs(result, output)
