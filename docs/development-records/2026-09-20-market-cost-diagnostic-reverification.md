# Market-cost diagnostic 재검증

- 기록 시각: 2026-09-20T02:50:00Z
- 입력: frozen US pilot `us-web-pilot-run.json`, input SHA-256
  `cc9150f8b77a27ffd6b001449c0475933ff744a37011801923f87cbdc5558275`
- 명령:
  `PYTHONPATH=backend backend/.venv/bin/python -m jusik.market_cost_diagnostics --pilot <frozen-run> --output /tmp/jusik-market-cost-diagnostics.json`

## 결과

- 독립 Decimal 진단: `diagnostic_status=success`, `stored_match=true`, 106 trades, 252 sessions.
- 저장값 mismatch: 0건.
- 독립 집계: buy fee `27.221555102124220260047625`, sell fee
  `25.720489058519236602343005`, sell tax `308.64586870223083922811606`, slippage
  `352.9373069013059138308` (USD).
- 결과의 `status=blocked`, `economic_evaluation=not-evaluated`는 유지됐습니다.

## 제한

- 거래소 휴장일 검증, 실제 체결 timestamp/order·partial-fill identity, 법정 세목·관할·유효기간·공식
  세율은 unavailable입니다.
- 따라서 이 재검증은 산술·저장값 일치만 증명하며 R2-01/02 완료, 순수익·CAGR/MDD·Sharpe/Calmar,
  PAPER 승격을 주장하지 않습니다. 원본 artifact와 코드·요율은 변경하지 않았습니다.
