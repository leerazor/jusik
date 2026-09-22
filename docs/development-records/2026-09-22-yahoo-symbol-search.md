# Yahoo 404 심볼 alias 조사

- 상태: 완료·명시적 alias 미확인
- 범위: Yahoo chart 404 20개를 Yahoo Finance search endpoint로 1회씩 조회했다.
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260922-yahoo-symbol-search-20260922/receipt.json`

## 결과

- HTTP 200 검색 20개 중 quote 후보가 반환된 심볼은 9개였으나, 미국 원래 symbol과 동일한 명시적 US equity alias는 확인되지 않았다.
- 반환 후보 대부분은 다른 국가 거래소·mutual fund·ETF·무관 종목이었다. 이를 원래 심볼의 alias로 적용하지 않았다.
- raw search response, query, HTTP 상태, captured_at, SHA를 보존했다.

## 경계

검색 후보는 identity 증거가 아니다. alias를 추정해 chart를 재조회하거나 기존 result를 수정하지 않았다. historical publication/observed_at, delisting 원인, PIT coverage, 경제 평가는 여전히 `not-evaluated`다.

## 검증

- 검색 요청 20회, 재시도 없음.
- 주문·PAPER/live·원장·DB·서비스·remote 변경 0회.
