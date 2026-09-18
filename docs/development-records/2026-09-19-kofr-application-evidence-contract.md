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

- `pytest -q backend/tests/test_kofr_application_evidence.py`: 7 passed
- Ruff check/format: passed
- strict mypy: passed
- 실패 fixture: timezone, completeness, publication semantics, source hash/interval ordering, source·manifest 날짜 집합 불일치 경계를 fail-closed로 확인했습니다.

## 제한과 다음 단계

현재 확보된 KOFR source evidence는 자체 business-date completeness와 공표시각 timezone을 독립적으로 증명하지 않습니다. 따라서 실제 application manifest를 만들거나 `missing_risk_free_evidence`를 제거하지 않았고 Sharpe를 재계산하지 않았습니다. 다음 작업은 provider가 제공하는 business-date/시간대 receipt가 이 계약을 충족하는지 별도로 확보하는 것입니다.

실제 source audit SHA를 pin한 임시 application manifest를 계약에 넣어 재현한 결과는
`business_date_completeness_unverified`로 종료했습니다. 이 결과는 자료 부족을 확인하는
진단이며 source evidence나 원본 audit을 수정하지 않습니다.

계약도 보강했습니다. `coverage_status=complete`인 application manifest의
`business_dates` 집합은 source rows의 관측일 집합과 정확히 같아야 합니다. source 행을
manifest에서 조용히 누락하거나 manifest에 source 밖 날짜를 추가하면
`business_date_manifest_mismatch`로 거부합니다. 이 검사는 provider 전체 영업일 목록을
증명하지 않으며, 그 외부 근거가 없으면 기존 `unverified` 차단을 유지합니다.

`validate_nav_date_application` preflight도 추가했습니다. 검증된 application report와
NAV 날짜를 exact 비교해 source 날짜가 없는 NAV 날짜를
`nav_date_application_missing`으로 거부합니다. carry-forward·calendar 추론은 구현하지
않았고 별도 reviewed contract가 없으면 계속 fail-closed입니다.

추가로 corrected NAV bundle은 614개 UTC daily date를 `2024-04-24~2026-09-08`
범위로 포함하지만 현재 KOFR source evidence는 `2025-09-11~2026-09-11`만 포함해
앞쪽 359개 NAV 날짜가 비어 있습니다. 따라서 현재 source로 전체 Sharpe를 계산할 수
없으며, 기간을 조용히 줄이거나 결측을 0으로 대체하지 않습니다.

동일 기간을 더 좁혀 대사해도 `2025-09-11~2026-09-08`의 NAV daily date는 255개이고
KOFR와 직접 겹치는 날짜는 242개입니다. NAV에만 있고 KOFR 행이 없는 13개 날짜는
`2025-10-03~2025-10-09`, `2026-02-17~2026-02-18`, `2026-03-02`,
`2026-05-01`, `2026-05-05`, `2026-06-03`, `2026-07-17`, `2026-08-17`입니다.
이 결손은 source 누락인지 시장별 휴장일 차이인지 현재 자료만으로 확정하지 않으며,
자동 carry-forward나 NAV 표본 삭제 없이 별도 calendar/application 정책을 요구합니다.

추가로 13개 날짜의 corrected NAV triggering close group을 확인한 결과 모두
`XNYS`만 존재하고 `XKRX` session은 없습니다. 따라서 이 날짜는 현재 자료에서
KOFR provider 누락으로 단정하지 않습니다. 다만 combined KRW NAV의 Sharpe를 계산하려면
미국-only 날짜에 risk-free를 적용할 명시적 정책과 그 근거가 필요합니다. 암묵적인
carry-forward나 XNYS-only 수익률 삭제는 application evidence로 인정하지 않습니다.

한국거래소의 표준 KOFR 설명서는 산정·재산정·검증 절차와 공시 주기·방법 변경을
설명하지만, 이 자료 자체에는 이 artifact에 필요한 provider business-date 전체 목록과
`PUBN_DTTM` timezone 계약이 없습니다. [공식 설명서](https://open.krx.co.kr/contents/OPN/01/01040505/%ED%91%9C%EC%A4%80_%ED%95%9C%EA%B5%AD%EB%AC%B4%EC%9C%84%ED%97%98%EC%A7%80%ED%91%9C%EA%B8%88%EB%A6%AC%5BKOFR%5D_%EC%84%A4%EB%AA%85%EC%84%9C.pdf)
와 원문을 함께 보존할 별도 자료 수집 계획이 필요합니다.
