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

## 현재 판정과 해결

초기 preflight는 현재 corrected code가 등록 identity와 달라 `identity_mismatch`였습니다. 계약을 갱신하지 않고 등록 시점 소스를 재구성했습니다. engine은 commit `0102858`, calendar는 등록 SHA를 가진 commit `c67e6e2`에서 가져온 immutable snapshot이며, 전체 identity가 계약 SHA `19d3622e5b195e52e1e06065d32d771d3e40c4e4c53f8fc25c101f510ca14fd7`와 일치합니다.

monitor는 이 snapshot을 `--code-root`로 사용해 status `observing`을 통과한 뒤 boundary capture만 수행합니다. 현재 corrected code·계약 JSON·전략 결과는 변경하지 않습니다. unit은 snapshot 경로를 고정해 설치·활성화할 수 있으며, end artifact 생성 후 정상 종료합니다. 이 snapshot 사용은 과거 전략 재실행이나 OOS 성과 계산이 아닙니다.
