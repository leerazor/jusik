import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

from jusik.kis import KisClient
from jusik.kiwoom import KiwoomClient
from jusik.models import (
    AccountResult,
    AggregateSummary,
    AssetSummary,
    AssetSummaryResult,
    Holding,
    MarketResult,
    Portfolio,
)
from jusik.portfolio import PortfolioService, available_account_id


class StubKis:
    async def portfolio(self) -> Portfolio:
        account = AccountResult(
            id="kiwoom",
            label="KIS",
            status="ok",
            asset_summary=AssetSummaryResult(
                status="ok", summary=AssetSummary(net_asset=Decimal("1000"))
            ),
            markets=[],
            totals=[],
        )
        return Portfolio(
            fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
            accounts=[account],
            aggregate=AggregateSummary(
                net_asset=Decimal("1000"),
                completeness="complete",
                included_accounts=1,
                registered_accounts=1,
            ),
            totals=[],
        )


class StubKiwoom:
    async def account(self) -> AccountResult:
        holding = Holding(
            market="NASD",
            symbol="AAPL",
            name="Apple",
            currency="USD",
            quantity=Decimal("1"),
            average_price=Decimal("100"),
            current_price=Decimal("110"),
            cost=Decimal("100"),
            value=Decimal("110"),
            profit=Decimal("10"),
            return_pct=Decimal("10"),
        )
        return AccountResult(
            id="kiwoom-2",
            label="키움",
            broker="kiwoom",
            status="ok",
            asset_summary=AssetSummaryResult(
                status="ok",
                summary=AssetSummary(
                    net_asset=None,
                    estimated_deposit_assets=Decimal("9000"),
                    scope="domestic",
                ),
            ),
            markets=[MarketResult(market="US", status="ok", holdings=[holding])],
            totals=[],
            fetched_at=datetime(2026, 1, 2, tzinfo=UTC),
        )


def test_account_id_collision_is_resolved_deterministically() -> None:
    assert available_account_id("kiwoom", {"default"}) == "kiwoom"
    assert (
        available_account_id("kiwoom", {"kiwoom", "kiwoom-2", "kiwoom-4"}) == "kiwoom-3"
    )


def test_composition_preserves_kis_and_excludes_estimate_from_net_asset() -> None:
    service = PortfolioService(
        cast(KisClient, StubKis()), cast(KiwoomClient, StubKiwoom())
    )
    result = asyncio.run(service.portfolio())
    assert [account.broker for account in result.accounts] == ["kis", "kiwoom"]
    assert result.aggregate.net_asset == Decimal("1000")
    assert result.aggregate.completeness == "partial"
    assert result.aggregate.included_accounts == 1
    assert result.aggregate.registered_accounts == 2
    assert result.totals[0].currency == "USD"
    assert result.totals[0].value == Decimal("110")
    assert result.fetched_at == datetime(2026, 1, 2, tzinfo=UTC)


def test_without_kiwoom_returns_original_kis_snapshot() -> None:
    kis = cast(KisClient, StubKis())
    expected = asyncio.run(kis.portfolio())
    actual = asyncio.run(PortfolioService(kis).portfolio())
    assert actual == expected
