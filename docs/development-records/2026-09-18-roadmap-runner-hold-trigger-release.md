# roadmap runner 운영 보류 trigger 해제

## 발견

operator hold의 `active` marker를 archive로 옮긴 뒤에도 runner DB에 다음 SQLite trigger가 남아 있었다.

- `operator_hold_no_new_tasks`: 모든 신규 task INSERT를 `RAISE(IGNORE)`로 무시
- `operator_hold_no_requeue`: blocked/failed task의 queued 전환을 원래 상태로 되돌림

따라서 service는 exit 0으로 보였지만 실제 planner/task가 큐에 들어가지 않는 조용한 운영 blocker였다.

## 조치

- 원본 DB를 `/home/kwl/.local/share/jusik/roadmap-development-runner/operator-hold/archive/`에 백업했다.
- 두 hold trigger만 제거했다. task·attempt·history 데이터와 기존 hold 문서는 변경하지 않았다.
- 신규 INSERT 동작을 임시 probe로 확인한 뒤 probe row는 즉시 삭제했다.
- planner task `planner-688b9ed2a568ecec6486f91f`를 전용 service로 실행했다.

## 결과

planner attempt `0065eefe2e294823975e75c1e3947349`는 `waiting`으로 정상 종료했다. R1-04/R1-05의 기술 slice는 존재하지만 실제 provider 원문 SHA, 관측시각, split raw 가격, dividend 권리·지급·보유수량 근거가 없어 경제 acceptance나 retry proposal을 만들지 않았다. 이 결과는 데이터 부족을 숨기지 않는 정상적인 fail-closed 판정이다.

timer는 enabled/active이며 실제 주문, PAPER/live 승격, network 수집, remote push는 수행하지 않았다.

## 다음 의존 작업

새로운 자료를 합성하지 않고, 기존 artifact에서 위 필드의 stable evidence가 있는지 read-only로 확인한다. 근거가 없으면 R1-04/R1-05는 미완료로 유지하고, 근거가 생길 때만 동일 task ID의 명시적 retry를 수행한다.
