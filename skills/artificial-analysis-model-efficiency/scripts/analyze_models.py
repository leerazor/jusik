#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from decimal import ROUND_FLOOR, Decimal, InvalidOperation
from http.client import HTTPMessage
from pathlib import Path
from typing import IO, Any, TypedDict
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

API_URL = "https://artificialanalysis.ai/api/v2/language/models/free"
KEY_NAMES = (
    "ARTIFICIAL_ANALYSIS_API_KEY",
    "ARTIFICIAL_ANALYSIS_API",
    "ARTIFICAL_ANALYSIS_API_KEY",
    "ARTIFICAL_ANALYSIS_API",
)
MAX_PAGES = 100
TIMEOUT = 30


class ModelRow(TypedDict):
    name: str
    slug: str
    score: Decimal | None
    task_cost: Decimal | None
    input: Decimal | None
    output: Decimal | None


class ReportError(Exception):
    pass


class SameOriginRedirects(HTTPRedirectHandler):
    def redirect_request(
        self,
        request: Request,
        file: IO[bytes],
        code: int,
        message: str,
        headers: HTTPMessage,
        new_url: str,
    ) -> Request | None:
        source = urlsplit(request.full_url)
        target = urlsplit(new_url)
        if (
            source.scheme != "https"
            or target.scheme != "https"
            or source.netloc != target.netloc
        ):
            raise HTTPError(
                request.full_url, code, "cross-origin redirect rejected", headers, file
            )
        return super().redirect_request(request, file, code, message, headers, new_url)


def parse_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ReportError("Could not read the requested env file.") from exc
    values: dict[str, str] = {}
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        name, value = line.split("=", 1)
        name, value = name.strip(), value.strip()
        if name not in KEY_NAMES:
            continue
        if value.startswith(("'", '"')):
            quote = value[0]
            closing = value.find(quote, 1)
            suffix = value[closing + 1 :].strip() if closing >= 0 else ""
            if closing < 0 or (suffix and not suffix.startswith("#")):
                raise ReportError("The selected API-key env value has invalid quoting.")
            value = value[1:closing]
        else:
            value = value.split(" #", 1)[0].strip()
        if value:
            values[name] = value
    return values


def choose_key(values: dict[str, str]) -> str | None:
    found = [values[name] for name in KEY_NAMES if values.get(name)]
    if not found:
        return None
    if len(set(found)) != 1:
        raise ReportError(
            "Conflicting Artificial Analysis API-key variables were found."
        )
    return found[0]


def load_api_key(env_file: Path) -> str:
    env = {name: os.environ[name] for name in KEY_NAMES if os.environ.get(name)}
    key = choose_key(env) or choose_key(parse_env_file(env_file.expanduser()))
    if key:
        if any(not ("!" <= char <= "~") for char in key):
            raise ReportError(
                "The API-key value contains characters that are invalid in an HTTP header."
            )
        return key
    raise ReportError(
        f"Set one supported API-key variable or add it to {env_file}: {', '.join(KEY_NAMES)}."
    )


def decimal_value(value: object, field: str) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ReportError(f"Invalid numeric API field: {field}.")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ReportError(f"Invalid numeric API field: {field}.") from exc
    if not result.is_finite():
        raise ReportError(f"Non-finite numeric API field: {field}.")
    return result


def require_object(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReportError(f"Invalid API response field: {field}.")
    return value


def fetch_catalog(api_key: str) -> tuple[list[dict[str, Any]], str, str]:
    opener = build_opener(SameOriginRedirects())
    models: list[dict[str, Any]] = []
    ids: set[str] = set()
    total_pages: int | None = None
    version: str | None = None
    digest = hashlib.sha256()
    for page in range(1, MAX_PAGES + 1):
        request = Request(
            API_URL + "?" + urlencode({"page": page}),
            headers={"x-api-key": api_key, "Accept": "application/json"},
            method="GET",
        )
        try:
            with opener.open(request, timeout=TIMEOUT) as response:
                body = response.read()
        except HTTPError as exc:
            raise ReportError(
                f"Artificial Analysis API returned HTTP {exc.code}; check key, tier, and quota."
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ReportError(
                "Could not complete the Artificial Analysis API request."
            ) from exc
        digest.update(len(body).to_bytes(8, "big"))
        digest.update(body)
        try:
            payload = require_object(json.loads(body), "response")
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ReportError("Artificial Analysis API returned invalid JSON.") from exc

        raw_version = decimal_value(
            payload.get("intelligence_index_version"), "index version"
        )
        if raw_version is None:
            raise ReportError("API response omitted the Intelligence Index version.")
        page_version = format(raw_version.normalize(), "f")
        if version is None:
            version = page_version
        elif version != page_version:
            raise ReportError("Intelligence Index version changed during pagination.")

        pagination = require_object(payload.get("pagination"), "pagination")
        page_count = pagination.get("total_pages")
        has_more = pagination.get("has_more")
        if pagination.get("page") != page:
            raise ReportError("API returned an unexpected page number.")
        if (
            not isinstance(page_count, int)
            or isinstance(page_count, bool)
            or page_count < 1
            or not isinstance(has_more, bool)
        ):
            raise ReportError("API returned invalid pagination metadata.")
        if total_pages is None:
            total_pages = page_count
        elif total_pages != page_count:
            raise ReportError("API pagination changed while reading the catalog.")
        if page_count > MAX_PAGES:
            raise ReportError("API pagination exceeded the configured page limit.")

        data = payload.get("data")
        if not isinstance(data, list):
            raise ReportError("API response omitted the model data list.")
        for item in data:
            model = require_object(item, "model")
            model_id = model.get("id")
            if not isinstance(model_id, str) or not model_id:
                raise ReportError("API response contains a model without an ID.")
            if model_id in ids:
                raise ReportError("API pagination returned a duplicate model ID.")
            ids.add(model_id)
            models.append(model)

        if not has_more:
            if page != page_count:
                raise ReportError("API pagination ended before total_pages.")
            return models, version, digest.hexdigest()
        if page >= page_count:
            raise ReportError("API pagination requested more pages than total_pages.")
    raise ReportError("API pagination exceeded the configured page limit.")


def openai_rows(models: list[dict[str, Any]]) -> tuple[list[ModelRow], int]:
    rows: list[ModelRow] = []
    count = 0
    for model in models:
        creator = require_object(model.get("model_creator"), "model_creator")
        if creator.get("name") != "OpenAI":
            continue
        count += 1
        name = model.get("name")
        if not isinstance(name, str) or not name:
            raise ReportError("API response contains an unnamed OpenAI model.")
        slug = model.get("slug")
        if not isinstance(slug, str) or not slug:
            raise ReportError("API response contains an OpenAI model without a slug.")
        evaluation = require_object(model.get("evaluations"), "evaluations")
        score = decimal_value(
            evaluation.get("artificial_analysis_intelligence_index"),
            "Intelligence Index",
        )
        if score is not None and not Decimal(0) <= score <= Decimal(100):
            raise ReportError("OpenAI Intelligence Index score was outside 0-100.")
        costs = require_object(
            model.get("artificial_analysis_intelligence_index_cost") or {}, "cost"
        )
        task = require_object(costs.get("cost_per_task") or {}, "cost per task")
        task_cost = decimal_value(task.get("total_cost"), "task cost")
        if task_cost is not None and task_cost <= 0:
            task_cost = None
        pricing = require_object(model.get("pricing") or {}, "pricing")
        rows.append(
            {
                "name": name,
                "slug": slug,
                "score": score,
                "task_cost": task_cost,
                "input": decimal_value(
                    pricing.get("price_1m_input_tokens"), "input price"
                ),
                "output": decimal_value(
                    pricing.get("price_1m_output_tokens"), "output price"
                ),
            }
        )
    return rows, count


def fmt(value: Decimal | None, places: int = 2) -> str:
    if value is None:
        return "—"
    value = value.quantize(Decimal(1).scaleb(-places))
    return format(value.normalize(), "f")


def money(value: Decimal | None) -> str:
    return "—" if value is None else "$" + fmt(value, 6)


def cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def make_legacy_report(
    models: list[dict[str, Any]], version: str, digest: str, band_width: int
) -> str:
    rows, catalog_count = openai_rows(models)
    scored = [row for row in rows if row["score"] is not None]
    if not scored:
        raise ReportError("The API catalog contains no scored OpenAI models.")
    width = Decimal(band_width)
    highest = max(row["score"] or Decimal(0) for row in scored)
    last_lower = (highest / width).to_integral_value(rounding=ROUND_FLOOR) * width
    available = sum(row["task_cost"] is not None for row in scored)
    lines = [
        "Retrieved at (UTC): " + datetime.now(UTC).isoformat(timespec="seconds"),
        f"Intelligence Index version: v{version} (API major/minor version)",
        f"OpenAI entries: {catalog_count}; scored: {len(scored)}; task cost available: {available}",
        "Ranking: maximize Intelligence Index / cost_per_task.total_cost within each band.",
        "Points per dollar is a derived comparison aid, not an official Artificial Analysis metric.",
        "Task cost reflects the Intelligence Index evaluation workload, not a Codex agent task bill.",
        "Token prices are USD per 1M input/output tokens; free response has no current/deprecated status field.",
        "API slugs identify catalog records; map them to host model IDs and reasoning effort through an explicit allowlist before dispatch.",
        f"Catalog response SHA-256: {digest}",
        "Source: Artificial Analysis Data API (https://artificialanalysis.ai/data-api/docs)",
        "",
        "| Index band | Efficiency leader | API slug | Score | Cost / task | Lowest measured task cost | Input / output USD per 1M | Points / cost USD | Measured / scored |",
        "|---:|---|---|---:|---:|---|---:|---:|---:|",
    ]
    lower = Decimal(0)
    while lower <= last_lower:
        upper = lower + width
        band = [row for row in scored if lower <= (row["score"] or Decimal(0)) < upper]
        priced = [row for row in band if row["task_cost"] is not None]
        label = f"{fmt(lower, 0)}–<{fmt(upper, 0)}"
        coverage = f"{len(priced)}/{len(band)}"
        if not band:
            lines.append(
                f"| {label} | No scored OpenAI model | — | — | — | — | — | 0/0 |"
            )
        elif not priced:
            lines.append(
                f"| {label} | No measured task cost | — | — | — | — | — | {coverage} |"
            )
        else:
            ranked = sorted(
                priced,
                key=lambda row: (
                    -((row["score"] or Decimal(0)) / (row["task_cost"] or Decimal(1))),
                    row["task_cost"] or Decimal(0),
                    -(row["score"] or Decimal(0)),
                    row["name"].casefold(),
                ),
            )
            cheapest = min(
                priced,
                key=lambda row: (
                    row["task_cost"] or Decimal(0),
                    -(row["score"] or Decimal(0)),
                    row["name"].casefold(),
                ),
            )
            winner = ranked[0]
            ratio = (winner["score"] or Decimal(0)) / (
                winner["task_cost"] or Decimal(1)
            )
            rates = money(winner["input"]) + " / " + money(winner["output"])
            cheapest_text = (
                cell(cheapest["name"]) + " (" + money(cheapest["task_cost"]) + ")"
            )
            values = (
                label,
                cell(winner["name"]),
                cell(winner["slug"]),
                fmt(winner["score"]),
                money(winner["task_cost"]),
                cheapest_text,
                rates,
                fmt(ratio),
                coverage,
            )
            lines.append("| " + " | ".join(values) + " |")
        lower = upper
    return "\n".join(lines)


def make_snapshot(
    models: list[dict[str, Any]], version: str, digest: str
) -> dict[str, object]:
    """Export only the documented public catalog fields, never API payloads."""
    rows, _ = openai_rows(models)
    if len({row["slug"] for row in rows}) != len(rows):
        raise ReportError("API returned duplicate model slugs.")

    def number(value: Decimal | None) -> str | None:
        if value is not None and value < 0:
            raise ReportError("API returned a negative catalog number.")
        return str(value) if value is not None else None

    return {
        "schema_version": 1,
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "index_version": version,
        "response_sha256": digest,
        "complete": True,
        "models": [
            {
                "aa_slug": row["slug"],
                "index": number(row["score"]),
                "benchmark_task_cost_usd": number(row["task_cost"]),
                "input_usd_per_million": number(row["input"]),
                "output_usd_per_million": number(row["output"]),
            }
            for row in sorted(rows, key=lambda item: item["slug"])
        ],
    }


def write_snapshot(snapshot: dict[str, object], output: Path) -> None:
    """Atomically replace requested sanitized output in its existing directory."""
    temporary: Path | None = None
    try:
        if output.is_symlink() or any(parent.is_symlink() for parent in output.parents):
            raise OSError("symlink output")
        output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=output.parent, delete=False
        ) as handle:
            temporary = Path(handle.name)
            json.dump(snapshot, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output)
    except (OSError, ValueError) as exc:
        raise ReportError("Could not atomically write catalog snapshot.") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def make_report(
    models: list[dict[str, Any]],
    version: str,
    digest: str,
    band_width: int | None = None,
) -> str:
    if band_width is not None:
        return make_legacy_report(models, version, digest, band_width)
    rows, count = openai_rows(models)
    measured = [
        row for row in rows if row["score"] is not None and row["task_cost"] is not None
    ]

    def dominated(row: ModelRow) -> bool:
        score, cost = row["score"], row["task_cost"]
        if score is None or cost is None:
            return False
        return any(
            other["score"] is not None
            and other["task_cost"] is not None
            and other["score"] >= score
            and other["task_cost"] <= cost
            and (other["score"] > score or other["task_cost"] < cost)
            for other in measured
        )

    lines = [
        "Retrieved at (UTC): " + datetime.now(UTC).isoformat(timespec="seconds"),
        f"Intelligence Index version: {version}; OpenAI entries: {count}",
        f"Catalog response SHA-256: {digest}",
        "Advisory model-level Pareto view: maximize benchmark Index and minimize benchmark task cost.",
        "Benchmark task costs are not actual agent bills or evidence of first-pass task quality.",
        "No recommendation or dispatch change follows from score or price alone.",
        "Unknown task cost remains unranked; token prices are USD per million tokens.",
        "Host support and exact model/effort mapping require an explicit verified allowlist.",
        "Source: Artificial Analysis (https://artificialanalysis.ai/data-api/docs)",
        "",
        "| Model | API slug | Index | Benchmark task USD | Input / output USD per 1M | Pareto status |",
        "|---|---|---:|---:|---:|---|",
    ]
    for row in sorted(
        rows, key=lambda item: (-(item["score"] or Decimal(0)), item["slug"])
    ):
        status = (
            "unknown"
            if row["score"] is None or row["task_cost"] is None
            else "dominated"
            if dominated(row)
            else "frontier"
        )
        lines.append(
            "| "
            + " | ".join(
                (
                    cell(row["name"]),
                    cell(row["slug"]),
                    fmt(row["score"]),
                    money(row["task_cost"]),
                    money(row["input"]) + " / " + money(row["output"]),
                    status,
                )
            )
            + " |"
        )
    return "\n".join(lines)


def positive_int(value: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if result < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare OpenAI models by Artificial Analysis Intelligence Index bands and cost."
    )
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument(
        "--band-width",
        type=positive_int,
        help="Explicit legacy Index/price band report",
    )
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args(argv)
    try:
        key = load_api_key(args.env_file)
        models, version, digest = fetch_catalog(key)
        snapshot = make_snapshot(models, version, digest)
        report = make_report(models, version, digest, args.band_width)
        if args.json_output is not None:
            write_snapshot(snapshot, args.json_output)
    except ReportError as exc:
        print("Error: " + str(exc), file=sys.stderr)
        return 2
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
