from __future__ import annotations

import asyncio
import json
import os
import re
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal, Protocol

from jusik.research_forward_models import ForwardClockHealth, ForwardSession

PROBE_INTERVAL_SECONDS = 60
PROBE_TIMEOUT_SECONDS = 3
MAX_OUTPUT_BYTES = 64 * 1024
_MEASUREMENT = re.compile(r"^([+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+))(ns|us|µs|ms|s)$")
_PACKET_COUNT = re.compile(r"^[0-9]{1,18}$")
_LABELS = {"Offset": "offset", "Delay": "delay", "Jitter": "jitter"}
ProbeErrorCode = Literal[
    "command_missing",
    "command_failed",
    "timeout",
    "output_oversize",
    "parse_error",
    "probe_failed",
]


class ClockEventStore(Protocol):
    def active_session(self) -> ForwardSession | None: ...

    def record_event(
        self,
        session_id: str,
        occurred_at: datetime,
        kind: str,
        detail: str,
        reference_id: str | None,
    ) -> None: ...


class ClockProbeError(ValueError):
    def __init__(self, code: ProbeErrorCode) -> None:
        super().__init__(code)
        self.code = code


@dataclass
class _OutputBudget:
    maximum: int
    consumed: int = 0

    def add(self, size: int) -> None:
        self.consumed += size
        if self.consumed > self.maximum:
            raise ClockProbeError("output_oversize")


async def _thread_call[T](operation: Callable[[], T]) -> T:
    task = asyncio.create_task(asyncio.to_thread(operation))
    cancelled = False
    while True:
        try:
            result = await asyncio.shield(task)
            break
        except asyncio.CancelledError:
            cancelled = True
        except BaseException:
            if cancelled:
                raise asyncio.CancelledError from None
            raise
    if cancelled:
        raise asyncio.CancelledError
    return result


async def _read_stream(
    stream: asyncio.StreamReader | None, budget: _OutputBudget
) -> bytes:
    if stream is None:
        raise ClockProbeError("probe_failed")
    body = bytearray()
    while chunk := await stream.read(4096):
        budget.add(len(chunk))
        body.extend(chunk)
    return bytes(body)


async def _reap(
    process: asyncio.subprocess.Process, tasks: list[asyncio.Task[bytes]]
) -> None:
    if process.returncode is None:
        try:
            process.kill()
        except ProcessLookupError:
            pass
    for task in tasks:
        if not task.done():
            task.cancel()
    await asyncio.gather(process.wait(), *tasks, return_exceptions=True)


async def run_timesync_status(
    *,
    timeout_seconds: float = PROBE_TIMEOUT_SECONDS,
    maximum_output_bytes: int = MAX_OUTPUT_BYTES,
    _process_factory: Callable[..., Awaitable[asyncio.subprocess.Process]] = (
        asyncio.create_subprocess_exec
    ),
) -> str:
    process: asyncio.subprocess.Process | None = None
    tasks: list[asyncio.Task[bytes]] = []
    try:
        async with asyncio.timeout(timeout_seconds):
            try:
                process = await _process_factory(
                    "timedatectl",
                    "timesync-status",
                    "--no-pager",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env={
                        "LC_ALL": "C",
                        "SYSTEMD_COLORS": "0",
                        "PATH": os.defpath,
                    },
                )
            except FileNotFoundError as exc:
                raise ClockProbeError("command_missing") from exc
            budget = _OutputBudget(maximum_output_bytes)
            stdout_task = asyncio.create_task(_read_stream(process.stdout, budget))
            stderr_task = asyncio.create_task(_read_stream(process.stderr, budget))
            tasks = [stdout_task, stderr_task]
            stdout, _stderr, return_code = await asyncio.gather(
                stdout_task, stderr_task, process.wait()
            )
    except TimeoutError as exc:
        if process is not None:
            await asyncio.shield(_reap(process, tasks))
        raise ClockProbeError("timeout") from exc
    except ClockProbeError:
        if process is not None:
            await asyncio.shield(_reap(process, tasks))
        raise
    except asyncio.CancelledError:
        if process is not None:
            await asyncio.shield(_reap(process, tasks))
        raise
    if return_code != 0:
        raise ClockProbeError("command_failed")
    try:
        return stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ClockProbeError("parse_error") from exc


def _milliseconds(raw: str) -> Decimal:
    match = _MEASUREMENT.fullmatch(raw.strip())
    if match is None:
        raise ClockProbeError("parse_error")
    try:
        value = Decimal(match.group(1))
    except InvalidOperation as exc:
        raise ClockProbeError("parse_error") from exc
    if not value.is_finite() or abs(value.adjusted()) > 18:
        raise ClockProbeError("parse_error")
    factor = {
        "ns": Decimal("0.000001"),
        "us": Decimal("0.001"),
        "µs": Decimal("0.001"),
        "ms": Decimal(1),
        "s": Decimal(1000),
    }[match.group(2)]
    return value * factor


def parse_timesync_status(
    output: str,
) -> tuple[Decimal, Decimal | None, Decimal | None, int | None]:
    fields: dict[str, str] = {}
    for line in output.splitlines():
        label, separator, value = line.partition(":")
        if not separator:
            continue
        normalized = label.strip()
        if normalized in _LABELS or normalized == "Packet count":
            if normalized in fields:
                raise ClockProbeError("parse_error")
            fields[normalized] = value.strip()
    if "Offset" not in fields:
        raise ClockProbeError("parse_error")
    offset = _milliseconds(fields["Offset"])
    delay = _milliseconds(fields["Delay"]) if "Delay" in fields else None
    jitter = _milliseconds(fields["Jitter"]) if "Jitter" in fields else None
    if delay is not None and delay < 0 or jitter is not None and jitter < 0:
        raise ClockProbeError("parse_error")
    packet_count: int | None = None
    if "Packet count" in fields:
        if _PACKET_COUNT.fullmatch(fields["Packet count"]) is None:
            raise ClockProbeError("parse_error")
        packet_count = int(fields["Packet count"])
    return offset, delay, jitter, packet_count


async def probe_clock_health(
    *,
    command: Callable[[], Awaitable[str]] = run_timesync_status,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> ForwardClockHealth:
    offset: Decimal | None
    delay: Decimal | None
    jitter: Decimal | None
    packet_count: int | None
    error_code: ProbeErrorCode | None
    try:
        output = await command()
        offset, delay, jitter, packet_count = parse_timesync_status(output)
    except asyncio.CancelledError:
        raise
    except ClockProbeError as exc:
        error_code = exc.code
        offset = delay = jitter = None
        packet_count = None
    except Exception:
        error_code = "probe_failed"
        offset = delay = jitter = None
        packet_count = None
    else:
        error_code = None
    sampled_at = now()
    if sampled_at.tzinfo is None:
        raise ValueError("clock probe timestamp must be timezone-aware")
    return ForwardClockHealth(
        sample_id=str(uuid.uuid4()),
        sampled_at=sampled_at.astimezone(UTC),
        state="available" if error_code is None else "unknown",
        offset_ms=offset,
        delay_ms=delay,
        jitter_ms=jitter,
        packet_count=packet_count,
        synced=None,
        persisted=False,
        error_code=error_code,
    )


class ClockHealthMonitor:
    def __init__(
        self,
        store: ClockEventStore,
        *,
        probe: Callable[[], Awaitable[ForwardClockHealth]] = probe_clock_health,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.store = store
        self._probe = probe
        self._monotonic = monotonic
        self._sleep = sleep
        self._task: asyncio.Task[None] | None = None
        self._latest: ForwardClockHealth | None = None

    @property
    def latest(self) -> ForwardClockHealth | None:
        return self._latest

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        await asyncio.gather(self._task, return_exceptions=True)
        self._task = None

    async def _loop(self) -> None:
        while True:
            started = self._monotonic()
            await self.run_once()
            remaining = PROBE_INTERVAL_SECONDS - (self._monotonic() - started)
            await self._sleep(max(0, remaining))

    async def run_once(self) -> ForwardClockHealth:
        try:
            sample = await self._probe()
        except asyncio.CancelledError:
            raise
        except Exception:
            sample = await probe_clock_health(
                command=_failed_probe,
            )
        persisted = sample.model_copy(update={"persisted": True})
        try:
            await _thread_call(lambda: self._persist(persisted))
        except asyncio.CancelledError:
            raise
        except Exception:
            sample = sample.model_copy(
                update={"persisted": False, "error_code": "persistence_failed"}
            )
            self._latest = sample
            return sample
        self._latest = persisted
        return persisted

    def _persist(self, sample: ForwardClockHealth) -> None:
        session = self.store.active_session()
        if session is None:
            raise ValueError("active forward session is unavailable")
        detail = json.dumps(
            sample.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        self.store.record_event(
            session.id,
            sample.sampled_at,
            "clock_sample",
            detail,
            sample.sample_id,
        )


async def _failed_probe() -> str:
    raise ClockProbeError("probe_failed")
