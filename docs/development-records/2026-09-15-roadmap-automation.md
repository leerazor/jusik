# 투자 개발 로드맵 자동 실행기

- 상태: 차단 (코드 검증 완료, 운영 활성화 대기)
- 기록 시각: 2026-09-15T07:10:21.954856+00:00
- 작업 slug: `roadmap-automation`
- 기준/통합: `3df0c0c` / 없음 (구현 브랜치)
- 범위: 기존 research runner를 보존하면서 `investment-roadmap` scope의 전용 상태 binding, Markdown checklist queue, coarse phase gate와 bounded planner/dispatch를 추가했다.

## 변경과 결정

- `RunnerConfig.scope`는 `research`를 기본값으로 유지한다. 투자 scope 초기화는 전용 blank state만 허용하고 기존 state나 기본 research state를 재사용하지 않는다.
- area는 tracked `docs/investment-development-roadmap.md` checklist ID를 소문자로 정규화한다. Markdown checkbox는 전체 checklist 완료의 authoritative source이며 slice 기술 완료와 분리하고 phase 전체를 자동 완료하지 않는다.
- R0→R1/R2/R3, R1+R2→R4, R4→R5/R6, R5→R7 gate를 planner와 CLI enqueue에 함께 적용한다. 실패·차단·중단 area는 같은 ID를 명시적으로 retry할 때까지 quarantine한다.
- Review 후 partial slice의 완료 이력은 새 bounded slice를 허용하되, 실행 중·실패·차단·중단 이력은 계속 격리한다. 실행 불가능한 queued dependency는 독립 phase planner를 막지 않으며, 필수 roadmap/mandate/runbook 문서는 regular readable tracked 파일인지 dispatch 전에 확인한다.

## 문서·계약 영향

- 사용자 문서: 해당 없음; 자동 실행기 운영 계약은 `docs/roadmap-automation.md`에 기록했다.
- 운영 문서: `docs/development-runner.md`에 전용 config·pause 경계를 갱신했다.
- API·설정·데이터 계약: `RunnerConfig.scope`와 roadmap completion/planner schema가 추가되었다. 기존 research config JSON은 기본값으로 호환된다.

## 검증

- `backend/.venv/bin/python -m pytest -q backend/tests/test_development_runner*.py` — 78 passed.
- `backend/.venv/bin/ruff format --check ... && backend/.venv/bin/ruff check ...` — 통과.
- `backend/.venv/bin/mypy --strict backend/jusik/development_runner.py backend/jusik/development_runner_roadmap.py` — 통과.
- `git diff --check` — 통과.

## 안전·운영 상태

- PAPER/live activation, 실제 주문, 운영 원장·서비스 변경, remote push는 수행하지 않았다.
- 전용 scope는 실제 dispatch 없이 임시 fake runner와 parser 경계만 검증했다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260915-roadmap-automation`; manifest: 없음; hash: 해당 없음
- 남은 작업·차단 조건: 주 agent의 runbook 통합·독립 review·local main 통합 전에는 운영 활성화하지 않는다.
- 다음 시작: 통합 worktree에서 전체 runner 검사와 scope config 경계를 재검증한 뒤 독립 review를 수행한다.

## 최종 검토 보완

- 운용 조건 JSON의 구문과 필수 필드 검사를 복구했다. 잘못된 조건은 queued seed와 빈 큐 planner 모두 attempt 생성 전에 차단하며 큐·dispatch 한도를 소비하지 않는다.
- 누락된 runbook뿐 아니라 실제 파일이 남아 있지만 Git 추적에서 제외된 경우도 검증했다.
- Luna 구현 완료 후 host agent thread limit으로 동일 담당자의 재호출이 세 번 거부됐다. 감독 Astra가 이 마지막 검사 복구와 회귀 테스트만 인계받아 수정했으며, 이를 Luna 수행으로 표시하지 않는다. 수정은 별도 commit과 동일 독립 reviewer의 재검토 대상으로 남긴다.
