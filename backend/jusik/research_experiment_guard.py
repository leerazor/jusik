"""Read-only checks for the isolated portfolio experiment."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def _read(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except (OSError, ValueError) as error:
        raise ValueError(f"required file is unavailable: {path}") from error


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of *path* without changing it."""

    return hashlib.sha256(_read(path)).hexdigest()


def verify_hashes(expected: Mapping[Path, str]) -> None:
    """Require every path to exist and match its expected SHA-256 digest."""

    for path, digest in expected.items():
        if (
            not isinstance(digest, str)
            or len(digest) != hashlib.sha256().digest_size * 2
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError(f"invalid expected SHA-256 digest for {path}")
        actual = sha256_file(path)
        if actual != digest:
            raise ValueError(f"SHA-256 mismatch: {path}")


_ANCHOR = b"                                and positions[symbol] > 0\n"
_BAND_CONDITION = (
    b"                                target_weight > 0\n"
    b"                                and abs(actual - target_weight)"
)
_BAND_CONDITION_VARIANT = (
    b"                                target_weight > 0\n"
    + _ANCHOR
    + b"                                and abs(actual - target_weight)"
)


def _verify_bytes_hash(body: bytes, path: Path, expected: str) -> None:
    if (
        not isinstance(expected, str)
        or len(expected) != hashlib.sha256().digest_size * 2
        or any(character not in "0123456789abcdef" for character in expected)
    ):
        raise ValueError(f"invalid expected SHA-256 digest for {path}")
    if hashlib.sha256(body).hexdigest() != expected:
        raise ValueError(f"SHA-256 mismatch: {path}")


def verify_unheld_entry_source(
    original: Path,
    variant: Path,
    expected_original_sha256: str,
    expected_variant_sha256: str,
) -> None:
    """Verify that the variant adds only the unheld-entry band guard.

    Both files are hash checked first.  The source comparison then permits the
    exact anchor at the portfolio engine's unique band condition and requires
    the complete resulting bytes to be identical.
    """

    original_bytes = _read(original)
    variant_bytes = _read(variant)
    _verify_bytes_hash(original_bytes, original, expected_original_sha256)
    _verify_bytes_hash(variant_bytes, variant, expected_variant_sha256)
    if original_bytes.count(_BAND_CONDITION) != 1:
        raise ValueError("original source must contain one unique band condition")
    if original_bytes.count(_ANCHOR) != 0:
        raise ValueError("original source already contains the band anchor")
    expected_variant = original_bytes.replace(
        _BAND_CONDITION, _BAND_CONDITION_VARIANT, 1
    )
    if variant_bytes != expected_variant:
        raise ValueError("variant contains an unexpected source change")


def _reject_constant(value: str) -> Any:
    raise ValueError(f"non-finite JSON constant is forbidden: {value}")


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _strict_json(body: bytes, path: Path) -> object:
    try:
        return json.loads(
            body.decode("utf-8"),
            parse_constant=_reject_constant,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"expected output is not valid JSON: {path}") from error


def _same_json(
    left: object,
    right: object,
    location: str = "$",
) -> bool:
    """Compare JSON values while keeping booleans distinct from numbers."""

    if type(left) is not type(right):
        return False
    if isinstance(left, float) and not math.isfinite(left):
        return False
    if isinstance(right, float) and not math.isfinite(right):
        return False
    if isinstance(left, dict):
        assert isinstance(right, dict)
        return set(left) == set(right) and all(
            _same_json(left[key], right[key], f"{location}.{key}") for key in left
        )
    if isinstance(left, list):
        assert isinstance(right, list)
        return len(left) == len(right) and all(
            _same_json(item, other, f"{location}[{index}]")
            for index, (item, other) in enumerate(zip(left, right, strict=True))
        )
    return left == right


def verify_control_output(
    actual: dict[str, object], expected_path: Path, expected_sha256: str
) -> None:
    """Verify the complete, strictly typed JSON control output."""

    if not isinstance(actual, dict):
        raise ValueError("control output must be a JSON object")
    expected_bytes = _read(expected_path)
    _verify_bytes_hash(expected_bytes, expected_path, expected_sha256)
    expected = _strict_json(expected_bytes, expected_path)
    if not isinstance(expected, dict):
        raise ValueError("expected control output must be a JSON object")
    if not _same_json(actual, expected):
        raise ValueError("control output differs from expected JSON")
