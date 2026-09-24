# 2026-09-24 runner empty-review dispatch guard

## 문제

R2-06 재시도에서 supervisor가 독립 review를 요청했지만 수신 agent가 0명인 host 상태에서 `collaboration.wait`를 호출해 bounded task가 무기한 대기했다. 이는 자료 부족이 아니라 dispatch 환경의 실행 제어 결함이며, 작업을 성공으로 승격하지 않았다.

## 변경

`backend/jusik/development_runner.py`의 runtime prompt에 빈 receiver 목록에서 `collaboration.wait`를 호출하지 말라는 fail-closed 규칙을 추가했다. supervisor는 현재 turn에서 bounded read-only review를 수행하거나, 근거를 남긴 유한 `review-unavailable` 결과로 종료해야 한다. `backend/tests/test_development_runner.py`에 해당 계약 회귀를 추가했다.

## 검증

- `backend/.venv/bin/python -m pytest backend/tests/test_development_runner.py -q`: 66 passed
- Ruff check: passed
- strict mypy: passed
- 기존 R2-06 구현·자료·주문/PAPER/live 경계는 변경하지 않았다.

## 제한

현재 R2-06 runner attempt는 이 변경 전 prompt로 이미 실행 중이었으므로 성공으로 재해석하지 않는다. 다음 cycle에서 fresh retry가 새 prompt를 사용해야 한다. R2-06의 complete fills·배당/FX·benchmark·미래 관찰 자료 및 경제 acceptance는 여전히 미완료다.

후속 독립 review에서 직접 생성 envelope의 finite `Decimal` metadata가 JSON 직렬화 전에 남는 P2가 발견되어, `market_counterfactual_comparison.py`에서 metadata를 lossless decimal string으로 정규화하고 회귀를 추가했다. 해당 focused suite는 42 passed, Ruff와 strict mypy도 통과했다.

최신 재시도는 현재 main 기준 counterfactual/accounting focused pytest 79개와 mypy를 통과했고, 포맷 보정 후 counterfactual 42개·Ruff도 통과했다. 독립 review dispatch는 여전히 receiver 없는 `collaboration.wait`에서 멈춰 attempt를 interrupted로 보존했으며, 이를 성공으로 승격하지 않는다.

후속 runner 보완으로 child stdout의 구조화된 `collaboration.wait` 이벤트에 빈 `receiver_thread_ids`가 나타나면 131 KiB tail 범위에서 감지해 child를 종료하고 `empty_review_dispatch`로 격리하도록 했다. 개발 runner focused pytest 67개·Ruff·strict mypy가 통과했다. 이는 무기한 대기를 실패로 바꾸는 fail-closed 보호이며 review 성공을 대신하지 않는다.
