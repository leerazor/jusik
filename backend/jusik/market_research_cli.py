from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast

from jusik.market_history_models import Market, MarketResearchRequest, anniversary_start
from jusik.market_history_sources import (
    FixtureMarketHistorySource,
    MarketHistorySource,
    UnavailableMarketHistorySource,
)
from jusik.market_history_store import MarketHistoryStore
from jusik.market_research_service import MarketResearchService


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        description="Bounded point-in-time market research"
    )
    subcommands = command.add_subparsers(dest="command", required=True)
    status = subcommands.add_parser("status")
    status.add_argument("--market", choices=("KR", "US"), default=None)
    backfill = subcommands.add_parser("backfill")
    backfill.add_argument("--market", choices=("KR", "US"), required=True)
    run = subcommands.add_parser("run")
    run.add_argument("--market", choices=("KR", "US"), required=True)
    run.add_argument("--start")
    run.add_argument("--end", required=True)
    run.add_argument("--stage", choices=("pilot", "final"), default="pilot")
    run.add_argument("--pilot-run-id")
    run.add_argument("--fixture", action="store_true")
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "status":
        status_source = UnavailableMarketHistorySource()
        markets: tuple[Market, ...] = (
            (cast(Market, args.market),) if args.market else ("KR", "US")
        )
        payload = [
            status_source.readiness(market, datetime.now(UTC)).model_dump(mode="json")
            for market in markets
        ]
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    if args.command == "backfill":
        print(
            "point-in-time backfill is unavailable until verified provider "
            "coverage is configured"
        )
        return 2
    end_date = date.fromisoformat(args.end)
    start_date = (
        date.fromisoformat(args.start)
        if args.start
        else anniversary_start(end_date, years=1 if args.stage == "pilot" else 3)
    )
    request = MarketResearchRequest(
        market=args.market,
        start_date=start_date,
        end_date=end_date,
        stage=args.stage,
        pilot_run_id=args.pilot_run_id,
    )
    source: MarketHistorySource = (
        FixtureMarketHistorySource()
        if args.fixture
        else UnavailableMarketHistorySource()
    )
    service = MarketResearchService(
        source, MarketHistoryStore(Path("market-research.db"))
    )
    run = asyncio.run(service.create_run(request))
    print(run.model_dump_json())
    return 0 if run.status == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
