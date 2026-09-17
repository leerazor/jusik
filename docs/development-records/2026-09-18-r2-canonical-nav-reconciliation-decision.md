# R2 canonical NAV reconciliation decision

- 상태: 완료
- 기록 시각: 2026-09-18T00:00:00Z
- 작업 slug: `r2-canonical-nav-reconciliation-decision`
- 기준/통합: `8ceaa8a3c02fc405a6522c274dc2e605aa846f44` / `c2a16e87800f8695c70b6b47b7c0bb2a26cc7417`
- 범위: 고정 canonical approximate run의 R2-05 기술 조건만 문서화했습니다. generic reconciliation 계약, 다른 R2 항목, artifact와 코드는 변경하지 않았습니다.

## 결정

- R2-05 checkbox를 기술 `pass`로 기록합니다. 이는 R2 전체 완료나 경제적 성공을 뜻하지 않습니다.
- generic report/envelope fields는 roadmap 상태를 직접 변경하지 않으며, 이번 별도 evidence-based documentation decision은 canonical adapter에 결속된 R2-05만 판정합니다.

## 증거

- 고정 범위는 `2025-09-11`~`2026-09-11` 양끝 포함 XNYS입니다. canonical adapter가 동일 run/manifest/dataset/기간/session identity를 결속하고 expected/observed ordered sessions `252/252`를 확인합니다.
- 고정 identity SHA는 run `cc9150f8b77a27ffd6b001449c0475933ff744a37011801923f87cbdc5558275`, manifest `03ff5a140138277d2161a0896c7c8aefd64abe0545de7cc33ed9270882481205`, dataset `e58e69fc19fd89589e5cd5d55a43259f1ad28c9b9f0a87c75dd7617f28906aea`, session evidence `9348e2f3f6d2120e99460e34dd0a20e285bd14daf6c1f45f96df688b7bc1046a`입니다.
- component projection 최대 residual은 `5E-20 KRW`, independent modeled ledger residual은 `0 KRW`이며 둘 다 `1 KRW` 이하입니다. 자료 grade는 `approximate`입니다.
- 세부 계약과 선행 구현 근거는 [NAV reconciliation 계약](../research-nav-reconciliation.md)과 [canonical evidence 연결 기록](2026-09-18-r2-canonical-nav-evidence-connection.md)에 있습니다.

## 실제 검증

- `PYTHONPATH=backend /tmp/jusik-r2-canonical-venv/bin/python -m jusik.research_canonical_nav_reconciliation` — exit 0; fixed envelope, 252 rows, projection max `5E-20 KRW`.
- `PYTHONPATH=backend /tmp/jusik-r2-canonical-venv/bin/python -m jusik.market_performance_cost_evidence --canonical` — exit 0; verified approximate evidence, 106 trades / 252 sessions, independent modeled ledger residual `0 KRW`.
- `PYTHONPATH=backend /tmp/jusik-r2-canonical-venv/bin/python -m pytest backend/tests/test_research_nav_reconciliation.py backend/tests/test_research_canonical_nav_reconciliation.py backend/tests/test_market_performance_cost_evidence.py backend/tests/test_market_performance_readiness.py -q` — 114 passed.
- `PYTHONPATH=backend /tmp/jusik-r2-canonical-venv/bin/python -m pytest backend/tests/test_research_nav_reconciliation.py backend/tests/test_research_canonical_nav_reconciliation.py backend/tests/test_market_performance_cost_evidence.py backend/tests/test_market_performance_readiness.py backend/tests/test_development_runner_roadmap.py -q` — 130 passed, 3 failed in unrelated governance expectation cases (`governance is invalid` was returned where the tests expect disabled/not-ready); the focused roadmap parser tests below passed.
- focused roadmap parser tests (`test_roadmap_areas_are_lowercase_and_gates_are_independent`, `test_roadmap_fixture_pins_baseline_when_live_items_are_all_checked`, `test_roadmap_enqueue_quarantines_used_area_and_complete_area`, `test_completed_partial_slice_can_enqueue_a_distinct_task_id`, `test_missing_or_malformed_roadmap_fails_closed`) — 5 passed.
- `load_roadmap(Path('.'))` 직접 확인 — 변경 전 R2-05는 incomplete였고, 문서 변경 후 R2-05만 complete; R2-01~04·06과 R4-01~05는 incomplete.
- `git diff --check` — 통과.
- local `main`에서 focused reconciliation/readiness pytest 114개와 focused roadmap parser 2개, 두 canonical CLI, `load_roadmap()` 직접 판정, `git diff --check`가 통과했습니다.
- Terra 독립 review — P1/P2 없음, PASS. 전체 roadmap test의 동일 3개 실패가 기준 커밋에서도 재현되어 이번 변경과 무관함을 확인했습니다.

## 안전

- 문서만 변경했습니다. canonical artifact/result, research run, network, runner, PAPER/live, orders, DB, service, config, remote는 변경하거나 실행하지 않았습니다.

## 남은 blocker

- R2-01/02/03/04/06과 R2 전체는 미완료입니다. readiness는 `blocked`, `ready_for_metrics=false`, 경제 평가는 `not-evaluated`로 유지합니다.
- initial-capital timestamp, NAV timestamps, risk-free evidence가 없고, dividend/split completeness, actual costs/taxes/FX validity, DD latch/counterfactual, benchmark/future claims는 평가하지 않았습니다.
- 별도 기존 문제: `docs/market-research-mandate.sha256`의 `docs/market-research.md` digest drift 때문에 governance test 3개가 fail-closed합니다. 이번 R2-05 판정과 무관하며 별도 무결성 작업으로 처리해야 합니다.
