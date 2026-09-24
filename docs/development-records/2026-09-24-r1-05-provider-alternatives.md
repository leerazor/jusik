# R1-05 대체 US historical provider 조사

## 결과

기존 Yahoo/EODHD/Alpha/Stooq 결과로 남은 LIME·MDA 누락을 해결할 수 있는 공식 대체 경로를 read-only로 조사했다.

- [Nasdaq Data Link 문서](https://docs.data.nasdaq.com/docs/r-installation)는 무료 계정/API key로 50회/일 이하 사용이 가능하다고 설명한다.
- [Nasdaq 공식 Bars 설명](https://www.nasdaq.com/products/data/data-link/api)는 US equity 10년 historical Bars가 subscriber 대상이라고 명시한다. 따라서 무료 계정만으로 complete coverage를 보장한다고 가정하지 않는다.
- [Alpaca 공식 market-data 문서](https://docs.alpaca.markets/us/docs/about-market-data-api)는 무료 tier의 equity coverage가 IEX임을 명시한다. 전체 US 거래소·delisted identity·PIT publication/complete coverage의 대체 근거로 채택하지 않는다.

## 결정

새 provider를 자동 추가하거나 기존 결과를 합치지 않았다. R1-05 승격에는 여전히 symbol/period/exchange/currency, request/session identity, cause, historical observed time, complete coverage가 필요하다. Nasdaq Data Link를 bounded probe하려면 별도 `NASDAQ_DATA_LINK_API_KEY`가 필요하고, probe 성공 후에도 dataset entitlement와 PIT 필드를 별도 검증해야 한다.

실거래·PAPER/live·전략 성과·기존 canonical cache 변경은 없었다.

## 키 추가 후 bounded probe

- 2026-09-24 KST에 `.env`의 `NASDAQ_DATA_LINK_API_KEY`, `ALPACA_API_KEY`, `ALPACA_API_SECRET` 변수 존재만 확인했다. 값은 출력·기록하지 않았다.
- Alpaca `data.alpaca.markets`의 AAPL IEX 일봉 과거 범위(2024-01-02~2024-01-05, limit=1)는 HTTP 200과 bar 1건을 반환했다. 이는 인증·기본 IEX 조회 성공 증거이지 전체 거래소·delisted·PIT 완전성 증거가 아니다.
- Nasdaq Data Link의 `FRED/GDP` 및 `WIKI/GOOG` bounded endpoint는 HTTP 403 HTML을 반환했다. JSON 권한 오류가 아닌 실행 환경의 edge/bot 차단으로 분류했으며, 키 무효나 premium entitlement로 단정하지 않는다. 재시도 가능한 probe로 남긴다.

## 다음 시작

Nasdaq endpoint를 공식 클라이언트/허용 네트워크에서 재시도해 인증과 dataset entitlement를 분리하고, 성공하더라도 대상 심볼의 기간·거래소·관측시점·완전성을 별도로 검증한다. Alpaca는 보조 진단 소스로만 유지한다.

## Nasdaq 재시도 결과

- 데이터 endpoint에 API key를 query parameter로 전달하거나 `X-API-Key` header로 전달하는 두 방식을 재시도했지만 모두 HTTP 403 HTML이었다.
- 동일 호스트의 잘못된 API 경로는 JSON `QECx01`을 반환했으므로 DNS/전체 네트워크 단절은 아니다. 데이터 경로의 WAF/edge 차단과 키 entitlement를 분리할 수 없어 키 무효로 판정하지 않는다.
- 추가적인 키 재발급은 요구하지 않는다. 다음 검증은 허용 네트워크 또는 Nasdaq 공식 클라이언트 경로에서 수행한다.

## Python SDK 경로

- `backend/pyproject.toml`에 `nasdaq` 선택 의존성(`nasdaq-data-link>=1,<2`)을 추가하고, `jusik.research_nasdaq_data_link`에 공식 `nasdaqdatalink.get()` bounded probe를 구현했다.
- probe는 `ApiConfig.api_key`와 공식 `https://data.nasdaq.com/api/v3` base URL을 사용하고, 응답 원문·키를 출력하지 않는다. 성공해도 canonical market history로 자동 승격하지 않는다.
- `backend/tests/test_research_nasdaq_data_link.py` 3개와 Ruff·strict mypy를 통과했다.
- 실제 `.env` 키로 `FRED/GDP`를 SDK 조회한 결과는 `DataLinkError`로 실패했다. SDK 호출 방식 자체는 검증됐지만 현재 환경의 403 edge 차단은 해결되지 않았다.

재현 명령:

```text
backend/.venv/bin/python -m pip install -e 'backend[nasdaq]'
backend/.venv/bin/python -m jusik.research_nasdaq_data_link --dataset FRED/GDP --rows 1 --env-file .env
```
