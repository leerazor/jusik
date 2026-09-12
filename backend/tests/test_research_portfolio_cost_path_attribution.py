from datetime import UTC, datetime
from typing import Any, cast

from jusik.research_portfolio_cost_path_attribution import first_trade_path_mismatch


def test_first_trade_path_mismatch_is_utc_sorted_and_excludes_price() -> None:
    class Trade:
        def __init__(self, at: datetime, symbol: str, side: str, quantity: int) -> None:
            self.executed_at, self.symbol, self.side, self.quantity = (
                at,
                symbol,
                side,
                quantity,
            )

    class Sim:
        def __init__(self, trades: list[Any]) -> None:
            self.trades = trades

    late = datetime(2024, 1, 1, 1, tzinfo=UTC)
    early = datetime(2024, 1, 1, 0, tzinfo=UTC)
    result = first_trade_path_mismatch(
        cast(Any, Sim([Trade(late, "ZZZ", "buy", 1), Trade(early, "AAA", "sell", 2)])),
        cast(Any, Sim([Trade(late, "ZZZ", "buy", 1), Trade(early, "AAA", "buy", 2)])),
    )
    assert result == {
        "index": 0,
        "left": ["2024-01-01T00:00:00+00:00", "AAA", "sell", 2],
        "right": ["2024-01-01T00:00:00+00:00", "AAA", "buy", 2],
    }


def test_identical_paths_have_no_mismatch() -> None:
    class Trade:
        executed_at = datetime(2024, 1, 1, tzinfo=UTC)
        symbol, side, quantity = "AAA", "buy", 1

    class Sim:
        trades = [Trade()]

    assert first_trade_path_mismatch(cast(Any, Sim()), cast(Any, Sim())) is None
