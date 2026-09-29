# LIME·MDA 누락 기간과 종목 식별 근거 확보

- 상태: 자료 탐색·원문 확보 완료; 종목 identity 재대사와 R1-05 판정은 미완료.
- 날짜: 2026-09-29. 정확한 UTC 수집 시각은 아래 profile의 `recorded_at`과 각 source의 `captured_at`에 보존했습니다.
- 작업 slug: `listing-identity-evidence`.
- 기준: local main `eadcaa06d5169b3992eea84e526d9bd2c19a9b29`.
- 목표: 시간·요금제 제약 아래 기존 366세션 차단을 해소할 실제 원천 근거와 가장 짧은 다음 작업을 찾습니다.

## 확인한 사실

| 종목 | 기존 listing 원문의 회사명 | 가격 응답의 회사명 | 공식 미국 거래 시작일 | 기존 캐시의 누락 |
| --- | --- | --- | --- | --- |
| LIME | Lime Energy Company | Neutron Holdings, Inc. | 2026-07-01 | 2025-08-13~2026-06-30의 221세션 |
| MDA | MacDonald Dettwiler and Associates Ltd | MDA Space Ltd. | 2026-03-12 | 2025-08-13~2026-03-11의 145세션 |

요청은 2025-09-11~2026-09-11, warmup 시작은 2025-08-13입니다. 두 종목 모두 기존 universe 272행과 bars를 session으로 직접 대조했고, 누락 366개가 전부 새 미국 종목의 거래 시작일 전임을 확인했습니다. 해당 요청 구간에서 거래 시작일 이후 누락은 0개입니다. 이는 기존 캐시 내부 집계이며 공급자 전체 자료의 완전성 판정이 아닙니다.

2025-08-13·2026-01-02 Alpha listing 원문 두 개는 manifest SHA와 일치합니다. 두 응답 모두 LIME의 `ipoDate=2000-01-31`, MDA의 `ipoDate=2017-10-05`, 옛 회사명, `status=Active`, `delistingDate=null`을 담고 있습니다. Yahoo 장기 원문의 `firstTradeDate`는 각각 2026-07-01T13:30:00Z, 2026-03-12T13:30:00Z이며 공식 거래 시작일과 일치합니다. 이전 기록에서 `firstTradeDateMilliseconds=null`을 관찰한 것은 다른 필드입니다. `firstTradeDate` 자체가 없었다고 해석하지 않습니다.

**판단:** 현재 회사의 상장 전 가격을 반복 요청하는 것으로 해결할 누락이 아닙니다. listing의 옛 회사 identity와 현대 가격 응답의 identity가 충돌합니다. 단순 이름 유사도나 티커 일치만으로 결합을 유지하거나 366개를 정상 coverage로 바꾸면 안 됩니다. MDA의 회사 계보·증권 연속성은 별도 매핑으로 확인해야 하며, 공시만으로 공급자가 잘못된 행을 반환한 내부 원인을 단정하지 않습니다.

## 새로 확보한 무료 공식 원문

다음 5개 URL을 각각 한 번 요청해 HTTP 200 원문을 별도 audit 폴더에 저장하고 SHA-256·수집시각을 남겼습니다.

1. [Lime IPO 발행사 발표](https://lime.gcs-web.com/news-releases/news-release-details/lime-announces-pricing-initial-public-offering): 2026-06-30 발표, Neutron·LIME·Nasdaq와 예정 거래일 연결.
2. [Lime SEC 10-Q](https://www.sec.gov/Archives/edgar/data/1699963/000162828026055698/lime-20260630.htm): CIK 1699963, 실제 Nasdaq 거래 시작일 2026-07-01 확인.
3. [MDA Space SEC 6-K 첨부](https://www.sec.gov/Archives/edgar/data/1857047/000110465926029598/tm266080d11_ex99-1.htm): CIK 1857047, 실제 NYSE 거래 시작일 2026-03-12 확인. TSX 거래는 별도입니다.
4. [Willdan SEC 8-K](https://www.sec.gov/Archives/edgar/data/1370450/000110465918067398/a18-39878_18k.htm): 2018-11-09 Lime Energy 인수 완료. 현대 Neutron과 같은 회사로 취급할 수 없습니다.
5. [옛 MDA의 Maxar 변경 공시](https://www.sec.gov/Archives/edgar/data/1121142/000119312517303941/d461944dex991.htm): 2017-10-05 회사명 변경·합병 맥락. 현대 MDA Space와의 증권 identity 연결을 별도로 검토할 근거입니다.

공시의 과거 사실·발표일과 이번 수집시각을 구분합니다. 이번 `captured_at`을 과거 provider `observed_at`으로 채우지 않았습니다. 거래 시작 뒤 제출된 10-Q·6-K는 사후 원인 확인 자료이며 당시 공개 시점을 자동 증명하지 않습니다.

## 필요한 자료를 채우는 순서

1. **즉시 가능한 기술 작업:** 위 고정 원문·listing·가격 응답을 입력으로 LIME/MDA 두 종목의 identity 충돌을 재현하고, symbol뿐 아니라 issuer/security·exchange·currency·유효 기간을 연결하는 검증 후보를 만듭니다. 출력은 정상·상장 전·identity 충돌·실제 상장 후 누락을 분리한 진단입니다. 원 캐시를 덮어쓰거나 종목을 조용히 삭제하지 않습니다.
2. **종목 목록 복구:** 공식 상장·회사변경 공시와 당시 listing snapshot으로 각 기간에 유효한 증권을 대사합니다. 현대 회사는 상장일 이후에도 당시 universe에 적격하게 들어왔다는 근거와 warmup이 필요합니다. 사후 확인된 새 종목을 과거 표본에 자동 추가하지 않습니다. MDA의 TSX/CAD 가격을 NYSE/USD의 과거 가격으로 이어 붙이지 않습니다.
3. **실제 가격 결손만 재수집:** identity가 확정된 뒤 상장 이후 빠진 날짜만 기존 공급자에 bounded 요청합니다. 현재 두 종목의 해당 구간은 0개이므로 더 긴 이력을 위한 신규 결제·키 발급은 현 단계 권고가 아닙니다.
4. **나머지 자료는 별도 확보:** 배당·분할의 발표/효력/지급일·권리수량은 기존 SEC 후보 52건과 발행사 원문에서 필요한 보유 구간부터 대사합니다. 기존 action 121행의 `observed_at` 누락과 전체 PIT 적격성, 초기 상태·가격·벤치마크 및 독립 OOS 조건은 이번 두 종목 근거로 해결되지 않습니다. 사전등록 전 노출된 자료를 untouched OOS로 재사용하지 않습니다.

다음 planner는 '더 긴 LIME/MDA 가격이 없어서 할 일이 없음'을 반복하기 전에 1번의 좁은 identity 진단·보호 작업을 검토합니다. 독립 scope 검토와 동결된 소유·인수 조건을 거치며, 새 자료의 존재만으로 R1-05 체크·전략 승인·수익률을 확정하지 않습니다.

## 검증과 운영

- 원 fresh-result SHA: `b659c38676d531b70c3ea172fdcb5e2680bd4eb0ec6a1f2a2f9f913ba50c5d0e`; 읽기 전후 동일.
- Alpha 원문 2개 content hash 일치, 두 종목의 universe/bar 차집합 221+145와 상장 후 결손 0 재현. 공식 HTML 본문의 거래 시작 문구 확인.
- 독립 `role.review`가 원 result·Alpha hash, request와 captured_at, 366세션 집계와 공시 본문을 별도 읽기 전용 재검증하여 제한된 판단 PASS. MDA는 미국 거래 시작 전이라는 의미이며 TSX·회사 전체 상장 전으로 일반화하지 않습니다.
- 제품 코드·테스트·원본 cache·연구 mandate·전략 판정 변경 없음. 제품 테스트 재실행 대상 없음.
- 기록 저장 중 runner를 잠시 pause하고 service를 중지했습니다. 통합 후 기존 설정으로 재개합니다. 루트 사용자 `HANDOFF.md`는 보존합니다.
- 공개 HTTP 조회만 실행했습니다. 키 사용·구매·연락 전송·주문·PAPER/live·원격 push 없음.

## 증거와 인계

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260929-listing-identity-evidence/`.
- `profile.json`: 입력 hash, Alpha 행·요청 identity, 누락 세션 목록, Yahoo metadata, 공시 URL·원문 hash·수집시각과 한계.
- profile SHA-256: `bb7c48d95552833b238e9507ef15360b476a3330c0aeb9abc5c09cdb5e901de1`.
- `collect.py`: 기존 자료 대조와 제한 수집 재현 스크립트. 재검토 시 저장된 자료를 우선 읽고 네트워크 재실행은 필요할 때만 합니다.
- handoff: `docs/handoffs/2026-09-29-listing-identity-evidence.md`.
