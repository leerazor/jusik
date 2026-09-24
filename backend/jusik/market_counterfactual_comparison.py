"""Compare prepared loss-accounting reports under one bounded assumption change.

This module only reads already prepared ``LossAccountingReport`` JSON.  It does
not call the accounting engine, a strategy, a market-data provider, or a
simulation.  Every source is hash checked before JSON parsing and unavailable
accounting values remain unavailable in the comparison.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Context, Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Literal, NoReturn, cast

PRECISION = 50
DECIMAL_CONTEXT = Context(prec=PRECISION, rounding=ROUND_HALF_EVEN)
MAX_SCENARIOS = 3
_ASSUMPTION_KINDS = ("cost", "dividend", "fx")
_COMPONENTS = (
    "raw_realized_pnl",
    "fill_realized_pnl",
    "raw_unrealized_pnl",
    "fill_unrealized_pnl",
    "dividends",
    "fees",
    "taxes",
    "slippage",
    "fx",
    "cash_balance",
    "raw_net_pnl",
    "fill_net_pnl",
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
JsonObject = dict[str, object]
DeltaAvailability = Literal["available", "unavailable"]


def _object(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _decimal(value: object, label: str) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError(f"{label} must be a finite decimal")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{label} must be a finite decimal") from exc
    if not result.is_finite():
        raise ValueError(f"{label} must be a finite decimal")
    return result


def _reject_in_memory_numbers(value: object, label: str) -> None:
    """Reject binary floats before they can lose decimal precision."""

    if isinstance(value, float):
        raise ValueError(f"{label} must not contain binary floating-point numbers")
    if isinstance(value, Decimal) and not value.is_finite():
        raise ValueError(f"{label} must contain only finite decimals")
    if isinstance(value, Mapping):
        for key, item in value.items():
            _reject_in_memory_numbers(item, f"{label}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_in_memory_numbers(item, f"{label}[{index}]")


def _iso_date(value: object, label: str) -> str:
    text = _string(value, label)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO date") from exc
    if parsed.isoformat() != text:
        raise ValueError(f"{label} must be an ISO date")
    return text


def _list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return value


class _DuplicateKey(ValueError):
    pass


class _InvalidJsonNumber(ValueError):
    pass


def _reject_decimal_number(value: str) -> NoReturn:
    raise _InvalidJsonNumber(
        f"non-integer JSON number {value!r} must be encoded as a decimal string"
    )


def _reject_nonstandard_constant(value: str) -> NoReturn:
    raise _InvalidJsonNumber(f"non-standard JSON numeric constant {value} is invalid")


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> JsonObject:
    result: JsonObject = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _parse_json(body: bytes, label: str) -> JsonObject:
    try:
        parsed = json.loads(
            body.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_float=_reject_decimal_number,
            parse_constant=_reject_nonstandard_constant,
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        _DuplicateKey,
        _InvalidJsonNumber,
    ) as exc:
        raise ValueError(f"{label} is invalid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{label} must contain an object")
    return parsed


def _sha256(value: object, label: str) -> str:
    text = _string(value, label)
    if not _SHA256.fullmatch(text):
        raise ValueError(f"{label} must be a lowercase SHA-256")
    return text


def _json_equal(left: object, right: object) -> bool:
    return _json_fingerprint(left) == _json_fingerprint(right)


def _json_fingerprint(value: object) -> tuple[object, ...]:
    """Return a recursive JSON fingerprint that keeps scalar types distinct."""

    if value is None:
        return ("null",)
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, int):
        return ("int", value)
    if isinstance(value, float):
        return ("float", repr(value))
    if isinstance(value, str):
        return ("string", value)
    if isinstance(value, list):
        return ("array", tuple(_json_fingerprint(item) for item in value))
    if isinstance(value, Mapping):
        entries = tuple(
            sorted(
                ((str(key), _json_fingerprint(item)) for key, item in value.items()),
                key=lambda item: item[0],
            )
        )
        return ("object", entries)
    return (type(value).__name__, repr(value))


def _leaf_differences(
    left: object, right: object, path: tuple[str, ...] = ()
) -> tuple[tuple[str, ...], ...]:
    if _json_equal(left, right):
        return ()
    left_is_mapping = isinstance(left, Mapping)
    right_is_mapping = isinstance(right, Mapping)
    left_is_list = isinstance(left, list)
    right_is_list = isinstance(right, list)
    if left_is_mapping != right_is_mapping or left_is_list != right_is_list:
        raise ValueError(
            "assumptions must not replace a container or change container type; "
            "this is not an atomic assumption leaf"
        )
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        if set(left) != set(right):
            raise ValueError(
                "assumption paths must exist on both sides; added or removed "
                "keys are not atomic leaves"
            )
        keys = sorted(left)
        differences: list[tuple[str, ...]] = []
        for key in keys:
            differences.extend(
                _leaf_differences(left[key], right[key], path + (str(key),))
            )
        return tuple(differences)
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            raise ValueError(
                "assumption paths must exist on both sides; added or removed "
                "list indexes are not atomic leaves"
            )
        differences = []
        for index in range(len(left)):
            left_item = left[index]
            right_item = right[index]
            differences.extend(
                _leaf_differences(left_item, right_item, path + (str(index),))
            )
        return tuple(differences)
    return (path,)


def _validate_path_keys(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if "." in str(key):
                raise ValueError("assumption keys must not contain dots")
            _validate_path_keys(item)
    elif isinstance(value, list):
        for item in value:
            _validate_path_keys(item)


def _at_path(value: object, path: tuple[str, ...]) -> object:
    current = value
    for part in path:
        if isinstance(current, Mapping):
            if part not in current:
                raise ValueError("assumption path must exist on both sides")
            current = current[part]
        elif isinstance(current, list) and part.isdigit():
            index = int(part)
            if index >= len(current):
                raise ValueError("assumption path must exist on both sides")
            current = current[index]
        else:
            raise ValueError("assumption path must exist on both sides")
    return current


@dataclass(frozen=True)
class PreparedReportSource:
    """A path and digest for one prepared report."""

    path: Path
    sha256: str

    @classmethod
    def from_mapping(cls, value: object, label: str) -> PreparedReportSource:
        data = _object(value, label)
        return cls(
            path=Path(_string(data.get("path"), f"{label}.path")),
            sha256=_sha256(data.get("sha256"), f"{label}.sha256"),
        )

    def as_dict(self) -> dict[str, object]:
        return {"path": str(self.path), "sha256": self.sha256}


@dataclass(frozen=True)
class PreparedLossReport:
    source: PreparedReportSource
    source_sha256: str
    metadata: JsonObject
    payload: JsonObject


@dataclass(frozen=True)
class ComparisonDelta:
    availability: DeltaAvailability
    value: Decimal | None
    evidence: tuple[str, ...] = ()
    resume_inputs: tuple[str, ...] = ()
    currency: str | None = None
    unit: str | None = None

    def as_dict(self) -> dict[str, object]:
        output: dict[str, object] = {
            "availability": self.availability,
            "value": None if self.value is None else str(self.value),
            "evidence": list(self.evidence),
            "resume_inputs": list(self.resume_inputs),
            "currency": self.currency,
            "unit": self.unit,
        }
        return output


@dataclass(frozen=True)
class ComparisonScenario:
    scenario_id: str
    source: PreparedReportSource
    change: Mapping[str, object]
    assumptions: Mapping[str, object]


@dataclass(frozen=True)
class ComparisonEnvelope:
    market: Literal["KR", "US"]
    period_start: str
    period_end: str
    sessions: tuple[str, ...]
    currency: Literal["KRW", "USD"]
    initial_capital: Decimal
    initial_capital_currency: Literal["KRW", "USD"]
    research_grade: str
    data_contract: str
    policy_contract: str
    fixed_assumptions: Mapping[str, object]
    baseline: ComparisonScenario
    scenarios: tuple[ComparisonScenario, ...]

    @classmethod
    def from_mapping(
        cls, value: object, *, base_dir: Path = Path(".")
    ) -> ComparisonEnvelope:
        _reject_in_memory_numbers(value, "comparison envelope")
        data = _object(value, "comparison envelope")
        if data.get("schema") != "market-counterfactual-comparison/v1":
            raise ValueError("comparison envelope schema is unsupported")
        period = _object(data.get("period"), "period")
        start = _iso_date(period.get("start"), "period.start")
        end = _iso_date(period.get("end"), "period.end")
        if start > end:
            raise ValueError("period.start is after period.end")
        raw_sessions = _list(data.get("sessions"), "sessions")
        sessions = tuple(_iso_date(item, "session") for item in raw_sessions)
        if len(set(sessions)) != len(sessions):
            raise ValueError("sessions must be unique")
        if tuple(sorted(sessions)) != sessions:
            raise ValueError("sessions must be chronological")
        if any(item < start or item > end for item in sessions):
            raise ValueError("sessions must be within period")
        market = data.get("market")
        currency = data.get("currency")
        if market not in {"KR", "US"}:
            raise ValueError("market must be KR or US")
        if currency not in {"KRW", "USD"}:
            raise ValueError("currency must be KRW or USD")
        expected_currency = "KRW" if market == "KR" else "USD"
        if currency != expected_currency:
            raise ValueError("currency does not match market")
        capital = _object(data.get("initial_capital"), "initial_capital")
        capital_value = _decimal(capital.get("value"), "initial_capital.value")
        capital_currency = capital.get("currency")
        if capital_value <= 0:
            raise ValueError("initial_capital.value must be positive")
        if capital_currency not in {"KRW", "USD"}:
            raise ValueError("initial_capital currency must be KRW or USD")
        if capital.get("unit") != "currency":
            raise ValueError("initial_capital.unit must be currency")
        fixed = _object(data.get("fixed_assumptions"), "fixed_assumptions")
        for key in _ASSUMPTION_KINDS:
            if key not in fixed:
                raise ValueError(f"fixed_assumptions missing {key}")
        baseline = _scenario(
            data.get("baseline"), "baseline", base_dir, require_change=False
        )
        scenarios_value = _list(data.get("scenarios"), "scenarios")
        if not scenarios_value or len(scenarios_value) > MAX_SCENARIOS:
            raise ValueError(f"scenarios must contain 1 to {MAX_SCENARIOS} items")
        scenarios = tuple(
            _scenario(item, f"scenario {index}", base_dir, require_change=True)
            for index, item in enumerate(scenarios_value)
        )
        ids = (baseline.scenario_id,) + tuple(item.scenario_id for item in scenarios)
        if len(set(ids)) != len(ids):
            raise ValueError("scenario IDs must be unique")
        _validate_assumptions(baseline, scenarios)
        envelope = cls(
            market=cast(Literal["KR", "US"], market),
            period_start=start,
            period_end=end,
            sessions=sessions,
            currency=cast(Literal["KRW", "USD"], currency),
            initial_capital=capital_value,
            initial_capital_currency=cast(Literal["KRW", "USD"], capital_currency),
            research_grade=_string(data.get("research_grade"), "research_grade"),
            data_contract=_string(data.get("data_contract"), "data_contract"),
            policy_contract=_string(data.get("policy_contract"), "policy_contract"),
            fixed_assumptions=copy.deepcopy(dict(fixed)),
            baseline=baseline,
            scenarios=scenarios,
        )
        _validate_envelope(envelope)
        return envelope


def _scenario(
    value: object, label: str, base_dir: Path, *, require_change: bool
) -> ComparisonScenario:
    data = _object(value, label)
    scenario_id = _string(data.get("id"), f"{label}.id")
    source_value = data.get("source", data.get("report"))
    source = PreparedReportSource.from_mapping(source_value, f"{label}.source")
    assumptions = _object(data.get("assumptions"), f"{label}.assumptions")
    change_value = data.get("change")
    if require_change and change_value is None:
        raise ValueError(f"{label}.change is required")
    change = {} if change_value is None else _object(change_value, f"{label}.change")
    if require_change:
        kind = change.get("kind")
        if kind not in _ASSUMPTION_KINDS:
            raise ValueError(f"{label}.change.kind must be cost, dividend, or fx")
    if not source.path.is_absolute():
        source = PreparedReportSource(base_dir / source.path, source.sha256)
    return ComparisonScenario(
        scenario_id, source, change, copy.deepcopy(dict(assumptions))
    )


def _validate_assumptions(
    baseline: ComparisonScenario, scenarios: Sequence[ComparisonScenario]
) -> None:
    expected_keys = set(_ASSUMPTION_KINDS)
    if set(baseline.assumptions) != expected_keys:
        raise ValueError("baseline assumptions must contain cost, dividend, and fx")
    _validate_path_keys(baseline.assumptions)
    for scenario in scenarios:
        if set(scenario.assumptions) != expected_keys:
            raise ValueError(
                f"scenario {scenario.scenario_id} assumptions must contain "
                "cost, dividend, and fx"
            )
        _validate_path_keys(scenario.assumptions)
        changed_leaves = tuple(
            (key,) + leaf
            for key in _ASSUMPTION_KINDS
            for leaf in _leaf_differences(
                baseline.assumptions[key], scenario.assumptions[key]
            )
        )
        declared = scenario.change.get("kind")
        if declared not in _ASSUMPTION_KINDS:
            raise ValueError(f"scenario {scenario.scenario_id} change.kind is invalid")
        if len(changed_leaves) != 1 or changed_leaves[0][0] != declared:
            raise ValueError(
                f"scenario {scenario.scenario_id} must change exactly one "
                "atomic assumption leaf"
            )
        changed_path = changed_leaves[0][1:]
        declared_path = scenario.change.get("path")
        if not isinstance(declared_path, str) or not declared_path:
            raise ValueError(f"scenario {scenario.scenario_id} change.path is required")
        if declared_path in {".".join(changed_path), ".".join(changed_leaves[0])}:
            pass
        else:
            raise ValueError(
                f"scenario {scenario.scenario_id} change.path does not match "
                "the atomic assumption leaf"
            )
        before = _at_path(baseline.assumptions[declared], changed_path)
        after = _at_path(scenario.assumptions[declared], changed_path)
        if not _json_equal(scenario.change.get("before"), before) or not _json_equal(
            scenario.change.get("after"), after
        ):
            raise ValueError(
                f"scenario {scenario.scenario_id} change before/after mismatch"
            )
    fingerprints: set[tuple[object, ...]] = set()
    for scenario in scenarios:
        fingerprint = _json_fingerprint(scenario.assumptions)
        if fingerprint in fingerprints:
            raise ValueError("scenarios must be semantically distinct")
        fingerprints.add(fingerprint)


def _change_record(
    baseline: ComparisonScenario, scenario: ComparisonScenario
) -> dict[str, object]:
    """Return the validated atomic change, deriving it from the changed leaf."""

    kind = cast(str, scenario.change["kind"])
    changed_paths = _leaf_differences(
        baseline.assumptions[kind], scenario.assumptions[kind]
    )
    if len(changed_paths) != 1:
        raise ValueError("scenario must change exactly one atomic assumption leaf")
    relative_path = changed_paths[0]
    before = _at_path(baseline.assumptions[kind], relative_path)
    after = _at_path(scenario.assumptions[kind], relative_path)
    record = copy.deepcopy(dict(scenario.change))
    record["atomic_path"] = ".".join((kind,) + relative_path)
    record["before"] = copy.deepcopy(before)
    record["after"] = copy.deepcopy(after)
    return record


def _component(payload: Mapping[str, object], name: str) -> Mapping[str, object]:
    value = _object(payload.get(name), f"report.{name}")
    availability = value.get("availability")
    if availability not in {"available", "unavailable"}:
        raise ValueError(f"report.{name}.availability is invalid")
    raw_value = value.get("value")
    if availability == "available":
        if raw_value is None:
            raise ValueError(f"report.{name}.value is required when available")
        _decimal(raw_value, f"report.{name}.value")
    elif raw_value is not None:
        raise ValueError(f"report.{name}.value must be null when unavailable")
    if value.get("unit") != "currency":
        raise ValueError(f"report.{name}.unit must be currency")
    evidence = value.get("evidence")
    resume = value.get("resume_inputs")
    if not isinstance(evidence, list) or not all(
        isinstance(item, str) for item in evidence
    ):
        raise ValueError(f"report.{name}.evidence must be an array of strings")
    if not isinstance(resume, list) or not all(
        isinstance(item, str) for item in resume
    ):
        raise ValueError(f"report.{name}.resume_inputs must be an array of strings")
    diagnostic = value.get("diagnostic_value")
    if diagnostic is not None:
        _decimal(diagnostic, f"report.{name}.diagnostic_value")
    currency = value.get("currency")
    if currency is not None and currency not in {"KRW", "USD"}:
        raise ValueError(f"report.{name}.currency is invalid")
    return value


def _load_source(source: PreparedReportSource) -> PreparedLossReport:
    body = source.path.read_bytes()
    actual = hashlib.sha256(body).hexdigest()
    if actual != source.sha256:
        raise ValueError(f"prepared report hash mismatch for {source.path}")
    payload = _parse_json(body, f"prepared report {source.path}")
    if payload.get("schema") != "prepared-loss-accounting-report/v1":
        raise ValueError("prepared report schema is unsupported")
    metadata = _object(payload.get("metadata"), "prepared report.metadata")
    report = _object(payload.get("report"), "prepared report.report")
    if report.get("status") not in {"complete", "blocked", "invalid"}:
        raise ValueError("prepared report.status is invalid")
    for name in _COMPONENTS:
        _component(report, name)
    return PreparedLossReport(source, actual, dict(metadata), dict(report))


def _validate_report_metadata(
    metadata: Mapping[str, object],
    envelope: ComparisonEnvelope,
    assumptions: Mapping[str, object],
) -> None:
    if metadata.get("market") != envelope.market:
        raise ValueError("prepared report market does not match envelope")
    if metadata.get("currency") != envelope.currency:
        raise ValueError("prepared report currency does not match envelope")
    period = _object(metadata.get("period"), "report.metadata.period")
    if (
        _iso_date(period.get("start"), "report.period.start") != envelope.period_start
        or _iso_date(period.get("end"), "report.period.end") != envelope.period_end
    ):
        raise ValueError("prepared report period does not match envelope")
    raw_sessions = _list(metadata.get("sessions"), "report.metadata.sessions")
    sessions = tuple(_iso_date(item, "report.session") for item in raw_sessions)
    if len(set(sessions)) != len(sessions) or sessions != envelope.sessions:
        raise ValueError("prepared report sessions do not match envelope")
    expected_capital = {
        "value": str(envelope.initial_capital),
        "currency": envelope.initial_capital_currency,
        "unit": "currency",
    }
    if not _json_equal(metadata.get("initial_capital"), expected_capital):
        raise ValueError("prepared report initial_capital does not match envelope")
    if metadata.get("research_grade") != envelope.research_grade:
        raise ValueError("prepared report research_grade does not match envelope")
    if metadata.get("data_contract") != envelope.data_contract:
        raise ValueError("prepared report data_contract does not match envelope")
    if metadata.get("policy_contract") != envelope.policy_contract:
        raise ValueError("prepared report policy_contract does not match envelope")
    if not _json_equal(metadata.get("fixed_assumptions"), envelope.fixed_assumptions):
        raise ValueError("prepared report fixed_assumptions does not match envelope")
    if not _json_equal(metadata.get("assumptions"), assumptions):
        raise ValueError("prepared report assumptions do not match scenario")


def _delta(
    baseline: Mapping[str, object], scenario: Mapping[str, object], name: str
) -> ComparisonDelta:
    base_availability = baseline["availability"]
    scenario_availability = scenario["availability"]
    base_currency = baseline.get("currency")
    scenario_currency = scenario.get("currency")
    base_unit = baseline.get("unit")
    scenario_unit = scenario.get("unit")
    base_evidence = tuple(
        str(item) for item in cast(list[object], baseline["evidence"])
    )
    scenario_evidence = tuple(
        str(item) for item in cast(list[object], scenario["evidence"])
    )
    evidence = base_evidence + scenario_evidence
    resume = tuple(
        str(item)
        for item in list(cast(list[object], baseline["resume_inputs"]))
        + list(cast(list[object], scenario["resume_inputs"]))
    )
    required_evidence = {
        "dividends": "provide complete dividend evidence for both reports",
        "fx": "provide complete FX evidence for both reports",
    }
    if base_availability != "available" or scenario_availability != "available":
        if not resume or all(not item.strip() for item in resume):
            resume = (f"resolve unavailable {name} evidence",)
        return ComparisonDelta("unavailable", None, evidence, resume, None, None)
    if name in required_evidence and (
        not base_evidence
        or not scenario_evidence
        or any(not item.strip() for item in evidence)
    ):
        return ComparisonDelta(
            "unavailable",
            None,
            evidence,
            resume + (required_evidence[name],),
            None,
            None,
        )
    if (
        base_currency is None
        or scenario_currency is None
        or base_currency != scenario_currency
        or base_unit != scenario_unit
    ):
        return ComparisonDelta(
            "unavailable",
            None,
            evidence + (f"{name} currency or unit mismatch",),
            resume + (f"provide matching {name} currency and unit",),
            None,
            None,
        )
    with localcontext(DECIMAL_CONTEXT):
        value = _decimal(scenario["value"], f"scenario.{name}.value") - _decimal(
            baseline["value"], f"baseline.{name}.value"
        )
    return ComparisonDelta(
        "available",
        value,
        evidence,
        resume,
        cast(str | None, base_currency),
        cast(str | None, base_unit),
    )


def _validate_envelope(envelope: ComparisonEnvelope) -> None:
    """Recheck invariants so direct dataclass construction cannot bypass them."""

    if envelope.market not in {"KR", "US"}:
        raise ValueError("market must be KR or US")
    expected_currency = "KRW" if envelope.market == "KR" else "USD"
    if envelope.currency != expected_currency:
        raise ValueError("currency does not match market")
    period_start = _iso_date(envelope.period_start, "period.start")
    period_end = _iso_date(envelope.period_end, "period.end")
    if period_start > period_end:
        raise ValueError("period.start is after period.end")
    sessions = tuple(_iso_date(session, "session") for session in envelope.sessions)
    if len(set(sessions)) != len(sessions):
        raise ValueError("sessions must be unique")
    if tuple(sorted(sessions)) != sessions:
        raise ValueError("sessions must be chronological")
    if any(session < period_start or session > period_end for session in sessions):
        raise ValueError("sessions must be within period")
    if _decimal(envelope.initial_capital, "initial_capital.value") <= 0:
        raise ValueError("initial_capital.value must be positive")
    if envelope.initial_capital_currency not in {"KRW", "USD"}:
        raise ValueError("initial_capital currency must be KRW or USD")
    _string(envelope.research_grade, "research_grade")
    _string(envelope.data_contract, "data_contract")
    _string(envelope.policy_contract, "policy_contract")
    if not isinstance(envelope.fixed_assumptions, Mapping):
        raise ValueError("fixed_assumptions must be an object")
    if set(envelope.fixed_assumptions) != set(_ASSUMPTION_KINDS):
        raise ValueError("fixed_assumptions must contain cost, dividend, and fx")
    if not 1 <= len(envelope.scenarios) <= MAX_SCENARIOS:
        raise ValueError(f"scenarios must contain 1 to {MAX_SCENARIOS} items")
    for item in (envelope.baseline,) + envelope.scenarios:
        _string(item.scenario_id, "scenario.id")
    ids = (envelope.baseline.scenario_id,) + tuple(
        item.scenario_id for item in envelope.scenarios
    )
    if len(set(ids)) != len(ids):
        raise ValueError("scenario IDs must be unique")
    for item in (envelope.baseline,) + envelope.scenarios:
        if not isinstance(item.source.path, Path):
            raise ValueError("source.path must be a path")
        if not isinstance(item.change, Mapping):
            raise ValueError("scenario.change must be an object")
        if not isinstance(item.assumptions, Mapping):
            raise ValueError("scenario.assumptions must be an object")
        _sha256(item.source.sha256, "source.sha256")
    _validate_assumptions(envelope.baseline, envelope.scenarios)


def compare_prepared_reports(envelope: ComparisonEnvelope) -> dict[str, object]:
    """Return component deltas for an already validated comparison envelope."""

    _validate_envelope(envelope)
    baseline = _load_source(envelope.baseline.source)
    scenarios = tuple(_load_source(item.source) for item in envelope.scenarios)
    _validate_report_metadata(
        baseline.metadata, envelope, envelope.baseline.assumptions
    )
    for scenario, report in zip(envelope.scenarios, scenarios, strict=True):
        _validate_report_metadata(report.metadata, envelope, scenario.assumptions)
    reports = (baseline,) + scenarios
    status: Literal["complete", "blocked"] = "complete"
    if any(report.payload["status"] != "complete" for report in reports):
        status = "blocked"
    comparisons: list[dict[str, object]] = []
    for scenario, report in zip(envelope.scenarios, scenarios, strict=True):
        deltas = {
            name: _delta(
                _component(baseline.payload, name),
                _component(report.payload, name),
                name,
            ).as_dict()
            for name in _COMPONENTS
        }
        if any(item["availability"] != "available" for item in deltas.values()):
            status = "blocked"
        comparisons.append(
            {
                "id": scenario.scenario_id,
                "source": {
                    "path": str(scenario.source.path),
                    "sha256": report.source_sha256,
                },
                "change": _change_record(envelope.baseline, scenario),
                "assumptions": copy.deepcopy(dict(scenario.assumptions)),
                "metadata": copy.deepcopy(report.metadata),
                "report": copy.deepcopy(report.payload),
                "deltas": deltas,
            }
        )
    return {
        "schema": "market-counterfactual-comparison-result/v1",
        "status": status,
        "market": envelope.market,
        "period": {"start": envelope.period_start, "end": envelope.period_end},
        "sessions": list(envelope.sessions),
        "currency": envelope.currency,
        "initial_capital": {
            "value": str(envelope.initial_capital),
            "currency": envelope.initial_capital_currency,
            "unit": "currency",
        },
        "research_grade": envelope.research_grade,
        "data_contract": envelope.data_contract,
        "policy_contract": envelope.policy_contract,
        "fixed_assumptions": copy.deepcopy(dict(envelope.fixed_assumptions)),
        "baseline": {
            "id": envelope.baseline.scenario_id,
            "source": {
                "path": str(envelope.baseline.source.path),
                "sha256": baseline.source_sha256,
            },
            "assumptions": copy.deepcopy(dict(envelope.baseline.assumptions)),
            "metadata": copy.deepcopy(baseline.metadata),
            "report": copy.deepcopy(baseline.payload),
        },
        "comparisons": comparisons,
        "contract": {
            "preserves_reports": True,
            "delta_only": True,
            "aggregates": False,
            "economic_evaluation": "not-evaluated",
        },
    }


def load_comparison_envelope(path: Path) -> ComparisonEnvelope:
    """Read and validate one envelope; report files are loaded only on compare."""

    body = path.read_bytes()
    return ComparisonEnvelope.from_mapping(
        _parse_json(body, f"comparison envelope {path}"), base_dir=path.parent
    )


def _paths_alias(first: Path, second: Path) -> bool:
    if first.resolve() == second.resolve():
        return True
    if not first.exists() or not second.exists():
        return False
    try:
        return first.samefile(second)
    except OSError:
        return False


def compare_saved_reports(envelope_path: Path, output_path: Path) -> dict[str, object]:
    """Compare reports referenced by ``envelope_path`` and write one result."""

    envelope = load_comparison_envelope(envelope_path)
    sources = (envelope.baseline.source,) + tuple(
        scenario.source for scenario in envelope.scenarios
    )
    input_paths = (envelope_path,) + tuple(source.path for source in sources)
    if any(_paths_alias(output_path, input_path) for input_path in input_paths):
        raise ValueError("output path must not overwrite an input")
    result = compare_prepared_reports(envelope)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, required=True, help="comparison envelope JSON"
    )
    parser.add_argument("--output", type=Path, required=True, help="result JSON")
    args = parser.parse_args()
    compare_saved_reports(args.input, args.output)
    return 0


__all__ = [
    "ComparisonDelta",
    "ComparisonEnvelope",
    "ComparisonScenario",
    "MAX_SCENARIOS",
    "PreparedLossReport",
    "PreparedReportSource",
    "compare_prepared_reports",
    "compare_saved_reports",
    "load_comparison_envelope",
]


if __name__ == "__main__":
    raise SystemExit(_main())
