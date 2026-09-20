# R1 CollectionDiagnostics all-failed 경계

- 상태: 완료 (기술 slice); R1-05 경제 acceptance는 미완료
- 기록 시각: 2026-09-20T00:14:26Z
- 작업 slug: `r1-diagnostics-all-failed-boundary-20260920`
- 기준/통합: `4c8170c` / 없음 (작업 브랜치)
- 범위: `CollectionDiagnostics`의 직렬화 입력 검증과 해당 회귀 테스트만 수정했습니다. collector, 네트워크 수집, 원장, PAPER/live, 경제 checkbox와 원격 저장소는 변경하지 않았습니다.

## 변경과 결정

- `all_failed=true`인 진단은 최소 하나의 요청 심볼을 포함해야 하도록
  `market_history_approximate.py`의 model validator를 보강했습니다.
- 심볼·`all_failure` reason·request exclusion·reason count를 갖춘 정상 all-failed
  diagnostics의 JSON round-trip은 계속 허용합니다. 기존 validator의 coverage 및
  심볼별 실패/제외 대사는 유지했습니다.
- 빈 all-failed payload 거부와 두 요청 심볼을 포함한 정상 round-trip 회귀를
  `test_market_history_approximate.py`에 추가했습니다.

## 문서·계약 영향

- 사용자 문서: 해당 없음. 내부 typed diagnostics 경계만 보강했습니다.
- 운영 문서: 해당 없음. runner와 서비스 상태를 변경하지 않았습니다.
- API·설정·데이터 계약: `CollectionDiagnostics`의 fail-closed 입력 계약만 강화했습니다.
  자료 coverage와 경제 평가는 그대로 `not-evaluated`입니다.

## 검증

- `PYTHONPATH=backend /home/kwl/projects/jusik-portfolio-rebalance-cadence-e017/.venv/bin/python -m pytest backend/tests/test_market_history_approximate.py backend/tests/test_market_data_collector.py -q --disable-warnings --maxfail=1` — 180 passed, warnings 2개.
- `/home/kwl/projects/jusik-portfolio-rebalance-cadence-e017/.venv/bin/python -m ruff check jusik/market_history_approximate.py tests/test_market_history_approximate.py` — 통과.
- `/home/kwl/projects/jusik-portfolio-rebalance-cadence-e017/.venv/bin/python -m mypy jusik/market_history_approximate.py` — 통과.
- `git diff --check` — 통과.
- `/home/kwl/projects/jusik-portfolio-rebalance-cadence-e017/.venv/bin/python -m ruff format --check jusik/market_history_approximate.py tests/test_market_history_approximate.py` — 기존 포맷 부채 3곳으로 실패했습니다. 실패 위치는
  변경하지 않은 기존 코드이며, 새 변경 라인은 formatter와 일치합니다.

## 안전·운영 상태

- 실제 주문, PAPER/live 승격, 네트워크 수집, 원본 데이터·원장·서비스·설정 변경과
  원격 push를 수행하지 않았습니다.

## 증거와 재개

- audit: 없음 (코드·회귀 테스트 작업); manifest: 없음.
- 남은 작업·차단 조건: local `main` 통합과 독립 review가 필요합니다. 이 작업만으로
  R1-05 경제 acceptance나 자료 coverage를 승격하지 않습니다.
- 다음 시작: 감독 agent가 이 브랜치의 변경·검증 결과를 review한 뒤 local `main`에
  통합하고 등록부 상태와 통합 SHA를 갱신합니다.
