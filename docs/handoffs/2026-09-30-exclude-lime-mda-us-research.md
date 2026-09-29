# 신규 미국 연구 종목 제외 인계

- 갱신: 2026-09-29 23:30 UTC. 저장소 `/home/kwl/projects/jusik`, 로컬 `main` 코드 통합 `2394294e4246537a26986cd05066f4cf3eca1457`.
- 목표: 앞으로 만드는 모든 미국 연구 표본에서 `LIME`·`MDA`를 제외하고 자동개발을 이어갑니다. 기존 동결 결과·원본·cache·replay는 보존합니다.
- 완료: 미국 collector는 checkpoint seed 전에 두 심볼을 제외해 빈자리를 다른 적격 종목으로 채웁니다. 이전 prepared/strict 입력은 원본을 남기고 실행 행에서 제외하며 축소 표본과 대체 보충 없음이 표시됩니다. 새 정책·정규화·자료 계약은 과거 pilot과 분리됩니다. [개발 기록](../development-records/2026-09-30-exclude-lime-mda-us-research.md).
- 검증: 독립 review 최종 PASS, 통합 `main` 관련 pytest 290 passed, Ruff lint·선택 파일 format·7개 소스 strict mypy·mandate validator·diff check 통과. collector와 해당 테스트의 전체 파일 format 차이는 기준 커밋에도 있었습니다.
- 상태: 수동 통합·문서 기록 동안 roadmap runner는 pause, service inactive입니다. tracked 문서 커밋 후 기존 설정으로 resume하고 실제 cycle·대기/READY를 관측해야 합니다. 현재까지 새 시세 수집이나 새 수익성 결과는 없습니다.
- 남은 경계: R1-05는 기존 366개 결손과 별도 provider/PIT completeness 근거 부족으로 `waiting_external`입니다. 새 표본 선정만으로 투자 acceptance, OOS, PAPER/live가 통과하지 않습니다. 새 미국 파일럿은 신규 수집·coverage 확인과 비용 포함 비교의 별도 검증이 필요합니다.
- 안전: 실제 주문·PAPER/live 승격·결제·원격 push 없음. 사용자 소유 미추적 루트 `HANDOFF.md`는 수정하지 않았습니다.

다음 시작: 이 인계와 작업 기록을 읽고 roadmap runner `status`의 실제 task/attempt와 mandate gate를 확인합니다. 기존 R1-05 attempt를 변경 없이 재사용하지 말고 새 정책의 자료 준비 또는 독립 READY 작업을 진행합니다.
