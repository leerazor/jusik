from __future__ import annotations

import importlib.util
import json
from http.client import HTTPMessage
from io import BytesIO
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request

import pytest


@pytest.fixture
def script() -> ModuleType:
    path = Path(__file__).parents[1] / "scripts/analyze_models.py"
    spec = importlib.util.spec_from_file_location("analyze_models", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def models() -> list[dict[str, Any]]:
    return [
        {
            "id": "fixture",
            "slug": "gpt-6-sol-high",
            "name": "Fixture",
            "model_creator": {"name": "OpenAI"},
            "evaluations": {"artificial_analysis_intelligence_index": 50},
            "pricing": {"price_1m_input_tokens": "1.50", "price_1m_output_tokens": "8"},
            "artificial_analysis_intelligence_index_cost": {
                "cost_per_task": {"total_cost": "0.25"}
            },
            "private_unused": "never-export",
        }
    ]


def test_default_pareto_is_advisory_and_legacy_is_explicit(script: ModuleType) -> None:
    report = script.make_report(models(), "4", "a" * 64)
    assert "Pareto" in report and "not actual agent bills" in report
    assert "Points per dollar" not in report and "Index band" not in report
    assert "Index band" in script.make_report(models(), "4", "a" * 64, 5)


def test_json_export_is_atomic_sanitized_and_decimal_safe(
    script: ModuleType, tmp_path: Path
) -> None:
    snapshot = script.make_snapshot(models(), "4", "a" * 64)
    output = tmp_path / "nested/catalog.json"
    script.write_snapshot(snapshot, output)
    value = json.loads(output.read_text())
    assert value["schema_version"] == 1 and value["complete"] is True
    assert value["models"][0]["input_usd_per_million"] == "1.50"
    assert set(value["models"][0]) == {
        "aa_slug",
        "index",
        "benchmark_task_cost_usd",
        "input_usd_per_million",
        "output_usd_per_million",
    }
    assert "never-export" not in output.read_text()
    script.write_snapshot(snapshot, output)
    assert list(output.parent.iterdir()) == [output]


def test_cli_never_exports_key(
    script: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    marker = "offline-test-marker"
    monkeypatch.setattr(script, "load_api_key", lambda _: marker)
    monkeypatch.setattr(script, "fetch_catalog", lambda _: (models(), "4", "a" * 64))
    output = tmp_path / "catalog.json"
    assert script.main(["--json-output", str(output)]) == 0
    captured = capsys.readouterr()
    assert marker not in captured.out + captured.err + output.read_text()


def test_secure_key_parser_and_redirect_boundary(
    script: ModuleType, tmp_path: Path
) -> None:
    env = tmp_path / "fixture-input"
    env.write_text('UNRELATED=ignored\nARTIFICIAL_ANALYSIS_API_KEY="fixture-only"\n')
    assert script.parse_env_file(env) == {"ARTIFICIAL_ANALYSIS_API_KEY": "fixture-only"}
    handler = script.SameOriginRedirects()
    with pytest.raises(HTTPError):
        handler.redirect_request(
            Request(script.API_URL),
            BytesIO(),
            302,
            "redirect",
            HTTPMessage(),
            "https://example.invalid/path",
        )


def test_missing_cost_stays_unknown(script: ModuleType) -> None:
    data = models()
    data[0]["artificial_analysis_intelligence_index_cost"] = {}
    assert (
        script.make_snapshot(data, "4", "a" * 64)["models"][0][
            "benchmark_task_cost_usd"
        ]
        is None
    )
    assert "unknown" in script.make_report(data, "4", "a" * 64)
