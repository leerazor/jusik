"""Fail-closed validation for externally captured KRX status evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

KrxStatus = Literal["trading_halt", "management", "normal"]


class KrxStatusEvidenceRow(BaseModel):
    """One explicitly classified KRX status row from an official source."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    session: date
    symbol: str = Field(pattern=r"^\d{6}$")
    status: KrxStatus
    reason: str | None = Field(default=None, max_length=1000)


class KrxStatusEvidenceReport(BaseModel):
    """Target-bound status evidence; absence never means normal."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["krx-status-evidence-v1"] = "krx-status-evidence-v1"
    session: date
    target_symbols: tuple[str, ...]
    rows: tuple[KrxStatusEvidenceRow, ...]
    missing_symbols: tuple[str, ...]
    duplicate_symbols: tuple[str, ...]
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    readiness: Literal["ready", "insufficient"]
    readiness_reason: str | None = None


def parse_krx_status_evidence(
    body: bytes,
    *,
    session: date,
    target_symbols: tuple[str, ...],
) -> KrxStatusEvidenceReport:
    """Parse a captured status payload without treating missing rows as normal."""
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("krx_status_invalid_json") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("krx_status_invalid_root")
    raw_rows = payload.get("rows", payload.get("OutBlock_1"))
    if not isinstance(raw_rows, list):
        raise ValueError("krx_status_rows_missing")
    targets = tuple(dict.fromkeys(target_symbols))
    if any(
        not isinstance(symbol, str) or len(symbol) != 6 or not symbol.isdigit()
        for symbol in targets
    ):
        raise ValueError("krx_status_target_symbol_invalid")
    rows: list[KrxStatusEvidenceRow] = []
    for raw in raw_rows:
        if not isinstance(raw, Mapping):
            raise ValueError("krx_status_row_invalid")
        raw_session = raw.get("session", raw.get("BAS_DD"))
        raw_symbol = raw.get("symbol", raw.get("ISU_CD"))
        raw_status = raw.get("status")
        if raw_status is None:
            raise ValueError("krx_status_explicit_status_required")
        try:
            row = KrxStatusEvidenceRow(
                session=date.fromisoformat(str(raw_session)),
                symbol=str(raw_symbol),
                status=raw_status,
                reason=raw.get("reason", raw.get("LIST_BZ_RSN_NM")),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("krx_status_row_invalid") from exc
        if row.session != session:
            raise ValueError("krx_status_session_mismatch")
        rows.append(row)
    target_set = set(targets)
    observed = [row.symbol for row in rows if row.symbol in target_set]
    duplicates = tuple(
        sorted({symbol for symbol in observed if observed.count(symbol) > 1})
    )
    missing = tuple(sorted(target_set - set(observed)))
    ready = bool(targets) and not missing and not duplicates
    return KrxStatusEvidenceReport(
        session=session,
        target_symbols=targets,
        rows=tuple(rows),
        missing_symbols=missing,
        duplicate_symbols=duplicates,
        source_sha256=hashlib.sha256(body).hexdigest(),
        readiness="ready" if ready else "insufficient",
        readiness_reason=(
            None if ready else "target status coverage is incomplete or duplicated"
        ),
    )


__all__ = [
    "KrxStatusEvidenceReport",
    "KrxStatusEvidenceRow",
    "parse_krx_status_evidence",
]
