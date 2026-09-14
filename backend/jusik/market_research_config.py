from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

KRX_BASE_URL = "https://data.krx.co.kr"
MASSIVE_BASE_URL = "https://api.massive.com"
DEFAULT_DB_PATH = Path.home() / ".local/share/jusik/market-research.db"
DEFAULT_ARTIFACT_DIR = Path.home() / ".local/share/jusik/market-research-artifacts"


class MarketResearchSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, frozen=True)

    krx_auth_key: SecretStr | None = None
    massive_api_key: SecretStr | None = None
    krx_base_url: str = KRX_BASE_URL
    massive_base_url: str = MASSIVE_BASE_URL
    db_path: Path = DEFAULT_DB_PATH
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR
    request_timeout_seconds: int = Field(default=15, ge=1, le=60)
    max_pages: int = Field(default=100, ge=1, le=1000)

    @model_validator(mode="after")
    def require_fixed_provider_hosts(self) -> MarketResearchSettings:
        if (
            self.krx_base_url != KRX_BASE_URL
            or self.massive_base_url != MASSIVE_BASE_URL
        ):
            raise ValueError("market research providers require fixed official hosts")
        return self

    @property
    def credentials_configured(self) -> bool:
        return self.krx_auth_key is not None and self.massive_api_key is not None


def load_market_research_settings(
    env_path: Path | None = None,
) -> MarketResearchSettings:
    values: Mapping[str, str | None] = (
        dotenv_values(env_path) if env_path is not None else os.environ
    )

    def text(name: str, default: str) -> str:
        value = values.get(name)
        return value if isinstance(value, str) and value else default

    def secret(name: str) -> SecretStr | None:
        value = values.get(name)
        return SecretStr(value) if isinstance(value, str) and value else None

    return MarketResearchSettings(
        krx_auth_key=secret("KRX_AUTH_KEY"),
        massive_api_key=secret("MASSIVE_API_KEY"),
        krx_base_url=text("KRX_BASE_URL", KRX_BASE_URL),
        massive_base_url=text("MASSIVE_BASE_URL", MASSIVE_BASE_URL),
        db_path=Path(text("MARKET_RESEARCH_DB_PATH", str(DEFAULT_DB_PATH))),
        artifact_dir=Path(
            text("MARKET_RESEARCH_ARTIFACT_DIR", str(DEFAULT_ARTIFACT_DIR))
        ),
    )
