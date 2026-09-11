from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ExternalSeries = Literal[
    "treasury_2y",
    "treasury_10y",
    "vix",
    "usdkrw",
    "uso",
    "gld",
    "hyg",
    "spy",
    "smh",
]


def external_evidence_metadata() -> dict[str, object]:
    return {
        "evidence_class": "reconstructed_historical_exploration",
        "point_in_time_verified": False,
        "prospective_validation_eligible": False,
    }


class ExternalObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    series: ExternalSeries
    observed_on: date
    value: Decimal = Field(allow_inf_nan=False)
    available_at: datetime
    revision: str = Field(min_length=1, max_length=80)

    @field_validator("available_at")
    @classmethod
    def require_aware_availability(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("External availability must include a timezone.")
        return value

    @model_validator(mode="after")
    def require_positive_market_values(self) -> Self:
        if self.series not in {"treasury_2y", "treasury_10y"} and self.value <= 0:
            raise ValueError("External market observations must be positive.")
        return self


class ExternalFeatureSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    observations: tuple[ExternalObservation, ...]
    bootstrap_policy: Literal[
        "current_archive_reconstructed_with_conservative_next_utc_day"
    ] = "current_archive_reconstructed_with_conservative_next_utc_day"
    gpr_policy: Literal["archived_only_first_seen_forward"] = (
        "archived_only_first_seen_forward"
    )
    effr_policy: Literal["archived_only_not_a_feature"] = "archived_only_not_a_feature"

    @model_validator(mode="after")
    def unique_revisions(self) -> Self:
        identities = [
            (item.series, item.observed_on, item.available_at, item.revision)
            for item in self.observations
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("External observation revisions must be unique.")
        return self

    def semantic_payload(self) -> dict[str, object]:
        return {
            "bootstrap_policy": self.bootstrap_policy,
            "gpr_policy": self.gpr_policy,
            "effr_policy": self.effr_policy,
            "observations": [
                item.model_dump(mode="json")
                for item in sorted(
                    self.observations,
                    key=lambda value: (
                        value.series,
                        value.observed_on,
                        value.available_at,
                        value.revision,
                    ),
                )
            ],
        }

    def semantic_hash(self) -> str:
        encoded = json.dumps(
            self.semantic_payload(),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(encoded).hexdigest()


class ExternalSourceStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str
    status: Literal["success", "stale", "error", "pending"]
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    coverage_start: date | None = None
    coverage_end: date | None = None
    observation_count: int = Field(default=0, ge=0)
    raw_archive_count: int = Field(default=0, ge=0)
    raw_bytes: int = Field(default=0, ge=0)
    age_hours: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    error: str | None = None
    usage: Literal["feature", "diagnostic_only", "archive_only"]
