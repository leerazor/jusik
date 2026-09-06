from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env.prod", extra="ignore")

    kis_app_key: SecretStr
    kis_app_secret: SecretStr
    kis_cano: SecretStr
    kis_acnt_prdt_cd: SecretStr
    kis_base_url: Literal["https://openapi.koreainvestment.com:9443"]
    cache_seconds: int = Field(default=30, ge=10, le=300)
