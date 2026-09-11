from __future__ import annotations

import argparse
import asyncio
import fcntl
import json
import sqlite3
import sys
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import cast
from zoneinfo import ZoneInfo

import httpx

from jusik.research_action_collection_models import (
    ActionCollectionStatus,
    CollectedAction,
    CollectedActionPayload,
    CollectorState,
)
from jusik.research_action_collection_store import ActionCollectionStore
from jusik.research_universe_data import (
    REGISTRY,
    YAHOO_BASE_URL,
    yahoo_request_parameters,
)
from jusik.research_universe_models import ResearchInstrument

DEFAULT_ACTION_COLLECTION_DB = (
    Path.home() / ".local/share/jusik/research-action-collection.db"
)
REQUEST_DAYS = 1095
MAX_BODY_BYTES = 2 * 1024 * 1024
TOTAL_TIMEOUT_SECONDS = 30
LOOP_INTERVAL_SECONDS = 60
MAX_NUMERIC_LITERAL_CHARS = 128
MAX_DECIMAL_DIGITS = 64
MAX_FIXED_DECIMAL_CHARS = 128
MAX_ACTION_INTEGER_DIGITS = 18


class CollectionError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _DatabaseCallCancelled(asyncio.CancelledError):
    def __init__(
        self, result: object = None, error: BaseException | None = None
    ) -> None:
        self.result = result
        self.error = error


async def _database_call[T](operation: Callable[[], T]) -> T:
    task = asyncio.create_task(asyncio.to_thread(operation))
    cancelled = False
    while True:
        try:
            result = await asyncio.shield(task)
            break
        except asyncio.CancelledError:
            cancelled = True
        except BaseException as exc:
            if cancelled:
                raise _DatabaseCallCancelled(error=exc) from None
            raise
    if cancelled:
        raise _DatabaseCallCancelled(result)
    return result


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise CollectionError("duplicate_json_key")
        result[key] = value
    return result


def _fixed_decimal_length(value: Decimal) -> int:
    digits = len(value.as_tuple().digits)
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int):
        return MAX_FIXED_DECIMAL_CHARS + 1
    sign = int(value.is_signed())
    if exponent >= 0:
        return sign + digits + exponent
    point = digits + exponent
    if point > 0:
        return sign + digits + 1
    return sign + 2 - point + digits


def _bounded_decimal(value: Decimal, code: str) -> Decimal:
    if (
        not value.is_finite()
        or len(value.as_tuple().digits) > MAX_DECIMAL_DIGITS
        or _fixed_decimal_length(value) > MAX_FIXED_DECIMAL_CHARS
    ):
        raise CollectionError(code)
    return value


def _parse_decimal_literal(value: str) -> Decimal:
    if len(value) > MAX_NUMERIC_LITERAL_CHARS:
        raise CollectionError("numeric_literal_too_large")
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        raise CollectionError("numeric_literal_invalid") from None
    return _bounded_decimal(parsed, "numeric_literal_too_large")


def _parse_integer_literal(value: str) -> int:
    if len(value) > MAX_NUMERIC_LITERAL_CHARS:
        raise CollectionError("numeric_literal_too_large")
    try:
        return int(value)
    except ValueError:
        raise CollectionError("numeric_literal_invalid") from None


def _reject_nonstandard_constant(_value: str) -> object:
    raise CollectionError("numeric_literal_invalid")


def _positive_decimal(value: object, code: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise CollectionError(code)
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise CollectionError(code) from None
    _bounded_decimal(parsed, code)
    if parsed <= 0:
        raise CollectionError(code)
    return parsed


def _positive_integer(value: object, code: str) -> int:
    parsed = _positive_decimal(value, code)
    integral = parsed.to_integral_value()
    if (
        parsed != integral
        or len(integral.as_tuple().digits) > MAX_ACTION_INTEGER_DIGITS
    ):
        raise CollectionError(code)
    return int(integral)


def _vendor_date(value: object, timezone: ZoneInfo) -> date:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise CollectionError("event_date_invalid")
    try:
        parsed = _bounded_decimal(Decimal(str(value)), "event_date_invalid")
        return datetime.fromtimestamp(float(parsed), timezone).date()
    except (InvalidOperation, OSError, OverflowError, TypeError, ValueError):
        raise CollectionError("event_date_invalid") from None


def parse_action_response(
    raw: bytes,
    instrument: ResearchInstrument,
    requested_start: date,
    requested_end: date,
) -> list[CollectedAction]:
    try:
        payload = json.loads(
            raw,
            object_pairs_hook=_unique_object,
            parse_float=_parse_decimal_literal,
            parse_int=_parse_integer_literal,
            parse_constant=_reject_nonstandard_constant,
        )
    except CollectionError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError):
        raise CollectionError("response_json_invalid") from None
    if not isinstance(payload, Mapping):
        raise CollectionError("response_root_invalid")
    chart = payload.get("chart")
    if not isinstance(chart, Mapping) or chart.get("error") is not None:
        raise CollectionError("response_chart_invalid")
    results = chart.get("result")
    if (
        not isinstance(results, list)
        or len(results) != 1
        or not isinstance(results[0], Mapping)
    ):
        raise CollectionError("response_result_invalid")
    result = cast(Mapping[str, object], results[0])
    metadata = result.get("meta")
    if not isinstance(metadata, Mapping):
        raise CollectionError("response_metadata_invalid")
    expected = {
        "symbol": instrument.yahoo_symbol,
        "exchangeName": instrument.exchange,
        "exchangeTimezoneName": instrument.timezone,
        "currency": instrument.currency,
    }
    if any(metadata.get(key) != value for key, value in expected.items()):
        raise CollectionError("response_metadata_mismatch")
    timezone = ZoneInfo(instrument.timezone)
    events = result.get("events", {})
    if not isinstance(events, Mapping):
        raise CollectionError("response_events_invalid")
    actions: list[CollectedAction] = []
    for provider_name, kind in (("splits", "split"), ("dividends", "dividend")):
        container = events.get(provider_name, {})
        if not isinstance(container, Mapping):
            raise CollectionError(f"response_{provider_name}_invalid")
        for provider_key, event in container.items():
            if (
                not isinstance(provider_key, str)
                or not provider_key
                or len(provider_key) > 200
            ):
                raise CollectionError("provider_key_invalid")
            if not isinstance(event, Mapping):
                raise CollectionError("event_payload_invalid")
            vendor_date = _vendor_date(event.get("date"), timezone)
            if not requested_start <= vendor_date <= requested_end:
                continue
            if kind == "split":
                action_payload = CollectedActionPayload(
                    vendor_date=vendor_date,
                    numerator=_positive_integer(
                        event.get("numerator"), "split_numerator_invalid"
                    ),
                    denominator=_positive_integer(
                        event.get("denominator"), "split_denominator_invalid"
                    ),
                )
            else:
                amount = _positive_decimal(
                    event.get("amount"), "dividend_amount_invalid"
                )
                action_payload = CollectedActionPayload(
                    vendor_date=vendor_date,
                    amount=format(amount, "f"),
                    currency=instrument.currency,
                )
            actions.append(
                CollectedAction(
                    provider_key=provider_key,
                    kind=kind,
                    payload=action_payload,
                )
            )
    identities = [(item.kind, item.provider_key) for item in actions]
    if len(identities) != len(set(identities)):
        raise CollectionError("duplicate_event_identity")
    return sorted(
        actions,
        key=lambda item: (item.payload.vendor_date, item.kind, item.provider_key),
    )


class ActionCollector:
    def __init__(
        self,
        store: ActionCollectionStore,
        client: httpx.AsyncClient,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.store = store
        self.client = client
        self._now = now
        self._task: asyncio.Task[None] | None = None
        self._state: CollectorState = "idle"
        self._error_code: str | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
        await self.client.aclose()
        self._state = "idle"

    async def _loop(self) -> None:
        while True:
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                self._state = "error"
                self._error_code = "collector_cycle_failed"
            await asyncio.sleep(LOOP_INTERVAL_SECONDS)

    async def run_once(self) -> bool:
        now = self._now().astimezone(UTC)
        lock_path = self.store.path.with_suffix(self.store.path.suffix + ".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                self._state = "locked"
                self._error_code = "collection_cycle_locked"
                return False
            try:
                self._state = "running"
                self._error_code = None
                await _database_call(lambda: self.store.ensure_sources(REGISTRY, now))
                await _database_call(lambda: self.store.recover_interrupted(now))
                due = await _database_call(lambda: self.store.due_symbols(now))
                by_symbol = {item.symbol: item for item in REGISTRY}
                for symbol in due:
                    instrument = by_symbol.get(symbol)
                    if instrument is None:
                        continue
                    try:
                        await self._collect(instrument)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        self._state = "error"
                        self._error_code = "collector_symbol_failed"
                if self._state == "running":
                    self._state = "idle"
                return True
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    async def _collect(self, instrument: ResearchInstrument) -> None:
        started = self._now().astimezone(UTC)
        local_today = started.astimezone(ZoneInfo(instrument.timezone)).date()
        requested_start = local_today - timedelta(days=REQUEST_DAYS)
        requested_end = local_today
        try:
            attempt_id = await _database_call(
                lambda: self.store.begin_attempt(
                    instrument.symbol,
                    requested_start,
                    requested_end,
                    started,
                )
            )
        except _DatabaseCallCancelled as exc:
            if exc.error is None:
                attempt_id = cast(str, exc.result)
                try:
                    await _database_call(
                        lambda: self.store.complete_failure(
                            attempt_id=attempt_id,
                            completed_at=self._now(),
                            error_code="interrupted",
                            interrupted=True,
                        )
                    )
                except _DatabaseCallCancelled:
                    pass
            raise asyncio.CancelledError from None
        path, parameters = yahoo_request_parameters(
            instrument, requested_start, requested_end
        )
        request_url: str | None = None
        http_status: int | None = None
        body: bytes | None = None
        attempt_completed = False

        async def complete_failure(
            error_code: str,
            *,
            preserved_body: bytes | None = None,
            interrupted: bool = False,
        ) -> None:
            nonlocal attempt_completed
            try:
                await _database_call(
                    lambda: self.store.complete_failure(
                        attempt_id=attempt_id,
                        completed_at=self._now(),
                        error_code=error_code,
                        http_status=http_status,
                        request_url=request_url,
                        body=preserved_body,
                        interrupted=interrupted,
                    )
                )
            except _DatabaseCallCancelled as exc:
                attempt_completed = exc.error is None
                raise
            attempt_completed = True

        try:
            async with asyncio.timeout(TOTAL_TIMEOUT_SECONDS):
                async with self.client.stream(
                    "GET", path, params=parameters
                ) as response:
                    request_url = str(response.request.url)
                    http_status = response.status_code
                    chunks: list[bytes] = []
                    size = 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > MAX_BODY_BYTES:
                            raise CollectionError("response_body_too_large")
                        chunks.append(chunk)
                    body = b"".join(chunks)
            completed = self._now().astimezone(UTC)
            if http_status != 200:
                code = (
                    f"http_{http_status}" if http_status is not None else "http_error"
                )
                await complete_failure(code, preserved_body=body)
                return
            assert body is not None
            actions = parse_action_response(
                body, instrument, requested_start, requested_end
            )
            try:
                await _database_call(
                    lambda: self.store.complete_success(
                        attempt_id=attempt_id,
                        completed_at=completed,
                        http_status=http_status,
                        request_url=request_url,
                        body=body,
                        actions=actions,
                    )
                )
            except _DatabaseCallCancelled as exc:
                attempt_completed = exc.error is None
                raise
            attempt_completed = True
        except asyncio.CancelledError:
            if not attempt_completed:
                try:
                    await complete_failure(
                        "interrupted", preserved_body=body, interrupted=True
                    )
                except _DatabaseCallCancelled:
                    pass
            raise
        except TimeoutError:
            await complete_failure("request_timeout")
        except CollectionError as exc:
            preserved_body = body if exc.code != "response_body_too_large" else None
            await complete_failure(exc.code, preserved_body=preserved_body)
        except httpx.HTTPError:
            await complete_failure("http_transport_error", preserved_body=body)

    async def status(self) -> ActionCollectionStatus:
        return await asyncio.to_thread(
            self.store.status,
            REGISTRY,
            self._now(),
            collector_state=self._state,
            error_code=self._error_code,
        )


async def _run_cli(db_path: Path) -> int:
    try:
        store = ActionCollectionStore(db_path)
        client = httpx.AsyncClient(
            base_url=YAHOO_BASE_URL,
            timeout=httpx.Timeout(TOTAL_TIMEOUT_SECONDS),
            headers={"User-Agent": "jusik-offline-research/1.0"},
            follow_redirects=False,
            trust_env=False,
        )
        collector = ActionCollector(store, client)
        try:
            return 0 if await collector.run_once() else 2
        finally:
            await collector.stop()
    except (OSError, sqlite3.Error, ValueError):
        print("action collection failed", file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect unverified corporate actions")
    parser.add_argument("--once", action="store_true", required=True)
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args()
    return asyncio.run(_run_cli(args.db))


if __name__ == "__main__":
    raise SystemExit(main())
