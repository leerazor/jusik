# 시장 비용 독립 진단

`backend/jusik/market_cost_diagnostics.py`는 저장된 체결 행을 전략·공유 모델·포트폴리오 엔진·증권사 API 없이 `Decimal` 정밀도 28로 다시 계산합니다. 금액은 quantize하지 않습니다.

계산 계약은 다음과 같습니다.

- 매수 체결가는 `open × (1 + slippage_rate)`, 매도 체결가는 `open × (1 - slippage_rate)`입니다.
- 체결금액은 체결가와 수량의 곱이고, fee는 체결금액×`fee_rate`입니다.
- 매도에만 체결금액×`sell_tax_rate`를 적용합니다. slippage는 체결가에 포함되므로 현금 차감에 다시 더하지 않습니다.
- 모든 저장 `fill_price`, `notional`, `fee`, `tax`를 독립 결과와 대조합니다. 입력이 누락되거나 chronology·통화·중복·상태가 잘못되면 fail-closed로 진단합니다.
- KR은 KRW, US는 USD 계약을 사용합니다. 저장 자료에 실제 체결 timestamp, 주문 ID, 부분체결·취소·거절의 이력이 없으므로 이를 추정하지 않습니다.

고정된 미국 파일럿 하나만 읽습니다. SHA-256은 `cc9150f8b77a27ffd6b001449c0475933ff744a37011801923f87cbdc5558275`이고, 252 평가 세션·106 거래가 아니면 실행을 거부합니다. 새 연구 실행, 네트워크, DB, 서비스, GPU, 주문은 사용하지 않습니다.

```bash
PYTHONPATH=backend backend/.venv/bin/python -m jusik.market_cost_diagnostics \
  --pilot /home/kwl/.local/share/jusik/portfolio-audit/20260915-market-data-live-contract-fixes/us-web-pilot-run.json \
  --output /tmp/market-cost-diagnostics.json
```

CLI 결과는 독립 산술과 저장값 대조를 기록하지만 항상 `economic_evaluation=not-evaluated`로 남깁니다. 거래소 휴장일 달력 검증, 실제 체결 시각, 법정 세목·관할·유효기간·공식 세율 근거는 unavailable이며, 해당 입력이 확보되기 전에는 R2-02 전체 체크를 완료했다고 해석하지 않습니다.
