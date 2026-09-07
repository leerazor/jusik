from __future__ import annotations

import json
from pathlib import Path

import pytest

from jusik import ngrok_launcher
from jusik.ngrok_launcher import (
    LauncherError,
    inspect_existing,
    tunnel_url,
    validate_policy,
    wait_for_tunnel,
)


def _policy(credential: str = "jusik:a-long-password") -> dict[str, object]:
    return {
        "on_http_request": [
            {
                "actions": [
                    {
                        "type": "basic-auth",
                        "config": {"credentials": [credential], "enforce": True},
                    }
                ]
            }
        ]
    }


def _write_policy(path: Path, policy: object) -> None:
    path.write_text(json.dumps(policy), encoding="utf-8")
    path.chmod(0o600)


def _tunnels(
    *,
    address: str = "http://127.0.0.1:3000",
    public_url: str = "https://private.ngrok-free.dev",
) -> dict[str, object]:
    return {"tunnels": [{"public_url": public_url, "config": {"addr": address}}]}


def test_validate_policy_accepts_exact_private_json(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.yml"
    _write_policy(policy_path, _policy())

    validate_policy(policy_path)


@pytest.mark.parametrize(
    "policy",
    [
        {},
        {"on_http_request": []},
        {
            "on_http_request": [
                {
                    "actions": [
                        {
                            "type": "basic-auth",
                            "config": {"credentials": ["user:pass"], "enforce": False},
                        }
                    ]
                }
            ]
        },
        {
            "on_http_request": [
                {
                    "expressions": ["true"],
                    "actions": [{"type": "basic-auth", "config": {}}],
                }
            ]
        },
    ],
)
def test_validate_policy_rejects_unprotected_or_conditional_rules(
    tmp_path: Path, policy: object
) -> None:
    policy_path = tmp_path / "policy.yml"
    _write_policy(policy_path, policy)

    with pytest.raises(LauncherError):
        validate_policy(policy_path)


def test_validate_policy_rejects_broad_file_permissions(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.yml"
    _write_policy(policy_path, _policy())
    policy_path.chmod(0o644)

    with pytest.raises(LauncherError, match="600"):
        validate_policy(policy_path)


def test_inspect_existing_reuses_authenticated_frontend_tunnel() -> None:
    result = inspect_existing(
        lambda: _tunnels(), lambda _: (401, 'Basic realm="ngrok"')
    )

    assert result == "https://private.ngrok-free.dev"


def test_inspect_existing_reports_absent_agent() -> None:
    assert inspect_existing(lambda: None) is None


def test_startup_inspection_allows_transient_empty_tunnel_list() -> None:
    assert inspect_existing(lambda: {"tunnels": []}, allow_empty=True) is None


def test_regular_inspection_rejects_empty_tunnel_list() -> None:
    with pytest.raises(LauncherError):
        inspect_existing(lambda: {"tunnels": []})


def test_wait_for_tunnel_retries_until_tunnel_is_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inspections = iter([None, "https://private.ngrok-free.dev"])
    monkeypatch.setattr(
        ngrok_launcher, "inspect_existing", lambda **_: next(inspections)
    )
    monkeypatch.setattr(ngrok_launcher.time, "sleep", lambda _: None)

    assert wait_for_tunnel(1) == "https://private.ngrok-free.dev"


def test_wait_for_tunnel_has_bounded_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ngrok_launcher, "inspect_existing", lambda **_: None)

    with pytest.raises(LauncherError, match="제한 시간"):
        wait_for_tunnel(0)


@pytest.mark.parametrize(
    ("status", "challenge"),
    [(200, None), (302, None), (401, None), (401, "Bearer")],
)
def test_inspect_existing_rejects_tunnel_without_basic_auth(
    status: int, challenge: str | None
) -> None:
    with pytest.raises(LauncherError, match="basic-auth"):
        inspect_existing(lambda: _tunnels(), lambda _: (status, challenge))


@pytest.mark.parametrize(
    ("address", "public_url"),
    [
        ("http://127.0.0.1:8000", "https://private.ngrok-free.dev"),
        ("http://192.168.0.1:3000", "https://private.ngrok-free.dev"),
        ("http://127.0.0.1:3000", "http://private.ngrok-free.dev"),
        ("http://127.0.0.1:3000", "https://example.com"),
        ("http://127.0.0.1:3000", "https://user:secret@private.ngrok-free.dev"),
    ],
)
def test_tunnel_url_rejects_wrong_target_or_unsafe_url(
    address: str, public_url: str
) -> None:
    with pytest.raises(LauncherError):
        tunnel_url(_tunnels(address=address, public_url=public_url))


def test_errors_do_not_contain_policy_credentials(tmp_path: Path) -> None:
    secret = "never-print-this-value"
    policy_path = tmp_path / "policy.yml"
    _write_policy(policy_path, _policy(f"missing-password-{secret}"))

    with pytest.raises(LauncherError) as error:
        validate_policy(policy_path)

    assert secret not in str(error.value)


@pytest.mark.parametrize(
    "credential",
    ["user:short", "user:${SECRET_VALUE}", "jusik:REPLACE_WITH_RANDOM_PASSWORD"],
)
def test_validate_policy_rejects_weak_or_interpolated_password(
    tmp_path: Path, credential: str
) -> None:
    policy_path = tmp_path / "policy.yml"
    _write_policy(policy_path, _policy(credential))

    with pytest.raises(LauncherError):
        validate_policy(policy_path)


def test_tunnel_url_rejects_payload_without_tunnels_key() -> None:
    with pytest.raises(LauncherError):
        tunnel_url({"version": "3"})
