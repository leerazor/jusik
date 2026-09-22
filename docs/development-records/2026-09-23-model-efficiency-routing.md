# 모델 효율 라우팅

- 상태: 완료 (local `main` 통합 대기)
- 기록 시각: 2026-09-22T23:16:52Z
- 작업 slug: `model-efficiency-routing`
- 기준/통합: worktree 기준 등록 커밋 `32f6ef8`; 검토 시작 source `54dcf22` / 통합 없음
- 범위: 프로젝트 기본 supervisor·planner·review는 Sol, 조사·구현은 Luna, 제한된 읽기 전용 난제 진단은 Astra로 명시하고 runner의 고정 Astra 호출을 Sol medium으로 교체합니다. 금융·권한·재시도 계약과 역사 기록은 보존합니다.

## 변경과 결정

- `.codex/config.toml`과 `.codex/agents/`에 역할별 모델·추론 수준을 고정하고, `escalate` 역할을 읽기 전용으로 추가했습니다. 일반 코드 문제는 서로 다른 가설 두 번 실패 뒤 Astra 진단으로 전환하며, 명백히 복잡한 금융 계산·미래 누출·설계 충돌은 감독 근거로 처음부터 한 번 선택할 수 있습니다.
- `backend/jusik/development_runner.py`는 일반/계획 dispatch 모두 Sol과 medium 추론 CLI override를 사용합니다. Astra escalation은 자동 runner model-switch가 아닙니다.
- `AGENTS.md`, agent/worktree/runner 운영 문서는 현재 역할표와 stale loaded-role fallback(`agent_type=default`, 기대 model·reasoning·`fork_turns=none`)을 반영하며 roleless adapter/helper 계약은 변경하지 않습니다.

## 문서·계약 영향

- 사용자 문서: 해당 없음.
- 운영 문서: `AGENTS.md`, `docs/agent-tooling.md`, `docs/worktree-workflow.md`, `docs/development-runner.md`를 갱신했습니다.
- API·설정·데이터 계약: `.codex/` 모델 라우팅 설정과 runner CLI invocation만 변경했습니다. 금융 계산·주문·재시도 경계는 변경하지 않았습니다.

## 검증

- `uv venv --python /home/kwl/.pyenv/versions/3.13.15/bin/python3.13 .venv` 및 `uv pip install --python .venv/bin/python -e './backend[dev]'` — 통과.
- `.venv/bin/python` TOML parse — 통과.
- `.venv/bin/python -m pytest -q backend/tests/test_development_runner.py backend/tests/test_development_runner_planning.py backend/tests/test_development_runner_roadmap.py backend/tests/test_agent_routing.py` — 124 passed.
- `.venv/bin/ruff check ...` 및 `.venv/bin/ruff format --check ...` — 통과.
- `(cd backend && ../.venv/bin/python -m mypy jusik/development_runner.py jusik/agent_routing.py)` — 통과.
- 실행하지 않은 검사: 실제 model/provider 호출, 실주문, frontend build는 범위 밖입니다.

## 안전·운영 상태

- 실제 주문·provider 호출·원격 push·서비스·운영 DB·전역 설정 변경은 수행하지 않습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260923-model-efficiency-7k7GWF/worker`; manifest: 없음.
- 남은 작업·차단 조건: supervisor의 독립 diff 검토와 local `main` 통합이 필요합니다.
- 다음 시작: 독립 검토 결과와 이 커밋을 대조한 뒤 local `main` 통합 검사를 수행합니다.
