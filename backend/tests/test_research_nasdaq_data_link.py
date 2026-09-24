from __future__ import annotations

import sys
import types

from jusik.research_nasdaq_data_link import probe_dataset


def test_probe_uses_sdk_and_returns_schema(monkeypatch) -> None:
    calls: list[tuple[str, int]] = []

    class Frame:
        columns = ("Date", "Value")

        def __len__(self) -> int:
            return 1

    def get(dataset: str, *, rows: int) -> Frame:
        calls.append((dataset, rows))
        return Frame()

    sdk = types.SimpleNamespace(
        ApiConfig=types.SimpleNamespace(api_base="", api_key=None), get=get
    )
    monkeypatch.setitem(sys.modules, "nasdaqdatalink", sdk)

    result = probe_dataset("FRED/GDP", "secret", rows=1)

    assert result.status == "ready"
    assert result.rows == 1
    assert result.columns == ("Date", "Value")
    assert calls == [("FRED/GDP", 1)]
    assert sdk.ApiConfig.api_base == "https://data.nasdaq.com/api/v3"
    assert sdk.ApiConfig.api_key == "secret"


def test_probe_fails_closed_without_sdk(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "nasdaqdatalink", None)

    result = probe_dataset("FRED/GDP", "secret")

    assert result.status == "missing_dependency"
    assert result.error == "nasdaq_data_link_sdk_missing"


def test_probe_does_not_expose_provider_error(monkeypatch) -> None:
    class DataLinkError(Exception):
        pass

    def get(_dataset: str, *, rows: int) -> object:
        raise DataLinkError("response contains a secret token")

    sdk = types.SimpleNamespace(
        ApiConfig=types.SimpleNamespace(api_base="", api_key=None), get=get
    )
    monkeypatch.setitem(sys.modules, "nasdaqdatalink", sdk)

    result = probe_dataset("FRED/GDP", "secret")

    assert result.status == "error"
    assert result.error == "nasdaq_data_link_error"
