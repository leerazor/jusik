# portfolio secondary metrics

- 상태: 완료
- 기록 시각: 2026-09-18T00:00:00Z
- 작업 slug: `portfolio-performance-metrics-secondary`
- 기준/구현: `39fd3a0` / 작업 브랜치 커밋 참조
- 범위: 기존 v1 envelope에 `secondary_metrics`만 결정적으로 추가했다. 기존 total/CAGR/MDD/Sharpe/Calmar result와 evaluator, policy, bundle, broker·runner·strategy·order 경로는 변경하지 않았다.

## 변경과 결정

- simulation artifact SHA 검증 이후 persisted `simulation.json.metrics.trade_count=171`을 envelope에 추가했다.
- full NAV chronology에서 running peak와 이후 peak 이상 회복 시점을 UTC로 비교해 최대 recovery duration을 seconds 및 ISO 8601 duration으로 기록한다.
- realized trade P&L이 없어서 `profit_factor`·`max_consecutive_loss`는 `missing_realized_trade_pnl`, downside target 정책이 없어서 `sortino`는 `missing_downside_target_policy`로 unavailable이다. 0% target이나 trade P&L을 합성하지 않는다.

## 문서·계약 영향

- 사용자 문서: `docs/market-performance-metrics.md`에 secondary metrics 계약을 추가했다.
- 운영 문서: 해당 없음. 오프라인 읽기 전용이다.
- API·설정·데이터 계약: 기존 `portfolio-performance-metrics-envelope/v1`에 `secondary_metrics` field를 추가했으며 기존 `result.metrics`는 보존한다.

## 검증

- `PYTHONPATH=backend ... pytest backend/tests/test_research_portfolio_performance_metrics.py -q` — 9 passed
- `... ruff check ...` 및 `ruff format --check ...` — 통과
- `PYTHONPATH=backend ... python -m mypy --strict ...` — 통과
- corrected bundle 재현 — trade_count 171, maximum recovery duration 23,707,800 UTC seconds (`P274DT9H30M0S`), 세 unavailable reason 확인
- simulation.json tamper — artifact SHA chain에서 fail-closed

## 안전·운영 상태

- 고정 audit artifact만 읽었다. 연구 재실행, 네트워크 수집, PAPER/live, 실제 주문, 운영 DB, 서비스, remote push는 수행하지 않았다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-calendar-2026-krx-holiday-correction/run-v3`; 기존 manifest SHA chain을 재사용한다.
- 남은 작업·차단 조건: realized trade P&L 및 downside target 정책 근거가 추가되기 전까지 해당 secondary metrics는 unavailable이다.
- 다음 시작: 부모 agent가 diff와 통합 검증을 확인한다.
