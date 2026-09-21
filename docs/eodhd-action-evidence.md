# EODHD 기업행사 증거 경계

`backend/jusik/research_eodhd_evidence.py`는 이미 수집한 EODHD `/div`와
`/splits` 응답 bytes를 검증하는 읽기 전용 adapter다. 요청은 대문자 US 심볼,
endpoint, 시작일과 종료일로 고정하며 응답 bytes의 SHA-256과 timezone-aware
retrieved UTC를 보존한다. 네트워크 호출·재시도·원장 적용은 이 경계에 없다.

배당의 EODHD `date`는 `ex_date`로 보존한다. `declarationDate`, `recordDate`,
`paymentDate`는 각각 별도 필드이며 null 또는 누락은 wire field 이름을 가진
`missing_fields`로 기록하고 evidence 상태를 `blocked`로 만든다. 모든 보조 날짜가
있어도 이 응답은 publication time, PIT, provider 전체 coverage를 증명하지 않으므로
`pit_evaluation`, `coverage`, `economic_evaluation`은 `not-evaluated`로 고정한다.

분할은 date와 decimal `numerator/denominator`의 exact rational만 보존한다.
법적 effective UTC나 거래 세션을 추론하지 않는다. 누락·잘못된 날짜/금액/비율,
중복 event date, 요청 기간 밖의 행은 전체 응답을 거부한다. 빈 응답도 동일한
평가 상태와 `automatic_ledger_application=false`를 가진다.

`bind_sec_reference`는 호출자가 지정한 기존 `event_key` 하나에만 SEC metadata를
붙인다. 기존 `parse_sec_submissions`와 `parse_sec_filing_candidate`를 사용해
expected filing-body SHA, submissions의 유일한 accession, CIK를 검증하고 SEC raw
SHA·filing retrieval UTC·submissions retrieval UTC·accepted UTC를 별도
`sec_reference`에 보존한다. submissions retrieval 시각은 필수이며 accepted 시간이
두 retrieval 시각 중 하나보다 늦으면 거부한다. SEC reference는 EODHD action facts를 검증하거나
승인하지 않으며, 심볼·날짜·PIT를 자동 연결하지 않는다. 실제 EODHD date와 SEC
문서의 legal effective date가 다를 수 있는 ATXG/IMUX 사례도 이 분리를 유지한다.
