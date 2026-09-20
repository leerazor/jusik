# R6 KRX service-response diagnostics

- 상태: 기술 진단 계약 완료·한국 readiness `insufficient`
- 기록 시각: 2026-09-20T05:40:00Z
- 통합 commit: `e9a6268`

## 변경

- `diagnose_krx_response()`와 `diagnose-krx-response` CLI를 추가했습니다.
- cache 진단은 `diagnose_krx_cache()`가 계속 담당하고, 서비스 응답 진단은 cache를 읽거나
  쓰지 않습니다. 서비스 결과의 `cache_integrity`는 `null`로 표시됩니다.
- HTTP 401/403, non-2xx, parser 오류, coverage 오류와 정상 응답의 OHLCV 결측을 서로 다른
  상태로 보존합니다. zero/missing OHLCV가 있으면 readiness exit code는 2입니다.

## 실제 검증

- artifact: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-r6-krx-diagnostics/service-response.json`
- artifact SHA-256: `ad733e5520027298c8e7f3f4c6966a27409d0d90778772a6a2d184285605873f`
- 결과: HTTP 200, membership 946, valid bars 917, zero/missing 29, parser/coverage는
  정상이나 readiness `insufficient`.
- focused pytest 3개, Ruff, strict mypy, 실제 CLI, diff 검사 통과.

## 제한

- 실패 HTTP 응답은 실제 요청 없이 과거 사실로 만들지 않습니다. auth/parse는 고정 fixture로
  분류 규칙만 검증합니다.
- 이 작업은 자료 품질 진단이며 한국 수익률·benchmark·PAPER/live 승격을 의미하지 않습니다.
