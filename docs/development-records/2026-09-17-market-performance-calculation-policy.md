# Market performance calculation policy

- 상태: 완료
- 기록 시각: 2026-09-17T00:00:00+09:00
- 작업 slug: `market-performance-calculation-policy`
- 기준/통합: `e43b963` / 없음
- 범위: forward-only 계산 정책 artifact와 fail-closed loader를 추가하고, evaluator의 Decimal Context를 명시하며 canonical readiness에만 정책 근거를 연결한다. 과거 성과 재계산·성과 수치 생성·주문·운영 데이터는 변경하지 않는다.

## 변경과 결정

- `backend/jusik/data/market_performance_calculation_policy_v1.json`에 수식, 상수, Context, availability와 historical 적용 금지를 고정한다.
- `backend/jusik/market_performance_policy.py`는 고정 sibling 경로, canonical bytes, artifact SHA와 evaluator source SHA를 검증한다.
- `market_performance_readiness.py`는 기존 run/session SHA chain 성공 뒤 canonical 경로에서만 정책을 검증하고 `missing_calculation_policy` 하나를 제거한다.

## 문서·계약 영향

- 사용자 문서: `docs/market-performance-metrics.md`에 정책의 forward-only 및 historical false 계약을 기록했다.
- 운영 문서: 해당 없음. 서비스·설정·운영 데이터는 변경하지 않았다.
- API·설정·데이터 계약: readiness report에 정책 식별·SHA·scope 사실을 추가했다.

## 검증

- `uv run --project backend --extra dev pytest -q backend/tests/test_market_performance_policy.py backend/tests/test_market_performance_metrics.py backend/tests/test_market_performance_readiness.py` — 61 passed.
- `uv run --no-project --with 'ruff>=0.11,<1' ruff check ...` 및 `ruff format --check ...` — 통과.
- `uv run --no-project --with 'mypy>=1.15,<2' --with 'pydantic>=2,<3' --with 'pydantic-settings>=2.8,<3' mypy --config-file backend/pyproject.toml backend/jusik/market_performance_policy.py backend/jusik/market_performance_metrics.py backend/jusik/market_performance_readiness.py` — 통과.
- `python -m compileall ...` 및 loader pin/manual evaluator checks — 통과.

## 안전·운영 상태

- PAPER/live 설정, broker API, 실제 주문, 서비스, 원격 push와 운영 데이터 변경은 없다.

## 증거와 재개

- audit: 없음; manifest: 없음; hash: policy artifact와 evaluator source SHA는 loader 상수·artifact에 고정.
- 남은 작업·차단 조건: 부모 agent의 독립 review와 통합 검증 대기.
- 다음 시작: pytest/Ruff/mypy가 설치된 환경에서 focused 및 canonical acceptance를 실행한다.
