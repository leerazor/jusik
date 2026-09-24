from __future__ import annotations

import io

import httpx
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from jusik.research_marketparquet import probe_symbols


def _parquet_bytes(column: str = "date") -> bytes:
    table = pa.table(
        {
            column: ["2026-07-01", "2026-07-01"],
            "symbol": ["LIME", "OTHER"],
        }
    )
    output = io.BytesIO()
    pq.write_table(table, output)
    return output.getvalue()


def test_probe_reads_date_schema_and_bounds() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/manifest/stock_daily"):
            return httpx.Response(
                200, json={"files": [{"download_url": "https://files.test/day"}]}
            )
        return httpx.Response(200, content=_parquet_bytes())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = probe_symbols(
            "2026-07-01", "2026-07-02", ("LIME",), "secret", client=client
        )
    assert result.status == "ready"
    assert result.rows == {"LIME": 1}
    assert result.first_date == {"LIME": "2026-07-01"}
    assert result.last_date == {"LIME": "2026-07-01"}
    assert "secret" not in repr(result)


def test_probe_accepts_legacy_timestamp_schema() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/manifest/stock_daily"):
            return httpx.Response(
                200, json={"files": [{"download_url": "https://files.test/day"}]}
            )
        return httpx.Response(200, content=_parquet_bytes("timestamp"))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = probe_symbols(
            "2026-07-01", "2026-07-02", ("LIME",), "secret", client=client
        )
    assert result.status == "ready"
    assert result.rows["LIME"] == 1


def test_probe_classifies_entitlement_and_missing_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(403))
    ) as client:
        result = probe_symbols(
            "2026-07-01", "2026-07-02", ("LIME",), "secret", client=client
        )
    assert result.status == "unavailable"
    assert result.error == "manifest_not_entitled"
    assert (
        probe_symbols("2026-07-01", "2026-07-02", ("LIME",), None).status
        == "missing_key"
    )


def test_probe_validates_bounds() -> None:
    with pytest.raises(ValueError, match="start"):
        probe_symbols("2026/07/01", "2026-07-02", ("LIME",), "secret")
    with pytest.raises(ValueError, match="after"):
        probe_symbols("2026-07-03", "2026-07-02", ("LIME",), "secret")
