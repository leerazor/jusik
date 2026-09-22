# Alpha Vantage 제외 심볼 listing receipt

- 상태: 완료·보조 historical listing 원문 확보, R1-05/PIT/경제 acceptance 미승격
- 요청: `LISTING_STATUS(date=2025-09-11)` 1회, HTTP 200, raw 867,056 bytes.
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260922-alpha-excluded-listing-20260922/receipt.json`

## 결과

- request-excluded 25개 중 24개가 Alpha 원문에 존재했다.
- 24개 모두 해당 요청 날짜 기준 `Active`이고, 21개는 SEC ticker map에 없던 심볼이다.
- `DYNX`는 Alpha 원문에도 없으므로 `unresolved`로 유지한다.
- raw CSV SHA, endpoint, request parameter, HTTP status, captured time, matched row와 누락 목록을 receipt에 보존했다.

## 해석 경계

Alpha `LISTING_STATUS`는 historical listing 보조 근거다. 이것만으로 Yahoo 요청 실패의 원인, 거래중단, provider coverage, 기업행사 publication time, historical `observed_at`을 확정하지 않는다. `captured_at`은 observation time으로 사용하지 않으며 PIT·경제 평가는 `not-evaluated`, 자동 ledger 적용은 금지한다.

## 검증

- Alpha CSV parser accepted ordinary rows 6,466개.
- 대상 심볼 raw match 24개, unmatched 1개(`DYNX`).
- 네트워크 호출 1회, 주문·PAPER/live·DB·서비스·remote 변경 0회.
