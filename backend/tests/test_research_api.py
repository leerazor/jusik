import asyncio
import time
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from jusik.operations_models import StrategyDefinition
from jusik.operations_store import OperationsStore
from jusik.research_app import create_research_app
from jusik.research_config import PAPER_BASE_URL, ResearchSettings
from jusik.research_engine import ENGINE_SPECIFICATION, snapshot_hash
from jusik.research_models import (
    DailyBar,
    ResearchInputSnapshot,
    ResearchRunRequest,
    SymbolSnapshot,
)
from jusik.research_store import ResearchStore


class StubProvider:
    async def collect(self, request: ResearchRunRequest) -> ResearchInputSnapshot:
        first = request.start_date - timedelta(days=65)
        snapshots = []
        for symbol in request.symbols:
            rows = []
            for index in range(70):
                price = Decimal(100 + index)
                rows.append(
                    DailyBar(
                        date=first + timedelta(days=index),
                        open=price,
                        high=price,
                        low=price,
                        close=price,
                        volume=100,
                        adjusted_open=price,
                        adjusted_high=price,
                        adjusted_low=price,
                        adjusted_close=price,
                    )
                )
            snapshots.append(
                SymbolSnapshot(
                    symbol=symbol,
                    market="KOSPI",
                    bars=rows,
                    source_url="https://example.com/daily",
                )
            )
        return ResearchInputSnapshot(
            captured_at=datetime.now(UTC),
            requested_start=request.start_date,
            requested_end=request.end_date,
            symbols=snapshots,
            events=request.events,
        )


def test_api_runs_lists_and_replays_immutable_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ResearchStore(tmp_path / "research.db")
    settings = ResearchSettings(
        app_key="key",
        app_secret="secret",
        base_url=PAPER_BASE_URL,
        db_path=tmp_path / "unused.db",
    )
    app = create_research_app(
        action_collection_enabled=False,
        settings=settings,
        store=store,
        provider=StubProvider(),
    )
    body = {
        "start_date": "2024-04-01",
        "end_date": "2024-04-05",
        "initial_cash": "1000000",
        "fee_rate": "0",
        "slippage_rate": "0",
        "sell_tax_rate": "0",
    }
    with TestClient(app) as client:
        created = client.post("/api/research/runs", json=body)
        assert created.status_code == 202
        run_id = created.json()["id"]
        for _ in range(100):
            detail = client.get(f"/api/research/runs/{run_id}")
            if detail.json()["status"] == "completed":
                break
            time.sleep(0.01)
        assert detail.json()["request"]["symbols"] == ["005930", "000660"]
        assert detail.json()["result"]["live_promotion_eligible"] is False

        listed = client.get("/api/research/runs")
        assert listed.status_code == 200
        assert listed.json()[0]["id"] == run_id
        assert "input_snapshot" not in listed.json()[0]

        replayed = client.post(f"/api/research/runs/{run_id}/replay")
        assert replayed.status_code == 202
        replay_id = replayed.json()["id"]
        for _ in range(100):
            replay = client.get(f"/api/research/runs/{replay_id}").json()
            if replay["status"] == "completed":
                break
            time.sleep(0.01)
        assert replay["replay_of"] == run_id
        assert replay["input_hash"] == detail.json()["input_hash"]
        assert replay["result"] == detail.json()["result"]

        with monkeypatch.context() as scoped:
            scoped.setattr("jusik.research_app.IMPLEMENTATION_HASH", "changed")
            incompatible = client.post(f"/api/research/runs/{run_id}/replay")
            assert incompatible.status_code == 409

        with monkeypatch.context() as scoped:
            changed_spec = ENGINE_SPECIFICATION.model_copy(update={"warmup_bars": 61})
            scoped.setattr("jusik.research_app.ENGINE_SPECIFICATION", changed_spec)
            incompatible = client.post(f"/api/research/runs/{run_id}/replay")
            assert incompatible.status_code == 409


def test_api_rejects_future_end_and_replay_without_snapshot(tmp_path: Path) -> None:
    store = ResearchStore(tmp_path / "research.db")
    settings = ResearchSettings(
        app_key="key",
        app_secret="secret",
        base_url=PAPER_BASE_URL,
    )
    app = create_research_app(
        action_collection_enabled=False,
        settings=settings,
        store=store,
        provider=StubProvider(),
    )
    with TestClient(app) as client:
        queued = store.create(
            ResearchRunRequest(
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 2),
            )
        )
        response = client.post(
            "/api/research/runs",
            json={"start_date": "2099-01-01", "end_date": "2099-01-02"},
        )
        assert response.status_code == 422
        replay = client.post(f"/api/research/runs/{queued.id}/replay")
        assert replay.status_code == 409


def test_store_marks_interrupted_work_failed(tmp_path: Path) -> None:
    store = ResearchStore(tmp_path / "research.db")
    run = store.create(
        ResearchRunRequest(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 2),
        )
    )
    store.update_status(run.id, "running")

    assert store.recover_interrupted() == 1
    recovered = store.get(run.id)
    assert recovered.status == "failed"
    assert recovered.error is not None


def test_store_refuses_to_replace_an_input_snapshot(tmp_path: Path) -> None:
    store = ResearchStore(tmp_path / "research.db")
    request = ResearchRunRequest(
        start_date=date(2024, 4, 1),
        end_date=date(2024, 4, 5),
    )
    provider = StubProvider()
    snapshot = asyncio.run(provider.collect(request))
    run = store.create(request, snapshot=snapshot)
    changed = snapshot.model_copy(
        update={"captured_at": datetime(2025, 1, 1, tzinfo=UTC)}
    )

    with pytest.raises(ValueError, match="immutable"):
        store.save_snapshot(run.id, changed, "different")


def test_symbol_metadata_persists_without_changing_research_snapshot_hash(
    tmp_path: Path,
) -> None:
    path = tmp_path / "research.db"
    store = ResearchStore(path)
    request = ResearchRunRequest(
        start_date=date(2024, 4, 1),
        end_date=date(2024, 4, 5),
    )
    input_snapshot = asyncio.run(StubProvider().collect(request))
    before = snapshot_hash(input_snapshot)

    stored = store.upsert_symbol_metadata("005930", " 삼성전자 ")
    reopened = ResearchStore(path)

    assert stored.name == "삼성전자"
    assert reopened.list_symbol_metadata() == [stored]
    assert snapshot_hash(input_snapshot) == before


def test_operations_api_updates_independent_universe_and_paper_strategy(
    tmp_path: Path,
) -> None:
    store = ResearchStore(tmp_path / "research.db")
    settings = ResearchSettings(
        app_key="key",
        app_secret="secret",
        base_url=PAPER_BASE_URL,
        db_path=tmp_path / "research.db",
    )
    app = create_research_app(
        action_collection_enabled=False,
        settings=settings,
        store=store,
        provider=StubProvider(),
    )
    store.upsert_symbol_metadata("035420", "NAVER")

    with TestClient(app) as client:
        metadata = client.get("/api/research/symbol-metadata")
        assert metadata.status_code == 200
        assert metadata.json()[0]["symbol"] == "035420"
        assert metadata.json()[0]["name"] == "NAVER"
        updated = client.put("/api/operations/universe", json={"symbols": ["035420"]})
        assert updated.status_code == 200
        assert updated.json() == ["035420"]
        activated = client.post(
            "/api/operations/strategies/activate",
            json={"version": "trend_20_v1", "mode": "paper"},
        )
        assert activated.status_code == 200
        status_response = client.get("/api/operations")
        assert status_response.status_code == 200
        payload = status_response.json()
        assert payload["universe"] == ["035420"]
        assert payload["execution_mode"] == "paper_only"
        assert payload["stream"]["state"] == "disabled"


def test_operations_api_returns_conflict_for_unvalidated_ai_strategy(
    tmp_path: Path,
) -> None:
    run_store = ResearchStore(tmp_path / "research.db")
    operation_store = OperationsStore(tmp_path / "research.db")
    operation_store.save_ai_suggestion(
        StrategyDefinition(
            version="ai_pending_api",
            name="AI 제안 · 미검증",
            fast_window=10,
            slow_window=30,
            definition="후속 관측이 필요한 후보",
        ),
        "후속 관측 대기",
        proposed_after_date=date.today(),
        provenance={"source_run_id": "source-run"},
    )
    settings = ResearchSettings(
        app_key="key",
        app_secret="secret",
        base_url=PAPER_BASE_URL,
        db_path=tmp_path / "research.db",
    )
    app = create_research_app(
        action_collection_enabled=False,
        settings=settings,
        store=run_store,
        provider=StubProvider(),
        operations_store=operation_store,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/operations/strategies/activate",
            json={"version": "ai_pending_api", "mode": "paper"},
        )

    assert response.status_code == 409
    assert "later-period" in response.json()["detail"]
