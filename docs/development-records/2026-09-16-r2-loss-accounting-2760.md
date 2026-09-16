# R2-01 독립 손실 회계 진단

## 2026-09-16 복구 기록

- 상태: 복구 구현 완료, 독립 검토 대기 (R2-01 경제 평가는 계속 차단)
- 기준/통합: `d7ee8ca` / 없음
- 범위: 기존 네 대상 파일만 수정했습니다. 전략, collector, shared model,
  registry, runner, DB, 서비스와 주문 계층은 읽기 전용으로 보존했습니다.

## 복구 변경과 결정

- 명시적 거래 입력은 side·currency·유한 수치·양수 수량/가격·비음수 비용과
  ISO `YYYY-MM-DD` 체결일을 검증하고, KRW/USD 혼합과 시장 통화 불일치를
  거부합니다. 중복 식별에는 fee·tax·currency를 포함합니다.
- 모든 공개 계산은 호출자 Decimal context와 독립적인 precision 50,
  `ROUND_HALF_EVEN` context에서 실행합니다. 순손익은 realized/unrealized/
  dividend 등 실제 의존 항목이 모두 available일 때만 available입니다.
- 매수 tax를 포함한 체결 비용과 완전한 배당 evidence가 있는 배당 현금흐름을
  계산 현금에 반영합니다. 배당 evidence가 없거나 불완전한 현금은
  `unavailable`로 유지하고 진단값과 관측 `cash_krw`를 구분합니다.
- 저장 결과의 equity 날짜 중복·역순과 fill session 누락을 거부합니다. 별도
  주문 상태/timestamp를 체결로 추정하지 않으며 독립 달력 근거 없이 날짜 간격을
  결측으로 판정하지 않습니다.

## 복구 검증

- `backend/.venv/bin/python -m pytest tests/test_market_loss_accounting.py -q` —
  PASS, 18 tests.
- `backend/.venv/bin/python -m ruff check jusik/market_loss_accounting.py
  tests/test_market_loss_accounting.py` — PASS.
- `backend/.venv/bin/python -m ruff format --check
  jusik/market_loss_accounting.py tests/test_market_loss_accounting.py` — PASS.
- `backend/.venv/bin/python -m mypy --strict jusik/market_loss_accounting.py
  tests/test_market_loss_accounting.py` — PASS, 2 source files.
- 파일럿 진단은 원본 manifest의 source SHA가 일치함을 확인한 뒤 focused gate
  완료 후 1회 실행했습니다. 252 sessions·106 trades이며 `blocked`이고, 완전한
  realized/unrealized/dividend evidence가 없어 경제 평가는 `not-evaluated`로
  유지됩니다. 결과 JSON과 명령별 원문 로그·wall/CPU 기록은 저장소 밖 audit에
  보관합니다.

- 이전 구현의 실패·fixture 초과 기록은 삭제하거나 재작성하지 않고 아래의
  역사 기록으로 보존합니다.

- 상태: 차단 (기술 slice 구현·검증 완료, 필수 회계 evidence 부족)
- 기록 시각: 2026-09-16T06:23:38Z
- 작업 slug: `r2-loss-accounting-2760`
- 기준/통합: `15b5800` / 없음
- 범위: 독립 Decimal 회계 모듈, 오프라인 테스트, 한국어 설명입니다. 전략,
  collector, shared model, registry, roadmap은 수정하지 않았습니다.

## 변경과 결정

`backend/jusik/market_loss_accounting.py`에 저장 `MarketResearchResult`의
거래·equity를 읽는 독립 CLI와 명시적 거래 입력을 위한 FIFO 계산을 추가했습니다.
원시 시가손익과 체결가 손익, 양방향 slippage, 수수료·세금, 배당 evidence,
FX 교차항, 현금 잔액을 분리합니다. 완전한 거래 이력·초기 포지션·기업행사·배당
자료가 없으면 값은 `unavailable`이고 진단용 FIFO 값과 재개 입력을 보존합니다.

수작업 기준값은 cash 1000, buy 2 (open 100/fill 101/fee 2.02), sell 1
(open 110/fill 108.9/fee 1.089/tax 0.19602), final mark 120입니다. raw
realized 10, unrealized 20, slippage 3.1, fee 3.109, tax 0.19602,
net 23.59498, cash 903.59498을 고정 테스트합니다. FX 기준은
N 100→110, F 1300→1320으로 local 13000, FX 2200(교차 200), total 15200입니다.

## 문서·계약 영향

- 사용자 문서: `docs/research/market-loss-accounting.md` — 독립 진단 계산식과
  증거 등급을 설명합니다.
- 운영 문서: 해당 없음. 서비스·DB·설정은 바꾸지 않았습니다.
- API·설정·데이터 계약: 기존 `MarketResearchResult`를 읽기만 하며 변경하지
  않았습니다.

## 검증

- `backend/.venv/bin/python -m pytest tests/test_market_loss_accounting.py -q` —
  PASS, 11 tests.
- `backend/.venv/bin/ruff check jusik/market_loss_accounting.py tests/test_market_loss_accounting.py` — PASS.
- `backend/.venv/bin/ruff format --check jusik/market_loss_accounting.py tests/test_market_loss_accounting.py` — PASS.
- `backend/.venv/bin/python -m mypy --strict jusik/market_loss_accounting.py tests/test_market_loss_accounting.py` — PASS.
- 저장 미국 pilot SHA 확인 후 CLI 1회 진단 — 필수 evidence 부족으로 `blocked`;
  결과는 audit 디렉터리에 보관합니다.
- 전체 backend suite와 simulation/replay는 범위·안전 조건에 따라 실행하지
  않았습니다.

## 안전·운영 상태

오프라인 저장 파일과 메모리 fixture만 읽었습니다. 네트워크 수집, GPU, 서비스,
DB/원장 변경, PAPER/live 실행, 주문, broker API, remote push는 수행하지 않았습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260916-r2-01-2760e570`;
  pilot 입력 SHA와 진단 JSON을 보관합니다.
- 남은 작업·차단 조건: complete ordered fills, opening positions, symbol-level
  marks, corporate actions, complete dividend evidence가 확보될 때까지 경제
  평가는 `not-evaluated`이며 R2-01 전체 체크는 변경하지 않습니다.
- 다음 시작: audit의 진단 JSON과 현재 입력 SHA를 확인한 뒤 누락 evidence 확보
  여부를 판단합니다.
