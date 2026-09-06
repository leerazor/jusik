import re
from pathlib import Path
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
ACCOUNT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")
ACCOUNT_NUMBER = re.compile(r"^\d{8}$")
PRODUCT_CODE = re.compile(r"^\d{2}$")


class AccountConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    id: str
    label: str = Field(min_length=1, max_length=40)
    cano: SecretStr
    acnt_prdt_cd: SecretStr
    app_key: SecretStr | None = None
    app_secret: SecretStr | None = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not ACCOUNT_ID.fullmatch(value):
            raise ValueError("Account id must use 1-32 letters, digits, '_' or '-'.")
        return value

    @field_validator("label")
    @classmethod
    def validate_label(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Account label must not be blank.")
        return value

    @field_validator("cano")
    @classmethod
    def validate_cano(cls, value: SecretStr) -> SecretStr:
        if not ACCOUNT_NUMBER.fullmatch(value.get_secret_value()):
            raise ValueError("Account number must contain 8 digits.")
        return value

    @field_validator("acnt_prdt_cd")
    @classmethod
    def validate_product_code(cls, value: SecretStr) -> SecretStr:
        if not PRODUCT_CODE.fullmatch(value.get_secret_value()):
            raise ValueError("Account product code must contain 2 digits.")
        return value

    @field_validator("app_key", "app_secret")
    @classmethod
    def validate_optional_credential(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and not value.get_secret_value().strip():
            raise ValueError("Account credential must not be blank.")
        return value

    @model_validator(mode="after")
    def validate_credentials(self) -> Self:
        if (self.app_key is None) != (self.app_secret is None):
            raise ValueError("Account credentials must provide both key and secret.")
        return self


class RegisteredAccount(BaseModel):
    model_config = ConfigDict(frozen=True, hide_input_in_errors=True)

    id: str
    label: str
    cano: SecretStr
    acnt_prdt_cd: SecretStr
    app_key: SecretStr
    app_secret: SecretStr

    @property
    def credential_key(self) -> tuple[str, str]:
        return (
            self.app_key.get_secret_value(),
            self.app_secret.get_secret_value(),
        )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env.prod",
        extra="ignore",
        hide_input_in_errors=True,
    )

    kis_app_key: SecretStr | None = None
    kis_app_secret: SecretStr | None = None
    kis_cano: SecretStr | None = None
    kis_acnt_prdt_cd: SecretStr | None = None
    kis_accounts: list[AccountConfig] | None = None
    kis_base_url: Literal["https://openapi.koreainvestment.com:9443"]
    cache_seconds: int = Field(default=30, ge=10, le=300)

    @field_validator("kis_app_key", "kis_app_secret")
    @classmethod
    def validate_global_credential(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and not value.get_secret_value().strip():
            raise ValueError("Global credential must not be blank.")
        return value

    @model_validator(mode="after")
    def validate_account_settings(self) -> Self:
        if (self.kis_app_key is None) != (self.kis_app_secret is None):
            raise ValueError("Global credentials must provide both key and secret.")

        if self.kis_accounts is None:
            if None in (
                self.kis_app_key,
                self.kis_app_secret,
                self.kis_cano,
                self.kis_acnt_prdt_cd,
            ):
                raise ValueError("Legacy account configuration is incomplete.")
            self._validate_legacy_account()
            return self

        if not self.kis_accounts:
            raise ValueError("KIS_ACCOUNTS must contain at least one account.")

        ids: set[str] = set()
        account_numbers: set[tuple[str, str]] = set()
        for account in self.kis_accounts:
            if account.id in ids:
                raise ValueError("KIS_ACCOUNTS contains a duplicate account id.")
            ids.add(account.id)
            number = (
                account.cano.get_secret_value(),
                account.acnt_prdt_cd.get_secret_value(),
            )
            if number in account_numbers:
                raise ValueError("KIS_ACCOUNTS contains a duplicate brokerage account.")
            account_numbers.add(number)
            if account.app_key is None and self.kis_app_key is None:
                raise ValueError("An account has no usable credentials.")
        return self

    def _validate_legacy_account(self) -> None:
        assert self.kis_cano is not None
        assert self.kis_acnt_prdt_cd is not None
        AccountConfig(
            id="default",
            label="기본 계좌",
            cano=self.kis_cano,
            acnt_prdt_cd=self.kis_acnt_prdt_cd,
        )

    @property
    def registered_accounts(self) -> tuple[RegisteredAccount, ...]:
        if self.kis_accounts is None:
            assert self.kis_cano is not None
            assert self.kis_acnt_prdt_cd is not None
            assert self.kis_app_key is not None
            assert self.kis_app_secret is not None
            return (
                RegisteredAccount(
                    id="default",
                    label="기본 계좌",
                    cano=self.kis_cano,
                    acnt_prdt_cd=self.kis_acnt_prdt_cd,
                    app_key=self.kis_app_key,
                    app_secret=self.kis_app_secret,
                ),
            )

        accounts = []
        for account in self.kis_accounts:
            app_key = account.app_key or self.kis_app_key
            app_secret = account.app_secret or self.kis_app_secret
            assert app_key is not None
            assert app_secret is not None
            accounts.append(
                RegisteredAccount(
                    id=account.id,
                    label=account.label,
                    cano=account.cano,
                    acnt_prdt_cd=account.acnt_prdt_cd,
                    app_key=app_key,
                    app_secret=app_secret,
                )
            )
        return tuple(accounts)
