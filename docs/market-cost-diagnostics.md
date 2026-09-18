# 시장 비용 독립 진단

`backend/jusik/market_cost_diagnostics.py`는 저장된 체결 행을 전략·공유 모델·포트폴리오 엔진·증권사 API 없이 `Decimal` 정밀도 28로 다시 계산합니다. 금액은 quantize하지 않습니다.

계산 계약은 다음과 같습니다.

- 매수 체결가는 `open × (1 + slippage_rate)`, 매도 체결가는 `open × (1 - slippage_rate)`입니다.
- 체결금액은 체결가와 수량의 곱이고, fee는 체결금액×`fee_rate`입니다.
- 매도에만 체결금액×`sell_tax_rate`를 적용합니다. slippage는 체결가에 포함되므로 현금 차감에 다시 더하지 않습니다.
- 고정 요율과 시가 100·수량 10의 독립 검산은 매수 `fill=100.1`, `notional=1001`, `fee=0.15015`, `tax=0`, `slippage=1`, `cash_delta=-1001.15015`, 매도 `fill=99.9`, `notional=999`, `fee=0.14985`, `tax=1.7982`, `slippage=1`, `cash_delta=997.05195`입니다. 왕복 현금 변동은 `-4.09820`, slippage 합계는 `2`이며 이를 현금에서 다시 차감하지 않습니다.
- 모든 저장 `fill_price`, `notional`, `fee`, `tax`를 독립 결과와 대조합니다. 저장값 mismatch나 구조 오류는 `invalid`와 `stored_match=false`로 닫고, 오류 없는 `partial`·취소·거절 상태만 `blocked`로 남깁니다.
- 거래 session은 입력 순서에서 감소하지 않아야 하며, equity session은 중복 없이 엄격히 증가하고 모든 fill session을 포함해야 합니다. 동일 session의 서로 다른 체결은 허용하고, session·symbol·side·quantity·가격·비용·통화·제공시각이 모두 같은 관측만 중복으로 거절합니다.
- supplied `executed_at`·`timestamp`는 timezone-aware ISO timestamp여야 하며 US `America/New_York`, KR `Asia/Seoul` 현지 날짜가 거래 session과 일치해야 합니다. 저장 pilot처럼 timestamp가 없으면 실제 시각을 추정하지 않고 unavailable로 둡니다.
- KR은 KRW, US는 USD 계약을 사용합니다. 저장 자료에 주문 ID, 부분체결·취소·거절의 완전한 이력이 없으므로 이를 추정하지 않습니다.

고정된 미국 파일럿 하나만 읽습니다. SHA-256은 `cc9150f8b77a27ffd6b001449c0475933ff744a37011801923f87cbdc5558275`이고, 252 평가 세션·106 거래가 아니면 실행을 거부합니다. 새 연구 실행, 네트워크, DB, 서비스, GPU, 주문은 사용하지 않습니다. 오프라인 회귀 inventory는 16개 이름(KR/US 매수·매도, zero, negative, missing, duplicate, rounding, holiday, timezone, partial, cancelled, rejected, chronology, stored mismatch)이며 timestamp·equity·assumptions 경계는 해당 이름 안에서 합성 자료로 검증합니다.

```bash
PYTHONPATH=backend backend/.venv/bin/python -m jusik.market_cost_diagnostics \
  --pilot /home/kwl/.local/share/jusik/portfolio-audit/20260915-market-data-live-contract-fixes/us-web-pilot-run.json \
  --output /tmp/market-cost-diagnostics.json
```

CLI 결과는 독립 산술과 저장값 대조를 기록하지만 항상 `economic_evaluation=not-evaluated`로 남깁니다. 거래소 휴장일 달력 검증, 실제 체결 시각, 법정 세목·관할·유효기간·공식 세율 근거는 unavailable이며, 해당 입력이 확보되기 전에는 R2-02 전체 체크를 완료했다고 해석하지 않습니다.

CLI는 진단 전에 `--pilot`과 `--output`이 동일 파일이거나 기존 symlink/hardlink 별칭인지 확인합니다. 별칭이면 exit 2로 거부하고 pilot 원본을 보존합니다. 별도 output 경로만 진단 JSON을 기록합니다.
