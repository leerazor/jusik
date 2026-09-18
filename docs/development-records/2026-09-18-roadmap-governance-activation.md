# 승인된 roadmap governance 재개

## 목적

사용자가 투자 개발 roadmap의 자동 진행을 승인했으므로, 일반 연구·PAPER/live·주문 경로를 재개하지 않고 `investment-roadmap` 전용 runner만 다시 실행할 수 있도록 governance와 운영 설정을 동기화했다.

## 변경 및 identity

- `docs/research-mandate.json`의 `dispatch_enabled`를 승인된 값인 `true`로 동기화했다.
- 전체 JSON bytes SHA-256은 `ceca2ee1d3e86cf79822b6b4a1606ac6699405f93eaf302fcf3842247f5de7ac`이며, governance projection SHA는 `624599f24864201fce981ed2e1407db3cf53eb3ad2da306bf3e7cc0b25031adb`이다.
- `~/.config/jusik/roadmap-development-runner.json`에서 `planning_enabled=true`를 사용하고, `scope=investment-roadmap`, `automatic_recovery=false`를 유지한다.
- runner의 mandate/dispatch fail-closed validator와 관련 focused pytest 54개, Ruff, strict mypy, diff 검사를 통과했다.

## 운영 경계

user timer는 전용 설정으로만 활성화한다. runner는 clean worktree, mandate SHA, dispatch gate를 통과한 roadmap 작업만 계획·실행한다. 전략 후보의 자동 승격, PAPER/live 전환, broker order, market-data network collection, remote push는 수행하지 않는다.

기존 operator hold는 2026-09-17의 “경제 목표 재정렬 및 명시적 사용자 승인 전 재개 금지” 기록이며, 당시 drain 작업과 service 종료가 완료되어 있다. 현재 승인과 일치하므로 표식 파일은 삭제하지 않고 audit archive로 이동한 뒤 service를 시작한다.

## 다음 단계

hold 해제 후 user service와 timer를 확인했다. 첫 cycle은 `status=idle`, exit 0으로 종료했고 timer는 활성 대기 중이다. 현재 큐에는 신규 실행 task가 없으며, 실패·차단 항목은 명시적 retry 전 격리하는 정책을 지켰다. 따라서 임의의 차단 연구를 재실행하지 않고, 다음 재개 대상의 근거와 retry 조건을 확정한 뒤 하나씩 넣는다. runner가 조건을 만족하지 못하면 작업을 시작하지 않고 fail-closed 상태를 유지한다.
