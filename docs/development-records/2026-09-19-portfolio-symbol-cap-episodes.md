# Symbol cap 초과 관측 episode 재구성

- 상태: 완료
- 작업 slug: `portfolio-symbol-cap-episodes-0e01`
- 기준/통합: `b27126b40cfdadf9b52cc1bd3406bdefc684f7b8` / `2b88c92`
- 범위: 고정 volatility15 cadence/cost archive의 32개 저장 cell과 351개 초과 관측을 종목별 13개 episode로 재구성했습니다. 저장 observer만 읽었으며 전략·시뮬레이션·수집·PAPER/live·주문 경로는 호출하지 않았습니다.

## 변경과 결정

- `research_portfolio_symbol_cap_episodes.py`는 current canonical mandate SHA `ceca2ee1…`, source report/manifest/results SHA와 manifest 72개 항목을 고정합니다.
- 원본 배열 순서와 동일 timestamp 반복을 보존하고, 저장 행의 연속성만 episode 경계로 사용합니다. 거래 인과나 회복을 추정하지 않습니다.
- `EXPECTED_EPISODES=13`을 fail-closed 계약으로 추가하고 fixed archive end-to-end 회귀를 고정했습니다.

## 검증

- 후보 pytest 6개, Ruff check/format, strict mypy — 통과.
- fixed archive 분석 2회와 main 재실행 결과: `32 cells / 351 observations / 13 episodes`, output SHA `34a9eeb0c8151067a8bb745f3be4f7f38f26c6f553b13e774417db8ddcf34320`.
- 독립 review: PASS. 초기 episode-count 고정 누락은 수정 후 재검토 통과.
- main 관련 테스트·lint·typecheck는 후보와 동일 범위로 재실행했으며 모두 통과했습니다.

## 안전·운영 상태

- 실제 주문, market-data network, simulation, GPU, PAPER/live, DB/service/runner 설정, remote push — 0회.
- 결과는 후향 저장 관측 진단이며 PIT·배당·receipt 완전성을 증명하지 않습니다.

## 증거와 다음 시작

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-symbol-cap-episodes-v1-20260919`.
- 이전 mandate pin mismatch audit은 `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-symbol-cap-breach-episodes-v1-0e018f57a6b14e3587dc5dfca65985d8`에 보존했습니다.
- 다음 시작: 외부 receipt 자료가 없으면 경제 acceptance를 승격하지 않습니다. 다음 세션은 runner·mandate SHA와 남은 worktree를 다시 확인합니다.
