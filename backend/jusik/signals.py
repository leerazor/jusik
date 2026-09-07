from datetime import UTC, datetime, timedelta
from decimal import Decimal

from jusik.models import Holding, InvestmentAdvice

RULE_VERSION = "v1"


def evaluate_holding(
    holding: Holding, *, now: datetime | None = None
) -> InvestmentAdvice:
    current_time = now or datetime.now(UTC)
    fundamentals = holding.fundamentals
    reasons: list[str] = []

    if holding.price_fetched_at is not None and (
        holding.price_fetched_at > current_time + timedelta(minutes=5)
        or holding.price_fetched_at < current_time - timedelta(minutes=20)
    ):
        return InvestmentAdvice(
            reasons=["잔고 시세 스냅샷이 오래되었거나 시각이 올바르지 않습니다."],
            rule_version=RULE_VERSION,
        )

    if holding.return_pct is not None and holding.return_pct <= Decimal("-12"):
        return InvestmentAdvice(
            signal="sell_review",
            label="매도 검토",
            reasons=[f"손실률 {holding.return_pct}%가 위험 기준 -12% 이하입니다."],
            rule_version=RULE_VERSION,
        )
    if holding.return_pct is not None and holding.return_pct >= Decimal("25"):
        return InvestmentAdvice(
            signal="sell_review",
            label="차익 실현 검토",
            reasons=[f"수익률 {holding.return_pct}%가 차익 검토 기준 25% 이상입니다."],
            rule_version=RULE_VERSION,
        )
    if fundamentals.status != "ok" or fundamentals.fetched_at is None:
        return InvestmentAdvice(
            reasons=["최신 기업가치 지표가 부족합니다."], rule_version=RULE_VERSION
        )
    if fundamentals.fetched_at > current_time + timedelta(minutes=5):
        return InvestmentAdvice(
            reasons=["기업가치 지표 시각이 미래로 표시되어 사용할 수 없습니다."],
            rule_version=RULE_VERSION,
        )
    if fundamentals.fetched_at < current_time - timedelta(hours=48):
        return InvestmentAdvice(
            reasons=["기업가치 지표가 48시간보다 오래되었습니다."],
            rule_version=RULE_VERSION,
        )
    instrument_type = (fundamentals.instrument_type or "").upper()
    if any(label in instrument_type for label in ("ETF", "ETN", "상장지수")):
        return InvestmentAdvice(
            signal="hold",
            label="보유 검토",
            reasons=["ETF는 개별기업 PER·PBR 규칙을 적용하지 않습니다."],
            rule_version=RULE_VERSION,
        )
    valuation_ok = False
    if fundamentals.per is not None and Decimal(0) < fundamentals.per <= Decimal(15):
        reasons.append(f"PER {fundamentals.per}로 규칙 기준 15 이하입니다.")
        valuation_ok = True
    if fundamentals.pbr is not None and Decimal(0) < fundamentals.pbr <= Decimal("1.5"):
        reasons.append(f"PBR {fundamentals.pbr}로 규칙 기준 1.5 이하입니다.")
        valuation_ok = True
    if fundamentals.eps is not None and fundamentals.eps > 0:
        reasons.append("EPS가 양수입니다.")
    if valuation_ok and fundamentals.eps is not None and fundamentals.eps > 0:
        return InvestmentAdvice(
            signal="buy_review",
            label="매수 검토",
            reasons=reasons,
            rule_version=RULE_VERSION,
        )
    if all(
        value is None
        for value in (
            fundamentals.per,
            fundamentals.pbr,
            fundamentals.eps,
            fundamentals.bps,
        )
    ):
        return InvestmentAdvice(
            reasons=["기업가치 지표 값이 제공되지 않았습니다."],
            rule_version=RULE_VERSION,
        )
    return InvestmentAdvice(
        signal="hold",
        label="보유 검토",
        reasons=reasons or ["매수·매도 검토 기준에 해당하지 않습니다."],
        rule_version=RULE_VERSION,
    )


def with_advice(holding: Holding, *, now: datetime | None = None) -> Holding:
    return holding.model_copy(update={"advice": evaluate_holding(holding, now=now)})
