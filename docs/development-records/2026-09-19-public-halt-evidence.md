# Nasdaq 공개 거래중단 evidence collector

- 상태: 기술 slice 완료. 경제 acceptance나 R1-02 전체 체크는 변경하지 않았습니다.
- 구현: `backend/jusik/research_public_evidence.py`
- 범위: Nasdaq Trader의 날짜별 공개 RSS를 조회하고 원문 XML, 수집 시각, source URL,
  SHA-256, symbol, halt date, reason code를 보존합니다.
- 안전: API key·주문·PAPER/live 상태·운영 원장·원격 push를 사용하지 않았습니다.
  공식 호출 제한을 지키도록 요청 간격을 60초로 제한합니다.

## 검증

- `pytest -q tests/test_research_public_evidence.py`: 2 passed
- Ruff: 통과
- 실제 공개 RSS 2024-01-02 1회 조회: 45건, 원문 XML 저장 성공
- 수집 결과는 `coverage`와 공급자 원문이 확보된 범위만 의미하며, 전체 미국 시장
  coverage 또는 역사적 provider PIT를 주장하지 않습니다.

## Alpha Vantage 기업행동 collector

- 구현: `backend/jusik/research_alpha_actions.py`
- `DIVIDENDS`/`SPLITS` 응답을 원문 JSON, source URL(키 제거), 수집 시각, SHA-256,
  ex/effective/payment date, 금액·통화·분할비율로 보존합니다.
- 무료 API 호출 제한을 고려해 요청 간격을 12초로 제한하며, 원문은 가격·원장에
  자동 적용하지 않습니다.
- 검증: `pytest -q tests/test_research_alpha_actions.py`: 2 passed; Ruff 통과.
- 실제 `.env` 키로 NVDA 2024–2025 응답 2건을 조회해 10개 action을 파싱했습니다.
  이 결과는 provider 응답의 수집 시각만 증명하며 historical PIT completeness를
  주장하지 않습니다.

## 다음 단계

SEC EDGAR filing receipt와 Alpha Vantage 배당·분할 응답을 같은 raw/evidence 계약으로
연결하고, SEC acceptance 시각을 source-specific `observed_at`으로 보존합니다.

## SEC filing collector 추가

- 구현: `backend/jusik/research_sec_evidence.py`
- CIK별 SEC submissions JSON 원문을 저장하고 accession, form, filing date,
  acceptance timestamp, primary document와 수집 시각·SHA-256을 보존합니다.
- 검증: `pytest -q tests/test_research_sec_evidence.py`: 1 passed; Ruff 통과.
- 실제 SEC CIK `1045810` 1회 조회 성공(1000 filings, raw JSON 저장). API key는
  사용하지 않았고 User-Agent만 요청 헤더에 사용했습니다.

## Public evidence catalog

- 구현: `backend/jusik/research_public_evidence_catalog.py`
- SEC filing, Nasdaq halt, Alpha action을 source-specific identity와 raw SHA로 결합하며
  중복을 제거합니다. catalog의 `coverage`는 의도적으로 `incomplete`로 고정되어
  원천 전체 coverage가 없는 상태에서 R1 checklist나 경제 acceptance를 승격하지
  않습니다.
- 검증: `pytest -q tests/test_research_public_evidence_catalog.py`: 1 passed; Ruff 통과.

## 2026-09-20 bounded batch 및 parser 교정

- 대상: 미국 registry 10개 심볼, Alpha 2024-01-01~2025-12-31, Nasdaq halt
  2024-01-02 1일.
- 결과: Alpha 53 actions, Nasdaq raw 45건 중 요청 기간에 포함된 catalog 27건.
  catalog SHA-256은 `/home/kwl/.local/share/jusik/portfolio-audit/20260920-public-evidence-batch/catalog.json`
  및 `request.json`에 보존했습니다.
- 결함 교정: Nasdaq HTML 표의 `Issue Symbol` 헤더를 symbol 값으로 읽던 parser를
  수정했습니다. 기존 raw 45건 재파싱에서 잘못된 `SYMBOL` 결과는 0건입니다.
- 판정: 무료 공급자의 전체 기간·PIT·권리 가격 경계가 없으므로 `coverage=incomplete`,
  R1-02/R1-04/R1-05 미체크를 유지합니다.

## SEC ticker mapping 및 filing batch

- SEC `company_tickers.json`을 자동 조회해 registry 미국 10개 심볼 중 8개를 CIK로
  매핑하고 submissions 6,243건을 수집했습니다. SOXL/TQQQ는 SEC ticker map에 없어
  매핑 누락으로 명시적으로 보존했습니다.
- 2024–2025 요청 범위에서 catalog에는 SEC 1,517건, Alpha 53건, Nasdaq 27건이
  source-specific identity로 포함되었습니다. 최종 catalog SHA-256은
  audit batch의 `catalog.json`과 `request.json`에 기록했습니다.
- SEC filing은 공시 접수 시각을 보존하지만 filing 본문에서 corporate-action 권리·가격
  경계를 완전히 추출한 것은 아니므로 R1-04/R1-05 acceptance는 승격하지 않습니다.

## SEC filing 본문 후보 추출 slice

- `SecFilingCandidate`와 `filing_document_url()`을 추가해 accession의 primary document를
  원문 URL로 재현하고, 본문 키워드(`dividend`, `split`, `merger`, `delisting`,
  `suspension`)를 후보 종류로만 기록합니다.
- 후보는 확정 기업행동·권리·가격·effective/payment date가 아니며 catalog acceptance나
  R1 checklist를 승격하지 않습니다. primary document가 없거나 UTF-8이 아니면
  fail-closed 합니다.
- 검증: SEC parser 관련 pytest 4개 및 Ruff 통과. 전체 backend pytest는 기존 archive/hash
  및 상태 기대치 불일치 7건으로 실패했으며 이번 SEC 변경과 무관한 실패로 기록합니다
  (1615 passed, 7 failed).

## SEC filing bounded candidate fetch

- 2024-01-01~2025-12-31 범위에서 기존 SEC submissions raw를 입력으로 8-K/8-K/A
  primary document 3건만 fetch했습니다. 원문 HTML 3개, summary/request와 SHA sidecar를
  `/home/kwl/.local/share/jusik/portfolio-audit/20260920-sec-filing-candidates/`에
  보존했습니다.
- 결과 후보 종류는 `merger` 1건과 빈 후보 2건입니다. 키워드 후보는 확정 event가 아니며
  권리·가격·effective/payment date 산출, catalog 승격, R1 acceptance에 사용하지 않습니다.
- 요청 경계는 `max_documents=3`, 허용 form `8-K`/`8-K/A`, SEC User-Agent, 요청 간격
  0.2초로 고정했습니다. 실제 주문·PAPER/live·원격 push는 없었습니다.
