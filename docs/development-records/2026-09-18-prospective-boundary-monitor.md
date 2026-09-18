# Prospective boundary monitor 격리 자동화

## 범위

prospective OOS의 시작·종료 raw boundary artifact만 자동 캡처하는 별도 CLI와 systemd unit을 추가했습니다. 기존 `BoundaryCaptureMonitor`를 재사용하며 `research_app` 전체, 개발 runner, optimizer, broker 주문과 PAPER/live 승격은 시작하지 않습니다.

## 동작

- 등록 계약·forward DB·source report·code identity를 읽기 전용으로 검증합니다.
- 기존 start artifact는 byte를 재사용하고, end 경계가 도래하면 allowlist 원장을 한 번 읽어 canonical artifact를 no-overwrite로 저장합니다.
- end artifact가 생성되면 monitor 프로세스는 정상 종료합니다. 오류·identity 불일치 시 기존 fail-closed 상태를 유지하고 systemd 재시작 정책으로만 재시도합니다.
- 평가 기간 중 전략·파라미터·후보를 바꾸지 않으며 OOS 성과 계산은 수행하지 않습니다.

## 검증과 운영

CLI import/format/lint와 기존 boundary capture 테스트를 통과시킨 뒤 unit 템플릿을 설치할 수 있습니다. 설치·enable은 별도 명령이며, 설치 전 현재 등록 identity와 capture 경로를 확인합니다. 실제 활성화 후에도 `systemctl --user status jusik-prospective-boundary-monitor.service`로 monitor만 실행 중인지 확인합니다.

## 현재 판정

사전등록 status preflight가 `identity_mismatch/registered_identity_changed`로 닫혔습니다. 등록 시점의 `research_portfolio_engine.py`와 `research_market_calendar.py` SHA가 현재 corrected-calendar 이후 코드와 다르므로, monitor는 경계 capture를 수행할 수 없습니다. 등록 계약을 사후 갱신하거나 현재 코드를 과거 시점에 소급하지 않습니다.

따라서 unit 템플릿은 추가했지만 설치·enable하지 않았습니다. 자동 개발 runner·research app·optimizer·주문·live 설정은 변경하지 않았습니다. 이 prospective 창은 OOS 근거로 사용할 수 없으며, 다음 prospective 기간에는 현재 코드 identity를 먼저 고정한 새 사전등록이 필요합니다.
