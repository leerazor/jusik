# R6 KRX response and zero-OHLC diagnostics

- 상태: 기술 진단 계약 완료·한국 자료 readiness 차단
- 기록 시각: 2026-09-20T03:20:00Z
- 작업 slug: `r6-krx-diagnostics-20260920`
- 통합 commit: `76d4569`

## 변경과 결정

- `diagnose_krx_cache()`와 `diagnose-krx-cache` CLI를 추가했습니다. 네트워크를 호출하거나
  cache를 변경하지 않고 HTTP status, raw SHA/size 무결성, parser/coverage 상태, membership
  행 수, 유효 OHLCV bar 수, zero/missing OHLCV 행 수와 readiness를 분리합니다.
- KRX zero-OHLC/volume 0 행은 membership은 보존하지만 bar는 만들지 않는 기존 parser 정책을
  그대로 사용합니다. zero 행이 있으면 readiness를 `insufficient`로 fail-closed 유지합니다.
- 실패 HTTP 응답이 cache에 없다는 사실을 과거 성공으로 합성하지 않습니다. 진단 결과의
  `http_status_counts`는 실제 cache에서 관측된 응답만 포함합니다.

## 실제 cache 진단

- 입력 cache: `/home/kwl/.local/share/jusik/portfolio-audit/20260915-market-data-live-contract-fixes/kr-approved-smoke-cache/`
- artifact: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-r6-krx-diagnostics/report.json`
- artifact SHA-256: `8c9fa160e597eba627ae27f7353ccfb8f59f7ff55157c7040f822a79650815bb`
- 관측: HTTP 200 1건, cache 무결성 통과, membership 946행, 유효 bar 917행,
  zero/missing OHLCV 29행, parser 실패 0건, coverage 실패 0건, readiness `insufficient`.

## 검증

- KRX diagnostic/zero-OHLC focused pytest — 2 passed
- Ruff — 통과
- strict mypy (`market_data_collector.py`, `market_research_cli.py`) — 통과
- 실제 cache CLI exit 2 — readiness insufficient을 반영한 의도된 fail-closed 결과
- `git diff --check` — 통과

## 제한

- 이 작업은 한국 raw 응답의 기술 상태를 진단할 뿐, provider 전체 coverage·PIT·기업행사·
  경제 성과를 증명하지 않습니다.
- zero 행의 원인은 KRX 응답의 무거래/거래정지 표현으로 재현됐지만, 이를 임의의 가격·거래량으로
  보간하지 않았습니다. R6-03/R6-04, R4 재실행, PAPER/live 승격은 변경하지 않습니다.
