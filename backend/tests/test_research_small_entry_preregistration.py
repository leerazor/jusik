from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from jusik.research_small_entry_preregistration import (
    HISTORICAL_DISTRIBUTION_SHA256,
    ORIGINAL_UNHELD_PREREGISTRATION_SHA256,
    SmallEntryPreregistrationDraft,
    canonical_bytes,
    canonical_json,
    classify_entry,
    draft_sha256,
    main,
    missing_decisions,
    write_draft,
)


def test_default_is_fixed_immutable_draft_with_missing_decisions() -> None:
    draft = SmallEntryPreregistrationDraft()
    assert draft.status == "draft"
    assert draft.runtime_activation_allowed is False
    assert draft.reused_data is True
    assert draft.historical_context_only is True
    assert draft.prospective_validation_eligible is False
    assert draft.historical_small_entry_preregistration_found is False
    assert draft.threshold_krw is None
    assert draft.approval_time is None
    assert draft.future_period_start is None
    assert draft.future_period_end is None
    assert (
        draft.provenance.entry_amount_distribution_sha256
        == HISTORICAL_DISTRIBUTION_SHA256
    )
    assert (
        draft.provenance.original_unheld_preregistration_sha256
        == ORIGINAL_UNHELD_PREREGISTRATION_SHA256
    )
    assert missing_decisions(draft)["missing"] == [
        "threshold_krw",
        "approval_time",
        "future_period_start",
        "future_period_end",
    ]
    with pytest.raises(ValidationError):
        SmallEntryPreregistrationDraft.model_validate({"status": "registered"})


@pytest.mark.parametrize("value", [True, False, 0, -1, "NaN", "Infinity", "-Infinity"])
def test_threshold_rejects_nonpositive_bool_and_nonfinite(value: object) -> None:
    with pytest.raises(ValidationError):
        SmallEntryPreregistrationDraft(threshold_krw=value)


def test_threshold_accepts_finite_decimal_and_canonicalizes_forms() -> None:
    first = SmallEntryPreregistrationDraft(threshold_krw=Decimal("1000.00"))
    second = SmallEntryPreregistrationDraft(threshold_krw=Decimal("1E+3"))
    assert first.threshold_krw == second.threshold_krw == Decimal("1000")
    assert canonical_bytes(first) == canonical_bytes(second)


def test_time_requires_awareness_converts_offset_and_checks_order() -> None:
    with pytest.raises(ValidationError):
        SmallEntryPreregistrationDraft(approval_time=datetime(2026, 1, 1))
    for field in ("future_period_start", "future_period_end"):
        with pytest.raises(ValidationError):
            SmallEntryPreregistrationDraft.model_validate(
                {field: "2026-01-01T00:00:00"}
            )
    start = datetime(2026, 1, 2, tzinfo=UTC)
    end = datetime(2026, 1, 3, tzinfo=UTC)
    draft = SmallEntryPreregistrationDraft(
        approval_time=datetime(2026, 1, 1, 9, tzinfo=UTC),
        future_period_start=start,
        future_period_end=end,
    )
    assert draft.approval_time is not None and draft.approval_time.tzinfo is UTC
    offset = SmallEntryPreregistrationDraft(
        approval_time=datetime(2026, 1, 1, 18, tzinfo=timezone(timedelta(hours=9))),
        future_period_start=datetime(
            2026, 1, 2, 9, tzinfo=timezone(timedelta(hours=9))
        ),
        future_period_end=end,
    )
    assert canonical_bytes(draft) == canonical_bytes(offset)
    for payload in (
        {"approval_time": start, "future_period_start": start},
        {"future_period_start": end, "future_period_end": end},
        {"future_period_start": end, "future_period_end": start},
    ):
        with pytest.raises(ValidationError):
            SmallEntryPreregistrationDraft(**payload)


def test_partial_nulls_and_fully_populated_values_remain_draft() -> None:
    partial = SmallEntryPreregistrationDraft(
        threshold_krw=1000,
        future_period_start=datetime(2026, 1, 2, tzinfo=UTC),
    )
    assert partial.status == "draft"
    full = SmallEntryPreregistrationDraft(
        threshold_krw=1000,
        approval_time=datetime(2026, 1, 1, tzinfo=UTC),
        future_period_start=datetime(2026, 1, 2, tzinfo=UTC),
        future_period_end=datetime(2026, 1, 3, tzinfo=UTC),
    )
    assert full.status == "draft" and full.runtime_activation_allowed is False
    with pytest.raises(ValidationError):
        SmallEntryPreregistrationDraft(status="registered")
    with pytest.raises(ValidationError):
        SmallEntryPreregistrationDraft(runtime_activation_allowed=True)


def test_fixed_hashes_and_unknown_fields_are_rejected() -> None:
    for field in (
        "entry_amount_distribution_sha256",
        "original_unheld_preregistration_sha256",
    ):
        with pytest.raises(ValidationError):
            SmallEntryPreregistrationDraft.model_validate(
                {"provenance": {field: "0" * 63}}
            )
        with pytest.raises(ValidationError):
            SmallEntryPreregistrationDraft.model_validate(
                {"provenance": {field: "z" * 64}}
            )
        with pytest.raises(ValidationError):
            SmallEntryPreregistrationDraft.model_validate(
                {"provenance": {field: "0" * 64}}
            )
    with pytest.raises(ValidationError):
        SmallEntryPreregistrationDraft.model_validate({"unexpected_field": 1})
    with pytest.raises(ValidationError):
        SmallEntryPreregistrationDraft.model_validate({"provenance": {"unknown": 1}})


def test_canonical_json_is_sorted_compact_utf8_and_self_hash_excluded() -> None:
    assert canonical_json({"z": 1, "a": "한글", "sha256": "ignored"}) == (
        '{"a":"한글","z":1}'.encode()
    )
    draft = SmallEntryPreregistrationDraft()
    assert draft_sha256(draft) != ORIGINAL_UNHELD_PREREGISTRATION_SHA256
    changed = SmallEntryPreregistrationDraft(threshold_krw=Decimal("1"))
    assert draft_sha256(changed) != draft_sha256(draft)
    long_value = Decimal("123456789012345678901234567890.12345678901234567890")
    assert json.loads(
        canonical_bytes(SmallEntryPreregistrationDraft(threshold_krw=long_value))
    )["threshold_krw"] == ("123456789012345678901234567890.1234567890123456789")


def test_entry_classification_and_notional_accounting() -> None:
    assert classify_entry(0) == "new_entry"
    assert classify_entry(Decimal("2")) == "additional_buy"
    assert classify_entry(None) == "unknown"
    assert classify_entry(-1) == "unknown"


def test_forged_model_copy_is_rejected_before_canonical_export(tmp_path: Path) -> None:
    draft = SmallEntryPreregistrationDraft()
    forged_status = draft.model_copy(update={"status": "registered"})
    forged_activation = draft.model_copy(update={"runtime_activation_allowed": True})
    forged_limits = draft.risk_limits.model_copy(
        update={"user_max_loss_pct": Decimal("999")}
    )
    forged_nested = draft.model_copy(update={"risk_limits": forged_limits})
    for forged in (forged_status, forged_activation, forged_nested):
        with pytest.raises(ValidationError):
            canonical_bytes(forged)
        with pytest.raises(ValidationError):
            write_draft(forged, tmp_path / "forged")


def test_cli_writes_three_files_and_refuses_nonempty_output(tmp_path: Path) -> None:
    output = tmp_path / "draft"
    assert main(["--output-dir", str(output)]) == 0
    assert {path.name for path in output.iterdir()} == {
        "draft.json",
        "draft.sha256",
        "missing-decisions.json",
    }
    body = (output / "draft.json").read_bytes()
    assert json.loads(body) == SmallEntryPreregistrationDraft().model_dump(mode="json")
    digest = (output / "draft.sha256").read_text(encoding="ascii").strip()
    assert digest == draft_sha256(SmallEntryPreregistrationDraft())
    assert main(["--output-dir", str(output)]) == 2
    nonempty = tmp_path / "nonempty"
    nonempty.mkdir()
    (nonempty / "existing").write_text("x", encoding="utf-8")
    assert main(["--output-dir", str(nonempty)]) == 2


def test_cli_accepts_input_json_and_preserves_draft(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    input_path.write_text(
        json.dumps(
            SmallEntryPreregistrationDraft(threshold_krw=Decimal("42")).model_dump(
                mode="json"
            ),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    output = tmp_path / "output"
    assert main(["--input", str(input_path), "--output-dir", str(output)]) == 0
    result = json.loads((output / "draft.json").read_text(encoding="utf-8"))
    assert result["threshold_krw"] == "42"
    assert result["status"] == "draft"


def test_cli_full_input_roundtrips_canonical_bytes(tmp_path: Path) -> None:
    full = SmallEntryPreregistrationDraft(
        threshold_krw=Decimal("1000.00"),
        approval_time=datetime(2026, 1, 1, 9, tzinfo=UTC),
        future_period_start=datetime(
            2026, 1, 2, 18, tzinfo=timezone(timedelta(hours=9))
        ),
        future_period_end=datetime(2026, 1, 3, tzinfo=UTC),
    )
    input_path = tmp_path / "full.json"
    input_path.write_bytes(canonical_bytes(full))
    output = tmp_path / "full-output"
    assert main(["--input", str(input_path), "--output-dir", str(output)]) == 0
    assert (output / "draft.json").read_bytes() == canonical_bytes(full)


def test_nested_protocol_fields_are_fixed() -> None:
    with pytest.raises(ValidationError):
        SmallEntryPreregistrationDraft.model_validate(
            {"evaluation": {"metrics": ["net_return_pct"]}}
        )
    with pytest.raises(ValidationError):
        SmallEntryPreregistrationDraft.model_validate(
            {"control": {"new_entry_floor_krw": 1}}
        )
