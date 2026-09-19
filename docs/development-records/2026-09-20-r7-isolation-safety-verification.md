# R7 격리 simulation/PAPER 안전 계약 검증

- 상태: 기술 계약 재검증 완료; R7 경제 평가와 PAPER 결정은 `not-evaluated`.
- 검증: prospective registration/readiness, GPU stress 경계, isolated experiment
  guard, calendar stress, forward paper boundary 관련 기존 pytest 81개와 새 R7
  workspace 계약 테스트 5개를 통과했습니다(총 86개).
- R7-01 보강: `research_r7_isolation.py`가 새 workspace 아래 market-data/config/
  database/artifacts를 만들고, source identity와 `paper_only=true`,
  `automatic_promotion_eligible=false`, retrospective write 차단을 manifest에
  고정합니다. 기존 retrospective 경로와 겹치거나 symlink·재사용·누락 source이면
  생성하지 않습니다. source path별 deterministic SHA-256을 실제로 대조하고 workspace와
  child를 `0700`으로 생성하며, 부모 symlink와 사용 불가 source를 거부합니다.
- 생성·manifest 쓰기·실패 정리는 `O_NOFOLLOW`와 고정 `dir_fd`를 사용해 경로 교체
  경쟁 조건에서 임의 경로를 따라가지 않도록 합니다.
- `research_r7_gate.py`의 진입 게이트를 추가해 prospective window/data readiness,
  untouched OOS, stress, independent review, isolation manifest가 모두 없으면
  simulation을 차단합니다. 게이트는 PAPER 결정을 수동으로 남기고 자동 승격은 항상
  `false`로 유지합니다.
- 게이트 테스트와 evidence/result 불변식 검사를 포함한 R7 focused pytest 89개가
  통과했습니다(경고 2개). 프로젝트
  전체 mypy는 기존 10개 오류가 남아 있어 전체 통과로 주장하지 않습니다.
- 연구 API의 `/api/research/validation/r7/gate`가 prospective readiness와 R7 gate를
  실제로 소비하도록 연결했습니다. 기본 설정에서는 workspace/evidence가 없어
  `blocked`를 반환하며, 실행·주문·PAPER 설정을 변경하지 않습니다.
- 확인: 고정 prospective 상태·stress 결과는 자동 승격되지 않으며, 해시 고정·엄격한
  JSON·격리된 입력/출력·calendar 변형 경계가 실패 시 차단됩니다. paper fill은 앱 내부
  paper 원장 경계에만 존재하고 broker 주문 경로와 분리됩니다.
- 한계: 최종 untouched OOS의 단회 경제 판정, 완전한 비용·기업행사·FX 자료, 독립
  reviewer 승인, 실제 PAPER 운영은 수행하지 않았습니다. 따라서 R7-01~R7-04 checkbox와
  PAPER 승격은 유지합니다.
- 안전: 실제 연구 실행·네트워크 수집·실주문·PAPER/live 설정 변경·원격 push 없음.
- 수동 검증 충돌을 막기 위해 roadmap runner를 pause하고 service/timer를 중지했습니다.
  timer도 disable했습니다. 확인 시 `paused=true`, service/timer `inactive`·`disabled`,
  queued/running task 0개였습니다. 자동 실행은 재개하지 않습니다.
