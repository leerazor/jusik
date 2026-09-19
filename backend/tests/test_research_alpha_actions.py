from datetime import UTC, date, datetime

from jusik.research_alpha_actions import alpha_action_url, parse_alpha_actions


def test_parse_alpha_dividend_preserves_payment_and_observation() -> None:
    body = (
        b'{"data":[{"ex_dividend_date":"2024-06-11",'
        b'"payment_date":"2024-06-28","amount":"0.0100"}]}'
    )
    result = parse_alpha_actions(
        body,
        symbol="NVDA",
        kind="dividend",
        start=date(2024, 1, 1),
        end=date(2024, 12, 31),
        source_url=alpha_action_url(symbol="NVDA", kind="dividend", api_key="secret"),
        observed_at=datetime(2026, 9, 20, 1, tzinfo=UTC),
    )

    assert len(result) == 1
    assert result[0].event_date == date(2024, 6, 11)
    assert result[0].payment_date == date(2024, 6, 28)
    assert result[0].amount == "0.0100"
    assert "apikey" not in result[0].source_url
    assert len(result[0].raw_sha256) == 64


def test_parse_alpha_split_requires_explicit_factor_and_date_range() -> None:
    body = (
        b'{"data":[{"effective_date":"2024-06-10","split_factor":"10:1"},'
        b'{"effective_date":"2020-01-01","split_factor":"2:1"}]}'
    )
    result = parse_alpha_actions(
        body,
        symbol="NVDA",
        kind="split",
        start=date(2024, 1, 1),
        end=date(2024, 12, 31),
        source_url="https://www.alphavantage.co/query",
        observed_at=datetime(2026, 9, 20, 1, tzinfo=UTC),
    )

    assert len(result) == 1
    assert result[0].numerator == 10
    assert result[0].denominator == 1
