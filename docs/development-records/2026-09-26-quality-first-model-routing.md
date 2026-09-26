# 품질 우선 중앙 모델 선택

- 상태: 구현 완료, supervisor 통합 대기
- 기록 시각: 2026-09-26T13:37:16+00:00
- 작업 slug: `quality-first-model-routing`
- 기준/통합: `b4c1a00` / supervisor 통합 예정
- 범위: 모델·effort 명시 선택을 한 정책으로 모으고 native, roleless, runner 호출에 연결합니다. 사용자의 단순화 지시에 따라 자동 품질 평가·비용 최적화·decision receipt 플랫폼은 구현하지 않습니다.

## 변경과 결정

- `.codex/model-routing.json`이 검증한 AA slug와 host model+effort registry, 역할 및 runner profile의 명시 선택을 관리합니다. 초기 선택은 기존과 같습니다. AA 점수·가격에 의한 자동 downgrade나 모델 retry ladder는 없습니다. Astra 진단 variant는 `role.escalate`만 선택합니다.
- `backend/jusik/model_routing.py`의 `resolve`가 설정을 읽고, `check`가 native spawn의 명시 모델·effort·role·독립 fork를 확인합니다. 잘못된 정책은 안전한 오류로 실패합니다. 역할 TOML은 모델 고정을 제거하고 지침·권한을 보존합니다. implicit 저가 subagent 기본값을 제거했습니다.
- runner의 일반·계획·완료 검토·계획 scope·code scope·discovery는 같은 정책을 읽습니다. explicit config 경로, 실행 repo 정책, 설치 코드의 기본 정책 순서입니다. 잘못된 정책은 dispatch하지 않고 claim한 attempt를 실패 종료합니다. command builder에 파일 쓰기 부작용은 없습니다.
- roleless adapter는 기존 v1 manifest와 정확한 다섯 인자를 유지합니다. model-free role은 인접 정책을 발견하거나 `--policy`를 사용합니다. policy 경로·hash·profile을 기록하고 pre/post에서 변경을 거부합니다. 기존 fixed-model 외부 role과 instruction/capability/child receipt 감사는 보존합니다.
- `skills/artificial-analysis-model-efficiency/`를 canonical repository source로 추가했습니다. 기본 보고서는 모델별 Pareto 참고 자료이고 band ratio는 `--band-width` 명시 때만 제공합니다. `--json-output`은 공개 필드만 Decimal 문자열로 원자 저장합니다. 키·원시 API 응답은 저장하지 않습니다. 정책 변경은 과제 품질 검토를 거친 명시 선택이며 실제 품질 개선이나 비용 절감을 측정했다고 주장하지 않습니다.

## 문서·계약 영향

- 운영 문서: `AGENTS.md`, `docs/agent-tooling.md`, `docs/development-runner.md`에 중앙 선택과 native/roleless 사용법을 기록했습니다.
- 설정 계약: 중앙 JSON policy, 선택적인 `RunnerConfig.model_routing_policy`, roleless v1의 선택적 policy provenance를 추가했습니다.
- 사용자 UI·금융 API·거래·재시도 계약은 변경하지 않았습니다.

## 검증

- 집중 pytest: `test_model_routing`, `test_agent_routing`, `test_development_runner`, `test_development_runner_planning`, `test_development_runner_review`, `test_development_runner_planning_scope`, `test_development_runner_roadmap_code_review`, `test_development_runner_discovery`, skill offline suite — 244 passed in 88.44s.
- `.venv/bin/python -m ruff check` 및 `ruff format --check` 변경 Python 7개 — 통과.
- `cd backend && ../.venv/bin/python -m mypy jusik/model_routing.py jusik/agent_routing.py jusik/development_runner.py ../skills/artificial-analysis-model-efficiency/scripts/analyze_models.py` — strict 설정으로 4개 source 통과.
- 마지막 core 수정 뒤 `pytest -q backend/tests/test_model_routing.py backend/tests/test_development_runner.py -k 'model_routing or runtime_prompt'` — 20 passed, 69 deselected.
- 실행하지 않은 검사: frontend 변경이 없어 build 생략. 유료 모델 호출·실주문·운영 DB 검증은 실행하지 않았습니다.

## 안전·운영 상태

- worker는 전용 worktree만 변경했습니다. `.env`, 운영 DB, 글로벌 skill, 서비스, 원격 push는 변경하지 않았습니다. global skill 설치·실제 AA smoke·runner 복구·main 통합은 supervisor 소유입니다.
- 거래 기본값, 권한, escalation 승인 조건과 독립 검토는 보존했습니다. named role이 이미 모델을 로드했다면 hot reload를 주장하지 않고 explicit default fallback을 사용합니다.

## 증거와 재개

- supervisor audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260926-quality-first-routing-0yutqlne/`.
- 남은 작업: supervisor의 독립 검토·main 통합 검증·canonical skill 설치·운영 상태 복구·handoff.
- 다음 시작: 현재 diff와 집중 검증 결과를 검토한 뒤 supervisor가 로컬 main에 통합합니다.
