# 계약 회귀 번들 재검증

- 상태: 기술 계약 재검증 완료, 경제 평가는 `not-evaluated`
- 기록 시각: 2026-09-20T00:00:00Z
- 범위: KRX cache/service 진단, SEC action review queue, 비용 evidence와 성과 metrics의
  fail-closed 경계를 하나의 읽기 전용 회귀 번들로 확인했습니다.
- 검증: `backend/.venv/bin/python -m pytest backend/tests/test_market_data_collector.py
  backend/tests/test_research_sec_evidence.py backend/tests/test_research_action_review.py
  backend/tests/test_research_action_collection.py backend/tests/test_research_corporate_actions.py
  backend/tests/test_market_performance_cost_evidence.py backend/tests/test_market_performance_metrics.py -q`
  — 231 passed, 2 non-blocking deprecation warnings.
- 정적 검사: Ruff, strict mypy(관련 3개 모듈), `git diff --check` 통과.
- 확인된 경계: KRX zero/missing OHLCV는 `readiness=insufficient`으로 유지하고, SEC 후보는
  수동 review 전 `automatic_ledger_application=false`로 유지하며, 공식 broker/시장별 비용
  계약이 없으면 성과 지표 승격을 하지 않습니다.
- 제한: 새 자료 수집·요율 추정·성과 재계산·PAPER/live·주문·원격 push·Windows 종료는 하지
  않았습니다. Alpha key rotation 전 Alpha 보조 수집도 재시도하지 않습니다.
