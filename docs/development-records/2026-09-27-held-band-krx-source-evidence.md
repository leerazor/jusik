# Held-band KRX 공식 자료 출처 후보 검토

- 상태: 완료 (공식 문서 기반 source 후보 권고; strict PIT·최종 자료 수용 판정 아님)
- 기록 시각: 2026-09-27T06:38:26Z
- 작업 slug: `portfolio-held-band-krx-source-evidence`
- 기준/통합: `57c5881f8ae20300ecdbcb9b3e1b683d043dbd04` / `4cc8c26352b3d3f9a17fd7874c88dfefaddc9903` (local `main`, fast-forward)
- 범위: KRX Open API 및 별도 데이터상품의 공개 공식 문서를 검토하고, KRX가 이후 KR 주식 scope에서 맡을 수 있는 역할을 권고했습니다. 로그인, 인증키 사용, API/data request, 구매, mandate·v2·제품 코드 변경, 성과/OOS 평가는 하지 않았습니다.

## 변경과 결정

- [held-band 결정 준비 문서](../research/portfolio-held-band-decision-preparation-v1.md)에 KRX coverage, API 승인·이용약관, data product 경로, PIT·historical universe 한계, Alpha Vantage와의 역할 비교를 기록했습니다.
- 공식 service catalog는 KOSPI·KOSDAQ 일별매매 및 종목기본정보를 2010-01-04부터, KONEX 일별매매 및 종목기본정보는 2013-07-01부터, ETF 일별매매를 2010-01-04부터 제공한다고 표시합니다. 개별 KOSPI·KOSDAQ 일별 API 페이지는 2026-01-16 수정일을 보이지만, 비로그인 화면은 output field와 request/response 명세를 렌더링하지 않습니다.
- 공식 이용 절차는 로그인·인증키 신청/관리자 승인 뒤 각 API별 활용 신청·승인을 요구합니다. 약관은 비상업 이용, 결과 대가 청구·정보의 제3자 제공 금지, 키당 하루 최대 10,000회, 자료의 정확성·완결성·연속 제공 비보장을 명시합니다. 사용자의 이용 목적 적격성은 확인되지 않았습니다. 별도 데이터상품은 품목별 가격·기간·필드를 확인하고 구매·결제 뒤 이용 목적 심사를 받습니다. 구체 비용은 확인하거나 지출하지 않았습니다.
- **권고:** KR 주식 scope가 추후 선택되면 KRX Open API를 KOSPI·KOSDAQ 일별 가격의 첫 공식 조사 후보로 둡니다. 공개 이력 시작일만으로 과거 당시 eligible universe, 상장·폐지 membership, 발표/수신 시각, correction history 또는 survivorship-free PIT를 입증하지 못하므로 현재 strict PIT source로 수용하지 않습니다. Alpha Vantage는 US date-specific membership 조사 후보로 유지합니다.
- 기존 KRX smoke 자료는 fixture 가능성을 보여줍니다. 2025-09-11 응답 960 universe 행 중 31개 무거래 행을 제외해 929 bars로 정규화했고, 2025-09-11~2026-09-11 수집은 완료됐습니다. 그러나 approximate pilot은 `insufficient`, `completeness=incomplete`, `readiness.ready=false`였으며 성과 지표를 만들지 않았습니다. 자료는 개발·회귀 fixture 전용이고 성과/OOS/후보·실거래 승인 근거에서 제외합니다.

## 문서·계약 영향

- 사용자 문서: 결정 준비 문서만 갱신했습니다. mandate, preregistration 초안과 사용자 동작은 그대로입니다.
- 운영 문서: 작업 등록부와 held-band handoff는 통합 후 갱신합니다.
- API·설정·데이터 계약: 변경 없음. API 명세·credential 상태를 검증한 것으로 주장하지 않습니다.

## 검증

- KRX 공식 서비스 목록, KOSPI/KOSDAQ 일별매매정보, 이용 방법·약관, 데이터 구입·수신방법 페이지를 직접 확인했습니다. 출력 명세가 공개 페이지에서 동적으로 보이지 않는 한계를 별도로 기록했습니다.
- 기존 프로젝트 KRX smoke/collector 기록을 교차 확인했습니다. 과거의 인증 성공 및 별도 인증 거부 결과를 서로 다른 시점의 시도로 보존했으며, 현재 key/approval 상태는 이 작업에서 검사하지 않았습니다.
- `git diff --check`와 결정 문서·개발 기록의 내부 상대 링크 확인 — 통과. mandate SHA-256은 기존 값과 일치했습니다. v2의 미결 필드 20개는 `null`, `registered=false`, `approved=false`, `execution_allowed=false`로 유지됐습니다.
- 독립 read-only review — PASS, 중대한 지적 없음. reviewer는 외부 공식 페이지를 재조회하지 않았고, 원문 대조는 supervisor가 별도로 수행했습니다.
- 제품 코드가 바뀌지 않아 pytest, Ruff, mypy는 실행하지 않았습니다.

## 안전·운영 상태

- 공개 문서 조사만 했습니다. 계정·credential·network API/data 수집·구매·DB·broker·주문·PAPER/live는 사용하지 않았습니다.
- 수동 편집 전 development runner는 paused였고 service는 inactive, timer는 active였습니다. config를 바꾸지 않았습니다. 기존 일반 queue의 pause 상태를 유지합니다.
- 사용자 작성 루트 `HANDOFF.md`는 미수정이며 미추적 상태를 유지합니다. remote push는 하지 않았습니다.

## 증거와 재개

- 공식 문서: [서비스 목록](https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd), [이용 방법](https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO003.jsp), [이용약관](https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO002.jsp), [데이터 구입안내](https://openapi.krx.co.kr/contents/OPP/DATA/OPPDATA001.jsp), [데이터 수신방법](https://openapi.krx.co.kr/contents/OPP/DATA/OPPDATA003.jsp).
- 기존 프로젝트 자료: [2026-09-19 KRX smoke](2026-09-19-r6-krx-smoke.md), [2026-09-15 시장자료 계약 기록](2026-09-15-market-data-live-contract-fixes.md).
- 남은 차단: 최종 market/universe/source/data acceptance 및 preregistration은 사용자 승인 대상입니다. 신규 KRX access에는 적용 가능한 이용 자격, API별 승인과 credential 확인이 필요합니다. 유료 data/service는 비용 승인 전 구매하지 않습니다. `FINAL_VALIDATION`/OOS는 승인된 preregistration freeze 이후 별도로 격리한 적격·미노출 미래자료가 생길 때까지만 `PENDING/BLOCKED`입니다.
- 다음 시작: 기존 `/home/kwl/.local/share/jusik/portfolio-audit/20260919-r6-krx-smoke`의 KRX 수집 산출물을 오프라인·읽기 전용으로 프로파일링해 fixture 범위와 실제 누락/시점 필드를 정리합니다. 이 결과도 최종 성과·OOS evidence로 사용하지 않습니다.
