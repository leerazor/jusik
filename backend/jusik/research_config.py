from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from jusik.config import ROOT

PAPER_BASE_URL = "https://openapivts.koreainvestment.com:29443"


class ResearchSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, frozen=True)

    app_key: SecretStr = Field(min_length=1)
    app_secret: SecretStr = Field(min_length=1)
    base_url: str
    db_path: Path = Path.home() / ".local/share/jusik/research.db"
    websocket_url: str = "ws://ops.koreainvestment.com:31000"
    openai_api_key: SecretStr | None = None
    openai_model: str | None = None
    openai_daily_token_budget: int = Field(default=0, ge=0, le=1_000_000)

    def model_post_init(self, __context: object) -> None:
        if self.base_url != PAPER_BASE_URL:
            raise ValueError("Research backend requires the official KIS paper host.")
        if self.websocket_url not in {
            "ws://ops.koreainvestment.com:31000",
            "ws://ops.koreainvestment.com:21000",
        }:
            raise ValueError("Research websocket requires an official KIS host.")
        if bool(self.openai_api_key) != bool(self.openai_model):
            raise ValueError("OpenAI key and model must be configured together.")


def load_research_settings(env_path: Path = ROOT / ".env.dev") -> ResearchSettings:
    values = dotenv_values(env_path, interpolate=False)

    try:
        if values.get("APP_ENV") != "dev":
            raise ValueError("Research configuration requires APP_ENV=dev.")
        return ResearchSettings(
            app_key=values.get("KIS_APP_KEY"),
            app_secret=values.get("KIS_APP_SECRET"),
            base_url=values.get("KIS_BASE_URL"),
            websocket_url=values.get("KIS_WEBSOCKET_URL")
            or "ws://ops.koreainvestment.com:31000",
            openai_api_key=values.get("OPENAI_API_KEY"),
            openai_model=values.get("OPENAI_MODEL"),
            openai_daily_token_budget=int(
                values.get("OPENAI_DAILY_TOKEN_BUDGET") or "0"
            ),
        )
    except (ValidationError, ValueError, TypeError):
        raise RuntimeError(
            "Invalid paper research settings. Check the local .env.dev file."
        ) from None
