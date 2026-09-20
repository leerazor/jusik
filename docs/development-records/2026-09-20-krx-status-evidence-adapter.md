# KRX status evidence adapter

- 상태: 완료·공식 status payload 대기
- 기록 시각: 2026-09-20T13:00:00Z
- 작업 slug: `krx-status-evidence-adapter-20260920`
- 기준/통합: `ee58724` / 다음 통합 커밋
- 범위: KRX 일별시세 수집과 별도로 공식 status payload를 나중에 주입·검증할 수 있는 순수 parser와 fail-closed 모델을 추가했습니다. 네트워크 endpoint나 기존 zero-bar 정책은 변경하지 않았습니다.

## 변경과 결정

- `backend/jusik/krx_status_evidence.py`의 `parse_krx_status_evidence()`는 `rows` 또는 KRX `OutBlock_1` payload를 읽고 대상 날짜·6자리 종목코드·명시적 `trading_halt | management | normal` 상태를 요구합니다.
- 대상 종목 누락·중복은 `readiness=insufficient`로 남기며, 상태 행이 없다는 이유로 `normal`을 추론하지 않습니다.
- raw payload SHA-256을 report에 보존해 향후 KRX status 원문과 결속할 수 있습니다.

## 검증

- `backend/tests/test_krx_status_evidence.py` 및 KRX collector 회귀 — `148 passed`
- Ruff — 통과
- strict mypy (`krx_status_evidence.py`) — 통과
- `git diff --check` — 통과

## 안전·운영 상태

- 실주문·PAPER/live 승격·remote push·Windows 종료 없음.
- runner paused, service inactive, timer disabled 유지.

## 다음 시작

- KRX 공식 status payload/API 권한이 확보되면 2026-06-29 29개 대상 종목을 이 adapter로 검증하고 기존 zero-row report와 결속합니다. 권한이 없으면 현재 `insufficient` 판정을 유지합니다.
