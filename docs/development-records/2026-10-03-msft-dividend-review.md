# MSFT 공식 배당 12건 보완

- 상태: 공식 근거 연결 완료; 전체 순수익 검증 미완료.
- 작업 slug: `msft-dividend-review-20261003`
- 기준: `8cac68b`; application 코드 변경 없음.
- 사용자 승인 범위: 등록 16종목 연구를 단계별로 계속, 자동매매·GitHub Pages 제외.

## 근거와 처리

Microsoft 공식 [배당 및 주식 이력](https://www.microsoft.com/en-us/investor/dividends-and-stock-history)에서 연결한 [배당 이력 XLSX](https://cdn-dynmedia-1.microsoft.com/is/content/microsoftcorp/Microsofts-Dividend-History)의 Quarterly Dividend 시트 3~14행을 읽었다. 2023-11-15~2026-08-20의 12건에 금액, 배당락일, 기준일, 지급일이 모두 있다. Amount는 달러 표시 형식이고 이 기간은 공식 주식 분할 이력의 마지막 분할(2003) 이후라 같은 주당 기준이다. 원문 19,932 bytes, SHA-256 `3c6b9f1aac489b672a2a69514182edbb2757a13059d2c5549783de340c4025e0`.

기존 최신 MSFT 공급자 revision 12건을 exact ID/content SHA로 고정하고 날짜·금액·통화·주당 기준을 기존 compare_review로 대조했다. 모두 matched다. DB 사본에서 import 12건 및 동일 manifest 재import 0건/idempotent 12건을 확인한 뒤 실제 연구 action-review DB에 append-only로 반영했다. 원문·추출 사실·가져오기 manifest·검증 결과는 아래 audit에 보존했다.

## 검증·한계

- 기존 load_review_coverage 재조회: MSFT 12건 eligible. 전체 관측 111건 중 eligible 13, excluded 98. 현재 원문과 검토 기록 기준이며 전체 사건 수집 완전성은 별도다.
- 이 자료는 오늘 확보한 후향 근거다. 발표 날짜를 당시 시스템 관측 시각으로 소급하지 않으며 PIT 검증이나 독립 OOS로 취급하지 않는다.
- 세금·FX·수수료·재투자 또는 전체 NAV 검증 완료를 뜻하지 않는다.
- 자동 현금 원장 적용 false, PAPER/live 승격과 실제 주문 없음. 기존 normalized price snapshot과 과거 결과 수정 없음.
- application 코드 검사 미실행: 코드 변경 없이 기존 importer/검증 모듈의 실제 입력 경로를 검증했다.

## 기록과 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20261003-msft-dividend-review/`; `review-manifest.json`, `validation.json`, `production-verification.json`, `manifest.json`.
- 다음: 남은 종목의 공식 지급일·배당락일 근거를 확보하고, 불완전한 기록은 그대로 보류한다. 가격만 있는 종목을 배당 없는 것으로 간주하지 않는다.
- workflow 판단: 도움 됨 — 기존 importer와 공식 통합 파일 하나를 재사용했다.
- 근거: 12건 대조·격리 import·idempotence·운영 재조회 통과. 비용 절감 미측정.
- 다음 조정: 유지 — 완전한 공식 표가 있는 자료를 먼저 보완한다.

## 다음 자료 조사: SOXL 정밀도 차이

Direxion 공식 상품 페이지의 SOXL 분배 표를 웹으로 확인했다. 최근 4건은 공급자 값/공식 값이 각각 2026-09-22 `0.093/0.09290`, 2025-09-23 `0.01/0.01008`, 2025-06-24 `0.068/0.06799`, 2025-03-25 `0.065/0.06477`이다. 공식 표 URL은 https://www.direxion.com/product/daily-semiconductor-bull-bear-3x-etfs 이다. 현재 strict 금액 비교의 통과 조건을 완화하거나 원본 revision을 덮어쓰지 않았다. 원문 보존용 직접 다운로드는 HTTP 403으로 실패했으므로 검토 manifest/import를 만들지 않았다. 다음에는 공식 연도별 분배 공지 등 다른 원문 확보 경로를 확인하고, 공급자 반올림과 공식 현금 금액을 구분하는 입력 계약을 검토한다. 동일 차단 URL을 재시도하지 않는다.
