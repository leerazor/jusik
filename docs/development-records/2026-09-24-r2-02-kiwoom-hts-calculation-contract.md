# 2026-09-24 R2-02 Kiwoom HTS calculation contract

## 공식 화면 설명

Kiwoom 공식 HTS 도움말의 [해외주식 당일 실현손익상세(2163)](https://download.kiwoom.com/htsg_help/kiwoom_fx/2163.html)와 [당일매매정리(2162)](https://download.kiwoom.com/htsg_help/kiwoom_fx/2162.html)를 확인했다.

- 체결일 기준으로 매수/매도 금액, 수수료, 세금, 실현손익을 계좌별 조회한다.
- HTS 수수료는 매도 체결단가×수량×`0.25%`로 일괄 표시한다.
- ECN fee는 매수·매도 각각 주당 `$0.003`으로 표시한다.
- SEC fee는 매도금액 기반이며 화면에는 `$0.0000218`로 표시되지만 “비정기적으로 변경될 수 있음”이라고 명시한다.
- 원화 표시에서는 전영업일 최종환율을 사용한다.
- 실현손익은 체결가 차이에서 수수료·세금을 차감한 값이다.

별도 Kiwoom 실현손익 화면(2153)은 최저수수료 `$7`, SEC 최소 `$0.01`을 설명하고 다른 SEC 식을 표시한다. 따라서 화면 간 SEC 값·최소금액이 동일하지 않다.

## 판정

이 자료로 R2-02 evaluator의 필수 입력 필드(매수/매도 체결금액·수량, broker fee, ECN fee, SEC fee rate/minimum, FX reference date/rate, account/medium, fill/settlement timestamp)를 확정할 수 있다. 그러나 SEC rate와 최소금액의 versioned contract가 화면마다 충돌하고 실제 계좌 receipt가 없으므로 수치·유효기간을 모델에 자동 반영하지 않는다. R2-02 checkbox와 경제 acceptance는 미승격한다.

