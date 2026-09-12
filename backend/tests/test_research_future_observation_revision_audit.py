from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from jusik.research_future_observation_replay import replay
from jusik.research_future_observation_revision_audit import audit

BASE = {
    "synthetic": True,
    "window_start_at": "2030-01-01T00:00:00Z",
    "window_end_at": "2030-01-02T00:00:00Z",
    "checked_at": "2030-01-02T00:00:00Z",
}


def obs(raw: str, source: str = "s", observation_id: str = "o") -> dict[str, object]:
    return {
        "source_id": source,
        "observation_id": observation_id,
        "raw": raw,
        "received_at": "2030-01-01T01:00:00Z",
        "event_at": "2030-01-01T01:00:00Z",
        "read_started_at": "2030-01-01T00:59:00Z",
        "read_finished_at": "2030-01-01T01:01:00Z",
    }


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def link(child: str, parent: str, **kwargs: object) -> dict[str, object]:
    value: dict[str, object] = {
        "source_id": "s",
        "observation_id": "o",
        "raw_sha256": digest(child),
        "parent_sha256": digest(parent),
        "effective_at": "2030-01-01T00:00:00Z",
    }
    value.update(kwargs)
    return value


def test_valid_chain_preserves_replay_and_declarations() -> None:
    fixture = {**BASE, "observations": [obs("a"), obs("b"), obs("c"), obs("a")]}
    links = {"synthetic": True, "revision_links": [link("b", "a"), link("c", "b")]}
    result = audit(fixture, links)
    assert result.diagnostics == []
    assert result.synthetic is True
    assert result.counts == {"revision_links": 2, "diagnostics": 0}
    assert result.replay == replay(fixture)
    assert [item.model_dump(mode="json") for item in result.revision_links] == links[
        "revision_links"
    ]
    assert (
        result.registered,
        result.accepted_nav,
        result.evaluation_inputs_complete,
    ) == (
        False,
        False,
        False,
    )
    assert result.selection_policy == result.temporal_policy == "unresolved"


@pytest.mark.parametrize(
    ("links", "codes"),
    [
        ([link("b", "missing")], {"missing_parent"}),
        (
            [link("b", "a", parent_sha256=digest("a")), link("b", "c")],
            {"ambiguous_parent"},
        ),
        ([link("a", "a")], {"self_link", "cycle_member"}),
        ([link("a", "b"), link("b", "a")], {"cycle_member"}),
        ([link("b", "a"), link("b", "a")], {"duplicate_link"}),
        ([link("missing", "a")], {"hash_mismatch"}),
        ([link("b", "a", effective_at="not-time")], {"effective_at_invalid"}),
    ],
)
def test_graph_errors_are_diagnosed_and_preserved(
    links: list[dict[str, object]], codes: set[str]
) -> None:
    fixture = {**BASE, "observations": [obs("a"), obs("b"), obs("c")]}
    result = audit(fixture, {"synthetic": True, "revision_links": links})
    assert {item.code for item in result.diagnostics} == codes
    assert [item.model_dump(mode="json") for item in result.revision_links] == links


def test_cross_source_parent_is_diagnosis_only() -> None:
    fixture = {**BASE, "observations": [obs("b"), obs("a", source="other")]}
    result = audit(
        fixture, {"synthetic": True, "revision_links": [link("b", "a", source_id="s")]}
    )
    assert "cross_source_parent" in {item.code for item in result.diagnostics}


def test_cross_observation_and_wrong_child_scopes_are_distinct() -> None:
    fixture = {
        **BASE,
        "observations": [obs("b"), obs("a", observation_id="other")],
    }
    wrong_parent = audit(
        fixture,
        {"synthetic": True, "revision_links": [link("b", "a")]},
    )
    assert "cross_observation_parent" in {
        item.code for item in wrong_parent.diagnostics
    }
    wrong_child = audit(
        fixture,
        {"synthetic": True, "revision_links": [link("a", "b", source_id="other")]},
    )
    assert "cross_source_child" in {item.code for item in wrong_child.diagnostics}


def test_global_parent_ambiguity_deduplicates_repeated_receipts() -> None:
    fixture = {
        **BASE,
        "observations": [
            obs("b"),
            obs("a", source="x"),
            obs("a", source="y"),
            obs("a", source="x"),
        ],
    }
    result = audit(fixture, {"synthetic": True, "revision_links": [link("b", "a")]})
    codes = [item.code for item in result.diagnostics]
    assert codes.count("ambiguous_parent") == 1


def test_scc_marks_all_cycle_members_but_not_tail() -> None:
    names = ["a", "b", "c", "d"]
    fixture = {**BASE, "observations": [obs(name) for name in names]}
    links = [
        link("a", "b"),
        link("b", "a"),
        link("a", "c"),
        link("c", "b"),
        link("d", "a"),
    ]
    result = audit(fixture, {"synthetic": True, "revision_links": links})
    members = {
        (item.raw_sha256, item.code)
        for item in result.diagnostics
        if item.code == "cycle_member"
    }
    assert {digest(name) for name in ("a", "b", "c")} == {raw for raw, _ in members}
    assert digest("d") not in {raw for raw, _ in members}


def test_time_zone_aware_offsets_are_accepted_and_malformed_are_retained() -> None:
    result = audit(
        {**BASE, "observations": [obs("a"), obs("b")]},
        {
            "synthetic": True,
            "revision_links": [
                link("b", "a", effective_at="2030-01-01T09:00:00+09:00")
            ],
        },
    )
    assert result.diagnostics == []
    malformed = audit(
        {**BASE, "observations": [obs("a"), obs("b")]},
        {
            "synthetic": True,
            "revision_links": [link("b", "a", effective_at="2030-01-01T00:00:00")],
        },
    )
    assert malformed.revision_links[0].effective_at.endswith("00")
    assert "effective_at_invalid" in {item.code for item in malformed.diagnostics}
    overflow = audit(
        {**BASE, "observations": [obs("a"), obs("b")]},
        {
            "synthetic": True,
            "revision_links": [
                link("b", "a", effective_at="9999-12-31T23:00:00-23:00")
            ],
        },
    )
    assert "effective_at_invalid" in {item.code for item in overflow.diagnostics}


def test_literal_synthetic_and_deep_graph() -> None:
    for marker in (None, False, 1, "true"):
        document: dict[str, object] = (
            {"revision_links": []}
            if marker is None
            else {"synthetic": marker, "revision_links": []}
        )
        with pytest.raises(ValidationError):
            audit(BASE, document)
    observations = [obs(str(i)) for i in range(1500)]
    links = [link(str(i + 1), str(i)) for i in range(1499)]
    result = audit(
        {**BASE, "observations": observations},
        {"synthetic": True, "revision_links": links},
    )
    assert result.diagnostics == []


def test_utf8_hashes_and_fixture_are_preserved() -> None:
    raws = ["원문 A\r\n", "원문 B\n", "원문 C\t", "원문 A\r\n"]
    fixture = {**BASE, "observations": [obs(raw) for raw in raws]}
    before = deepcopy(fixture)
    result = audit(fixture, {"synthetic": True, "revision_links": []})
    assert fixture == before
    receipt_hashes = [
        receipt.raw_sha256
        for item in result.replay.observations
        for receipt in item.receipts
    ]
    assert receipt_hashes == [
        hashlib.sha256(raw.encode("utf-8")).hexdigest() for raw in raws
    ]
    assert [
        receipt.raw for item in result.replay.observations for receipt in item.receipts
    ] == raws


def test_future_receipt_stays_unavailable_regardless_of_backdated_link() -> None:
    future = obs("b")
    future["received_at"] = "2030-01-03T00:00:00Z"
    result = audit(
        {**BASE, "observations": [obs("a"), future]},
        {
            "synthetic": True,
            "revision_links": [link("b", "a", effective_at="2020-01-01T00:00:00Z")],
        },
    )
    receipt = result.replay.observations[0].receipts[1]
    assert receipt.available_at_check is False
    assert "not_due" in result.replay.observations[0].classifications


def test_audit_bounds_receipts_and_links() -> None:
    with pytest.raises(ValueError, match="observations"):
        audit(
            {**BASE, "observations": [obs(str(i)) for i in range(10001)]},
            {"synthetic": True},
        )
    with pytest.raises(ValueError, match="links"):
        audit(
            BASE,
            {
                "synthetic": True,
                "revision_links": [link("a", "b") for _ in range(10001)],
            },
        )


def test_cli_is_deterministic_and_rejects_alias_and_bounds(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.json"
    links = tmp_path / "links.json"
    fixture.write_text(
        json.dumps({**BASE, "observations": [obs("a")]}), encoding="utf-8"
    )
    links.write_text(
        json.dumps({"synthetic": True, "revision_links": []}), encoding="utf-8"
    )
    output = tmp_path / "audit.json"
    command = [
        sys.executable,
        "-m",
        "jusik.research_future_observation_revision_audit",
        "--fixture",
        str(fixture),
        "--revision-links",
        str(links),
        "--output",
        str(output),
    ]
    first = subprocess.run(command, cwd=Path(__file__).parents[1], capture_output=True)
    assert first.returncode == 0
    payload = output.read_bytes()
    second_output = tmp_path / "audit-2.json"
    assert (
        subprocess.run(
            [*command[:-1], str(second_output)], cwd=Path(__file__).parents[1]
        ).returncode
        == 0
    )
    assert second_output.read_bytes() == payload
    assert subprocess.run(command, cwd=Path(__file__).parents[1]).returncode != 0
    alias = tmp_path / "alias.json"
    alias.hardlink_to(fixture)
    assert (
        subprocess.run(
            [*command[:-1], str(alias)], cwd=Path(__file__).parents[1]
        ).returncode
        != 0
    )
    link_alias = tmp_path / "link-alias.json"
    link_alias.hardlink_to(links)
    assert (
        subprocess.run(
            [
                *command[:3],
                "--fixture",
                str(fixture),
                "--revision-links",
                str(link_alias),
                "--output",
                str(link_alias),
            ],
            cwd=Path(__file__).parents[1],
        ).returncode
        != 0
    )
    fixture_symlink = tmp_path / "fixture-symlink.json"
    fixture_symlink.symlink_to(fixture)
    assert (
        subprocess.run(
            [
                *command[:3],
                "--fixture",
                str(fixture_symlink),
                "--revision-links",
                str(links),
                "--output",
                str(fixture_symlink),
            ],
            cwd=Path(__file__).parents[1],
        ).returncode
        != 0
    )
    oversized_fixture = tmp_path / "oversized-fixture.json"
    oversized_fixture.write_text(
        json.dumps({**BASE, "observations": [obs("x" * (4 * 1024 * 1024))]}),
        encoding="utf-8",
    )
    oversized_fixture_out = tmp_path / "oversized-out.json"
    oversized_fixture_proc = subprocess.run(
        [
            *command[:3],
            "--fixture",
            str(oversized_fixture),
            "--revision-links",
            str(links),
            "--output",
            str(oversized_fixture_out),
        ],
        cwd=Path(__file__).parents[1],
        capture_output=True,
    )
    assert oversized_fixture_proc.returncode != 0
    assert b"exceeds 4 MiB limit" in oversized_fixture_proc.stderr
    assert not oversized_fixture_out.exists()
    oversized_links = tmp_path / "oversized-links.json"
    oversized_links.write_text(
        json.dumps(
            {
                "synthetic": True,
                "revision_links": [
                    link("a", "b", effective_at="x" * (4 * 1024 * 1024))
                ],
            }
        ),
        encoding="utf-8",
    )
    oversized_links_out = tmp_path / "oversized-links-out.json"
    oversized_links_proc = subprocess.run(
        [
            *command[:3],
            "--fixture",
            str(fixture),
            "--revision-links",
            str(oversized_links),
            "--output",
            str(oversized_links_out),
        ],
        cwd=Path(__file__).parents[1],
        capture_output=True,
    )
    assert oversized_links_proc.returncode != 0
    assert b"exceeds 4 MiB limit" in oversized_links_proc.stderr
    assert not oversized_links_out.exists()
    many_links = tmp_path / "many-links.json"
    many_links.write_text(
        json.dumps(
            {
                "synthetic": True,
                "revision_links": [link("a", "b") for _ in range(10001)],
            }
        ),
        encoding="utf-8",
    )
    many_links_proc = subprocess.run(
        [
            *command[:3],
            "--fixture",
            str(fixture),
            "--revision-links",
            str(many_links),
            "--output",
            str(tmp_path / "many-links-out.json"),
        ],
        cwd=Path(__file__).parents[1],
        capture_output=True,
    )
    assert many_links_proc.returncode != 0
    assert b"exceeds 10000 links" in many_links_proc.stderr
