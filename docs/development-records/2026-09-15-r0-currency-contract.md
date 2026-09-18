# R0-04 통화·독립 simulated account 계약

- 상태: 완료
- 기록 시각: 2026-09-15T03:40:46Z
- 작업 slug: `r0-currency-contract`
- 기준/통합: `967df2f664dfcc5b3ad97f36d2fa1ec8ff3a008a` / 없음
- 범위: 결과에 optional market-specific account와 KRW/USD 단위 metadata를 추가했습니다. 기존 Decimal 계산, fee·tax·FX, snapshot/data/policy/pool hash, strategy·gate는 보존했습니다.

## 변경과 결정

- `MarketResearchAccountMetadata`는 account scope, KRW reporting currency, market native currency, request 초기 자본, KRW-per-USD quote, 초기 자본 환전 방향만 포함하며 account identifier를 저장하지 않습니다.
- `MarketResearchService`가 계산된 result metrics와 request에서 metadata를 만들어 결과에만 주입합니다. KR은 native KRW·FX identity `1`, US는 native USD·초기 KRW-per-USD quote·`initial_krw_to_usd`를 사용하며 quote가 없는 불충분 결과는 `null`입니다.
- Python model validator와 frontend Zod schema가 market/native/reporting/conversion/initial cash의 모순을 거부합니다. 기존 result의 account 누락은 `None`/unknown으로 파싱됩니다.
- frontend는 binary float 없이 BigInt canonical 비교를 사용해 trailing zero·지수 표기의 동등 Decimal을 허용하고, 0·음수·비수치·NaN·Infinity와 정밀도 차이를 거부합니다.
- 계약 문서에 trade native currency와 equity native/reporting 금액의 의미, KR FX identity, 독립 simulated scope를 기록했습니다.

## 문서·계약 영향

- 사용자 문서: `docs/market-research-contract.md`에 통화·account metadata 계약을 추가했습니다.
- 운영 문서: 해당 없음. account identifier·broker 연동·운영 설정은 변경하지 않았습니다.
- API·설정·데이터 계약: `MarketResearchResult.account`를 optional nullable additive field로 추가했습니다. 기존 hash payload·gate·금융 계산은 변경하지 않았습니다.

## 검증

- `cd backend && PYTHONPATH=. .venv/bin/python -m pytest tests/test_market_research.py tests/test_market_history_approximate.py` — 통과; 48개 테스트, deprecation warning 2개.
- `cd backend && .venv/bin/ruff format --check jusik/market_history_models.py jusik/market_research_service.py tests/test_market_research.py && .venv/bin/ruff check jusik/market_history_models.py jusik/market_research_service.py tests/test_market_research.py` — 통과.
- `cd backend && .venv/bin/python -m mypy --strict jusik/market_history_models.py jusik/market_research_service.py` — 통과.
- `cd frontend && npm run verify:market-research-contract && npm run lint && npm run typecheck && npm run build` — 통과; US·KR·legacy와 모순된 native currency fixture를 검증했습니다.
- `git diff --check` 및 audit manifest JSON parse — 통과.

## 안전·운영 상태

- 전용 venv와 frontend 의존성만 사용했습니다. 운영 DB·서비스·provider 호출·실주문·원격 push는 수행하지 않았습니다.
- 비밀정보·자격증명·계좌 식별자는 기록하거나 변경하지 않았습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/r0-currency-contract`; manifest: `r0-currency-contract-verification.json`; SHA-256: `62c2da3cf4cc6723c8400c7766b77b485f0504854abb360336ae76f54861253e`.
- 남은 작업·차단 조건: supervisor 독립 review와 local `main` 통합 전입니다. R0-05와 R0-03은 후속 작업입니다.
- 다음 시작: supervisor가 이 브랜치의 currency metadata diff와 fixture·hash 불변성을 검토합니다.

## 통합 검증

최종62ae5ac 독립 review 중요 지적 없음. main `f949a635bc6e750b6d2b50a5a0beb889890f0111` 통합 후 pytest48개, Ruff format/check, strict mypy2개, npm 계약fixture·lint·typecheck·build 및 diff 검사 통과. R0-04만 완료하며 R0-05·R0-03은 후속입니다.
