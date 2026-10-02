from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from jusik.approved_universe import (
    ApprovedInstrument,
    ApprovedUniverseStore,
    ApprovedUniverseUpdate,
    StaleApprovedUniverseError,
)
from jusik.research_app import create_research_app
from jusik.research_config import PAPER_BASE_URL, ResearchSettings


def test_store_empty_normalization_atomicity_and_stale(tmp_path: Path) -> None:
    path = tmp_path / "approved.db"
    store = ApprovedUniverseStore(path)
    assert store.read().model_dump() == {
        "revision": 0,
        "updated_at": None,
        "instruments": [],
    }
    update = ApprovedUniverseUpdate(
        revision=0,
        instruments=[
            {"market": "KR", "exchange": "KRX", "symbol": " 0173y0 "},
            {"market": "US", "exchange": "NAS", "symbol": "aapl"},
        ],
    )
    saved = store.replace(update)
    assert [item.symbol for item in saved.instruments] == ["0173Y0", "AAPL"]
    assert ApprovedUniverseStore(path).read() == saved
    with pytest.raises(StaleApprovedUniverseError):
        store.replace(update)
    assert store.read() == saved
    with pytest.raises(ValidationError):
        ApprovedUniverseUpdate(
            revision=1,
            instruments=[
                {"market": "US", "exchange": "NYS", "symbol": "ibm"},
                {"market": "US", "exchange": "NYS", "symbol": "IBM"},
            ],
        )
    for market, exchange, symbol in [
        ("KR", "NAS", "005930"),
        ("KR", "KRX", "12345"),
        ("US", "KRX", "AAPL"),
        ("US", "NAS", "BAD TICKER"),
    ]:
        with pytest.raises(ValidationError):
            ApprovedInstrument.model_validate(
                {"market": market, "exchange": exchange, "symbol": symbol}
            )
    assert store.read() == saved
    cleared = store.replace(ApprovedUniverseUpdate(revision=1, instruments=[]))
    assert cleared.revision == 2 and cleared.instruments == []
    assert cleared.updated_at is not None


def test_api_isolated_from_operations_universe(tmp_path: Path) -> None:
    settings = ResearchSettings(
        app_key="test",
        app_secret="test",
        base_url=PAPER_BASE_URL,
        db_path=tmp_path / "research.db",
    )
    app = create_research_app(
        settings=settings,
        approved_universe_db_path=tmp_path / "approved.db",
        forward_db_path=tmp_path / "forward.db",
        universe_db_path=tmp_path / "universe-input.db",
        external_db_path=tmp_path / "external.db",
        history_dir=tmp_path / "history",
        history_db_path=tmp_path / "history.db",
        action_collection_db_path=tmp_path / "actions.db",
        portfolio_report_dir=tmp_path / "reports",
        dividend_report_dir=tmp_path / "dividends",
        validation_report_dir=tmp_path / "validation",
        prospective_dir=tmp_path / "prospective",
        prospective_source_report_dir=tmp_path / "reports",
        boundary_capture_dir=tmp_path / "boundary",
        runner_db_path=tmp_path / "runner.db",
        runner_config_path=tmp_path / "runner-config.json",
        progress_history_dir=tmp_path / "history",
        action_collection_enabled=False,
    )
    with TestClient(app) as client:
        path = "/api/research/approved-universe"
        assert client.get(path).json()["instruments"] == []
        before = client.get("/api/operations").json()
        response = client.put(
            path,
            json={
                "revision": 0,
                "instruments": [
                    {"market": "KR", "exchange": "KRX", "symbol": "0173y0"}
                ],
            },
        )
        assert response.status_code == 200
        assert response.json()["instruments"][0]["symbol"] == "0173Y0"
        assert (
            client.put(path, json={"revision": 0, "instruments": []}).status_code == 409
        )
        assert (
            client.put(
                path,
                json={
                    "revision": 1,
                    "instruments": [
                        {"market": "US", "exchange": "KRX", "symbol": "AAPL"}
                    ],
                },
            ).status_code
            == 422
        )
        assert client.get(path).json()["revision"] == 1
        after = client.get("/api/operations").json()
        assert after["universe"] == before["universe"]
