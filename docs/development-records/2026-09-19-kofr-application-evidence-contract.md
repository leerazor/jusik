# KOFR 적용 근거 계약

- 상태: 기술 slice 완료·실제 적용 자료 대기
- 기록 시각: 2026-09-19T00:00:00Z
- 범위: `kofr_source_evidence`의 source artifact를 Sharpe 입력으로 직접 연결하지 않고, 명시적 application manifest를 fail-closed 검증하는 순수 오프라인 계약을 추가했습니다.
- 변경: `backend/jusik/kofr_application_evidence.py`, `backend/tests/test_kofr_application_evidence.py`

## 고정한 계약

- source evidence 전체 bytes SHA-256을 application manifest가 직접 고정해야 합니다.
- 공표시각은 `Asia/Seoul`의 local wall time으로 명시하고 UTC로 변환합니다. 다른 timezone이나 암묵적 timezone은 거부합니다.
- provider business-date completeness는 manifest가 `complete`와 명시적인 날짜 목록을 제공해야 하며, XKRX·평일 추정으로 대체하지 않습니다.
- interval마다 시작·종료일, source observation date, annual rate를 명시하고 source 원문과 값을 일치시킵니다.
- 공표 instant가 interval 시작 시각 이후이면 look-ahead로 거부합니다. 이 계약은 carry-forward 정책을 자동으로 만들지 않습니다.
- 검증기는 Sharpe, readiness, NAV, runner, PAPER/live, 주문을 호출하거나 변경하지 않습니다.

## 검증

- `pytest -q backend/tests/test_kofr_application_evidence.py`: 5 passed
- Ruff check/format: passed
- strict mypy: passed
- 실패 fixture: timezone, completeness, publication semantics, source hash/interval ordering 경계를 fail-closed로 확인했습니다.

## 제한과 다음 단계

현재 확보된 KOFR source evidence는 자체 business-date completeness와 공표시각 timezone을 독립적으로 증명하지 않습니다. 따라서 실제 application manifest를 만들거나 `missing_risk_free_evidence`를 제거하지 않았고 Sharpe를 재계산하지 않았습니다. 다음 작업은 provider가 제공하는 business-date/시간대 receipt가 이 계약을 충족하는지 별도로 확보하는 것입니다.

실제 source audit SHA를 pin한 임시 application manifest를 계약에 넣어 재현한 결과는
`business_date_completeness_unverified`로 종료했습니다. 이 결과는 자료 부족을 확인하는
진단이며 source evidence나 원본 audit을 수정하지 않습니다.
