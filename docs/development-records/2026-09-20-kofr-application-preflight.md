# KOFR 적용 계약 오프라인 preflight

- 상태: 차단 유지·추가 원천 근거 대기
- 기록 시각: 2026-09-20T00:00:00Z
- 작업 slug: `kofr-application-preflight-20260920`
- 범위: 기존 KOFR source evidence와 새 canonical time-evidence candidate를 변경하지 않고, application contract의 fail-closed 경계를 오프라인에서 재현했습니다.

## 입력과 재현

- source: `/home/kwl/.local/share/jusik/portfolio-audit/20260919-kofr-browser-context/evidence.json`
- source schema: `kofr-source-evidence/v1`
- source SHA-256: `995f963074aa9fe2b83236b27d67f152ec4697780d851ba4ef14e9b3ed180337`
- source rows: 245개, 관측일 `2025-09-11~2026-09-11`
- NAV 입력: `/home/kwl/.local/share/jusik/portfolio-audit/canonical-time-evidence-candidate-20260920/candidate-run-with-time-evidence.json`
- NAV 관측일: 252개, 동일 기간

`validate_application_contract`에 source SHA를 고정한 임시 manifest를 넣어 재현한 결과,
provider의 실제 completeness가 `unknown`이면 `business_date_completeness_unverified`로
종료했습니다. 이는 source bytes나 audit 파일을 수정하지 않는 읽기 전용 진단입니다.

## 날짜 대사

현재 source에 없는 canonical NAV 날짜는 13개입니다.

`2025-10-03`, `2025-10-06`, `2025-10-07`, `2025-10-08`, `2025-10-09`,
`2026-02-17`, `2026-02-18`, `2026-03-02`, `2026-05-01`, `2026-05-05`,
`2026-06-03`, `2026-07-17`, `2026-08-17`

반대로 source에만 있는 날짜는 6개입니다.

`2025-11-27`, `2026-01-19`, `2026-04-03`, `2026-06-19`, `2026-07-03`,
`2026-09-07`

이 차이는 provider 누락, 미국·한국 시장 휴장 차이, 또는 application 기간 정책을
구분할 근거가 아닙니다. 따라서 NAV 표본 삭제, 기간 축소, 직전 금리 carry-forward,
0 대체를 하지 않습니다.

## 판정과 다음 조건

- `missing_risk_free_evidence`는 제거하지 않았습니다.
- Sharpe 등 경제 지표를 재계산하지 않았습니다.
- readiness는 blocked와 not-evaluated를 유지합니다.
- 다음 application 증거에는 provider completeness의 독립 근거, `PUBN_DTTM`의
  timezone/instant 의미, 미국-only 날짜를 포함한 exact-date 적용 정책이 필요합니다.
- 이 조건이 충족되기 전에는 application manifest를 정본으로 만들거나 성과 계산에
  연결하지 않습니다.

## 검증

- source SHA와 schema를 읽기 전용으로 확인했습니다.
- canonical NAV 252개와 source 245개를 결정적으로 대사했습니다.
- `validate_application_contract`의 completeness 차단 code가 재현됐습니다.
- 실제 네트워크 요청, 연구 실행, 주문, runner 재개, readiness 승격은 없었습니다.
