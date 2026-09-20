# R6 KRX zero-row adjacent-date recheck

- 기록 시각: 2026-09-20T03:25:00Z
- 목적: 기존 `2026-06-29` KRX zero-row signature를 전후 공식 STK 응답과 read-only 대조했습니다.

## 결과

| 날짜 | HTTP | membership | valid bars | 대상 29개 zero |
|---|---:|---:|---:|---:|
| 2026-06-26 | 200 | 946 | 915 | 29 |
| 2026-06-29 | 200 | 946 | 917 | 29 |
| 2026-06-30 | 200 | 945 | 917 | 28 |

`011330`은 6월 30일에만 정상 bar가 재개됐고, 나머지 28개는 계속 membership-only/zero
signature였습니다. 원문 SHA는 diagnostic summary에 고정했습니다.

- summary SHA-256: `db2b63fdf6ea427e44ed49ccae943c42a02661c3cbb242b2d3e415881a414a57`
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-krx-zero-adjacent-recheck/`

## 판정

반복되는 zero OHLCV는 provider가 no-trade 또는 상태 제한을 표현하는 강한 정황이지만, 별도
거래정지/status 원문 없이 거래정지·상장상태로 확정하지 않습니다. zero 행을 보간하거나 정상
bar로 승격하지 않았고, R6 readiness `insufficient`, R6-04 benchmark/경제 평가는 유지합니다.
