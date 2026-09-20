# US market collection recheck

- 기록 시각: 2026-09-20T03:18:35Z
- 목적: 기존 frozen US cache를 덮어쓰지 않고, 현재 `.env` 자격증명으로 bounded 1년 approximate
  collection과 isolated pilot readiness를 재확인했습니다.

## 실행과 artifact

- source cache 복사본: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-us-market-collection-recheck/cache`
- collection: `--market US --start 2025-09-11 --end 2026-09-11 --sample-size 80
  --request-budget 405 --resume`
- prepared dataset: universe `17,310`, bars `17,263`, FX `272`, events `104`
- request-excluded symbols: `17`
- prepared SHA-256: `2bb7ff36a95714b4c419f51ac9d09252120f044e7ab4f859e37417b2f23da9eb`
- cache manifest SHA-256: `8fb89945ababeb39eea017963582e64dabc1b37d72a4a52710cd8530bb1e9006`

## readiness 판정

- isolated approximate pilot output SHA-256:
  `449f7869991fd9034e6c1b13e22c81f7bef94c2b87a8896d263b87e18b22841a`
- `status=insufficient`, `completeness=incomplete`, `readiness.ready=false`
- `credentials`, `calendar`, `membership`, `bars`, `fx`는 준비 상태로 읽혔지만 `actions`는
  `partial`입니다.
- 불확실 기업행사 심볼 35개는 발생시각·관측시각이 확인되지 않아 거래·equity·metrics를 만들지
  않았습니다. 따라서 이번 실행은 수집 성공이지 성과 계산 성공이 아닙니다.

## 결정

기존 NVDA/TQQQ review를 다른 심볼에 전이하거나 날짜·관측시각을 추정하지 않았습니다. R4-01~05,
경제 지표, PAPER/live 승격은 기업행사 원문·PIT 관측시각과 coverage가 보강될 때까지 보류합니다.
실제 주문, runner 재개, frozen artifact 변경, remote push, Windows 종료는 수행하지 않았습니다.
