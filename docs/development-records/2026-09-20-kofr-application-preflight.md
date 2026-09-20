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

한국거래소의 [표준 KOFR 설명서](https://open.krx.co.kr/contents/OPN/01/01040505/%ED%91%9C%EC%A4%80_%ED%95%9C%EA%B5%AD%EB%AC%B4%EC%9C%84%ED%97%98%EC%A7%80%EA%B8%88%EB%A6%AC%5BKOFR%5D_%EC%84%A4%EB%AA%85%EC%84%9C.pdf)는 산출 절차와 공시 주기·방법 변경, 비상시 대체금리를 설명하지만, 이 application에 필요한 행별 `PUBN_DTTM` timezone/instant 의미나 provider 전체 business-date 목록은 제공하지 않습니다. 비상시 직전 KOFR 대체금리 규정도 일반적인 미국-only NAV 날짜의 carry-forward 근거로 확장하지 않습니다.

## 검증

- source SHA와 schema를 읽기 전용으로 확인했습니다.
- canonical NAV 252개와 source 245개를 결정적으로 대사했습니다.
- `validate_application_contract`의 completeness 차단 code가 재현됐습니다.

## 보조 공시 일정 증거

- KODEX KOFR 공식 투자위험 설명서가 KOFR INDEX를 매일 오전 11시 00분에
  공시한다고 설명하는 원문을 별도 보조 자료로 보존했습니다.
- 원문: [KODEX KOFR 투자위험 설명서](https://m.samsungfund.com/upload/core/2ETFG6-Aa.pdf)
- raw SHA-256: `57037e008a62ccfdda91a61f1d86f79fc6a3cdffd1bce0bbac46beca97afd6cd`
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-kofr-publication-schedule-evidence/`
- 이 자료는 공식 KSD 응답의 행별 `PUBN_DTTM` timezone/instant 또는 canonical NAV
  기간의 provider business-date 완전성을 증명하지 않으므로 `operator_verified=false`,
  자동 적용=false를 유지합니다.

## 반복 응답 대조

- 동일한 KSD `getGridRateExcelList` 요청을 한 번 재실행해 245행을 받았고,
  기존 245행 projection과 날짜·금리·`PUBN_DTTM` 원문이 exact match했습니다.
- repeat raw SHA-256: `d35ca9232d1e3ef02af31f667387497476a9b4b6c66e146ecb4744aa0abce142`
- alternate `getGridRateList` action은 malformed XML(40 bytes)로 fail-closed되어
  보존했으며 채택하지 않았습니다.
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-kofr-repeat-response-evidence/`
- 반복 응답은 provider 반환의 결정성을 보강할 뿐 completeness·publication instant를
  증명하지 않으므로 application status는 변하지 않습니다.
- 실제 네트워크 요청, 연구 실행, 주문, runner 재개, readiness 승격은 없었습니다.

## carry-forward 자료 검토

- KRX 공식 검색 결과에는 KOFR 미산출일에 직전 KOFR을 대리 사용하는 선물 산식 설명이
  노출되지만, 이는 선물 복리 산식의 문맥이며 이 NAV application에 자동 확장하지
  않았습니다.
- 연결된 KRX 표준 설명서 URL의 직접 요청은 PDF가 아닌 MenuSearch HTML을 반환하여
  raw evidence로 채택하지 않았습니다. carry-forward 정책과 미국-only 날짜 적용은
  별도 계약·검토 없이는 추가하지 않습니다.
