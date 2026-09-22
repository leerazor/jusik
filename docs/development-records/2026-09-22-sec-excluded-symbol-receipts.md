# SEC 제외 심볼 원문 receipt 조사

- 상태: 완료·보조 원문 확보, R1-05/PIT/경제 acceptance 미승격
- 범위: 고정 100-symbol 수집 결과에서 `request_excluded`인 25개 심볼에 대해 SEC 공개 ticker map과 submissions를 bounded read-only 조회했다.
- 입력: `20260922-us-vintage-collection-100/result.json`의 제외 심볼 25개, `.env`의 `SEC_USER_AGENT`.
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260922-sec-excluded-receipts-20260922/receipt-manifest.json`

## 결과

- SEC ticker map은 4개 심볼을 CIK에 연결했다: `BERZ`, `FNGS`, `GPACW`, `TNMG`.
- 21개 심볼은 현재 SEC ticker map에 없어 `unresolved`로 보존했다. 이를 상장폐지·거래중단·원인으로 추정하지 않는다.
- raw JSON 6개, 총 2,196,377 bytes, parsed submissions 8,664행을 SHA-256과 파일 크기와 함께 보존했다.
- 조회는 ticker map 1회와 CIK submissions 4회로 제한했다. 주문·PAPER/live·원장·DB·서비스 변경은 없었다.

## 해석 경계

SEC submissions의 retrieval/captured 시각은 기업행사의 historical publication 또는 provider first-seen 시각이 아니다. filing acceptance가 존재해도 EODHD/Yahoo 진단 원인·coverage·effective UTC를 자동 확정하지 않는다. 따라서 `historical_observed_at`, PIT, coverage, 경제 평가는 `not-evaluated`로 유지하고 자동 ledger 적용도 금지한다.

## 검증

- `parse_sec_submissions` offline parse 성공: 4개 CIK raw, 8,664행.
- receipt manifest의 raw SHA/size와 unmatched 목록을 재현 가능한 JSON으로 저장했다.
- 네트워크는 위 bounded 조회 외 추가 실행하지 않았다.

## 다음

SEC ticker map에 없는 21개는 historical symbol mapping 또는 provider-specific failed-response receipt가 필요하다. 새 증거 없이 R1-05 checkbox나 경제 acceptance를 승격하지 않는다.
