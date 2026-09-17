# forward simulation time evidence run

- 상태: 완료
- 기록 시각: 2026-09-18T00:00:00Z
- 작업 slug: `forward-simulation-time-evidence-run`
- 기준/통합: `818120c92aea5aa929a77c1329a96c827d89c1c7` / 통합 전
- 범위: 고정 historical input과 tracked official calendar로 새 offline time-evidence bundle 하나를 생성·검증했습니다. 기존 canonical run과 readiness는 변경하지 않았습니다.

## 변경과 결정

- 문서에 historical bundle 예시와 approximate/time-order 한계를 추가했습니다.
- 고정 후보는 `portfolio_inverse_volatility_fx_vix_v1`, 정책은 `low_turnover_combined`, 기간은 문서화된 continuous `2024-04-24..2026-09-08`, execution-time policy는 `official`입니다.
- 입력·요청·설정은 audit root에 0600으로 보존했습니다. source manifest SHA-256은 `1a2934466efa12c09d08e7792b1a5e4b7c0c880d2aaabab9b25919bd0ec5c825`, input/config/request SHA-256은 각각 `f295946b3b5d9ba5fd53380afe649b6bb99fdaf7c327d81b8c69fc456df5c10c`, `b3c7d2388ece2e79713c3ac3b2b7edfbc6ff5a7585b860015433f8aa3196dc3e`, `d630fec551a31875b47612594d5d58efa5b193a849147a6dcdbcd15626d320d4`입니다.

## 문서·계약 영향

- 사용자 계약 문서: `docs/forward-simulation-time-evidence.md`에 재현 가능한 historical 예시와 제한을 추가했습니다.
- 운영·API·설정·데이터 계약: 변경 없음. runner/network/KOFR/PAPER/live/order/DB/service/config/remote를 사용하지 않았습니다.

## 검증

- 선행 preflight manifest SHA-256 `7a2ddb3488d1bc08d155411122e8727c84a67db9b1150a3df7ef504acf207af4`를 확인하고 current code SHA와 calendar SHA를 재검증했습니다. 재실행 preflight는 official, simulation 0회, 11,321 bars, 20,303 events, 0.742초, max RSS 105,548 KiB로 통과했습니다.
- generation은 `--allow-new-simulation`으로 정확히 한 번 실행해 exit 0, wall 2.75초, max RSS 132,416 KiB였습니다. bundle manifest SHA-256은 `eec4aae8ed3c0366e9d15fa84657004d0e25429e2815b05e8a4870727718520b`입니다.
- 지정 manifest SHA를 사용한 verify는 simulation 없이 정확히 한 번 실행해 exit 0, wall 1.21초, max RSS 132,552 KiB였습니다.
- 독립 대조: artifact set/hash/size, initial-capital engine-event anchor, UTC NAV/session causality, official policy와 engine SHA, source/config/calendar identity를 통과했습니다. bundle은 event 16,824개(rebalance 124/open 8,350/close 8,350), NAV 1,172개, trade 171개입니다.
- `PYTHONPATH=. backend/.venv/bin/python -m pytest backend/tests/test_research_portfolio_time_evidence.py -q` — 20 passed.
- `backend/.venv/bin/ruff check backend/jusik/research_portfolio_time_evidence.py backend/jusik/research_portfolio_time_models.py backend/tests/test_research_portfolio_time_evidence.py` — 통과.
- `backend/.venv/bin/ruff format --check backend/jusik/research_portfolio_time_evidence.py backend/jusik/research_portfolio_time_models.py backend/tests/test_research_portfolio_time_evidence.py` — 3 files already formatted.
- `PYTHONPATH=. backend/.venv/bin/python -m mypy --strict backend/jusik/research_portfolio_time_evidence.py backend/jusik/research_portfolio_time_models.py` — Success, no issues found in 2 source files.
- `git diff --check` — 통과.

## 안전·운영 상태

- 결과는 historical/approximate technical time evidence이며 prospective/PIT/canonical/R4 economic evidence가 아닙니다. 성과 계산·readiness 연결·자동 승격을 하지 않았습니다.
- 실제 broker 주문, PAPER/live 실행, network, KOFR, runner, 운영 DB·서비스·config·remote 변경은 없습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/forward-simulation-time-evidence-run/run-gr68c4`; bundle manifest SHA-256 `eec4aae8ed3c0366e9d15fa84657004d0e25429e2815b05e8a4870727718520b`; 독립 검증 SHA는 audit `independent-validation.json`에 보존했습니다.
- 남은 작업·차단 조건: 이 실행 범위에는 없음. 자료의 historical/PIT 한계와 economic evidence·readiness 미연결은 유지합니다.
- 다음 시작: 별도 승인과 별도 source evidence 없이는 이 bundle을 prospective 또는 canonical 근거로 재해석하지 않습니다.
