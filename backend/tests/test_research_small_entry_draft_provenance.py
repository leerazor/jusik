from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from jusik import research_small_entry_draft_provenance as provenance
from jusik import research_small_entry_preregistration as draft_module

ARCHIVE = Path(
    "/home/kwl/.local/share/jusik/portfolio-audit/"
    "small-entry-preregistration-draft-v1-a55b6ee8a036463da688fafe04567542"
)
ROLE_PATHS = provenance.ROLE_RELATIVE_PATHS


def _synthetic_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    distribution = b'{"kind":"distribution"}'
    historical = b'{"kind":"historical-preregistration"}'
    distribution_sha = hashlib.sha256(distribution).hexdigest()
    historical_sha = hashlib.sha256(historical).hexdigest()
    monkeypatch.setattr(
        draft_module, "HISTORICAL_DISTRIBUTION_SHA256", distribution_sha
    )
    monkeypatch.setattr(
        draft_module, "ORIGINAL_UNHELD_PREREGISTRATION_SHA256", historical_sha
    )
    monkeypatch.setattr(provenance, "HISTORICAL_DISTRIBUTION_SHA256", distribution_sha)
    monkeypatch.setattr(
        provenance, "ORIGINAL_UNHELD_PREREGISTRATION_SHA256", historical_sha
    )
    draft = draft_module.SmallEntryPreregistrationDraft(
        provenance={
            "entry_amount_distribution_sha256": distribution_sha,
            "original_unheld_preregistration_sha256": historical_sha,
        }
    )
    draft_raw = draft_module.canonical_bytes(draft)
    draft_sha = hashlib.sha256(draft_raw).hexdigest()
    monkeypatch.setattr(provenance, "DRAFT_SHA256", draft_sha)
    monkeypatch.setattr(provenance, "CANONICAL_DRAFT_SHA256", draft_sha)

    root = tmp_path / "bundle"
    (root / "draft").mkdir(parents=True)
    (root / "historical-context").mkdir()
    (root / "draft/draft.json").write_bytes(draft_raw)
    (root / "historical-context/distribution.json").write_bytes(distribution)
    (root / "historical-context/preregistration.json").write_bytes(historical)
    entries = [
        {
            "path": str((provenance.ARCHIVE_ROOT / relative).absolute()),
            "sha256": digest,
        }
        for relative, digest in (
            (ROLE_PATHS["draft"], draft_sha),
            (ROLE_PATHS["historical_distribution"], distribution_sha),
            (ROLE_PATHS["historical_preregistration"], historical_sha),
        )
    ]
    manifest = json.dumps(entries, separators=(",", ":")).encode()
    (root / "manifest.json").write_bytes(manifest)
    monkeypatch.setattr(
        provenance, "MANIFEST_SHA256", hashlib.sha256(manifest).hexdigest()
    )
    return root


def test_synthetic_bundle_validates_and_public_outputs_are_deterministic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _synthetic_bundle(tmp_path, monkeypatch)
    result = provenance.validate_bundle(root)
    assert result.status == "draft"
    assert result.runtime_activation_allowed is False
    assert result.prospective_validation_eligible is False
    assert str(root) not in result.public_manifest_bytes().decode()
    output = tmp_path / "out"
    provenance.write_public_outputs(result, output)
    first = {path.name: path.read_bytes() for path in output.iterdir()}
    assert json.loads(first["public-manifest.json"])["status"] == "draft"

    second = tmp_path / "out-second"
    provenance.write_public_outputs(result, second)
    assert first == {path.name: path.read_bytes() for path in second.iterdir()}


@pytest.mark.parametrize("role", [*ROLE_PATHS, "manifest"])
def test_one_byte_tamper_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, role: str
) -> None:
    root = _synthetic_bundle(tmp_path, monkeypatch)
    relative = Path("manifest.json") if role == "manifest" else ROLE_PATHS[role]
    path = root / relative
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(provenance.BundleValidationError):
        provenance.validate_bundle(root)


def test_role_digest_duplicate_path_swapped_source_and_symlink_are_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _synthetic_bundle(tmp_path, monkeypatch)
    manifest_path = root / "manifest.json"
    entries = json.loads(manifest_path.read_text())
    entries[0]["sha256"] = "0" * 64
    body = json.dumps(entries, separators=(",", ":")).encode()
    manifest_path.write_bytes(body)
    monkeypatch.setattr(provenance, "MANIFEST_SHA256", hashlib.sha256(body).hexdigest())
    with pytest.raises(provenance.BundleValidationError, match="digest"):
        provenance.validate_bundle(root)

    root = _synthetic_bundle(tmp_path / "duplicate", monkeypatch)
    manifest_path = root / "manifest.json"
    entries = json.loads(manifest_path.read_text())
    entries.append(entries[0])
    body = json.dumps(entries, separators=(",", ":")).encode()
    manifest_path.write_bytes(body)
    monkeypatch.setattr(provenance, "MANIFEST_SHA256", hashlib.sha256(body).hexdigest())
    with pytest.raises(provenance.BundleValidationError, match="duplicate"):
        provenance.validate_bundle(root)

    root = _synthetic_bundle(tmp_path / "swapped", monkeypatch)
    distribution = root / ROLE_PATHS["historical_distribution"]
    historical = root / ROLE_PATHS["historical_preregistration"]
    distribution.write_bytes(historical.read_bytes())
    historical.write_bytes(b'{"kind":"distribution"}')
    with pytest.raises(provenance.BundleValidationError):
        provenance.validate_bundle(root)


@pytest.mark.parametrize("missing_role", [*ROLE_PATHS])
def test_missing_role_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing_role: str
) -> None:
    root = _synthetic_bundle(tmp_path, monkeypatch)
    manifest_path = root / "manifest.json"
    entries = json.loads(manifest_path.read_text())
    missing_path = str((provenance.ARCHIVE_ROOT / ROLE_PATHS[missing_role]).absolute())
    entries = [entry for entry in entries if entry["path"] != missing_path]
    body = json.dumps(entries, separators=(",", ":")).encode()
    manifest_path.write_bytes(body)
    monkeypatch.setattr(provenance, "MANIFEST_SHA256", hashlib.sha256(body).hexdigest())
    with pytest.raises(provenance.BundleValidationError, match="missing role"):
        provenance.validate_bundle(root)


@pytest.mark.parametrize("bad_digest", ["0" * 63, "z" * 64])
def test_malformed_manifest_digest_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad_digest: str
) -> None:
    root = _synthetic_bundle(tmp_path, monkeypatch)
    manifest_path = root / "manifest.json"
    entries = json.loads(manifest_path.read_text())
    entries[0]["sha256"] = bad_digest
    body = json.dumps(entries, separators=(",", ":")).encode()
    manifest_path.write_bytes(body)
    monkeypatch.setattr(provenance, "MANIFEST_SHA256", hashlib.sha256(body).hexdigest())
    with pytest.raises(provenance.BundleValidationError, match="invalid SHA"):
        provenance.validate_bundle(root)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("status", "registered"),
        ("runtime_activation_allowed", True),
        ("reused_data", False),
        ("prospective_validation_eligible", True),
    ],
)
def test_draft_activation_and_history_invariants_are_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    replacement: object,
) -> None:
    root = _synthetic_bundle(tmp_path, monkeypatch)
    draft_path = root / ROLE_PATHS["draft"]
    payload = json.loads(draft_path.read_text())
    payload[field] = replacement
    raw = json.dumps(payload, separators=(",", ":")).encode()
    draft_path.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    manifest_path = root / "manifest.json"
    entries = json.loads(manifest_path.read_text())
    entries[0]["sha256"] = digest
    body = json.dumps(entries, separators=(",", ":")).encode()
    manifest_path.write_bytes(body)
    monkeypatch.setattr(provenance, "MANIFEST_SHA256", hashlib.sha256(body).hexdigest())
    monkeypatch.setattr(provenance, "DRAFT_SHA256", digest)
    monkeypatch.setattr(provenance, "CANONICAL_DRAFT_SHA256", digest)
    with pytest.raises(provenance.BundleValidationError, match="draft model"):
        provenance.validate_bundle(root)


def test_root_and_output_ancestor_symlinks_are_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _synthetic_bundle(tmp_path, monkeypatch)
    root_alias = tmp_path / "root-alias"
    root_alias.symlink_to(root, target_is_directory=True)
    with pytest.raises(provenance.BundleValidationError, match="symlink"):
        provenance.validate_bundle(root_alias)

    output_parent = tmp_path / "output-parent"
    output_parent.mkdir()
    output_target = tmp_path / "output-target"
    output_target.mkdir()
    output_parent.rmdir()
    output_parent.symlink_to(output_target, target_is_directory=True)
    with pytest.raises(provenance.BundleValidationError, match="symlink"):
        provenance.write_public_outputs(
            provenance.validate_bundle(root), output_parent / "out"
        )

    root = _synthetic_bundle(tmp_path / "symlink", monkeypatch)
    draft = root / ROLE_PATHS["draft"]
    target = tmp_path / "target.json"
    target.write_bytes(draft.read_bytes())
    draft.unlink()
    draft.symlink_to(target)
    with pytest.raises(provenance.BundleValidationError):
        provenance.validate_bundle(root)


def test_real_archive_replay_uses_frozen_manifest_when_available() -> None:
    if not ARCHIVE.is_dir():
        pytest.skip("durable replay archive is unavailable")
    result = provenance.validate_bundle(ARCHIVE)
    assert result.canonical_draft_sha256 == provenance.DRAFT_SHA256


def test_cli_rejects_nonempty_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _synthetic_bundle(tmp_path, monkeypatch)
    output = tmp_path / "output"
    assert (
        provenance.main(["--bundle-root", str(root), "--output-dir", str(output)]) == 0
    )
    assert (
        provenance.main(["--bundle-root", str(root), "--output-dir", str(output)]) == 2
    )
