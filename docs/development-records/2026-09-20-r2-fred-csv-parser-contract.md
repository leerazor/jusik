# FRED 공개 CSV parser 계약

- 상태: 완료된 기술 slice; 자동 FX/NAV 적용은 차단
- 기록 시각: 2026-09-20T00:00:00Z
- 작업 slug: `r2-fred-csv-parser-contract-20260920`
- 기준/통합: `22677a8` / `a061838`
- 범위: 기존 JSON parser와 분리된 FRED graph CSV offline parser와 inline regression
  cases만 추가했습니다.
  network transport, credentials, readiness, performance, 원장, service, PAPER/live는
  변경하지 않았습니다.

## 변경과 결정

- exact header `observation_date,DEXKOUS`만 허용하고 UTF-8 BOM을 처리합니다.
- 명시적 요청 범위, Decimal 값, 빈 관측값(`.`), 중복 날짜, malformed row/header,
  empty/no-coverage를 fail-closed로 처리합니다.
- `available_at`은 호출자가 제공한 retrieval 시각을 보존하며, 없을 때의 기본값은
  기존 JSON parser와 같은 다음 날 UTC 자정입니다.
- parser 통과는 source parsing만 의미하며 FRED CSV의 PIT availability나 application
  completeness를 증명하지 않습니다.
- 보존한 audit CSV를 offline replay한 결과 요청 기간 내 유효 관측은 251개였고, caller가
  고정한 retrieval 시각을 모든 row에 보존했습니다. 이 replay도 source/application
  readiness를 승격하지 않습니다.

## 검증

- `PYTHONPATH=backend /home/kwl/projects/jusik/backend/.venv/bin/python -m pytest
  backend/tests/test_market_data_collector.py -k 'fred' -q` — 11 passed
- `PYTHONPATH=backend /home/kwl/projects/jusik/backend/.venv/bin/python -m pytest
  backend/tests/test_market_data_collector.py -q` — 137 passed
- `/home/kwl/projects/jusik/backend/.venv/bin/python -m ruff check
  backend/jusik/market_data_collector.py backend/tests/test_market_data_collector.py` — passed
- `/home/kwl/projects/jusik/backend/.venv/bin/python -m mypy --config-file
  backend/pyproject.toml backend/jusik/market_data_collector.py` — passed
- `git diff --check` — passed
- audit CSV offline replay — 251 parsed rows, raw SHA
  `06751750c69089e33aaac8d5bdd0e102887c9c4db2d4d5da529561ad318f8210`

## 제한과 다음 시작

- 공개 CSV를 NetworkCollectorTransport나 readiness에 연결하지 않았습니다.
- 다음 작업은 CSV source availability/application evidence를 독립적으로 검증하는 것이며,
  결측을 carry-forward하거나 Sharpe를 계산하지 않습니다.
