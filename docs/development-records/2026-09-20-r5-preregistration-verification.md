# R5 사전등록·검증 계약 점검

- 상태: 기술 계약 검증 완료. 최초 50개 실행에서 테스트 fixture가 현재 날짜/window와
  drift해 2개가 실패했으며, production 코드는 수정하지 않고 fixture 기대치를 교정했습니다.
- 교정: signal 검증일을 fixed prospective window에서 허용되는 `2026-09-14`로 변경하고,
  2026-09-20 현재 전진 등록 상태를 `observing`으로 기대하도록 수정했습니다.
- 재검증: optimizer/preregistration/validation focused 테스트 52개 통과.
- 후보 최대 3개, 기간 freeze, MDD hard filter, 자동 winner 금지 계약은 유지하며 실제
  전략 성과·PAPER 승격은 별도 자료 gate 뒤에만 허용합니다.
- 실제 전략 실행·network 수집·PAPER/live·주문·원격 push 없음.
