# corrected portfolio bundle 성과 지표 adapter

- 상태: 완료
- 기록 시각: 2026-09-18T00:00:00Z
- 작업 slug: `portfolio-performance-metrics-corrected-calendar`
- 기준/구현: `649e17b` / 작업 브랜치 커밋 참조
- 범위: corrected calendar bundle의 독립 회계 근거와 기존 Decimal evaluator를 연결하는 읽기 전용 adapter·회귀 테스트를 추가했다. 기존 evaluator, calculation policy, canonical/old bundle, broker·runner·strategy·order 경로는 변경하지 않았다.

## 변경과 결정

- `backend/jusik/research_portfolio_performance_metrics.py`는 등록 manifest SHA와 accounting report SHA, artifact SHA/size, UTC NAV chronology를 bounded하게 확인한 뒤 `verify_accounting_bundle()`을 호출당 정확히 한 번 실행한다.
- stored 1,172개 NAV는 UTC 날짜별 마지막 causally completed row 614개로 투영한다. total return·CAGR·Sharpe는 daily projection을 사용하고, MDD·Calmar는 전체 chronology를 사용한다. 초기자본 anchor에서 첫 NAV까지의 return은 보존하며 휴장일 forward fill·0 수익률을 합성하지 않는다.
- KOFR 근거가 없으므로 Sharpe는 `missing_risk_free_evidence`로 unavailable이며, 원래 approximate grade와 `not-evaluated` 회계 범위를 승격하지 않는다. 결과는 결정적 `portfolio-performance-metrics-envelope/v1`로 직렬화할 수 있다.
- synthetic projection/anchor 및 manifest·time-evidence·accounting-report 변조 테스트를 추가했다.

## 문서·계약 영향

- 사용자 문서: `docs/market-performance-metrics.md`의 기존 회계·성과 계약은 유지되며 이번 작업은 신규 개발 기록으로 adapter 연결을 남긴다.
- 운영 문서: 해당 없음. 오프라인 읽기 전용이며 서비스·주문·runner를 호출하지 않는다.
- API·설정·데이터 계약: 새 envelope는 `portfolio-performance-metrics-envelope/v1`이며 고정 corrected bundle의 manifest/report SHA를 요구한다.

## 검증

- `PYTHONPATH=backend ... pytest backend/tests/test_research_portfolio_performance_metrics.py -q` — 7 passed
- `... ruff check ...` 및 `ruff format --check ...` — 통과
- `PYTHONPATH=backend ... python -m mypy --strict ...` — 통과
- corrected bundle 재현 — full NAV 1,172개, UTC daily projection 614개, Sharpe unavailable(`missing_risk_free_evidence`), MDD/Calmar full chronology 확인
- envelope: `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-calendar-2026-krx-holiday-correction/performance-envelope.json`
- envelope SHA-256: `7e866ef5fb9a66943f26fa53a2ff9776f5da0ef0af453e926ceea653a547aeb8`
- total net return `0.163268124744995331088760521181225046386`, CAGR `0.0657385546019824424128508399999526447379403462741`, MDD `0.073743511705833131472595651962985278354913344557870`, Calmar `0.89144865875410304314635859803184788494925619127820`

## 안전·운영 상태

- 고정 audit artifact만 읽었다. 연구 재실행, 네트워크 수집, PAPER/live, 실제 주문, 운영 DB, 서비스, remote push는 수행하지 않았다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-calendar-2026-krx-holiday-correction/run-v3`; manifest SHA와 accounting report SHA는 adapter 상수·테스트에서 고정한다.
- 남은 작업·차단 조건: KOFR source evidence가 추가되기 전까지 Sharpe는 unavailable이다. 이 작업은 readiness 승격이나 경제 평가를 수행하지 않는다.
- 다음 시작: 부모 agent가 focused 결과와 diff를 검토한 뒤 main 통합 여부를 결정한다.
