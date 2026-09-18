# R1-03 미국 상품 유형 분류

- 상태: 완료; 독립 재검토와 main 통합 검증 통과
- 기록 시각: 2026-09-16T00:09:40Z
- 작업 slug: `r1-us-product-types`
- 기준/통합: `f4a57e34125430ead35dea908343d659ca68cdea` / `dc59347261e41ca232f2b50dc41dabb0d08e6c63`
- 범위: Alpha Vantage listing parser 내부 상품 분류와 거래소 alias 정규화, 고정 회귀 fixture, 관련 계약 문서

## 변경과 결정

- `backend/jusik/market_data_collector.py`에 private `StrEnum`과 순수 분류 helper를 추가했습니다. `assetType` exact 값, 명확한 상품명 suffix·구문, warrant 심볼 suffix를 결합하며 ordinary와 비대상 근거 충돌 및 서로 다른 비대상 충돌을 보수적으로 처리합니다.
- parser는 ordinary만 기존 stock row로 내보내고 security type 제외 집계·검사 순서·공개 row schema를 유지합니다.
- Alpha 거래소 정규화는 상품 정보와 분리했으며 `NCM`·`NMS`·`NGM`을 `NAS`로 정규화합니다.
- `backend/tests/test_market_data_collector.py`에 신규 고정 fixture 40건을 추가했습니다. ordinary·ETF·warrant·other·unknown, 공백·대소문자·충돌·회사명 오탐·NASDAQ alias를 포함합니다.

## 문서·계약 영향

- 사용자 문서: `docs/market-research.md`에 내부 분류, ordinary 출력 규칙, 이름 기반 보수적 제외 한계, 거래소 alias 독립성을 기록했습니다.
- 운영 문서: 해당 없음. 수집·서비스·설정·DB는 변경하지 않았습니다.
- API·설정·데이터 계약: 공개 schema와 membership/event/Yahoo source 계약은 유지했습니다.

## 검증

- `backend/.venv/bin/python -m pytest backend/tests/test_market_data_collector.py -k 'alpha_listing or yahoo_parser' -q` — 통과, 40 passed.
- `backend/.venv/bin/python -m pytest backend/tests/test_market_data_collector.py -q` — 통과, 81 passed.
- 계획의 membership selector — 통과, 15 passed; contract selector — 통과, 8 passed (audit `code-checks-final/results.json` 참조).
- `backend/.venv/bin/ruff check backend/jusik/market_data_collector.py backend/tests/test_market_data_collector.py` — 통과.
- `backend/.venv/bin/python -m mypy --config-file backend/pyproject.toml backend/jusik/market_data_collector.py` — 통과.
- `git diff --check` — 통과.
- `ruff format --check` — 기준 commit에도 있던 기존 미포맷 줄 때문에 실패 (`baseline-format.log`와 `code-checks-final/format.log`); 변경 helper/parser 줄은 formatter 출력에 맞췄고 기존 FreeMarketDataCollector·membership/event source 보존을 위해 대량 재포맷하지 않았습니다.

## 안전·운영 상태

- 네트워크 수집, backtest/replay, 서비스·설정·DB 변경, PAPER/live 실행, 주문, 원격 push는 수행하지 않았습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260916-r1-03-9bd64c13`; manifest: `code-checks-final/results.json`, `boundary-verification-committed-r2.json`, `baseline-format.log`
- 남은 작업·차단 조건: 독립 review와 감독의 local main 통합 검증 대기
- 다음 시작: 감독은 commit SHA와 diff를 review한 뒤 main 통합 전 동일 selector 및 boundary 검사를 재실행합니다.

## 최종 통합 검증

- 통합 commit: `dc59347261e41ca232f2b50dc41dabb0d08e6c63`, 병합 직전 `ce03cb2282061f22f272a5dc25b41fb011ec256c`. Terra가 초기 이름 오제외 및 증거 참조 지적의 수정을 재검토하여 PASS했습니다.
- main 검사: parser40 + membership15 + contract8 = pytest63, Ruff, strict mypy, source 보존37개 및 diff check 통과. format은 실패하나 기준 commit과 요구 edit가 정확히 같음을 `format-baseline-comparison.json`으로 확인했습니다.
- `integration-verification.json`에 통합 SHA·시간·검사 및 한계를 보존합니다. 신규 fixture40개. 경제 평가는 not-evaluated이며 기존 비측정 검사 일부의 정확한 CPU 총합은 주장하지 않습니다.
- R1-03 checkbox만 완료했습니다. R1 전체와 다른 체크리스트는 변경하지 않았습니다. UI·성과 공개 변경이 없어 웹 게시/빌드는 해당하지 않습니다.
- audit `HANDOFF.md`와 SHA-256 manifest의 91파일을 저장·검증한 뒤 해당 worktree와 병합 브랜치를 정리했습니다. 기존 루트 HANDOFF.md와 다른 worktree6개는 보존합니다.
