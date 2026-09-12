"""Validate the archived small-entry draft provenance bundle.

The validator is an offline, read-only audit.  It verifies the archive
manifest before parsing the three role-bound artifacts, revalidates the draft
with the existing draft model, and emits a path-free public result.  It never
opens arbitrary manifest entries and it has no database, network, or trading
side effects.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import NoReturn

from pydantic import ValidationError

from jusik.research_small_entry_preregistration import (
    HISTORICAL_DISTRIBUTION_SHA256,
    ORIGINAL_UNHELD_PREREGISTRATION_SHA256,
    SmallEntryPreregistrationDraft,
    canonical_bytes,
    draft_sha256,
)

MANIFEST_SHA256 = "937e98f457829699ef5dd4b2f8a713a9ae11a0a3136546e74607bccf558fa45e"
DRAFT_SHA256 = "71691f864ccc0e61e351b52298027e6df4e8c864ab9c15f16ae0887bbfe35dbb"
ARCHIVE_MANIFEST_SHA256 = MANIFEST_SHA256
CANONICAL_DRAFT_SHA256 = DRAFT_SHA256
ARCHIVE_ROOT = Path(
    "/home/kwl/.local/share/jusik/portfolio-audit/"
    "small-entry-preregistration-draft-v1-a55b6ee8a036463da688fafe04567542"
)

ROLE_DRAFT = "draft"
ROLE_DISTRIBUTION = "historical_distribution"
ROLE_PREREGISTRATION = "historical_preregistration"
ROLE_RELATIVE_PATHS = {
    ROLE_DRAFT: Path("draft/draft.json"),
    ROLE_DISTRIBUTION: Path("historical-context/distribution.json"),
    ROLE_PREREGISTRATION: Path("historical-context/preregistration.json"),
}
_ROLE_ORDER = (ROLE_DRAFT, ROLE_DISTRIBUTION, ROLE_PREREGISTRATION)
_HEX_DIGEST_LENGTH = 64


class BundleValidationError(ValueError):
    """Raised when an archive is not the pinned provenance bundle."""


def _fail(message: str) -> NoReturn:
    raise BundleValidationError(message)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == _HEX_DIGEST_LENGTH
        and all(char in "0123456789abcdef" for char in value)
    )


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _fail(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _json_bytes(data: bytes, label: str) -> object:
    try:
        return json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda value: _fail(
                f"non-finite JSON number in {label}: {value}"
            ),
        )
    except BundleValidationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError):
        _fail(f"invalid JSON in {label}")


def _absolute_path(path: Path) -> Path:
    # absolute() is intentionally used instead of resolve(): resolving would
    # erase a symlink that must be rejected and would change manifest identity.
    if ".." in path.parts:
        _fail("dot-dot path components are not allowed")
    return path.absolute()


def _ensure_no_symlink_ancestors(path: Path, label: str) -> None:
    current = Path(path.anchor)
    for component in path.parts[1:]:
        current /= component
        if current.is_symlink():
            _fail(f"{label} has a symlink path component")


def _ensure_real_file(path: Path, label: str) -> None:
    try:
        if path.is_symlink():
            _fail(f"{label} is a symlink")
        if not path.is_file():
            _fail(f"{label} is not a regular file")
        stat = path.stat()
    except OSError as exc:
        _fail(f"cannot inspect {label}: {exc}")
    if not stat:
        _fail(f"cannot inspect {label}")


def _ensure_root(root: Path) -> Path:
    root = _absolute_path(root)
    _ensure_no_symlink_ancestors(root, "bundle root")
    if not root.is_dir():
        _fail("bundle root is not a directory")
    return root


def _ensure_path_components(root: Path, path: Path, label: str) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError:
        _fail(f"{label} is outside the bundle root")
    current = root
    for component in relative.parts:
        current /= component
        if current.is_symlink():
            _fail(f"{label} has a symlink path component")


def _read_fixed_file(root: Path, relative: Path, label: str) -> bytes:
    path = root / relative
    _ensure_path_components(root, path, label)
    _ensure_real_file(path, label)
    try:
        return path.read_bytes()
    except OSError as exc:
        _fail(f"cannot read {label}: {exc}")


def _read_manifest(root: Path) -> tuple[bytes, list[dict[str, str]]]:
    raw = _read_fixed_file(root, Path("manifest.json"), "manifest")
    if _sha256(raw) != MANIFEST_SHA256:
        _fail("manifest SHA-256 does not match the pinned archive")
    payload = _json_bytes(raw, "manifest")
    if not isinstance(payload, list):
        _fail("manifest must be an array")
    entries: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    for item in payload:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            _fail("manifest entries must contain exactly path and sha256")
        path, digest = item["path"], item["sha256"]
        if not isinstance(path, str) or not path.startswith("/"):
            _fail("manifest paths must be absolute")
        if path in seen_paths:
            _fail("manifest contains duplicate paths")
        seen_paths.add(path)
        if not _is_digest(digest):
            _fail("manifest contains an invalid SHA-256")
        entries.append({"path": path, "sha256": digest})
    return raw, entries


def _role_entries(
    root: Path, entries: list[dict[str, str]]
) -> dict[str, dict[str, str]]:
    expected = {
        role: str(_absolute_path(ARCHIVE_ROOT / relative))
        for role, relative in ROLE_RELATIVE_PATHS.items()
    }
    found: dict[str, dict[str, str]] = {}
    for entry in entries:
        for role, path in expected.items():
            if entry["path"] == path:
                if role in found:
                    _fail(f"manifest contains duplicate role: {role}")
                found[role] = entry
                break
    missing = [role for role in _ROLE_ORDER if role not in found]
    if missing:
        _fail(f"manifest is missing role: {missing[0]}")
    return found


def _manifest_digest(role: str, role_entry: dict[str, str]) -> str:
    expected = {
        ROLE_DRAFT: DRAFT_SHA256,
        ROLE_DISTRIBUTION: HISTORICAL_DISTRIBUTION_SHA256,
        ROLE_PREREGISTRATION: ORIGINAL_UNHELD_PREREGISTRATION_SHA256,
    }[role]
    if role_entry["sha256"] != expected:
        _fail(f"manifest digest for {role} does not match the pinned source")
    return expected


def _output_directory(output_dir: Path, root: Path) -> Path:
    output_dir = _absolute_path(output_dir)
    _ensure_no_symlink_ancestors(output_dir, "output directory")
    if output_dir == root or root in output_dir.parents:
        _fail("output directory must be outside the input bundle")
    current = output_dir
    missing: list[Path] = []
    while not current.exists():
        missing.append(current)
        if current.parent == current:
            _fail("output directory has no existing parent")
        current = current.parent
    if current.is_symlink():
        _fail("output directory has a symlink parent")
    for parent in missing:
        if parent.is_symlink():
            _fail("output directory has a symlink path component")
    if output_dir.exists():
        if output_dir.is_symlink() or not output_dir.is_dir():
            _fail("output directory is not a real directory")
        if any(output_dir.iterdir()):
            _fail("output directory must be empty")
    else:
        output_dir.mkdir(parents=False)
    return output_dir


@dataclass(frozen=True)
class BundleValidation:
    """Verified identities and flags safe for public publication."""

    manifest_sha256: str
    raw_sha256: dict[str, str]
    canonical_draft_sha256: str
    draft_identity: str
    historical_identities: dict[str, str]
    historical_data_reused: bool = True
    prospective_validation_eligible: bool = False
    status: str = "draft"
    runtime_activation_allowed: bool = False
    _bundle_root: Path = field(default=Path("."), repr=False, compare=False)

    @property
    def public_manifest(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "status": self.status,
            "runtime_activation_allowed": self.runtime_activation_allowed,
            "historical_data_reused": self.historical_data_reused,
            "prospective_validation_eligible": self.prospective_validation_eligible,
            "roles": {
                role: {
                    "raw_sha256": self.raw_sha256[role],
                    **(
                        {"canonical_sha256": self.canonical_draft_sha256}
                        if role == ROLE_DRAFT
                        else {}
                    ),
                }
                for role in _ROLE_ORDER
            },
            "identities": {
                "draft_canonical_sha256": self.draft_identity,
                "historical_distribution_sha256": self.historical_identities[
                    ROLE_DISTRIBUTION
                ],
                "historical_preregistration_sha256": self.historical_identities[
                    ROLE_PREREGISTRATION
                ],
                "draft_is_separate_from_historical_preregistration": True,
            },
            "verification": {
                "manifest_sha256": self.manifest_sha256,
                "manifest_pinned": True,
                "source_sha256_pinned": True,
                "canonical_draft_sha256_pinned": True,
                "draft_model_valid": True,
            },
        }

    def public_manifest_bytes(self) -> bytes:
        return _canonical_json(self.public_manifest)

    def public_report_bytes(self) -> bytes:
        lines = [
            "# 작은 진입 초안 provenance 검증 보고서",
            "",
            "- 상태: `draft`",
            "- 런타임 활성화 허용: `false`",
            "- 역사 자료 재사용: `true`",
            "- 전향 검증 적격: `false`",
            "",
            "## 검증된 역할",
            "",
        ]
        labels = {
            ROLE_DRAFT: "초안",
            ROLE_DISTRIBUTION: "역사 진입 금액 분포",
            ROLE_PREREGISTRATION: "역사 원본 preregistration",
        }
        for role in _ROLE_ORDER:
            lines.append(f"- {labels[role]} raw SHA-256: `{self.raw_sha256[role]}`")
        lines.extend(
            [
                f"- 초안 canonical SHA-256: `{self.canonical_draft_sha256}`",
                "- 초안 identity와 역사 원본 identity는 별개입니다.",
                "- 모든 검증을 통과했지만 활성화 가능한 등록으로 승격하지 않습니다.",
                "",
            ]
        )
        return "\n".join(lines).encode("utf-8")


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        + b"\n"
    )


def validate_bundle(bundle_root: Path) -> BundleValidation:
    """Validate one pinned archive without reading arbitrary manifest paths."""

    root = _ensure_root(bundle_root)
    manifest_raw, entries = _read_manifest(root)
    roles = _role_entries(root, entries)
    for role in _ROLE_ORDER:
        _manifest_digest(role, roles[role])

    raw_by_role: dict[str, bytes] = {
        role: _read_fixed_file(root, ROLE_RELATIVE_PATHS[role], role)
        for role in _ROLE_ORDER
    }
    raw_sha256 = {role: _sha256(raw_by_role[role]) for role in _ROLE_ORDER}
    for role in _ROLE_ORDER:
        if raw_sha256[role] != roles[role]["sha256"]:
            _fail(f"raw SHA-256 mismatch for {role}")
    if raw_sha256[ROLE_DRAFT] != DRAFT_SHA256:
        _fail("draft raw SHA-256 does not match the pinned draft")
    if raw_sha256[ROLE_DISTRIBUTION] != HISTORICAL_DISTRIBUTION_SHA256:
        _fail("historical distribution SHA-256 does not match the pinned source")
    if raw_sha256[ROLE_PREREGISTRATION] != ORIGINAL_UNHELD_PREREGISTRATION_SHA256:
        _fail("historical preregistration SHA-256 does not match the pinned source")

    # Parse each role after raw identity checks so duplicate keys cannot hide
    # in a synthetic replacement of a pinned source.
    _json_bytes(raw_by_role[ROLE_DISTRIBUTION], ROLE_DISTRIBUTION)
    historical_payload = _json_bytes(
        raw_by_role[ROLE_PREREGISTRATION], ROLE_PREREGISTRATION
    )
    draft_payload = _json_bytes(raw_by_role[ROLE_DRAFT], ROLE_DRAFT)
    if not isinstance(draft_payload, dict):
        _fail("draft must be a JSON object")
    try:
        draft = SmallEntryPreregistrationDraft.model_validate(draft_payload)
        canonical = canonical_bytes(draft)
        canonical_digest = draft_sha256(draft)
    except (ValidationError, ValueError) as exc:
        _fail(f"draft model validation failed: {exc}")
    if canonical_digest != CANONICAL_DRAFT_SHA256 or _sha256(canonical) != DRAFT_SHA256:
        _fail("canonical draft SHA-256 does not match the pinned draft")
    if not isinstance(historical_payload, dict):
        _fail("historical preregistration must be a JSON object")
    if (
        draft.provenance.entry_amount_distribution_sha256
        != HISTORICAL_DISTRIBUTION_SHA256
        or draft.provenance.original_unheld_preregistration_sha256
        != ORIGINAL_UNHELD_PREREGISTRATION_SHA256
    ):
        _fail("draft historical provenance does not match the source identities")
    if canonical_digest == ORIGINAL_UNHELD_PREREGISTRATION_SHA256:
        _fail("draft identity must differ from historical preregistration identity")
    if draft.status != "draft" or draft.runtime_activation_allowed is not False:
        _fail("draft activation invariant was violated")
    return BundleValidation(
        manifest_sha256=_sha256(manifest_raw),
        raw_sha256=raw_sha256,
        canonical_draft_sha256=canonical_digest,
        draft_identity=canonical_digest,
        historical_identities={
            ROLE_DISTRIBUTION: HISTORICAL_DISTRIBUTION_SHA256,
            ROLE_PREREGISTRATION: ORIGINAL_UNHELD_PREREGISTRATION_SHA256,
        },
        _bundle_root=root,
    )


def write_public_outputs(result: BundleValidation, output_dir: Path) -> None:
    """Write deterministic public outputs into a new or empty directory."""

    target = _output_directory(output_dir, result._bundle_root)
    files = {
        target / "public-manifest.json": result.public_manifest_bytes(),
        target / "report.md": result.public_report_bytes(),
    }
    for path in files:
        if path.exists() or path.is_symlink():
            _fail("output file already exists")
    for path, content in files.items():
        try:
            with path.open("xb") as stream:
                stream.write(content)
        except FileExistsError:
            _fail("output file already exists")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = validate_bundle(args.bundle_root)
        output = _output_directory(args.output_dir, _absolute_path(args.bundle_root))
        for name in ("public-manifest.json", "report.md"):
            path = output / name
            if path.exists() or path.is_symlink():
                _fail("output file already exists")
        write_public_outputs(result, output)
    except (BundleValidationError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
