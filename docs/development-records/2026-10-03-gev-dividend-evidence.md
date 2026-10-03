# GEV 지급일 근거와 배당금 정밀도 원인 확인

- 상태: 자료 보완·원인 확인 완료; 총수익 자료 적격은 미완료.
- 작업 slug: `gev-dividend-evidence-20261003`; 기준 main `78b10ee`. application 코드 변경 없음.
- 시작 확인: 승인 목록 revision 1/16종목 유지, 개발 runner paused, 서비스/timer 및 과거 optimizer inactive. 웹 active. 진행 중인 개발 writer 없음. 사용자 루트 `HANDOFF.md` 보존.

## 공식 근거와 검증

GE Vernova의 [2026년 2분기 공지](https://www.gevernova.com/news/press-releases/ge-vernova-declares-second-quarter-2026-dividend)와 [3분기 공지](https://www.gevernova.com/news/press-releases/ge-vernova-declares-third-quarter-2026-dividend) 원문을 각각 한 번 확보했다. 주당 USD 0.50, 기준일/지급일은 각각 2026-03-17/04-14와 2026-06-16/07-14다. 공지는 배당락일을 명시하지 않는다. 기준일을 배당락일로 추정하거나 주당 기준 일치를 선언하지 않았다.

- 현재 source revision 2건의 ID/content SHA를 고정해 기존 importer의 `partial` 사실을 생성했다. 원문 바이트와 SHA, 수집 시각, 문단 locator를 보존했다.
- DB 사본 import 2건, 재import 0건/idempotent 2건. 기존 coverage에서 두 사건 모두 `excluded/latest_review_partial`인 것을 검증했다.
- 실제 연구 검토 DB에 append-only import 2건 후 재조회했다. 적격 13/111, 제외 98은 유지된다. 기존 원본·과거 검토를 수정하지 않았고 현금 원장 자동 적용은 없다.
- 코드·UI·배포 변경 없음. 실제 importer 경로와 coverage 재조회로 검증했으며 application suite는 코드 변경이 없어 반복하지 않았다.

## 다음 단계: 정밀도 차이 원인 규명

[Vertiv 공식 2024년 4분기 공지](https://investors.vertiv.com/news/news-details/2024/Vertiv-Hosts-Investor-Event-and-Announces-Quarterly-Dividend/default.aspx)는 USD 0.0375, 기준일 2024-12-03, 지급일 2024-12-19를 명시한다. 웹 본문을 확인했지만 원문 보존용 다운로드는 403이라 검토 import를 만들지 않았다. 같은 URL 재요청 금지; 원문 확보 가능한 공식 대체 자료가 재개 조건이다.

기존 캐시의 VRT 1건과 앞서 확인한 SOXL 4건을 `attempt_id → raw body SHA → provider event → stored revision` 순서로 대조했다. **다섯 건 모두 공급자 원문과 저장 금액이 같았다.** VRT `0.038` 대 공식 `0.0375`, SOXL `0.093/0.09290`, `0.01/0.01008`, `0.068/0.06799`, `0.065/0.06477` 차이는 정규화 전부터 존재한다. 공식 값 대비 차이는 확인했지만 공급자의 내부 반올림 방식은 추정하지 않는다. 현재 `_positive_decimal`과 `format(amount, "f")`에 원인을 돌려 수정할 근거가 없다.

다음 구현 후보는 기존 strict 검토를 완화하는 것이 아니라, 원본 revision을 보존하면서 공식 현금 금액과 날짜·주당 기준을 별도로 검증하는 원천 우선순위 계약이다. 이를 아직 구현·승인된 적격 경로로 취급하지 않는다. source 금액 허용 오차 확대, 기존 review의 matched 강제 변경, 원문 덮어쓰기는 하지 않는다.

## 증거와 재개

- audit `/home/kwl/.local/share/jusik/portfolio-audit/20261003-gev-dividend-evidence/`; 원문 2개, sources, exact revision, review manifest, 격리/실제 결과, `precision-trace.json`.
- `manifest.json` SHA-256 `8a5d21010fd90f8d21f408221d216c1e3f7c870a41d9fcebbc008eb939827515`.
- 현재 확보한 후향 근거이며 PIT 관측시각·미사용 OOS·비용 차감 수익성 검증으로 취급하지 않는다. 실제 주문·PAPER/live·Pages·원격 push 없음.
- workflow 판단: 도움 됨 — 기존 importer와 원문 캐시를 재사용해 적격 오인과 불필요한 parser 수정을 피했다.
- 근거: 격리·idempotence·실제 재조회와 5건 원문 해시 대조. 비용 절감은 미측정.
- 다음 조정: 유지 — 반복 실패 대신 공식 원천 우선순위·날짜 근거 계약을 다음 bounded 작업으로 진행.
