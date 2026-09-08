import asyncio
import json

import httpx

from jusik.research_ai import OpenAiResearchReviewer
from jusik.research_config import PAPER_BASE_URL, ResearchSettings


def settings() -> ResearchSettings:
    return ResearchSettings(
        app_key="broker-key-placeholder",
        app_secret="broker-secret-placeholder",
        base_url=PAPER_BASE_URL,
        openai_api_key="openai-secret-placeholder",
        openai_model="test-model",
        openai_daily_token_budget=10_000,
    )


def test_openai_request_uses_strict_schema_and_never_serializes_api_key() -> None:
    async def scenario() -> None:
        captured: dict[str, object] = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            captured["authorization"] = request.headers["authorization"]
            captured["body"] = request.content.decode()
            return httpx.Response(
                200,
                json={
                    "output_text": json.dumps(
                        {
                            "summary": "bounded candidate",
                            "suggested_fast_window": 15,
                            "suggested_slow_window": 45,
                            "suggested_min_volume_ratio": "1.2",
                            "reasons": ["later evaluation required"],
                        }
                    ),
                    "usage": {"input_tokens": 120, "output_tokens": 30},
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            reviewer = OpenAiResearchReviewer(settings(), client)
            request = reviewer.build_request(
                run_id="run-public", deterministic_summary='{"return":"1"}'
            )
            request["max_output_tokens"] = 123
            result = await reviewer.analyze(request)

        body = str(captured["body"])
        payload = json.loads(body)
        output_format = payload["text"]["format"]
        assert output_format["type"] == "json_schema"
        assert output_format["strict"] is True
        assert payload["max_output_tokens"] == 123
        assert "openai-secret-placeholder" not in body
        assert result.error is None
        assert result.input_tokens == 120
        assert result.output_tokens == 30
        assert result.suggestion is not None
        assert result.suggestion.suggested_fast_window == 15

    asyncio.run(scenario())


def test_openai_invalid_or_error_response_is_bounded_failure() -> None:
    async def run_response(response: httpx.Response) -> str | None:
        async def handler(_: httpx.Request) -> httpx.Response:
            return response

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            reviewer = OpenAiResearchReviewer(settings(), client)
            request = reviewer.build_request(
                run_id="run-public", deterministic_summary="{}"
            )
            return (await reviewer.analyze(request)).error

    invalid = asyncio.run(
        run_response(httpx.Response(200, json={"output_text": '{"summary": 3}'}))
    )
    failed = asyncio.run(run_response(httpx.Response(503, json={"error": "down"})))

    assert invalid == "OpenAI 연구 검토 응답을 안전하게 검증하지 못했습니다."
    assert failed == "OpenAI 연구 검토 응답을 안전하게 검증하지 못했습니다."


def test_conservative_input_reservation_covers_serialized_request() -> None:
    request: dict[str, object] = {
        "model": "test-model",
        "input": [{"role": "user", "content": "한글 summary"}],
    }
    serialized_bytes = len(
        json.dumps(
            request, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    )

    assert (
        OpenAiResearchReviewer.conservative_input_tokens(request)
        >= serialized_bytes + 512
    )
