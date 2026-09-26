# 자동 발굴 호출 장애 복구 handoff

- 작업 저장소: `/home/kwl/projects/jusik`, local `main`, 통합 `0578faf`.
- 목표: 호출 장애 때문에 자동 발굴 전체가 영구 대기하지 않도록 고치고 agent 지침을 실행 테스트로 검증한다.
- 현재: 구현 `2befc7a`와 잔존 process group 방어 `6a4cca2`를 통합했다.
  독립 Sol review PASS, 작업 branch 관련 pytest 256개·Ruff·strict mypy PASS.
  main에서도 pytest 256개·Ruff·소스 strict mypy·수정 테스트 focused strict mypy를 통과했다.
  일반 테스트 import 타입 검사에는 기존 roadmap 테스트 오류 8개가 남아 있다.
  작업 worktree는 정상 제거했고, 최종 문서 commit 뒤 운영 재개 증거는 외부 RUNTIME에 기록한다.

## 결정과 증거

모델 capacity와 401이 기존 infra 2회 제한으로 terminal 처리된 것이 멈춤 원인이다.
같은 로그인·Sol/high 설정의 실제 read-only probe는 성공했으므로 credential 변경은 하지 않았다.
알려진 호출 오류만 5분→15분→60분, 401은 6시간 예약 재시도한다. READY·구현 review 우선,
no_work·무효 결과·알 수 없는 오류·orphan의 fail-closed 정책과 투자 게이트는 유지한다.
기존 terminal과 frozen spec은 보존한다. 세부 내용과 검사 명령은
`docs/development-records/2026-09-26-lab-discovery-transport-recovery.md`를 읽는다.

운영 DB online backup과 migration 검증 복사본은
`/home/kwl/.local/share/jusik/portfolio-audit/20260926-lab-discovery-recovery/`에 있다.
복사본 migration에서 기존 10개 테이블의 행 보존과 integrity `ok`를 확인했다.
운영 재개 후 증거는 같은 디렉터리의 `RUNTIME.md`에 남긴다. 기록 시각 이후 상태는
현재 DB·process와 대조해야 하며 timer 활성만으로 개발 중이라고 판단하지 않는다.

## 안전·다음 시작

사용자 소유 미추적 `HANDOFF.md`는 수정하지 않았다. 실주문·PAPER/live 활성화·추가 결제·
credential/모델/권한 변경·원격 push·Windows 종료는 하지 않았다. 자동 개발의 범위는
기존 승인된 공학 allowlist이며 임의의 투자 기준 변경을 포함하지 않는다.

재개 지시: 이 문서와 연결된 개발 기록·외부 RUNTIME을 읽고 현재 runner의 paused,
최신 discovery attempt, retry_after와 process를 확인한다. 예약 전에는 같은 실패를
반복 호출하지 말고 독립 READY를 선택한다. 수동 변경 전에는 canonical runbook의
pause·service inactive 절차를 지킨다.
