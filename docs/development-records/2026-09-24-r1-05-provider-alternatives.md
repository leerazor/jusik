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
- 사용자가 검증한 방식에 맞춰 `get_table()` 경로도 추가했다. 실제 `.env` 키로 `MER/F1`, `compnumber=39102`, `paginate=True`를 조회해 HTTP 계층을 거치지 않고 1,314행·32열을 반환했다.
- `MER/F1`은 재무 데이터 테이블이므로 이 성공을 OHLCV·delisted·PIT 가격 데이터의 완전성 증거로 해석하지 않는다.
- 가격 후보 bounded probe도 추가했다. `SHARADAR/SEP`, `ticker=AAPL`은 OHLCV 필드 10개와 82행을 반환했고, `QUOTEMEDIA/PRICES`, `ticker=AAPL`은 OHLCV·조정가격 필드와 42행을 반환했다.
- 두 가격 테이블의 현재 반환 구간은 각각 2018-09-04~2018-12-31, 2017-09-01~2017-10-31로 제한적이었다. 2020년·2024년 date filter는 0행이었다. 따라서 가격 테이블 접근은 확인했지만 R1-05 complete historical/PIT evidence는 미충족이다.
- ticker를 AAPL·MSFT·TSLA로 바꿔도 `SHARADAR/SEP`의 동일 2018-09-04~2018-12-31 샘플이 반환됐다. ticker 선택 오류보다는 테이블 entitlement/샘플 제한으로 분류한다. probe 결과에 `first_date`·`last_date`를 보존한다.
- Nasdaq 공식 API 소개의 Bars 상품(`NDAQ/BAR`)도 SDK로 bounded 조회했지만 현재 계정에서는 `404 QECx02 datatable does not exist`였다. 문서상 상품 존재와 계정별 실제 테이블 entitlement를 동일하게 취급하지 않는다.
- Alpaca IEX 일봉도 AAPL·LIME·MDA에 대해 2016/2020/2024/2026 구간을 bounded 조회했다. AAPL은 2024·2026만, LIME은 2026-07-01부터, MDA는 2026-03-12부터 반환됐고 이전 구간은 0행이었다. 기존 Yahoo 부분 이력 누락을 보완하지 못하므로 canonical source로 승격하지 않는다.

## Alpha Vantage 가격 endpoint 재검증

- `jusik.research_alpha_price_probe`와 6개 회귀 테스트를 추가했다. probe는
  `TIME_SERIES_DAILY`의 응답 shape·행 수·첫/마지막 날짜만 보존하고 API key나 원문
  provider 메시지는 출력하지 않는다. `ALPHA_VANTAGE_API_KEY`와 기존 호환 alias
  `ALPHA_VANTAGE_KEY`를 모두 읽는다.
- 2026-09-24 KST에 `.env` 키로 LIME·MDA·AAPL을 각각 1회 bounded 조회했다. 세 요청 모두
  HTTP 200이었지만 `Information` envelope로 분류되어 가격 행은 0개였다. 이는 무료
  entitlement 또는 endpoint 정책 제한 가능성을 보여 주지만 원문 메시지를 보존하지
  않았으므로 원인을 premium/invalid key로 단정하지 않는다.
- 따라서 Alpha Vantage도 LIME/MDA의 누락 기간을 보완하는 historical/PIT source가
  아니며, 기존 canonical cache·성과·거래 설정은 변경하지 않았다.

재현 명령:

```text
backend/.venv/bin/python -m jusik.research_alpha_price_probe LIME --env-file .env
backend/.venv/bin/python -m jusik.research_alpha_price_probe MDA --env-file .env
```

## MarketParquet free-window 확인

- [MarketParquet의 공식 안내](https://marketparquet.com/guides/free-historical-stock-data)는
  무료 계정에 최근 약 365일의 US stock/ETF daily 파일과 delisted symbol 포함을
  설명하지만, 무료 계정 이전 날짜와 전체 archive는 별도 범위라고 명시한다.
- 2026-09-24 KST에 인증 없이 `stock_daily/2026-09-23.parquet`와 `2026-09-17.parquet`를
  각각 1회 읽기 전용으로 요청했다. 두 파일 모두 HTTP 200 Parquet 응답이었다.
  `2026-01-10`은 HTTP 401, `2025-09-11`은 HTTP 403으로 인증/범위 제한을 확인했다.
  응답 원문은 저장하지 않았고 SHA만 임시 진단에 사용했다.
- 이 원천은 canonical history에 자동 연결하지 않았다. 무료 계정 key가 있으면 최근
  365일 범위의 LIME/MDA 보완 후보로 별도 검증할 수 있지만, 기존 R1-05가 요구하는
  PIT publication/complete coverage와 배당·기업행사 근거를 자동으로 충족하지 않는다.

## MarketParquet key 추가 후 SDK 없는 bounded reader

- `.env`의 `MARKETPARQUET_API_KEY` 존재를 확인하고, `pyarrow`를 backend venv의 선택
  의존성(`marketparquet`)으로 추가했다. 새 `research_marketparquet` probe는 manifest를
  읽고 최대 파일 수를 제한하며, 2026-03-27 전후의 `timestamp`/`date` 스키마 차이를
  모두 처리한다. API key·서명 URL·원문 응답은 결과에 남기지 않는다.
- `2026-07-01` daily file 1개를 실제 읽기 전용으로 검증했다. Parquet 다운로드는
  성공했지만 LIME·MDA 행은 0개였다. 이는 해당 날짜의 provider 파일 내 미관측이지
  전체 이력 부재의 증거가 아니므로 canonical 누락 원인으로 승격하지 않는다.
- probe 회귀 테스트 4개, Ruff, strict mypy가 통과했다. full-window 수집은 provider
  요청 한도와 59MB manifest 범위를 고려해 자동으로 실행하지 않았으며, `max-files`로
  bounded 재현을 제공한다.

재현 명령:

```text
backend/.venv/bin/python -m pip install -e 'backend[nasdaq]'
backend/.venv/bin/python -m jusik.research_nasdaq_data_link --dataset FRED/GDP --rows 1 --env-file .env
backend/.venv/bin/python -m jusik.research_nasdaq_data_link --table MER/F1 --compnumber 39102 --env-file .env
backend/.venv/bin/python -m jusik.research_nasdaq_data_link --table SHARADAR/SEP --ticker AAPL --env-file .env
```
