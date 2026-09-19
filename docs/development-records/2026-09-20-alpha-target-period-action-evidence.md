# Alpha Vantage 목표 기간 기업행사 근거 재대조

- 기록 시각: 2026-09-20T00:30:00Z
- 범위: 기존에 보존한 Alpha Vantage raw 응답 20개를 재호출 없이 읽어
  `2025-09-11`~`2026-09-11` 목표 기간의 배당·분할 관측을 산출했습니다.
- 대상: 기존 public-evidence batch의 10개 미국 심볼과 dividend/split 응답

## 결과

- raw 응답: 20개
- 목표 기간에 값이 있는 응답: 8개
- 목표 기간 관측: 27개
- 관측 심볼: `GEV`, `GOOGL`, `MSFT`, `NVDA`, `SOXL`, `TQQQ`, `VRT`
- `TQQQ`에서 split 1건, 나머지는 배당 관측으로 확인됐습니다.

## 증거·제한

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-alpha-target-period-evidence/`
  (`target-period-summary.json`, `request.json`)
- 각 raw SHA와 날짜별 결과를 summary에 고정했으며 비밀값은 저장하지 않았습니다.
- 이는 provider raw source evidence일 뿐 정확한 PIT publication instant, provider/issuer
  완전성, operator-verified effective/payment/rights 검토를 증명하지 않습니다.
- 따라서 R1-04/R1-05 checkbox, action review manifest, 자동 ledger, NAV·CAGR/MDD/
  Sharpe/Calmar 계산과 PAPER/live 승격에는 사용하지 않았습니다.

## 운영 상태

- 기존 raw 재사용만 수행했고 신규 API 호출·주문·PAPER/live·원격 push·Windows 종료는
  없습니다.
