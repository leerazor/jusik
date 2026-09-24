# 2026-09-24 R2-02 US fee source conflict

## 확인

Kiwoom 공식 자료를 교차 확인했으나 미국 SEC 비용 표기가 서로 달랐다.

- [Kiwoom RIA 안내 PDF](https://download.kiwoom.com/deploy/AG003/pdf/AG003_30.pdf): 미국주식 기본수수료 온라인 0.25%, 오프라인 0.50%를 안내한다.
- [Kiwoom MY랭킹 공식 페이지](https://rank.kiwoom.com/r/heroad/myleague/VLeagueInfoAllView?menuId=HRD0025): 미국 매도 SEC 제비용 0.00278%를 표시한다.
- [Kiwoom 2026 이벤트 공식 페이지](https://www.kiwoom.com/e/wm/event/evtUserEC250053View): 이벤트 시작일 기준 SEC FEE 0%이며 수시 변동 가능하다고 표시한다.

## 판정

온라인 broker fee `0.25%`는 반복 확인되지만, SEC 비용은 공식 페이지 간 값과 적용 시점이 충돌한다. 이벤트/광고 표기를 일반 위탁계좌 계약으로 확정할 수 없고, 사용자의 실제 계좌·매체·상품·거래일별 fee schedule과 체결/결제 receipt도 없다. 따라서 SEC 비용을 임의로 0·0.00278% 또는 다른 값으로 모델에 주입하지 않으며, R2-02 checkbox·경제 acceptance는 미승격한다.

재개 조건은 계좌 유형과 거래 매체를 특정한 Kiwoom 공식 fee schedule, 유효기간, SEC fee 적용 대상/최소금액, 실제 체결·결제 timestamp를 하나의 versioned source contract로 확보하는 것이다.

