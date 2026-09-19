# Backend 전체 검증 기준 기록

- 기록 시각: 2026-09-20T00:00:00Z
- 범위: 현재 `main`의 backend 전체 pytest와 이번 자료 조사에 직접 연결된
  SEC/action-review/collector 묶음의 회귀 검증
- 변경: 코드·자료·설정·runner는 변경하지 않았습니다.

## 결과

- 직접 관련 묶음: `152 passed, 2 warnings`
- 전체 backend (`cd backend && .venv/bin/python -m pytest -q`):
  `1638 passed, 5 failed, 2 warnings`
- 실패 5건:
  - investor의 `hold_review`/quote freshness 기대치 2건
  - 고정 held-band variant SHA 1건
  - 고정 symbol-cap archive의 mandate SHA 1건
  - timestamp-forensics frozen archive의 imported calendar SHA 1건

실패들은 이번 ALFRED/FRED 자료 조사 변경과 무관하며, 고정 archive를 재생성하거나
기대치를 임의로 바꾸지 않았습니다. archive/hash 관련 실패는 기존 replay의 기준과
현재 소스가 어긋난 상태를 뜻하므로 별도 재등록·독립 검토 없이 승격하지 않습니다.

## 운영 상태

- runner: `paused=true`, service/timer `inactive`, timer `disabled`
- 주문·PAPER/live·remote push·Windows 종료: 없음
- 재개 조건: 각 실패의 소유 작업을 별도 등록하고 원인·기준 SHA·재현 archive를 먼저
  고정한 뒤, 해당 범위의 수정과 독립 검토를 순차 수행합니다.
