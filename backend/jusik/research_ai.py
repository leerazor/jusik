import json
from datetime import date
from decimal import Decimal
from typing import cast

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from jusik.research_config import ResearchSettings

PROMPT_VERSION = "research_review_v1"


class AiCandidateSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=1000)
    suggested_fast_window: int | None = Field(default=None, ge=5, le=120)
    suggested_slow_window: int | None = Field(default=None, ge=10, le=240)
    suggested_min_volume_ratio: Decimal | None = Field(
        default=None,
        ge=Decimal("0.5"),
        le=Decimal("3"),
        allow_inf_nan=False,
    )
    reasons: list[str] = Field(min_length=1, max_length=5)


class AiResult(BaseModel):
    suggestion: AiCandidateSuggestion | None
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    error: str | None = None


class OpenAiResearchReviewer:
    def __init__(self, settings: ResearchSettings, client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.client = client

    @property
    def configured(self) -> bool:
        return bool(self.settings.openai_api_key and self.settings.openai_model)

    def build_request(
        self, *, run_id: str, deterministic_summary: str
    ) -> dict[str, object]:
        if not self.configured:
            raise RuntimeError("OpenAI API is not configured.")
        assert self.settings.openai_model is not None
        return {
            "model": self.settings.openai_model,
            "max_output_tokens": 500,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "You review deterministic Korean-stock backtests. "
                        "Suggest only bounded trend/volume parameters. "
                        "Never decide promotion or generate executable code."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"run_id={run_id}; date={date.today().isoformat()}; "
                        f"result={deterministic_summary}"
                    ),
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "research_candidate_suggestion",
                    "strict": True,
                    "schema": AiCandidateSuggestion.model_json_schema(),
                }
            },
        }

    @staticmethod
    def conservative_input_tokens(request: dict[str, object]) -> int:
        # A token cannot contain less than one UTF-8 byte. Counting every byte as
        # one token plus protocol overhead intentionally over-reserves the budget.
        encoded = json.dumps(
            request, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        return len(encoded) + 512

    async def analyze(self, request: dict[str, object]) -> AiResult:
        if not self.configured:
            return AiResult(
                suggestion=None,
                input_tokens=0,
                output_tokens=0,
                error="OpenAI API가 설정되지 않았습니다.",
            )
        assert self.settings.openai_api_key is not None
        try:
            response = await self.client.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "authorization": (
                        f"Bearer {self.settings.openai_api_key.get_secret_value()}"
                    ),
                    "content-type": "application/json",
                },
                json=request,
                timeout=30,
                follow_redirects=False,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("Invalid response")
            output_text = payload.get("output_text")
            if not isinstance(output_text, str):
                output_text = self._output_text(payload)
            usage = payload.get("usage", {})
            if not isinstance(usage, dict):
                raise ValueError("Invalid usage")
            suggestion = AiCandidateSuggestion.model_validate_json(output_text)
            return AiResult(
                suggestion=suggestion,
                input_tokens=int(usage.get("input_tokens", 0)),
                output_tokens=int(usage.get("output_tokens", 0)),
            )
        except (
            httpx.HTTPError,
            ValueError,
            TypeError,
            ValidationError,
            json.JSONDecodeError,
        ):
            return AiResult(
                suggestion=None,
                input_tokens=0,
                output_tokens=0,
                error="OpenAI 연구 검토 응답을 안전하게 검증하지 못했습니다.",
            )

    @staticmethod
    def _output_text(payload: object) -> str:
        if not isinstance(payload, dict):
            raise ValueError("Invalid response")
        for item in payload.get("output", []):
            if not isinstance(item, dict):
                continue
            for content in item.get("content", []):
                if isinstance(content, dict) and isinstance(content.get("text"), str):
                    return cast(str, content["text"])
        raise ValueError("Missing structured output")
