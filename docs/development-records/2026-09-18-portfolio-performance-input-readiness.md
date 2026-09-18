# portfolio performance input readiness

- 상태: 완료
- 기록 시각: 2026-09-18T00:00:00Z
- 작업 slug: `portfolio-performance-input-readiness`
- 기준/통합: `deae4acd0bef8b3f2d64a7d445f8f3f922ec7d1f` / `901ac636f93f37ff2b3ab2c6c03ae0bf640572f1`
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
- 디렉터리는 `os.scandir`로 여섯 항목까지만 점진적으로 수집하고, engine source도
  descriptor-pinned bounded reader로 symlink·non-regular·oversize·replacement를
  거부합니다. 절대 audit bundle 없이 로더/순수 원장 경계 테스트를 추가했습니다.

## 문서·계약 영향

- `docs/forward-simulation-time-evidence.md`와
  `docs/market-performance-metrics.md`에 독립 modeled accounting 범위와
  비주장 사항을 추가했습니다.
- 새 외부 API/설정/서비스 없이 읽기 전용 bundle 계약만 추가했습니다.

## 검증

- `PYTHONPATH=backend /tmp/jusik-r2-canonical-venv/bin/python -m pytest backend/tests/test_research_portfolio_accounting_evidence.py -q` — 11 passed.
- Ruff check와 format check — 통과; strict mypy source — 통과.
- 고정 bundle CLI — exit 0, 171 trades/1,172 NAV, consumed 1,172,
  max residual `0 KRW`; source self-pin `35efe5f691f7161efd215616781832e71240d78faa8ca66a1a7727a6d49a7514`.
- review audit report SHA-256 `a90fde0e8a2f9e0ddaa36630cc91617f1da46c9346832ce9156a85a8588527ed`;
  runtime 1.40s, max RSS 61,808 KiB.
- 최종 review에서 실제 pathname 교체 race, same-time close-before-NAV 및 terminal
  quantity/mark/value tamper synthetic 경계를 추가 검증했습니다. 13개 테스트가
  통과했고 source self-pin은 `8a5444639ef754f6f88223f3f84623a403db7cf35dab570b78aee0e707474c8a`입니다.
- 최종 audit report SHA-256 `7390e79432319f834ff92f029833b9afd74839944909c711a60fee888037bad1`;
  runtime 1.48s, max RSS 61,980 KiB.
- local `main`에서 accounting/time-evidence/metrics pytest 53개, Ruff check/format,
  strict mypy, fixed bundle CLI와 `git diff --check`가 통과했습니다. CLI 출력 SHA는
  최종 audit report SHA와 같습니다.
- Terra 독립 review — P1/P2 없음, PASS. resource/path race, same-time close ordering,
  terminal tamper와 원장 독립성을 재검토했습니다.

## 안전·운영 상태

- 실제 broker 주문, PAPER/live 실행, network, DB, service, runner, remote push와
  bundle 원본 변경은 없습니다. audit report만 별도 collision-safe 경로에 씁니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-performance-input-readiness/review3-YE6rGl/`
- manifest: `eec4aae8ed3c0366e9d15fa84657004d0e25429e2815b05e8a4870727718520b`
- 남은 작업·차단 조건: daily sampling policy와 metrics 연결은 별도 작업입니다.
- 다음 시작: 전체 intraday NAV는 MDD용으로 보존하고 daily-return sampling의
  평가 timezone·시장 휴장 의미·단일 표본 선택을 사용자 승인 후 versioned policy로 고정합니다.
