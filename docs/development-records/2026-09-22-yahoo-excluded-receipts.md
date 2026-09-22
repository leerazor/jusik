# Yahoo 제외 심볼 재조회 receipt

- 상태: 완료·provider response receipt 확보, R1-05/PIT/경제 acceptance 미승격
- 범위: 기존 100-symbol 수집에서 `request_excluded`였던 25개를 동일 warmup/기간으로 1회씩 재조회했다. 기존 result·manifest·raw는 변경하지 않았다.
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260922-yahoo-excluded-receipts-20260922/receipt.json`

## 결과

- HTTP 404: 20개. provider error text는 `No data found, symbol may be delisted`로 보존했으며 상장폐지 원인으로 확정하지 않았다.
- HTTP 200: 5개. `BERZ`, `FNGS`, `TNMG`는 272개 timestamp를 반환했고 `AVNS`, `GPACW`는 응답은 있으나 timestamp가 0개였다.
- 25개 raw response, 총 92,284 bytes, URL·요청 기간·HTTP 상태·captured_at·SHA·provider error/meta를 보존했다.

## 해석 경계

404 문구는 Yahoo의 현재 응답 관찰값이지 historical delisting 또는 R1-05 causal receipt가 아니다. HTTP 200도 complete coverage나 historical publication timestamp를 증명하지 않는다. `captured_at`은 `observed_at`으로 사용하지 않으며 PIT·경제 평가는 `not-evaluated`, 자동 ledger 적용은 금지한다.

## 검증

- 요청 25회, 네트워크 재시도 없음.
- raw SHA와 바이트 크기는 `receipt.json`에 고정했다.
- 주문·PAPER/live·원장·DB·서비스·remote 변경 0회.
