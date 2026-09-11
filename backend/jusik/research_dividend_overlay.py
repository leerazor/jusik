from __future__ import annotations

import argparse
import csv
import hashlib
import inspect
import io
import json
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Literal, cast
from zoneinfo import ZoneInfo

from jusik.research_action_review import (
    MAX_EVIDENCE_BYTES,
    ExtractedFacts,
    compare_review,
)
from jusik.research_dividend_overlay_models import (
    DividendComparison,
    DividendCoverage,
    DividendEntitlement,
    DividendEquityPoint,
    DividendLedgerPoint,
    DividendOverlayResult,
    PositionReconciliation,
)
from jusik.research_external_models import ExternalObservation
from jusik.research_market_calendar import DEFAULT_CALENDAR_PATH, load_market_calendar
from jusik.research_portfolio import DEFAULT_REPORT_DIR
from jusik.research_portfolio_models import (
    PortfolioInput,
    PortfolioRunResult,
    PortfolioSimulation,
    PortfolioTrade,
)

SOURCE_RUN_ID = "c94690f0ee13f01b1810ac0368e84fdcaeb1c1bbe7f396985d04dd3634b5ead0"
SOURCE_MANIFEST_SHA256 = (
    "1a2934466efa12c09d08e7792b1a5e4b7c0c880d2aaabab9b25919bd0ec5c825"
)
SOURCE_RESULT_SHA256 = (
    "db7ff9f5108e9112a495e2c47f8abf21cde8870f375139930e44ec01056ee8ca"
)
DEFAULT_DIVIDEND_REPORT_DIR = (
    Path.home() / ".local/share/jusik/research-dividend-reports"
)
ARTIFACTS = (
    "result.json",
    "report.md",
    "entitlements.csv",
    "ledger.csv",
    "equity.csv",
    "coverage.csv",
)
ASSUMPTIONS = [
    "검증된 현재 dividend revision만 사용한 세전 기여분 overlay입니다.",
    "배당락일 실제 개장 직전에 보유한 정수 수량으로 gross receivable을 기록합니다.",
    "지급일 다음 현지 자정에 receivable을 native cash로 옮기는 표시 관례입니다.",
    (
        "세금·재투자·환전·이자·환전비용을 반영하지 않고 "
        "원본 거래와 목표를 바꾸지 않습니다."
    ),
    "과거 자료를 현재 공식 근거로 대조한 후향 계산이며 point-in-time 검증이 아닙니다.",
]
OVERLAY_DECIMAL_PRECISION = 128
MAX_OVERLAY_QUANTITY = 10**18 - 1


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _code_hash() -> str:
    digest = hashlib.sha256()
    for module in (
        sys.modules[__name__],
        sys.modules[DividendOverlayResult.__module__],
        sys.modules[compare_review.__module__],
        sys.modules[load_market_calendar.__module__],
        sys.modules[PortfolioInput.__module__],
    ):
        digest.update(inspect.getsource(module).encode())
    return digest.hexdigest()


def _read_bounded(path: Path, maximum: int = 32 * 1024 * 1024) -> bytes:
    with path.open("rb") as source:
        body = source.read(maximum + 1)
    if len(body) > maximum:
        raise ValueError(f"Source artifact too large: {path.name}")
    return body


def load_review_coverage(review_db: Path) -> tuple[list[DividendCoverage], str]:
    snapshot: list[dict[str, object]] = []
    coverage: list[DividendCoverage] = []
    with sqlite3.connect(
        f"file:{review_db}?mode=ro", uri=True, timeout=0.1
    ) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("BEGIN")
        rows = connection.execute(
            """SELECT e.id AS event_id, e.symbol, e.vendor_date,
                r.id AS revision_id, r.content_sha256, r.payload_json,
                v.id AS review_id, v.sequence AS review_sequence,
                v.extracted_facts_json, v.comparison_status,
                d.id AS evidence_id, d.sha256 AS evidence_sha256,
                length(d.body) AS evidence_size
            FROM action_collection_events e
            JOIN action_collection_revisions r
              ON r.event_id=e.id AND r.sequence=e.latest_revision_sequence
            LEFT JOIN action_reviews v ON v.id=(
                SELECT v2.id FROM action_reviews v2
                WHERE v2.revision_id=r.id ORDER BY v2.sequence DESC LIMIT 1)
            LEFT JOIN action_review_evidence d ON d.id=v.evidence_id
            WHERE e.kind='dividend' ORDER BY e.symbol, e.vendor_date, e.id"""
        ).fetchall()
        verified_evidence: set[str] = set()
        for row in rows:
            reason: str | None = None
            facts: ExtractedFacts | None = None
            if row["review_id"] is None:
                reason = "current_revision_unreviewed"
            else:
                evidence_id = row["evidence_id"]
                if (
                    not isinstance(evidence_id, str)
                    or not isinstance(row["evidence_size"], int)
                    or not 0 < row["evidence_size"] <= MAX_EVIDENCE_BYTES
                ):
                    raise ValueError(
                        "Official review evidence unavailable or too large."
                    )
                if evidence_id not in verified_evidence:
                    body_row = connection.execute(
                        "SELECT body FROM action_review_evidence WHERE id=?",
                        (evidence_id,),
                    ).fetchone()
                    if body_row is None or not isinstance(body_row["body"], bytes):
                        raise ValueError("Official review evidence unavailable.")
                    if _sha(body_row["body"]) != row["evidence_sha256"]:
                        raise ValueError("Official review evidence hash mismatch.")
                    verified_evidence.add(evidence_id)
                facts = ExtractedFacts.model_validate_json(row["extracted_facts_json"])
                payload = json.loads(row["payload_json"])
                comparison, _fields = compare_review("dividend", payload, facts)
                if comparison != "matched" or row["comparison_status"] != "matched":
                    reason = f"latest_review_{comparison}"
                elif (
                    facts.amount is None
                    or facts.currency is None
                    or facts.ex_dividend_date is None
                    or facts.payment_date is None
                    or facts.comparable_share_basis is not True
                ):
                    reason = "required_official_fact_missing"
                elif facts.payment_date < facts.ex_dividend_date:
                    reason = "official_payment_precedes_ex_date"
            item = DividendCoverage(
                event_id=row["event_id"],
                revision_id=row["revision_id"],
                symbol=row["symbol"],
                vendor_date=row["vendor_date"],
                status="eligible" if reason is None else "excluded",
                reason=reason,
                review_id=row["review_id"],
                evidence_id=row["evidence_id"],
                evidence_sha256=row["evidence_sha256"],
                ex_dividend_date=facts.ex_dividend_date if facts else None,
                payment_date=facts.payment_date if facts else None,
                amount=Decimal(facts.amount) if facts and facts.amount else None,
                currency=facts.currency if facts else None,
            )
            coverage.append(item)
            snapshot.append(
                {
                    "event_id": row["event_id"],
                    "revision_id": row["revision_id"],
                    "content_sha256": row["content_sha256"],
                    "review_id": row["review_id"],
                    "review_sequence": row["review_sequence"],
                    "comparison_status": row["comparison_status"],
                    "evidence_id": row["evidence_id"],
                    "evidence_sha256": row["evidence_sha256"],
                    "facts": facts.model_dump(mode="json") if facts else None,
                }
            )
    duplicates: dict[tuple[str, date], list[int]] = defaultdict(list)
    for index, item in enumerate(coverage):
        if item.status == "eligible" and item.ex_dividend_date is not None:
            duplicates[(item.symbol, item.ex_dividend_date)].append(index)
    for indexes in duplicates.values():
        if len(indexes) > 1:
            for index in indexes:
                coverage[index] = coverage[index].model_copy(
                    update={
                        "status": "excluded",
                        "reason": "ambiguous_economic_duplicate",
                    }
                )
    return coverage, _sha(
        _canonical(
            {
                "reviews": snapshot,
                "coverage_decisions": [
                    item.model_dump(mode="json") for item in coverage
                ],
            }
        ).encode()
    )


def _fx_observation(source: PortfolioInput, at: datetime) -> ExternalObservation | None:
    at_utc = at.astimezone(UTC)
    candidates = [
        item
        for item in source.external.observations
        if item.series == "usdkrw"
        and item.available_at.astimezone(UTC) <= at_utc
        and item.observed_on <= at_utc.date()
        and (at_utc.date() - item.observed_on).days <= 7
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: (item.observed_on, item.available_at, item.revision),
    )


def calculate_scenario(
    name: Literal["heldout", "equal_baseline"],
    simulation: PortfolioSimulation,
    source: PortfolioInput,
    coverage: list[DividendCoverage],
) -> tuple[
    list[DividendEntitlement],
    list[DividendLedgerPoint],
    list[DividendEquityPoint],
    PositionReconciliation,
    list[str],
]:
    calendar = load_market_calendar()
    if not simulation.equity:
        raise ValueError("Source scenario has no equity observations.")
    horizon_end = simulation.equity[-1].at.astimezone(UTC)
    instruments = {
        item.instruments[0].instrument.symbol: item for item in source.instruments
    }
    positions: dict[str, int] = defaultdict(int)
    events: list[tuple[datetime, int, str, object]] = []
    reasons: list[str] = []
    seen_trades: set[str] = set()
    for trade in simulation.trades:
        identity = _canonical(trade.model_dump(mode="json"))
        if identity in seen_trades:
            reasons.append("duplicate_source_trade")
        seen_trades.add(identity)
        if trade.quantity > MAX_OVERLAY_QUANTITY:
            reasons.append(f"trade_quantity_out_of_range:{trade.symbol}")
            continue
        trade_snapshot = instruments.get(trade.symbol)
        if trade_snapshot is None:
            reasons.append(f"trade_symbol_missing:{trade.symbol}")
        else:
            trade_instrument = trade_snapshot.instruments[0].instrument
            local_date = trade.executed_at.astimezone(
                ZoneInfo(trade_instrument.timezone)
            ).date()
            trade_lookup = calendar.lookup(trade_instrument.exchange, local_date)
            bar_dates = {bar.date for bar in trade_snapshot.instruments[0].bars}
            if (
                trade_lookup.session is None
                or local_date not in bar_dates
                or trade.executed_at.astimezone(UTC) != trade_lookup.session.open_at
            ):
                reasons.append(
                    f"trade_open_or_bar_unavailable:{trade.symbol}:{local_date}"
                )
        events.append((trade.executed_at.astimezone(UTC), 2, "trade", trade))
    for symbol, instrument_snapshot in instruments.items():
        bar_dates = {bar.date for bar in instrument_snapshot.instruments[0].bars}
        exchange = instrument_snapshot.instruments[0].instrument.exchange
        basis_by_date = {
            action.date: action.factor for action in instrument_snapshot.basis_actions
        }
        for split in instrument_snapshot.corporate_actions:
            if not simulation.period_start <= split.date <= simulation.period_end:
                continue
            factor = split.factor
            lookup = calendar.lookup(exchange, split.date)
            if (
                basis_by_date.get(split.date) != factor
                or sum(
                    action.date == split.date
                    for action in instrument_snapshot.basis_actions
                )
                != 1
                or sum(
                    action.date == split.date
                    for action in instrument_snapshot.corporate_actions
                )
                != 1
                or factor != factor.to_integral_value()
                or factor <= 1
                or lookup.session is None
                or split.date not in bar_dates
            ):
                reasons.append(f"unsupported_or_unresolved_split:{symbol}:{split.date}")
                continue
            events.append((lookup.session.open_at, 0, "split", (symbol, int(factor))))
    eligible = [item for item in coverage if item.status == "eligible"]
    for item in eligible:
        assert item.ex_dividend_date is not None
        if (
            not simulation.period_start
            <= item.ex_dividend_date
            <= simulation.period_end
        ):
            continue
        dividend_snapshot = instruments.get(item.symbol)
        if dividend_snapshot is None:
            reasons.append(f"dividend_symbol_missing:{item.symbol}")
            continue
        instrument = dividend_snapshot.instruments[0].instrument
        bar_dates = {bar.date for bar in dividend_snapshot.instruments[0].bars}
        lookup = calendar.lookup(instrument.exchange, item.ex_dividend_date)
        if lookup.session is None or item.ex_dividend_date not in bar_dates:
            reasons.append(f"dividend_ex_open_unavailable:{item.event_id}")
            continue
        events.append((lookup.session.open_at, 1, "dividend", item))
    entitlements: list[DividendEntitlement] = []
    for at, _priority, kind, payload in sorted(
        events, key=lambda row: (row[0], row[1])
    ):
        if kind == "split":
            split_symbol, integer_factor = cast(tuple[str, int], payload)
            if positions[split_symbol] > MAX_OVERLAY_QUANTITY // integer_factor:
                reasons.append(f"split_quantity_out_of_range:{split_symbol}")
            else:
                positions[split_symbol] *= integer_factor
        elif kind == "trade":
            trade = cast(PortfolioTrade, payload)
            if trade.side == "buy":
                positions[trade.symbol] += trade.quantity
            elif positions[trade.symbol] < trade.quantity:
                reasons.append(f"negative_quantity:{trade.symbol}")
            else:
                positions[trade.symbol] -= trade.quantity
        else:
            dividend = cast(DividendCoverage, payload)
            assert dividend.amount is not None and dividend.currency is not None
            assert dividend.payment_date is not None
            timezone = instruments[dividend.symbol].instruments[0].instrument.timezone
            payment_boundary = datetime.combine(
                dividend.payment_date + timedelta(days=1), time(), ZoneInfo(timezone)
            ).astimezone(UTC)
            quantity = positions[dividend.symbol]
            entitlements.append(
                DividendEntitlement(
                    scenario=name,
                    event_id=dividend.event_id,
                    revision_id=dividend.revision_id,
                    symbol=dividend.symbol,
                    ex_open_at=at,
                    payment_boundary_at=payment_boundary,
                    entitled_quantity=quantity,
                    amount_per_share=dividend.amount,
                    currency=dividend.currency,
                    gross_native=_multiply(Decimal(quantity), dividend.amount),
                )
            )
    expected = {
        item.symbol: item.quantity for item in simulation.positions if item.quantity > 0
    }
    actual = {
        symbol: quantity for symbol, quantity in positions.items() if quantity > 0
    }
    if actual != expected:
        reasons.append("final_position_reconciliation_failed")
    reconciliation_payload = {"expected": expected, "replayed": actual}
    reconciliation = PositionReconciliation(
        scenario=name,
        expected_quantities=expected,
        replayed_quantities=actual,
        matches=actual == expected,
        quantities_sha256=_sha(_canonical(reconciliation_payload).encode()),
    )
    ledger: list[DividendLedgerPoint] = []
    ledger_balances: dict[str, tuple[Decimal, Decimal]] = {
        "KRW": (Decimal(), Decimal()),
        "USD": (Decimal(), Decimal()),
    }
    ledger_events: list[tuple[datetime, int, DividendEntitlement]] = []
    for entitlement in entitlements:
        ledger_events.append((entitlement.ex_open_at, 0, entitlement))
        if entitlement.payment_boundary_at <= horizon_end:
            ledger_events.append((entitlement.payment_boundary_at, 1, entitlement))
    for at, priority, entitlement in sorted(
        ledger_events, key=lambda row: (row[0], row[1], row[2].event_id)
    ):
        receivable, cash = ledger_balances[entitlement.currency]
        if priority == 0:
            receivable = _add(receivable, entitlement.gross_native)
            kind_value: Literal["accrual", "payment"] = "accrual"
        else:
            receivable = _subtract(receivable, entitlement.gross_native)
            cash = _add(cash, entitlement.gross_native)
            kind_value = "payment"
        ledger_balances[entitlement.currency] = receivable, cash
        ledger.append(
            DividendLedgerPoint(
                scenario=name,
                event_id=entitlement.event_id,
                symbol=entitlement.symbol,
                kind=kind_value,
                at=at,
                currency=entitlement.currency,
                amount_native=entitlement.gross_native,
                receivable_after_native=receivable,
                cash_after_native=cash,
            )
        )
    equity: list[DividendEquityPoint] = []
    for point in simulation.equity:
        balances: dict[str, tuple[Decimal, Decimal]] = {}
        for currency in ("KRW", "USD"):
            relevant = [item for item in entitlements if item.currency == currency]
            receivable = _sum_decimals(
                [
                    item.gross_native
                    for item in relevant
                    if item.ex_open_at <= point.at < item.payment_boundary_at
                ]
            )
            cash = _sum_decimals(
                [
                    item.gross_native
                    for item in relevant
                    if item.payment_boundary_at <= point.at
                ]
            )
            balances[currency] = (receivable, cash)
        krw_total = _sum_decimal(balances["KRW"])
        usd_total = _sum_decimal(balances["USD"])
        fx_observation = None if usd_total == 0 else _fx_observation(source, point.at)
        fx = fx_observation.value if fx_observation else None
        reason = None
        contribution: Decimal | None
        if usd_total != 0 and fx is None:
            contribution = None
            reason = "timely_usdkrw_unavailable"
            reasons.append(reason)
        else:
            with localcontext() as context:
                context.prec = OVERLAY_DECIMAL_PRECISION
                contribution = krw_total + usd_total * (fx or Decimal())
        equity.append(
            DividendEquityPoint(
                scenario=name,
                at=point.at,
                baseline_equity_krw=point.equity_krw,
                dividend_contribution_krw=contribution,
                equity_with_known_dividends_krw=(
                    _add(point.equity_krw, contribution)
                    if contribution is not None
                    else None
                ),
                fx_rate=fx,
                fx_observed_on=(fx_observation.observed_on if fx_observation else None),
                fx_available_at=(
                    fx_observation.available_at if fx_observation else None
                ),
                fx_revision=fx_observation.revision if fx_observation else None,
                receivable_native={
                    currency: balances[currency][0] for currency in ("KRW", "USD")
                },
                cash_native={
                    currency: balances[currency][1] for currency in ("KRW", "USD")
                },
                reason=reason,
            )
        )
    return entitlements, ledger, equity, reconciliation, sorted(set(reasons))


def _multiply(left: Decimal, right: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = OVERLAY_DECIMAL_PRECISION
        return left * right


def _add(left: Decimal, right: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = OVERLAY_DECIMAL_PRECISION
        return left + right


def _subtract(left: Decimal, right: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = OVERLAY_DECIMAL_PRECISION
        return left - right


def _sum_decimals(values: list[Decimal]) -> Decimal:
    with localcontext() as context:
        context.prec = OVERLAY_DECIMAL_PRECISION
        return sum(values, Decimal())


def _sum_decimal(values: tuple[Decimal, Decimal]) -> Decimal:
    return _add(values[0], values[1])


def _comparison(
    name: Literal["heldout", "equal_baseline"],
    simulation: PortfolioSimulation,
    equity: list[DividendEquityPoint],
    *,
    complete: bool,
) -> DividendComparison:
    final = equity[-1]
    contribution = final.dividend_contribution_krw if complete else None
    if contribution is None:
        included = increase = None
    else:
        with localcontext() as context:
            context.prec = OVERLAY_DECIMAL_PRECISION
            included = (
                (simulation.metrics.final_equity_krw + contribution)
                / simulation.metrics.initial_equity_krw
                - 1
            ) * 100
            increase = included - simulation.metrics.total_return_pct
    return DividendComparison(
        scenario=name,
        baseline_return_pct=simulation.metrics.total_return_pct,
        known_dividend_krw=contribution,
        return_with_known_dividends_pct=included,
        increase_percentage_points=increase,
    )


def run_overlay(
    source_run_id: str,
    review_db: Path,
    source_report_dir: Path,
    report_dir: Path,
    *,
    created_at: datetime | None = None,
) -> DividendOverlayResult:
    if source_run_id != SOURCE_RUN_ID:
        raise ValueError("Dividend overlay source run is not the fixed baseline.")
    source_dir = source_report_dir / "portfolio-runs" / source_run_id
    manifest_raw = _read_bounded(source_dir / "manifest.json")
    result_raw = _read_bounded(source_dir / "result.json")
    if (
        _sha(manifest_raw) != SOURCE_MANIFEST_SHA256
        or _sha(result_raw) != SOURCE_RESULT_SHA256
    ):
        raise ValueError("Fixed source artifact hash mismatch.")
    manifest = json.loads(manifest_raw)
    result = PortfolioRunResult.model_validate_json(result_raw)
    if manifest.get("run_id") != source_run_id or result.run_id != source_run_id:
        raise ValueError("Source run identity mismatch.")
    source = PortfolioInput.model_validate(manifest["frozen_input"])
    coverage, review_hash = load_review_coverage(review_db)
    calendar = load_market_calendar(DEFAULT_CALENDAR_PATH)
    if not calendar.available:
        raise ValueError("Verified market calendar unavailable.")
    code_hash = _code_hash()
    identity: dict[str, object] = {
        "source_run_id": source_run_id,
        "source_manifest_sha256": _sha(manifest_raw),
        "source_result_sha256": _sha(result_raw),
        "review_snapshot_sha256": review_hash,
        "calendar_sha256": calendar.artifact_sha256,
        "code_sha256": code_hash,
        "assumptions": ASSUMPTIONS,
    }
    run_id = _sha(_canonical(identity).encode())
    output_dir = report_dir / "dividend-overlay-runs" / run_id
    if output_dir.exists():
        return _read_existing(output_dir, identity)
    all_entitlements: list[DividendEntitlement] = []
    all_ledger: list[DividendLedgerPoint] = []
    all_equity: list[DividendEquityPoint] = []
    reconciliations: list[PositionReconciliation] = []
    reasons: list[str] = []
    comparisons: list[DividendComparison] = []
    scenarios: tuple[
        tuple[Literal["heldout", "equal_baseline"], PortfolioSimulation], ...
    ] = (
        ("heldout", result.heldout),
        ("equal_baseline", result.equal_baseline),
    )
    for name, simulation in scenarios:
        entitlements, ledger, equity, reconciliation, scenario_reasons = (
            calculate_scenario(name, simulation, source, coverage)
        )
        all_entitlements.extend(entitlements)
        all_ledger.extend(ledger)
        all_equity.extend(equity)
        reconciliations.append(reconciliation)
        reasons.extend(f"{name}:{reason}" for reason in scenario_reasons)
        comparisons.append(
            _comparison(name, simulation, equity, complete=not scenario_reasons)
        )
    comparisons.append(
        DividendComparison(
            scenario="cash_baseline",
            baseline_return_pct=result.cash_baseline.total_return_pct,
            known_dividend_krw=Decimal(),
            return_with_known_dividends_pct=result.cash_baseline.total_return_pct,
            increase_percentage_points=Decimal(),
        )
    )
    in_period = [
        item
        for item in coverage
        if result.heldout.period_start <= item.vendor_date <= result.heldout.period_end
    ]
    overlay = DividendOverlayResult(
        run_id=run_id,
        source_run_id=source_run_id,
        created_at=(created_at or datetime.now(UTC)).astimezone(UTC),
        source_manifest_sha256=identity["source_manifest_sha256"],
        source_result_sha256=identity["source_result_sha256"],
        review_snapshot_sha256=review_hash,
        calendar_sha256=calendar.artifact_sha256,
        code_sha256=code_hash,
        calculation_complete=not reasons,
        calculation_reasons=sorted(set(reasons)),
        current_dividend_revision_count=len(coverage),
        eligible_dividend_count=sum(item.status == "eligible" for item in coverage),
        excluded_dividend_count=sum(item.status == "excluded" for item in coverage),
        in_period_eligible_count=sum(item.status == "eligible" for item in in_period),
        in_period_excluded_count=sum(item.status == "excluded" for item in in_period),
        coverage=coverage,
        entitlements=all_entitlements,
        ledger=all_ledger,
        equity=all_equity,
        position_reconciliations=reconciliations,
        comparisons=comparisons,
        assumptions=ASSUMPTIONS,
        artifacts=list(ARTIFACTS),
    )
    _write_artifacts(report_dir, output_dir, overlay, identity)
    return overlay


def _csv(rows: list[dict[str, object]]) -> str:
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _write_artifacts(
    report_dir: Path,
    output_dir: Path,
    result: DividendOverlayResult,
    identity: dict[str, object],
) -> None:
    temporary = output_dir.with_name(f".{output_dir.name}.{os.getpid()}.tmp")
    temporary.mkdir(parents=True, exist_ok=False)
    try:
        contents = {
            "result.json": result.model_dump_json(indent=2) + "\n",
            "report.md": (
                f"# 검증된 배당 기여분 포함 세전 연구\n\n"
                f"- 원본 실행: `{result.source_run_id}`\n"
                f"- 계산 완전성: `{result.calculation_complete}`\n"
                f"- 전체 현재 배당 revision: {result.current_dividend_revision_count}\n"
                f"- 공식 근거 eligible: {result.eligible_dividend_count}\n"
                f"- 제외: {result.excluded_dividend_count}\n\n"
                "이 결과는 확인된 일부 배당 기여분 overlay이며 "
                "완전한 총수익률이 아닙니다.\n"
            ),
            "entitlements.csv": _csv(
                [item.model_dump(mode="json") for item in result.entitlements]
            ),
            "ledger.csv": _csv(
                [item.model_dump(mode="json") for item in result.ledger]
            ),
            "equity.csv": _csv(
                [item.model_dump(mode="json") for item in result.equity]
            ),
            "coverage.csv": _csv(
                [item.model_dump(mode="json") for item in result.coverage]
            ),
        }
        hashes: dict[str, str] = {}
        for name, content in contents.items():
            raw = content.encode()
            (temporary / name).write_bytes(raw)
            hashes[name] = _sha(raw)
        (temporary / "manifest.json").write_text(
            _canonical({**identity, "run_id": result.run_id, "artifacts": hashes})
            + "\n",
            encoding="utf-8",
        )
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temporary, output_dir)
        pointer = report_dir / "dividend-overlay-latest.json"
        pointer_tmp = pointer.with_suffix(".tmp")
        pointer_tmp.write_text(_canonical({"run_id": result.run_id}) + "\n")
        os.replace(pointer_tmp, pointer)
    except Exception:
        if temporary.exists():
            for child in temporary.iterdir():
                child.unlink()
            temporary.rmdir()
        raise


def _read_existing(
    output_dir: Path, identity: dict[str, object] | None = None
) -> DividendOverlayResult:
    manifest = json.loads(_read_bounded(output_dir / "manifest.json", 1024 * 1024))
    if not isinstance(manifest, dict):
        raise ValueError("Invalid dividend overlay manifest.")
    expected_keys = {
        "source_run_id",
        "source_manifest_sha256",
        "source_result_sha256",
        "review_snapshot_sha256",
        "calendar_sha256",
        "code_sha256",
        "assumptions",
        "run_id",
        "artifacts",
    }
    if set(manifest) != expected_keys or manifest.get("run_id") != output_dir.name:
        raise ValueError("Invalid dividend overlay manifest.")
    stored_identity = {
        key: manifest[key] for key in expected_keys - {"run_id", "artifacts"}
    }
    if _sha(_canonical(stored_identity).encode()) != output_dir.name:
        raise ValueError("Dividend overlay identity hash mismatch.")
    if identity is not None:
        for key, value in identity.items():
            if manifest.get(key) != value:
                raise ValueError("Existing dividend overlay identity mismatch.")
    hashes = manifest.get("artifacts")
    if not isinstance(hashes, dict) or set(hashes) != set(ARTIFACTS):
        raise ValueError("Invalid dividend overlay artifact index.")
    for name, digest in hashes.items():
        if (
            not isinstance(digest, str)
            or _sha(_read_bounded(output_dir / name)) != digest
        ):
            raise ValueError("Existing dividend overlay artifact mismatch.")
    result = DividendOverlayResult.model_validate_json(
        _read_bounded(output_dir / "result.json")
    )
    if result.run_id != output_dir.name:
        raise ValueError("Existing dividend overlay result mismatch.")
    for key in (
        "source_run_id",
        "source_manifest_sha256",
        "source_result_sha256",
        "review_snapshot_sha256",
        "calendar_sha256",
        "code_sha256",
        "assumptions",
    ):
        if result.model_dump(mode="json")[key] != manifest[key]:
            raise ValueError("Existing dividend overlay result mismatch.")
    return result


class DividendOverlayRepository:
    def __init__(self, report_dir: Path = DEFAULT_DIVIDEND_REPORT_DIR) -> None:
        self.report_dir = report_dir

    def latest(self) -> DividendOverlayResult | None:
        pointer = self.report_dir / "dividend-overlay-latest.json"
        if not pointer.is_file():
            return None
        run_id = json.loads(_read_bounded(pointer, 1024))["run_id"]
        if (
            not isinstance(run_id, str)
            or len(run_id) != 64
            or any(character not in "0123456789abcdef" for character in run_id)
        ):
            raise ValueError("Invalid dividend overlay pointer.")
        return _read_existing(self.report_dir / "dividend-overlay-runs" / run_id)

    def artifact(self, run_id: str, name: str) -> Path:
        if (
            len(run_id) != 64
            or any(character not in "0123456789abcdef" for character in run_id)
            or name not in (*ARTIFACTS, "manifest.json")
        ):
            raise ValueError("Invalid dividend overlay artifact.")
        output_dir = self.report_dir / "dividend-overlay-runs" / run_id
        _read_existing(output_dir)
        path = output_dir / name
        return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build verified dividend overlay")
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--review-db", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--source-report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    args = parser.parse_args()
    try:
        result = run_overlay(
            args.source_run_id,
            args.review_db,
            args.source_report_dir,
            args.report_dir,
        )
    except (OSError, sqlite3.Error, ValueError):
        print("dividend overlay failed", file=sys.stderr)
        return 1
    print(
        _canonical(
            {
                "run_id": result.run_id,
                "calculation_complete": result.calculation_complete,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
