from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import jusik.research_experiment_guard as guard
from jusik.research_experiment_guard import (
    sha256_file,
    verify_control_output,
    verify_hashes,
    verify_unheld_entry_source,
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_hash_checks_are_read_only(tmp_path: Path) -> None:
    path = tmp_path / "source.py"
    path.write_bytes(b"source\n")
    before = path.read_bytes()
    assert sha256_file(path) == _digest(path)
    verify_hashes({path: _digest(path)})
    assert path.read_bytes() == before


@pytest.mark.parametrize("kind", ["missing", "mismatch"])
def test_hash_checks_reject_missing_or_mismatched_file(
    tmp_path: Path, kind: str
) -> None:
    path = tmp_path / "source.py"
    path.write_bytes(b"source\n")
    target = path if kind == "mismatch" else tmp_path / "missing.py"
    digest = "0" * 64 if kind == "mismatch" else "a" * 64
    with pytest.raises(ValueError):
        verify_hashes({target: digest})


def test_unheld_entry_allows_only_the_anchor_line(tmp_path: Path) -> None:
    original = tmp_path / "original.py"
    variant = tmp_path / "variant.py"
    original.write_text(
        "                                target_weight > 0\n"
        "                                and abs(actual - target_weight)",
        encoding="utf-8",
    )
    variant.write_text(
        "                                target_weight > 0\n"
        "                                and positions[symbol] > 0\n"
        "                                and abs(actual - target_weight)",
        encoding="utf-8",
    )
    verify_unheld_entry_source(original, variant, _digest(original), _digest(variant))


def test_unheld_entry_uses_the_real_engine_as_read_only_original(
    tmp_path: Path,
) -> None:
    engine = Path(__file__).parents[1] / "jusik" / "research_portfolio_engine.py"
    original = tmp_path / "research_portfolio_engine.py"
    variant = tmp_path / "research_portfolio_engine_variant.py"
    source = engine.read_bytes()
    original.write_bytes(source)
    needle = b"                                and abs(actual - target_weight)"
    replacement = (
        b"                                and positions[symbol] > 0\n" + needle
    )
    assert source.count(needle) == 1
    variant.write_bytes(source.replace(needle, replacement, 1))
    verify_unheld_entry_source(original, variant, _digest(original), _digest(variant))
    assert engine.read_bytes() == source


def test_unheld_entry_rejects_duplicate_anchor_and_extra_change(tmp_path: Path) -> None:
    original = tmp_path / "original.py"
    variant = tmp_path / "variant.py"
    original.write_text(
        "                                target_weight > 0\n"
        "                                and abs(actual - target_weight)",
        encoding="utf-8",
    )
    variant.write_text(
        "                                target_weight > 0\n"
        "                                and abs(actual - target_weight)\n"
        "                                and positions[symbol] > 0",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unexpected"):
        verify_unheld_entry_source(
            original, variant, _digest(original), _digest(variant)
        )
    original.write_text(
        "                                target_weight > 0\n"
        "                                and abs(actual - target_weight)\n"
        "                                target_weight > 0\n"
        "                                and abs(actual - target_weight)",
        encoding="utf-8",
    )
    variant.write_text(
        "                                target_weight > 0\n"
        "                                and positions[symbol] > 0\n"
        "                                and abs(actual - target_weight)\n"
        "                                target_weight > 0\n"
        "                                and abs(actual - target_weight)",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unique"):
        verify_unheld_entry_source(
            original, variant, _digest(original), _digest(variant)
        )


def test_control_output_requires_whole_strict_json_match(tmp_path: Path) -> None:
    expected_path = tmp_path / "control.json"
    expected_path.write_text(
        json.dumps(
            {
                "trades": [
                    {"quantity": 1, "side": "buy"},
                    {"quantity": 2, "side": "sell"},
                ],
                "events": [
                    {"kind": "band_skip", "detail": "NVDA"},
                    {"kind": "risk_exit", "detail": "limit"},
                ],
            }
        ),
        encoding="utf-8",
    )
    actual = {
        "trades": [
            {"quantity": 1, "side": "buy"},
            {"quantity": 2, "side": "sell"},
        ],
        "events": [
            {"kind": "band_skip", "detail": "NVDA"},
            {"kind": "risk_exit", "detail": "limit"},
        ],
    }
    verify_control_output(actual, expected_path, _digest(expected_path))

    changed_outputs = [
        {
            **actual,
            "trades": [{"quantity": 3, "side": "buy"}, actual["trades"][1]],
        },
        {
            **actual,
            "events": [
                {"kind": "band_skip", "detail": "OTHER"},
                actual["events"][1],
            ],
        },
        {
            **actual,
            "trades": list(reversed(actual["trades"])),
            "events": list(reversed(actual["events"])),
        },
    ]
    for changed in changed_outputs:
        with pytest.raises(ValueError, match="differs"):
            verify_control_output(changed, expected_path, _digest(expected_path))

    with pytest.raises(ValueError, match="differs"):
        verify_control_output(
            {
                **actual,
                "trades": [{"quantity": True, "side": "buy"}, actual["trades"][1]],
            },
            expected_path,
            _digest(expected_path),
        )


def test_control_output_reads_expected_file_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected_path = tmp_path / "control.json"
    expected_path.write_text('{"events": []}', encoding="utf-8")
    original_read = guard._read
    reads: list[Path] = []

    def read_once(path: Path) -> bytes:
        reads.append(path)
        return original_read(path)

    monkeypatch.setattr(guard, "_read", read_once)
    verify_control_output({"events": []}, expected_path, _digest(expected_path))
    assert reads == [expected_path]


def test_control_output_rejects_nan_and_duplicate_keys(tmp_path: Path) -> None:
    expected_path = tmp_path / "control.json"
    expected_path.write_text('{"events": NaN}', encoding="utf-8")
    with pytest.raises(ValueError, match="non-finite"):
        verify_control_output({"events": None}, expected_path, _digest(expected_path))
    expected_path.write_text('{"events": [], "events": []}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        verify_control_output({"events": []}, expected_path, _digest(expected_path))
