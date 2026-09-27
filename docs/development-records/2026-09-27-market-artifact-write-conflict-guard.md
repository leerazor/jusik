# Market artifact write conflict guard

- 상태: 준비 (planner 재현 완료, 독립 구현 전)
- 기록 시각: 2026-09-27T07:39:39Z
- 작업 slug: `market-artifact-write-conflict-guard`
- 기준/통합: `a88b14cb389982790cb7fa0df11bc1b129c5b568` / 없음
- provisional assumption: 신규 artifact 저장과 같은 bytes의 idempotent 재저장은 기존대로 성공합니다. 같은 digest key에 다른 bytes가 있으면 덮어쓰지 않고 fail closed하며, 기존 content type/captured_at metadata를 유지합니다. 이 값은 가역적인 저장 무결성 기본값이고 투자·데이터 합격 기준을 정하지 않습니다.

## 근거와 범위

- `MarketHistoryStore.save_artifact()`의 `INSERT OR IGNORE`는 기존 key와 충돌해도 보존된 body를 확인하지 않고 요청 content digest를 반환합니다. `MarketResearchService.create_run()`은 이 값만 검사하므로 손상된 body가 저장된 상황을 성공으로 받아 계산 단계로 진행할 수 있습니다.
- planner는 in-memory SQLite에서 정상 bytes의 SHA key 아래 다른 bytes를 먼저 저장한 다음 정상 bytes를 재저장해도 성공 digest가 반환되고, 저장물은 달라지지 않으며, 이후 `get_artifact()`는 손상 bytes를 거부하는 것을 재현했습니다.
- 구현 범위는 `backend/jusik/market_history_store.py`, `backend/tests/test_market_research.py`, 이 기록입니다. 자동 복구·덮어쓰기·DB migration·API/schema·data grade·투자 mandate 변경은 포함하지 않습니다.
- 완료 조건은 신규 저장/roundtrip, 동일 bytes 중복 저장의 기존 metadata 보존, 충돌 시 원본 bytes 보존과 비민감 실패, 충돌 뒤 service 계산 함수 미호출, focused test/lint/type check와 독립 review입니다.

## 의존성과 상태

- 외부 차단 조건이 없습니다. 임시 SQLite와 fixture만으로 실행할 수 있습니다.
- 실제 credential·외부 API·운영 DB·주문·PAPER/live·실제 지출은 필요하지 않습니다.
- `FINAL_VALIDATION`/OOS는 별도 task로 사용자 승인 preregistration freeze와 그 뒤 확보한 적격·미노출 미래자료 전까지 `PENDING/BLOCKED`입니다. 이 구현이나 임시 가정은 정식 기준을 동결하지 않습니다.
- 다음 시작: `fix/market-artifact-write-conflict-guard` 전용 worktree에서 단일 `role.code_small` 구현자를 실행하고 별도 review를 수행합니다.
