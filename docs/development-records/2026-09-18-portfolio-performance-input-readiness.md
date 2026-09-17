# portfolio performance input readiness

- 상태: 완료
- 기록 시각: 2026-09-18T00:00:00Z
- 작업 slug: `portfolio-performance-input-readiness`
- 기준/통합: `deae4acd0bef8b3f2d64a7d445f8f3f922ec7d1f` / 이 worktree 구현 커밋
- 범위: 고정 historical time-evidence bundle에 독립 modeled accounting
  loader/ledger/CLI와 집중 테스트·계약 문서를 추가했습니다. daily sampling,
  metrics 계산/readiness 승격과 bundle 원본 변경은 제외했습니다.

## 변경과 결정

- `backend/jusik/research_portfolio_accounting_evidence.py`는 표준 라이브러리만
  사용하며 manifest/artifact SHA·size, engine/source identity, bounded regular
  reads, exact artifact set, official calendar/sidecar chronology와 warmup raw
  session을 검증합니다.
- Decimal precision 40에서 초기 KRW cash, split/fractional cash-in-lieu, 저장
  체결의 매도→매수·symbol 순서, raw open/close, as-of FX, modeled fee/slippage/
  spread를 독립 재구성합니다. 171 trades와 1,172 NAV/equity 행을 모두 소비하고
  terminal positions/marks/FX/value를 대조합니다.
- 결과는 `portfolio-modeled-accounting-evidence/v1`, approximate,
  economic not-evaluated이며 법정 비용·세금·배당·실제 FX·PIT·경제적 성과를
  주장하지 않습니다.

## 문서·계약 영향

- `docs/forward-simulation-time-evidence.md`와
  `docs/market-performance-metrics.md`에 독립 modeled accounting 범위와
  비주장 사항을 추가했습니다.
- 새 외부 API/설정/서비스 없이 읽기 전용 bundle 계약만 추가했습니다.

## 검증

- `PYTHONPATH=backend /tmp/jusik-r2-canonical-venv/bin/python -m pytest backend/tests/test_research_portfolio_accounting_evidence.py -q` — 5 passed.
- Ruff check와 format check — 통과; strict mypy source — 통과.
- 고정 bundle CLI — exit 0, 171 trades/1,172 NAV, consumed 1,172,
  max residual `0 KRW`; source self-pin `0d0be289c8643342aef4bb666e160cc2202479b92f6dfc0b2b65db9373fc434f`.
- audit report SHA-256 `34d8655ee7111e5db8e35c6e0fdef769f98bc73bac3fd32343b40665091160af`;
  runtime 1.40s, max RSS 61,892 KiB.

## 안전·운영 상태

- 실제 broker 주문, PAPER/live 실행, network, DB, service, runner, remote push와
  bundle 원본 변경은 없습니다. audit report만 별도 collision-safe 경로에 씁니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-performance-input-readiness/run-UVaER1/`
- manifest: `eec4aae8ed3c0366e9d15fa84657004d0e25429e2815b05e8a4870727718520b`
- 남은 작업·차단 조건: daily sampling policy와 metrics 연결은 별도 작업입니다.
- 다음 시작: 최종 커밋 SHA와 audit report SHA를 확인한 뒤 local main 통합 검증을
  수행합니다.
