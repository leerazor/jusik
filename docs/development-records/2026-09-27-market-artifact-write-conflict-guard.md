# Market artifact write conflict guard

- 상태: 완료 (검증·독립 review·local main 통합·worktree 정리 완료)
- 기록 시각: 2026-09-27T07:53:07Z
- 작업 slug: `market-artifact-write-conflict-guard`
- 기준/통합: `447e2d2dea58966fd6a5b187f45b74ae8ecd8ff4` / `a80b758d367fcf6ec04a8e68a565a0723e38985e`
- provisional assumption: 신규 artifact 저장과 같은 bytes의 idempotent 재저장은 기존대로 성공합니다. 같은 digest key에 다른 bytes가 있으면 덮어쓰지 않고 fail closed하며, 기존 content type/captured_at metadata를 유지합니다. 이 값은 가역적인 저장 무결성 기본값이고 투자·데이터 합격 기준을 정하지 않습니다.

## 근거와 범위

- `MarketHistoryStore.save_artifact()`의 `INSERT OR IGNORE`는 기존 key와 충돌해도 보존된 body를 확인하지 않고 요청 content digest를 반환합니다. `MarketResearchService.create_run()`은 이 값만 검사하므로 손상된 body가 저장된 상황을 성공으로 받아 계산 단계로 진행할 수 있습니다.
- planner는 in-memory SQLite에서 정상 bytes의 SHA key 아래 다른 bytes를 먼저 저장한 다음 정상 bytes를 재저장해도 성공 digest가 반환되고, 저장물은 달라지지 않으며, 이후 `get_artifact()`는 손상 bytes를 거부하는 것을 재현했습니다.
- 구현 범위는 `backend/jusik/market_history_store.py`, `backend/tests/test_market_research.py`, 이 기록입니다. 자동 복구·덮어쓰기·DB migration·API/schema·data grade·투자 mandate 변경은 포함하지 않습니다.
- 완료 조건은 신규 저장/roundtrip, 동일 bytes 중복 저장의 기존 metadata 보존, 충돌 시 원본 bytes 보존과 비민감 실패, 충돌 뒤 service 계산 함수 미호출, focused test/lint/type check와 독립 review입니다.
- 구현 commit `e08403eba263c27cc02b6f8613f0ffeea20e5b81`: store는 INSERT 뒤 같은 connection에서 row bytes를 다시 읽어 요청 bytes 및 SHA-256과 대조합니다. 불일치는 고정 오류로 거부하고 기존 row는 수정하지 않습니다. 동일 bytes 재저장은 기존 content type/captured_at을 보존합니다.
- 독립 review: PASS. reviewer는 artifact subset 6 passed, changed-file Ruff check/format 및 diff check를 재확인했습니다. 중요/보통 finding은 없습니다.

## 의존성과 상태

- 외부 차단 조건이 없습니다. 임시 SQLite와 fixture만으로 실행할 수 있습니다.
- 실제 credential·외부 API·운영 DB·주문·PAPER/live·실제 지출은 필요하지 않습니다.
- `FINAL_VALIDATION`/OOS는 별도 task로 사용자 승인 preregistration freeze와 그 뒤 확보한 적격·미노출 미래자료 전까지 `PENDING/BLOCKED`입니다. 이 구현이나 임시 가정은 정식 기준을 동결하지 않습니다.
- 작업 환경: `/home/kwl/projects/jusik-market-artifact-write-conflict-guard`, branch `fix/market-artifact-write-conflict-guard`, base `447e2d2dea58966fd6a5b187f45b74ae8ecd8ff4`; Python 3.13 venv는 잠금 의존성을 offline cache에서 설치했습니다.
- main 통합 후 검증: `backend/.venv/bin/python -m pytest -q backend/tests/test_market_research.py` — 34 passed, dependency deprecation warning 2개. changed-file Ruff check/format, `market_history_store.py` strict mypy, `git diff HEAD^ HEAD --check` 모두 통과.
- worktree `/home/kwl/projects/jusik-market-artifact-write-conflict-guard`는 ignored venv/cache만 확인한 후 clean 제거했고 branch `fix/market-artifact-write-conflict-guard`와 commit을 보존했습니다.
- 남은 task-local blocker는 없습니다. 전체 backend suite와 동시 writer stress 검사는 실행하지 않았습니다. planner가 artifact/snapshot 저장 경계 및 broader held-band 자료·pipeline 범위를 현재 main에서 읽기 전용 점검했으며 새 standalone READY task는 찾지 못했습니다. PTN 98 bars는 membership 시작 전 warmup 가격이고, 편입 전 거래 금지를 기존 `test_market_data_collector.py:2045`가 검증하므로 중복 task를 만들지 않습니다.
