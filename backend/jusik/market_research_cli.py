from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast

from jusik.market_data_collector import (
    AtomicResponseCache,
    CollectorError,
    collect_market_data,
    completed_collection_is_valid,
    load_collector_settings,
)
from jusik.market_history_approximate import (
    ApproximateDataset,
    ApproximateMarketHistorySource,
    ApproximateProviderError,
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
    collect_status = subcommands.add_parser(
        "collect-status", help="show bounded collector cache status"
    )
    collect_status.add_argument("--cache", type=Path, required=True)
    collect_status.add_argument("--market", choices=("KR", "US"), required=True)
    collect_status.add_argument("--start")
    collect_status.add_argument("--end")
    collect_status.add_argument("--sample-size", type=int, default=100)
    collect_status.add_argument("--output", type=Path)
    collect = subcommands.add_parser(
        "collect", help="collect and validate a prepared approximate dataset"
    )
    collect.add_argument("--market", choices=("KR", "US"), required=True)
    collect.add_argument("--start", required=True)
    collect.add_argument("--end", required=True)
    collect.add_argument("--output", type=Path, required=True)
    collect.add_argument("--cache", type=Path, required=True)
    collect.add_argument("--sample-size", type=int, default=100)
    collect.add_argument("--request-budget", type=int)
    collect.add_argument("--resume", action="store_true")
    prepared = subcommands.add_parser(
        "import-file",
        aliases=("backfill",),
        help="validate and import one prepared provider response file",
    )
    prepared.add_argument("--market", choices=("KR", "US"), required=True)
    prepared.add_argument("--input", type=Path)
    prepared.add_argument("--output", type=Path)
    prepared.add_argument("--start", required=True)
    prepared.add_argument("--end", required=True)
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
    if args.command == "collect-status":
        settings = load_collector_settings()
        missing = settings.required_missing_credentials(args.market)
        cache_payload = AtomicResponseCache(args.cache).status()
        marker_args = (args.start, args.end, args.output)
        completed = False
        if all(value is not None for value in marker_args):
            try:
                completed = completed_collection_is_valid(
                    AtomicResponseCache(args.cache),
                    market=cast(Market, args.market),
                    start=date.fromisoformat(args.start),
                    end=date.fromisoformat(args.end),
                    sample_size=args.sample_size,
                    output=args.output,
                )
            except ValueError:
                completed = False
        cache_payload.update(
            {
                "market": args.market,
                "credentials_missing": list(missing),
                "completed": completed,
                "ready": not missing and completed,
            }
        )
        print(json.dumps(cache_payload, ensure_ascii=False))
        return 0 if bool(cache_payload["ready"]) else 2
    if args.command == "collect":
        settings = load_collector_settings()
        missing = settings.required_missing_credentials(args.market)
        if missing:
            print(
                json.dumps(
                    {
                        "status": "unavailable",
                        "market": args.market,
                        "missing_credentials": list(missing),
                    },
                    ensure_ascii=False,
                )
            )
            return 2
        try:
            if args.request_budget is not None:
                settings = settings.model_copy(
                    update={"request_budget": args.request_budget}
                )
            result = asyncio.run(
                collect_market_data(
                    market=cast(Market, args.market),
                    start=date.fromisoformat(args.start),
                    end=date.fromisoformat(args.end),
                    output=args.output,
                    cache_dir=args.cache,
                    settings=settings,
                    sample_size=args.sample_size,
                    resume=args.resume,
                )
            )
        except (CollectorError, ValueError) as exc:
            print(json.dumps({"status": "insufficient", "reason": str(exc)}))
            return 2
        print(
            json.dumps(
                {
                    "status": "collected",
                    "market": args.market,
                    "output": str(args.output),
                    "excluded_symbols": list(result.excluded_symbols),
                },
                ensure_ascii=False,
            )
        )
        return 0
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
        status_payload = [
            status_source.readiness(market, datetime.now(UTC)).model_dump(mode="json")
            for market in markets
        ]
        print(json.dumps(status_payload, ensure_ascii=False))
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
            start = date.fromisoformat(args.start)
            end = date.fromisoformat(args.end)
            if start > end:
                raise ValueError("prepared response start is after end")
            asyncio.run(
                JsonApproximateProvider(args.input).fetch(args.market, start, end)
            )
            if args.output is not None:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_bytes(raw)
        except (
            OSError,
            ValueError,
            json.JSONDecodeError,
            ApproximateProviderError,
        ) as exc:
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
