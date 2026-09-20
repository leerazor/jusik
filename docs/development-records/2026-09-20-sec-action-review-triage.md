# SEC action review 원문 triage

- 상태: 부분 triage 완료·operator verification 대기
- 기록 시각: 2026-09-20T07:00:00Z
- 작업 slug: `sec-action-review-triage-20260920`
- 기준/통합: `db4403d` / 다음 통합 커밋
- 범위: priority catalog 8건의 SEC HTML을 read-only로 확인해 검토 순서와 누락 필드를 분류했습니다. form·ledger·action DB·성과 결과는 변경하지 않았습니다.

## 확인 결과

- 원문 SHA/source binding: `8/8` verified (`event-near-candidates` 경로)
- `BMRC` filing `0001403475-25-000068`: `$0.25` common dividend, payment `2025-11-13`, record `2025-11-06` 문구가 보이지만 ex-dividend date와 comparable share basis는 원문 triage만으로 확정하지 않았습니다.
- `RWT` filing `0001410578-25-002042`: common `$0.18` 및 preferred `$0.625` dividend와 payment/record dates가 함께 있어 계급별 분리와 ex-date 확인이 필요합니다.
- `ATXG` filing `0001493152-26-013202`: `1-for-15` reverse split와 `2026-03-30` effective 기대 문구가 있으나 보상 grant 조정 문맥이므로 issuer corporate-action effective date를 별도 확인해야 합니다.
- `IMUX` filing `0001193805-26-000495`: `1-for-10` reverse split, certificate `2026-04-22`, post-split trading `2026-04-27` 문구가 있어 legal effective/trading date 경계를 operator가 확인해야 합니다.
- 나머지 `ADAMI`, `AVX`, `IMUX` second filing, `RWT` compensation filing은 후보 keyword 또는 과거 event 언급만으로 ledger fact를 확정할 수 없습니다.

## 결정

- 위 문구는 검토 보조 관찰값일 뿐 `ExtractedFacts`, `operator_verified`, `revision_id`, `content_sha256`, `pit_link`를 자동 생성하지 않습니다.
- ex-date·권리수량·법적 effective date·PIT 관측시각이 모두 operator 원문 확인으로 채워지기 전에는 R1-04/R1-05, action ledger, NAV, 경제 acceptance를 승격하지 않습니다.
- priority form은 기존 blank 상태를 보존하고 자동 ledger 적용은 계속 `false`입니다.

## 검증·안전

- 원문 8개를 `event-near-candidates`에서 읽어 kind별 키워드/context를 대조했습니다.
- source SHA mismatch/missing: `0/0`; 실제 주문·PAPER/live·network collection·remote push·Windows 종료 없음.
- runner paused, service inactive, timer disabled를 유지합니다.

## 재개 조건

- operator가 각 후보의 issuer 원문에서 event type, amount/ratio, ex/effective/payment/record UTC 경계, share basis와 PIT link를 채운 뒤 form validator를 다시 실행합니다.
- 하나라도 불확실하면 해당 행은 제외 사유와 함께 남기고, 자동 삭제·0 대체·ledger 적용을 하지 않습니다.
