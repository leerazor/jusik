# 자동 개발 CLI 역할 전달 호환성 수정

- 상태: 코드 통합·검증 완료. 자동 개발 재착수 확인은 아래 activation.json에서 이어집니다.
- 기록 시각: 2026-09-15T23:10:42.254522+00:00
- 작업 slug: `runner-routing-compat`
- 기준/구현/통합: `d90373b` / `cf30c906c0b62f387836d550bc5f3b004096a5fb` / `f9ed8b1f09decdde1c730c1ff37b30880bceff41`

## 변경과 결정

실제 자동 실행 CLI의 spawn 도구에는 `agent_type`이 없어 기존 필수 검사가 네 로드맵 작업을 구현 전에 차단했습니다. `backend/jusik/agent_routing.py`에 stdlib 전용 prepare/pre/post를 추가하고, 실제 capability 증거가 있는 roleless CLI에만 적용하도록 AGENTS와 실행기 안내를 연결했습니다. native helper는 유지했습니다.

준비 단계에서 역할 TOML의 모델·추론 설정·지침과 작업 원본을 고정합니다. 감사는 정확한 인자 집합, 실제 반환 child와 parent 연결, child 소유 모델, 도구 호출 전 첫 assistant receipt를 확인합니다. private 준비 파일은 덮어쓰지 않으며 원본 변경·잘못된 연결·손상된 JSONL을 실패로 처리합니다.

실제 로그에서 호출 message 원문을 확인할 수 없어 명시적 `model-only-encrypted-message-v1` 모드를 추가했습니다. 이 모드는 관측된 opaque envelope 형태, 네 non-message 인자, 모델과 receipt를 검증합니다. 원문 동일성·암호학적 무결성·native role sandbox 적용은 증명하지 않으며 결과에 한계를 명시합니다. 키 접근·복호화·로그 변조는 수행하지 않았습니다.

## 문서·계약 영향

- 운영 문서: `AGENTS.md`, `docs/agent-tooling.md`, `docs/development-runner.md`를 갱신했습니다.
- 웹·금융 계산·외부 API·큐 스키마 변경은 없습니다. 기존 연구 수익률과 완료 체크리스트를 변경하지 않았습니다.

## 검증

- 통합 main의 `python -m pytest -q backend/tests/test_agent_routing.py backend/tests/test_development_runner.py backend/tests/test_development_runner_planning.py backend/tests/test_development_runner_roadmap.py` — 95개 통과, 13.95초. 프로젝트 venv 사용.
- 변경 Python 파일과 관련 테스트 Ruff 검사 — 통과.
- `python -m mypy --strict jusik/agent_routing.py jusik/development_runner.py` — 2개 source 통과.
- 실제 동일 codex exec 환경에서 준비·사전검사·Luna/Terra 호출·사후 감사 — 양쪽 통과. native 구현자·검토자 모델 감사도 통과했습니다.
- 독립 Terra 검토 — P1/P2 없음. 검토 diff hash와 구현 commit 일치 확인.
- 프런트엔드 빌드는 UI 변경이 없어 실행하지 않았습니다.

## 안전·운영 상태

수동 작업 전에 전용 로드맵 큐를 pause하고 service inactive를 확인했습니다. 통합과 검증을 마쳤으며 기존 네 blocked task ID를 보존한 채 retry/resume할 예정입니다. 이 문서는 시작 직전 기록이며 실행 성공을 선행 주장하지 않습니다. 실제 운영 결과는 `/home/kwl/.local/share/jusik/portfolio-audit/20260916-runner-routing/activation.json`을 확인합니다. 기존 연구 큐는 paused를 유지하며 실주문·PAPER/live 활성화·운영 거래 원장 변경·원격 push는 없습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260916-runner-routing`. `integration-verification.json`, `review-verification.json`, `full-smoke-v2/`는 검증 근거이며 `source-snapshot/`에 관련 소스·역할 설정·lockfile과 hash를 보존했습니다.
- 이번 워크트리와 병합된 작업 브랜치는 정리했습니다. 다른 여섯 작업의 워크트리는 보존했습니다.
- handoff: 루트 `HANDOFF.md`는 현재 재개 상태를 기록하며 untracked로 유지합니다.
- 다음 시작: `activation.json`과 전용 runner 상태를 읽고 R1-01의 실제 구현 착수 여부 및 후속 진행을 확인합니다. 자동 실행 중에는 수동 main 변경을 하지 않습니다.
