from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from jusik.config import ACCOUNT_NUMBER, PRODUCT_CODE, ROOT

KIWOOM_ENV_FILE = ROOT / ".env.kiwum"
KIWOOM_ORIGIN = "https://api.kiwoom.com"


class KiwoomSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=KIWOOM_ENV_FILE,
        extra="ignore",
        hide_input_in_errors=True,
        case_sensitive=True,
    )

    app_env: Literal["kiwum"] = Field(validation_alias="APP_ENV")
    app_key: SecretStr = Field(validation_alias="APP_KEY")
    app_secret: SecretStr = Field(validation_alias="APP_SECRET")
    cano: SecretStr | None = Field(default=None, validation_alias="CANO")
    acnt_prdt_cd: SecretStr | None = Field(
        default=None, validation_alias="ACNT_PRDT_CD"
    )
    base_url: str = Field(validation_alias="BASE_URL")
    cache_seconds: int = Field(default=30, ge=10, le=300)

    @field_validator("app_key", "app_secret")
    @classmethod
    def validate_credential(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("Kiwoom credential must not be blank.")
        return value

    @field_validator("cano")
    @classmethod
    def validate_cano(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return value
        if not ACCOUNT_NUMBER.fullmatch(value.get_secret_value()):
            raise ValueError("Account number must contain 8 digits.")
        return value

    @field_validator("acnt_prdt_cd")
    @classmethod
    def validate_product_code(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return value
        if not PRODUCT_CODE.fullmatch(value.get_secret_value()):
            raise ValueError("Account product code must contain 2 digits.")
        return value

    @field_validator("base_url")
    @classmethod
    def normalize_base_url(cls, value: str) -> str:
        parsed = urlsplit(value.strip())
        if (
            parsed.scheme != "https"
            or parsed.netloc != "api.kiwoom.com"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path.rstrip("/") not in ("", "/oauth2/token")
        ):
            raise ValueError("Only the official Kiwoom production API is allowed.")
        return KIWOOM_ORIGIN

    @model_validator(mode="after")
    def validate_account(self) -> Self:
        if (self.cano is None) != (self.acnt_prdt_cd is None):
            raise ValueError("CANO and ACNT_PRDT_CD must be configured together.")
        return self

    @property
    def account_number(self) -> str | None:
        if self.cano is None or self.acnt_prdt_cd is None:
            return None
        return self.cano.get_secret_value() + self.acnt_prdt_cd.get_secret_value()


def load_kiwoom_settings(
    env_file: Path = KIWOOM_ENV_FILE,
) -> KiwoomSettings | None:
    if not env_file.is_file():
        return None
    return KiwoomSettings(_env_file=env_file)
