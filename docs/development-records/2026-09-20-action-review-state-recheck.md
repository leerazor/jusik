# Corporate-action review state recheck

- 기록 시각: 2026-09-20T02:52:00Z
- 입력: canonical SQLite `/home/kwl/.local/share/jusik/research-action-collection.db`를 SQLite read-only
  URI로 열었습니다. DB bytes와 rows는 변경하지 않았습니다.

## 현재 상태

- `action_collection_revisions`: `111`
- `action_reviews`: `4`
- comparison status: `matched=3`, `partial=1`
- partial 항목: `official-nvda-dividend-2026-06-04-20260910`; amount/currency/share basis는 matched지만
  `ex_dividend_date`가 missing입니다.
- matched 항목: NVDA 2024 dividend, TQQQ 2025 split, NVDA 2024 split.

## 판정

- 일부 공식 review가 존재한다는 사실은 확인했지만 전체 symbol/period coverage, PIT publication/effective/
  payment 경계, 권리수량과 가격 근거를 증명하지 않습니다.
- 따라서 R1-04/R1-05, action ledger 자동 적용, NAV·CAGR/MDD/Sharpe/Calmar 및 PAPER 승격은 계속
  fail-closed로 유지합니다. 추가 review는 원문·SHA·operator verification이 확보될 때만 반영합니다.
