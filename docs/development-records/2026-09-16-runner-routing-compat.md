# Runner roleless CLI routing compatibility

- 상태: 진행
- 기록 시각: 2026-09-15T22:56:46Z
- 작업 slug: `runner-routing-compat`
- 기준/통합: `d90373b` / 통합 전
- 범위: role 필드가 없는 실제 spawn CLI에 한정한 model-only routing adapter, focused 검증, 운영 안내를 추가했습니다. native interactive helper, registry, 금융 코드, 큐·스키마와 서비스는 보존했습니다.

## 변경과 결정

- `backend/jusik/agent_routing.py`는 stdlib-only `prepare`, `pre`, `post` CLI를 제공합니다. role TOML과 실제 capability probe를 읽고 정확히 다섯 spawn 인자, private manifest, nonce·receipt를 생성합니다. pre는 현재 TOML의 model/effort와 task source도 재검증합니다.
- `post`는 완결된 parent/child JSONL에서 실제 인자·call output 경로·session parent link·child 첫 assistant receipt·child-owned turn model을 확인합니다. host가 raw initial input을 보존하지 않는 경우 명시적 opaque message mode에서 envelope 형태만 확인하고 receipt를 delivery evidence로 기록합니다.
- `AGENTS.md`, `docs/agent-tooling.md`, `docs/development-runner.md`에 roleless CLI 예외와 fail-closed 감사 절차를 연결했습니다.

## 문서·계약 영향

- 사용자 문서: 해당 없음.
- 운영 문서: `docs/agent-tooling.md`, `docs/development-runner.md`를 갱신했습니다.
- API·설정·데이터 계약: 외부 API와 runner 큐 계약은 변경하지 않았습니다.

## 검증

- `PYTHONPATH=backend backend/.venv/bin/pytest -q backend/tests/test_agent_routing.py` — 통과(16개).
- `backend/.venv/bin/ruff check backend/jusik/agent_routing.py backend/tests/test_agent_routing.py` — 통과.
- 실제 CLI layout synthetic prepare→pre→post smoke — 통과.
- 실행하지 않은 검사: 통합 `pytest`, strict mypy, runner 전체 회귀는 parent 통합 단계에서 실행합니다.

## 안전·운영 상태

- 실제 brokerage order, live/paper engine, service, queue/database, remote push는 실행하거나 변경하지 않았습니다.
- native helper와 전역 skill/helper/config는 변경하지 않았습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260916-runner-routing`; 실제 probe와 protocol layout은 parent가 보존합니다.
- 남은 작업·차단 조건: parent의 explicit opaque message full smoke와 통합 검증, 독립 review가 필요합니다.
- 다음 시작: parent가 capability evidence로 prepare/pre를 실행하고 실제 완결 parent/child JSONL로 post를 실행한 뒤 통합합니다.
