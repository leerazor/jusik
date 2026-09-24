# R1-05 대체 US historical provider 조사

## 결과

기존 Yahoo/EODHD/Alpha/Stooq 결과로 남은 LIME·MDA 누락을 해결할 수 있는 공식 대체 경로를 read-only로 조사했다.

- [Nasdaq Data Link 문서](https://docs.data.nasdaq.com/docs/r-installation)는 무료 계정/API key로 50회/일 이하 사용이 가능하다고 설명한다.
- [Nasdaq 공식 Bars 설명](https://www.nasdaq.com/products/data/data-link/api)는 US equity 10년 historical Bars가 subscriber 대상이라고 명시한다. 따라서 무료 계정만으로 complete coverage를 보장한다고 가정하지 않는다.
- [Alpaca 공식 market-data 문서](https://docs.alpaca.markets/us/docs/about-market-data-api)는 무료 tier의 equity coverage가 IEX임을 명시한다. 전체 US 거래소·delisted identity·PIT publication/complete coverage의 대체 근거로 채택하지 않는다.

## 결정

새 provider를 자동 추가하거나 기존 결과를 합치지 않았다. R1-05 승격에는 여전히 symbol/period/exchange/currency, request/session identity, cause, historical observed time, complete coverage가 필요하다. Nasdaq Data Link를 bounded probe하려면 별도 `NASDAQ_DATA_LINK_API_KEY`가 필요하고, probe 성공 후에도 dataset entitlement와 PIT 필드를 별도 검증해야 한다.

실거래·PAPER/live·전략 성과·기존 canonical cache 변경은 없었다.
