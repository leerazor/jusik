from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast

from jusik.market_history_approximate import (
    ApproximateDataset,
    ApproximateMarketHistorySource,
    JsonApproximateProvider,
)
from jusik.market_history_models import (
    Market,
    MarketResearchRequest,
    ResearchGrade,
    anniversary_start,
)
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
    status.add_argument("--grade", choices=("strict", "approximate"), default="strict")
    prepared = subcommands.add_parser(
        "import-file",
        aliases=("backfill",),
        help="validate and import one prepared provider response file",
    )
    prepared.add_argument("--market", choices=("KR", "US"), required=True)
    prepared.add_argument("--input", type=Path)
    prepared.add_argument("--output", type=Path)
    prepared.add_argument("--start")
    prepared.add_argument("--end")
    run = subcommands.add_parser("run")
    run.add_argument("--market", choices=("KR", "US"), required=True)
    run.add_argument("--start")
    run.add_argument("--end", required=True)
    run.add_argument("--stage", choices=("pilot", "final"), default="pilot")
    run.add_argument("--pilot-run-id")
    run.add_argument("--fixture", action="store_true")
    run.add_argument("--grade", choices=("strict", "approximate"), default="strict")
    run.add_argument("--approximate-data", type=Path)
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "status":
        status_source: MarketHistorySource
        if args.grade == "approximate":
            status_source = ApproximateMarketHistorySource(
                JsonApproximateProvider(Path("approximate-market-data.json"))
            )
        else:
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
    if args.command in {"import-file", "backfill"}:
        if args.input is None:
            print("prepared-file import requires a provider response file")
            return 2
        try:
            raw = args.input.read_bytes()
            dataset = ApproximateDataset.model_validate(json.loads(raw))
            if dataset.market != args.market:
                raise ValueError("market mismatch")
            start = date.fromisoformat(args.start) if args.start else date.min
            end = date.fromisoformat(args.end) if args.end else date.max
            asyncio.run(
                JsonApproximateProvider(args.input).fetch(args.market, start, end)
            )
            if args.output is not None:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_bytes(raw)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"approximate response rejected: {exc}")
            return 2
        print(
            json.dumps(
                {"status": "imported", "market": args.market}, ensure_ascii=False
            )
        )
        return 0
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
        research_grade=cast("ResearchGrade", args.grade),
    )
    source: MarketHistorySource = (
        FixtureMarketHistorySource()
        if args.fixture
        else UnavailableMarketHistorySource()
    )
    approximate_source = (
        ApproximateMarketHistorySource(JsonApproximateProvider(args.approximate_data))
        if args.approximate_data is not None
        else None
    )
    service = MarketResearchService(
        source,
        MarketHistoryStore(Path("market-research.db")),
        approximate_source=approximate_source,
    )
    run = asyncio.run(service.create_run(request))
    print(run.model_dump_json())
    return 0 if run.status == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
