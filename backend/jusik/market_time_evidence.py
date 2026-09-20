"""Attach causal session timing to newly produced market research results.

Legacy saved runs remain unchanged.  This adapter is called only at the
service boundary for new runs, where the same official calendar used by the
strategy is available.  It never derives timestamps for an existing artifact.
"""

from __future__ import annotations

from jusik.market_history_models import MarketResearchResult
from jusik.research_market_calendar import MarketCalendar


def attach_time_evidence(
    result: MarketResearchResult, calendar: MarketCalendar
) -> MarketResearchResult:
    """Return a result with an explicit engine anchor and per-NAV close times."""

    if not result.equity:
        return result
    exchange = "KRX" if result.market == "KR" else "NMS"
    evaluations = []
    for point in result.equity:
        lookup = calendar.lookup(exchange, point.session)
        if lookup.state != "session" or lookup.session is None:
            raise ValueError(f"missing official session for NAV: {point.session}")
        evaluations.append(lookup.session.close_at)
    if evaluations != sorted(evaluations) or len(set(evaluations)) != len(evaluations):
        raise ValueError("NAV session timestamps are not strictly increasing")
    first = calendar.lookup(exchange, result.equity[0].session)
    if first.state != "session" or first.session is None:
        raise ValueError("missing first official session for initial capital")
    return result.model_copy(
        update={
            "initial_capital_at": first.session.open_at,
            "equity": tuple(
                point.model_copy(update={"evaluation_at": at})
                for point, at in zip(result.equity, evaluations, strict=True)
            ),
        }
    )


__all__ = ["attach_time_evidence"]
