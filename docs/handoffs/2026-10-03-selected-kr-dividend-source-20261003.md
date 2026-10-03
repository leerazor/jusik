# 국내 배당 결손 보존 후 비교 설계로 계속

- 2026-10-03T12:19:52Z; 기준main d5723e9. 사용자 지속 진행 승인 유지.
- [기록](../development-records/2026-10-03-selected-kr-dividend-source-20261003.md)의 공식 IR3개·exact revision24건을 재사용한다. audit manifest8e4a470f... . 사건 날짜 결손으로 import0/전체eligible24 유지.
- 삼성 source raw=2026Q2 374원 record6/30; SKraw=2023Q1~2026Q1 분기액. 분기→vendor exdate 연결 미인수. 84356원문403 반복 금지,84746직접 미요청. 날짜가 명시된 새 공식 사건 원문이 재개 조건.
- 다음 진행 중: 등록16 단순보유/최대3 저회전 후보 사전등록 설계. explore 완료, `selected_comparison_plan` read-only planner 소유. 기존 엔진 equal도 trend filter가 있어 단순보유가 아니다. 비용/매도세·배당 포함 실행·입력결속·warmup강제·레버리지 drift를 별도 검증해야 한다.
- 기존128grid나 과거holdout실험을 실행하지 않는다. 성과 없는 protocol 작업이며 이미 본 자료는 untouched OOS가 아니다. 준비 가능한 고정 규칙부터 확정한다.
- 주문·PAPER/live·Pages·push 없음. 등록16/revision1,1억원·레버리지20%·MDD20% 유지. 사용자 HANDOFF.md 보존.
