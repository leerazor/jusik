# 시장 손실 회계 독립 진단

`backend/jusik/market_loss_accounting.py`는 저장된 `MarketResearchResult` 또는
명시적인 거래 목록을 읽어 손실 회계 항목을 Decimal로 재계산합니다. 전략,
collector, simulation, replay, broker를 호출하지 않습니다. 계산은 입력의 통화와
단위를 보존하며, 저장 결과의 `cash_krw`는 관측된 KRW 현금이고 native 현금과 FX
항목은 별도로 표시합니다.

## 계산 계약

- FIFO 원시 가격손익은 매수 시가와 매도 시가로 계산합니다. 체결가 손익은
  매수·매도 체결가를 사용합니다. 원시 손익에서 slippage를 한 번만 차감하며
  체결가 손익에는 다시 차감하지 않습니다.
- 매수 slippage는 `수량 × (체결가 - 시가)`, 매도 slippage는
  `수량 × (시가 - 체결가)`입니다. 양수는 비용입니다.
- 수수료와 세금은 저장된 거래 값의 합입니다. 수수료·세금 정책의 적정성을
  판단하지 않습니다.
- 매수·매도 체결의 fee와 tax, 완전한 배당 근거가 제공된 경우의 배당 현금흐름을
  현금 잔액에 반영합니다. 계산된 현금 잔액은 초기 현금, 완전한 체결 이력,
  배당 mapping, 완전한 배당 evidence가 모두 있어야 `available`입니다. 어느
  조건이 빠졌는지와 재개에 필요한 입력을 각각 기록합니다. 배당 근거가 없거나
  불완전하면 현금 잔액을 `unavailable`로 유지하고 부분 현금흐름을 진실값으로
  표시하지 않습니다.
- FX는 `Δ(NF)=F0ΔN+N0ΔF+ΔNΔF`로 분해하고 교차항을 FX 항목에 귀속합니다.
- 명시적 거래 입력에 FX 관측이 없으면 FX의 `value`와 `diagnostic_value`를 모두
  `null`로 두며, 관측된 FX가 저장 결과에 있는 경우의 분해값은 그대로 보존합니다.
- 배당 자료가 없으면 `unavailable`이며 실제 0으로 추정하지 않습니다. 완전한
  배당 evidence를 명시한 경우에만 0도 입력할 수 있습니다.
- 명시적 거래 계산은 KRW와 USD를 하나의 합계로 섞지 않으며, side·currency·양수
  수량/가격·비음수 비용·`YYYY-MM-DD` 체결일을 검증합니다. 저장 결과는 equity
  날짜가 유일하고 증가하는지, 모든 fill session이 equity에 존재하는지 확인합니다.
- 공개 계산은 호출자의 Decimal precision·rounding·trap 설정과 독립적인
  `Context(prec=50, ROUND_HALF_EVEN)`에서 수행합니다. 독립 달력 근거가 없으므로
  equity 날짜 사이의 휴장일·간격을 결측으로 판정하지 않습니다.
- 직렬화된 각 회계 component에는 `currency`와 `unit`이 포함됩니다. 명시적 US
  거래의 PnL·fee·tax·slippage·배당은 native `USD`/`currency`, 저장 결과의
  `fx`와 관측 `cash_balance`는 `KRW`/`currency`입니다. 빈 명시적 입력처럼 통화를
  증명할 수 없는 경우 `currency`는 `null`로 남습니다. FX 분해는 native 통화,
  local `KRW`, rate unit `KRW_per_USD`를 구조화해 보존합니다.

## 증거 등급

수작업 입력에서 `complete_history=True`, 초기 포지션, 종목별 최종 mark와
완전한 배당 evidence를 함께 제공하면 FIFO 검산값을 사용할 수 있습니다.
저장 결과는 초기 포지션·완전한 체결 이력·기업행사 수량 보존을 증명하지
않으므로 FIFO realized/unrealized와 순손익은 `unavailable`로 남고 진단용
값만 별도 보존합니다. 저장된 현금, 수수료, 세금, slippage, 첫·마지막 FX
관측은 각각의 evidence와 함께 기록됩니다. 저장 입력에 주문 상태나 별도 timestamp
metadata가 있어도 이를 체결로 간주하지 않으며, 실제 주문 생명주기와 시간대 변환은
이 진단의 범위가 아닙니다.

CLI는 이미 저장된 파일 하나의 SHA-256을 확인한 뒤 진단합니다.

```bash
PYTHONPATH=backend backend/.venv/bin/python -m jusik.market_loss_accounting \
  --pilot /path/to/us-web-pilot-run.json \
  --expected-sha256 <sha256> \
  --output /path/to/loss-accounting.json
```

이는 기존 approximate pilot의 기술 진단이며 경제 평가나 R2-01 전체 완료를
의미하지 않습니다. 필수 배당·초기 포지션·기업행사 자료가 없는 결과 상태는
`blocked`로 남깁니다.
