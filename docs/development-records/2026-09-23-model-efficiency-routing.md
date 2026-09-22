# 모델 효율 라우팅

- 상태: 완료
- 기록 시각: 2026-09-22T23:22:11Z
- 작업 slug: `model-efficiency-routing`
- 기준/통합: worktree 기준 등록 커밋 `32f6ef8`; 검토 시작 source `54dcf22` / local main `23e2b2a`
- 범위: 프로젝트 기본 supervisor·planner·review는 Sol, 조사·구현은 Luna, 제한된 읽기 전용 난제 진단은 Astra로 명시하고 runner의 고정 Astra 호출을 Sol medium으로 교체합니다. 금융·권한·재시도 계약과 역사 기록은 보존합니다.

## 변경과 결정

- `.codex/config.toml`과 `.codex/agents/`에 역할별 모델·추론 수준을 고정하고, `escalate` 역할을 읽기 전용으로 추가했습니다. 일반 코드 문제는 서로 다른 가설 두 번 실패 뒤 Astra 진단으로 전환하며, 명백히 복잡한 금융 계산·미래 누출·설계 충돌은 감독 근거로 처음부터 한 번 선택할 수 있습니다.
- `backend/jusik/development_runner.py`는 일반/계획 dispatch 모두 Sol과 medium 추론 CLI override를 사용합니다. Astra escalation은 자동 runner model-switch가 아닙니다.
- `AGENTS.md`, agent/worktree/runner 운영 문서는 현재 역할표와 stale loaded-role fallback(`agent_type=default`, 기대 model·reasoning·`fork_turns=none`)을 반영하며 roleless adapter/helper 계약은 변경하지 않습니다.
- 독립 review P2 조치: `read-only`를 host의 실효 OS 권한 격리로 과장하지 않고 `escalate` 쓰기 작업 배정 금지와 별도 권한 확인을 명시했습니다.

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

- 실제 주문·provider 호출·원격 push·금융 운영 DB·전역 설정은 변경하지 않았습니다. 수동 통합 충돌 방지를 위해 roadmap runner를 일시 pause하고 service를 stop했습니다. 작업 전 timer는 active/enabled, pause는 false였으며 최종 복구 상태는 audit handoff에 기록합니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260923-model-efficiency-7k7GWF`; `integration-verification.md`, `METHODOLOGY_REVIEW.md`, `HANDOFF.md`를 보존했습니다.
- 통합 검증: main에서 focused pytest `124 passed`, Ruff check/format, configured mypy, 역할 5개와 기본 모델·추론 TOML assertion이 통과했습니다. 독립 Sol high 검토의 권한 설명 P2는 `23e2b2a`에서 수정하고 재검토 PASS를 받았습니다. native routing post와 child metadata에서 이번 실제 구현 모델 `gpt-5.6-luna high`, review 모델 `gpt-6-sol high`를 확인했습니다.
- 정리: 필요한 증거·인계 보존 후 병합된 소유 worktree/branch와 임시 환경만 제거했습니다. 기존 사용자 `HANDOFF.md`와 다른 worktree는 보존했습니다.
- 남은 작업: 모델 설정은 완료했습니다. 방법론의 자동 복구 활성화·반복 대기 억제·새 end-to-end 연구 입력·자동매매 로드맵은 검토안이며 이번 변경에 포함하지 않았습니다. 실제 모델별 비용·지연 개선율은 측정하지 않았습니다.
- 다음 시작: audit의 방법론 검토와 현재 운영 상태를 대조하고 최우선 운영 개선을 별도 범위로 실행합니다. 이미 완료한 receipt 감사를 재수행하지 않습니다.
