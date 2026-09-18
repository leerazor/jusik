# runner hold trigger fail-closed gate

## 목적

파일 marker만 확인하면 DB에 남은 operator hold trigger 때문에 신규 task 삽입·retry가 조용히 무시될 수 있었다. 승인 전 hold가 남은 상태를 `idle`로 오인하지 않도록 runner 코드에 명시적 gate를 추가했다.

## 구현

- `RunnerStore.operator_hold_triggers()`가 `operator_hold_no_new_tasks`, `operator_hold_no_requeue`를 deterministic하게 조회한다.
- roadmap `resume`은 해당 trigger가 있으면 `RunnerResumeError`로 거부한다.
- 모든 `run-once` scope는 trigger가 있으면 queue claim 전에 `blocked`와 trigger 목록을 반환한다.
- 기존 task/attempt/history와 일반 SQLite trigger는 변경하지 않는다.

## 검증

- `backend/tests/test_development_runner.py`: 60 passed
- Ruff check/format 통과
- `mypy --strict` 대상 production source 통과
- 임시 SQLite DB에 두 hold trigger를 만들고 `run_once`가 정확히 fail-closed 되는지 확인했다.

## 운영 상태

현재 운영 DB의 hold trigger는 승인된 재개 시점에 제거되어 없으며, 제거 전 DB 백업은 operator-hold archive에 보존했다. 실제 주문, PAPER/live 승격, network 수집, remote push는 하지 않았다. 문서 커밋 후 전용 runner를 resume한다.
