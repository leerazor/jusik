from collections.abc import Iterable
from datetime import UTC, date, datetime
from decimal import Decimal

from jusik.investor_models import (
    AnalysisResult,
    DailyBar,
    EntryKind,
    FundamentalFacts,
    Instrument,
    QuoteFact,
    Thesis,
    ThesisReview,
    TrendFacts,
    ValuationAssumptions,
)


def _invalid_bars(bars: list[DailyBar], today: date) -> str | None:
    if len(bars) < 22:
        return "조정 일봉 22개 이상이 필요합니다."
    sessions = [bar.session for bar in bars]
    if len(set(sessions)) != len(sessions):
        return "중복 거래일이 있어 추세를 보류합니다."
    if any(session > today for session in sessions):
        return "미래 거래일 자료가 포함되어 추세를 보류합니다."
    if not all(bar.adjusted for bar in bars):
        return "분할·배당 조정 여부가 확인된 일봉만 사용합니다."
    if sessions != sorted(sessions):
        return "일봉 순서가 일관되지 않습니다."
    return None


def evaluate_trend(
    bars: Iterable[DailyBar],
    *,
    today: date | None = None,
    source: str = "KIS/Yahoo chart",
) -> TrendFacts:
    """Evaluate a fixed interpretable observation on completed daily bars."""
    values = list(bars)
    current_day = today or datetime.now(UTC).date()
    reason = _invalid_bars(values, current_day)
    if reason:
        return TrendFacts(source=source, unavailable_reasons=[reason])
    latest = values[-1]
    previous = values[-2]
    previous20 = values[-21:-1]
    prior_previous20 = values[-22:-2]
    latest20 = values[-20:]
    previous20_including = values[-21:-1]
    latest_sma = sum((bar.close for bar in latest20), Decimal(0)) / Decimal(20)
    previous_sma = sum(
        (bar.close for bar in previous20_including), Decimal(0)
    ) / Decimal(20)
    latest_breakout = latest.close > max(
        bar.close for bar in previous20
    ) and latest.volume > sum((bar.volume for bar in previous20), Decimal(0)) / Decimal(
        20
    )
    previous_breakout = previous.close > max(
        bar.close for bar in prior_previous20
    ) and previous.volume > sum(
        (bar.volume for bar in prior_previous20), Decimal(0)
    ) / Decimal(20)
    return TrendFacts(
        breakout_observed=latest_breakout and not previous_breakout,
        deterioration_observed=latest.close < latest_sma
        and previous.close < previous_sma,
        latest_completed_session=latest.session,
        source=source,
    )


def _value_status(
    quote: QuoteFact, facts: FundamentalFacts, assumptions: ValuationAssumptions | None
) -> tuple[str, list[str]]:
    if (
        assumptions is None
        or assumptions.normalized_eps is None
        or assumptions.target_pe_lower is None
        or assumptions.target_pe_upper is None
        or assumptions.margin_of_safety is None
    ):
        return "unassessed", [
            "정규화 EPS·목표 PER·안전마진 가정이 모두 있어야 가치 진입을 검토합니다."
        ]
    if quote.price is None:
        return "unassessed", ["현재가가 없어 가치 진입을 평가할 수 없습니다."]
    lower = assumptions.normalized_eps * assumptions.target_pe_lower
    upper = assumptions.normalized_eps * assumptions.target_pe_upper
    safety = lower * (Decimal(1) - assumptions.margin_of_safety)
    if quote.price <= safety:
        return "review", [
            "가정한 안전마진 기준 가격 이하입니다. 가치 진입을 검토하세요."
        ]
    if quote.price >= upper:
        return "exit_review", [
            "가정한 상단 가격 이상입니다. 가치 평가 출구 검토 대상입니다."
        ]
    return "unassessed", ["가정한 가치 범위 안이지만 추가 진입 판단 자료가 필요합니다."]


def _assumed_prices(
    assumptions: ValuationAssumptions | None,
) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    if (
        assumptions is None
        or assumptions.normalized_eps is None
        or assumptions.target_pe_lower is None
        or assumptions.target_pe_upper is None
        or assumptions.margin_of_safety is None
    ):
        return None, None, None
    lower = assumptions.normalized_eps * assumptions.target_pe_lower
    upper = assumptions.normalized_eps * assumptions.target_pe_upper
    return lower, upper, lower * (Decimal(1) - assumptions.margin_of_safety)


def analyze(
    instrument: Instrument,
    quote: QuoteFact,
    fundamentals: FundamentalFacts,
    trend: TrendFacts,
    *,
    assumptions: ValuationAssumptions | None = None,
    entry_kind: EntryKind = "value",
    now: datetime | None = None,
) -> AnalysisResult:
    timestamp = now or datetime.now(UTC)
    if instrument.instrument_type != "stock":
        value_status = "unassessed"
        value_reasons = [
            "주식으로 확인되지 않은 종목은 기업 EPS 가치평가를 적용하지 않습니다."
        ]
    else:
        value_status, value_reasons = _value_status(quote, fundamentals, assumptions)
    assumed_lower, assumed_upper, assumed_safety = _assumed_prices(assumptions)
    trend_status = "unassessed"
    trend_reasons: list[str] = []
    if trend.breakout_observed:
        trend_status = "review"
        trend_reasons.append(
            "완료된 조정 일봉에서 20일 고점 돌파 관찰이 확인되었습니다."
        )
    elif trend.deterioration_observed:
        trend_status = "exit_review"
        trend_reasons.append(
            "완료된 조정 일봉에서 20일 평균 아래 종가가 이틀 연속 관찰되었습니다."
        )
    else:
        trend_reasons.extend(
            trend.unavailable_reasons or ["고정 추세 관찰 규칙에 해당하지 않습니다."]
        )
    return AnalysisResult(
        instrument=instrument,
        quote=quote,
        fundamentals=fundamentals,
        trend=trend,
        entry_kind=entry_kind,
        value_entry_status=value_status,
        trend_entry_status=trend_status,
        assumed_value_lower=assumed_lower,
        assumed_value_upper=assumed_upper,
        assumed_safety_price=assumed_safety,
        reasons=value_reasons + trend_reasons,
        analyzed_at=timestamp,
    )


def analyze_entry(
    instrument: Instrument,
    quote: QuoteFact,
    fundamentals: FundamentalFacts,
    trend: TrendFacts,
    assumptions: ValuationAssumptions | None,
    entry_kind: EntryKind,
    *,
    now: datetime | None = None,
) -> AnalysisResult:
    return analyze(
        instrument,
        quote,
        fundamentals,
        trend,
        assumptions=assumptions,
        entry_kind=entry_kind,
        now=now,
    )


def review_thesis(
    thesis: Thesis, analysis: AnalysisResult, *, today: date | None = None
) -> ThesisReview:
    current_day = today or datetime.now(UTC).date()
    overdue = thesis.next_review < current_day
    reasons: list[str] = []
    if thesis.health == "broken":
        reasons.append("사용자가 근거 훼손을 표시했습니다. 출구 검토가 필요합니다.")
        decision = "exit_review"
    elif thesis.state == "closed":
        return ThesisReview(
            decision="closed",
            reasons=["종료된 연구 기록입니다."],
            review_overdue=overdue,
        )
    elif (
        thesis.risk_price is not None
        and analysis.quote.price is not None
        and analysis.quote.price <= thesis.risk_price
    ):
        reasons.append("사용자가 정한 위험 가격에 도달했습니다. 출구 검토 대상입니다.")
        decision = "exit_review"
    elif thesis.entry_kind == "trend" and analysis.trend.deterioration_observed:
        reasons.append("추세 진입 thesis에서 이틀 연속 SMA20 하회가 관찰되었습니다.")
        decision = "exit_review"
    elif thesis.entry_kind == "value" and analysis.value_entry_status == "exit_review":
        reasons.append(
            "가치 가정 상단 도달은 기존 가치 thesis 실패가 아니며, "
            "평가 출구를 검토합니다."
        )
        decision = "hold_review"
    elif analysis.quote.price is None:
        reasons.append("현재가가 없어 가격 기반 출구를 만들지 않습니다.")
        decision = "deferred"
    else:
        reasons.append("현재 자료에서 명시적인 출구 조건은 확인되지 않았습니다.")
        decision = "hold_review"
    if overdue:
        reasons.append(
            "다음 검토일이 지났습니다. 검토 기한 초과와 매도 신호를 구분하세요."
        )
    return ThesisReview(decision=decision, reasons=reasons, review_overdue=overdue)
