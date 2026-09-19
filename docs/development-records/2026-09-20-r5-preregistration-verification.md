# R5 사전등록·검증 계약 점검

- 상태: 부분 검증. optimizer/preregistration 관련 50개 테스트는 통과했으나 validation
  API 2개가 기존 기대치와 달라 R5 승격은 하지 않았습니다.
- 실패 근거:
  - `test_robustness_repository_and_validation_api_are_bounded`: `/api/research/validation/signal`
    응답 `503` (기대 `200`)
  - `test_read_only_status_api_returns_registration_contract`: 상태 `observing` (기대 `planned`)
- 따라서 후보 최대 3개, 기간 freeze, MDD hard filter, 자동 winner 금지 계약은 유지하되,
  API 상태 계약 복구와 전체 focused 재검증 전에는 R5/R4 성과를 승격하지 않습니다.
- 실제 전략 실행·network 수집·PAPER/live·주문·원격 push 없음.
