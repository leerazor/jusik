# 2026-09-24 portfolio time-evidence artifact refresh

## 목적

기존 time-evidence bundle이 현재 `research_portfolio_engine.py` 및 accounting verifier source identity와 달라 전체 backend 회귀에서 fail-closed 되던 원인을 해소한다. 기존 audit artifact는 보존하고, 동일한 고정 입력·정책·공식 달력으로 별도 경로에 현재 엔진 bundle을 생성했다.

## 산출물

- primary bundle: `/home/kwl/.local/share/jusik/portfolio-audit/forward-simulation-time-evidence-run/run-current-engine-20260924/bundle-v2`
  - manifest SHA: `ecc65f333b8731946064d6bbd9f1f80df4524b772c28e18eb18ff2be30556d41`
  - simulation result SHA: `7d30263562fdab6edb3c27ff5c6812dd66bd0c29b9d3d8ba991bf9204229954e`
  - accounting report SHA: `0fd6cc4019756c09b9661830eb1c2821190257896a6003d9cd5c2142280b31cd`
- corrected bundle: `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-calendar-2026-krx-holiday-correction/run-current-engine-20260924/bundle-v2`
  - manifest SHA: `a13d33668def16a8c9cbd3e755b8316df62419f5f55d936ef90e45c24be69722`
  - accounting report: `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-calendar-2026-krx-holiday-correction/accounting-report-current-engine.json`
  - accounting report SHA: `d24811b504263e1c31497007d2747e7d77934d8ab7d3dd5d53b234e1bff02934`

현재 engine SHA는 `2e48b0bcedb740210a6dd58f6b15e99e2b2e1c416aacf553569ec0ea98166653`, verifier normalized source SHA는 `59261364bd1de2b5c01a3abb0d641758e72ce5864bfb4bbbf36356f4f648c90c`이다. 두 bundle 모두 NAV 1,172·trade 171이며 accounting residual은 0 KRW이다.

## 검증

- primary/corrected generation 각 1회, exit 0; 기존 bundle은 덮어쓰지 않았다.
- accounting verifier 각 1회, `verified`; metrics/accounting focused pytest `25 passed`.
- 전체 `backend/tests`: `1764 passed, 3 failed`. 남은 실패는 held-band guarded variant hash, frozen signal-forensics archive의 imported calendar hash, validation API의 동일 archive 의존성이다. 모두 기존 pinned artifact와 현재 소스의 drift를 fail-closed로 감지한 것으로 이번 bundle refresh의 회귀가 아니다.
- 실거래·PAPER/live·네트워크 수집·자동 성과 승격은 수행하지 않았다.

## 판정과 제한

이번 변경은 stale artifact identity를 현재 코드와 일치시키는 기술적 복구다. historical/approximate evidence이며 PIT·prospective·R4 경제 acceptance, readiness 승격, 후보 채택 근거가 아니다. KOFR·배당·세금·법정 비용의 완전성도 주장하지 않는다.
