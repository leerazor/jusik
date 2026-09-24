# 2026-09-24 R2-01 accounting boundary fixes

## 발견

독립 read-only review에서 세 가지 경계 결함을 재현했다.

- 보유 이력에 없는 심볼의 배당 mapping을 합산해 complete dividend/cash/net PnL로 만들 수 있었다.
- `initial_cash`가 없어서 `cash_balance=unavailable`이어도 report `status=complete`가 될 수 있었다.
- 금융 입력의 `float`를 `Decimal(str(value))`로 받아 이미 반올림된 binary value를 허용했다.

## 수정

`market_loss_accounting.py`에서 unheld dividend symbol을 명시적으로 거절하고, cash availability를 report complete gate에 포함했으며, float 입력을 Decimal 변환 전에 거절했다. 각 결함에 회귀 테스트를 추가했다.

## 검증

- `backend/tests/test_market_loss_accounting.py`: 39 passed
- Ruff check/format: passed
- strict mypy: passed
- 네트워크·engine·replay·PAPER/live·주문·운영 원장 변경 없음

## 제한

complete fills, opening positions, corporate-action/dividend evidence, FX, benchmark와 미래 관찰 자료가 없으므로 R2-01 checkbox와 경제 acceptance는 미승격한다.
