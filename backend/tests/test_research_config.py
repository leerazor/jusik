from pathlib import Path

import pytest

from jusik.research_config import PAPER_BASE_URL, load_research_settings


def write_env(path: Path, **changes: str) -> None:
    values = {
        "APP_ENV": "dev",
        "KIS_APP_KEY": "paper-key",
        "KIS_APP_SECRET": "paper-secret",
        "KIS_BASE_URL": PAPER_BASE_URL,
    }
    values.update(changes)
    path.write_text(
        "\n".join(f"{key}={value}" for key, value in values.items()),
        encoding="utf-8",
    )


def test_research_settings_read_only_explicit_paper_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env.dev"
    write_env(env_file)
    monkeypatch.setenv("KIS_APP_KEY", "environment-production-key")
    monkeypatch.setenv("KIS_BASE_URL", "https://openapi.koreainvestment.com:9443")

    settings = load_research_settings(env_file)

    assert settings.base_url == PAPER_BASE_URL
    assert settings.app_key.get_secret_value() == "paper-key"


@pytest.mark.parametrize(
    "changes",
    [
        {"APP_ENV": "prod"},
        {"KIS_BASE_URL": "https://openapi.koreainvestment.com:9443"},
        {"KIS_APP_SECRET": ""},
    ],
)
def test_research_settings_reject_non_paper_or_incomplete_values_without_secrets(
    tmp_path: Path, changes: dict[str, str]
) -> None:
    env_file = tmp_path / ".env.dev"
    write_env(env_file, **changes)

    with pytest.raises(RuntimeError) as caught:
        load_research_settings(env_file)

    message = str(caught.value)
    assert "paper-secret" not in message
    assert "paper-key" not in message
