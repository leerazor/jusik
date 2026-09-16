# R2-06 준비 회계 결과 counterfactual 비교

- 상태: 진행. 구현 완료·독립 검토 대기입니다.
- 기록 시각: 2026-09-17T00:00:00+00:00
- 작업 slug: `r2-counterfactual-fe92`
- 기준/통합: `d0d029996ea993216036385962c9153968ea61fe` / 없음
- 범위: 준비된 loss report wrapper를 hash 고정해 기준과 cost/dividend/fx 중 하나만 바꾼 시나리오를 비교합니다. 기존 회계·전략·시장 자료 경로와 작업 등록부는 보존했습니다.

## 변경과 결정

- `backend/jusik/market_counterfactual_comparison.py`: wrapper metadata와 envelope의 시장·기간·세션·report native 통화·초기 계좌 통화·등급·자료/정책 계약·공통 고정 조건을 type-preserving equality로 완전 비교하고, available이며 같은 통화·단위인 component만 Decimal 차감합니다. atomic leaf 하나만 변경하도록 before/after를 검증하고, 배당·FX 근거 부족은 원문 보존 blocked delta로 기록합니다.
- `backend/tests/test_market_counterfactual_comparison.py`: 독립 Decimal, hash 선검증, 중복 key/ID/세션, type-preserving bool/int, 단일 atomic assumption, metadata 불일치, unavailable diagnostic 보존, 배당·FX evidence, 비용·FX·joint 비가산 delta, 0·음수·고정밀 수치, timezone·휴장 세션, partial/cancelled/rejected 상태, 출력 overwrite 경계를 합성 fixture로 고정했습니다. 합성 fixture는 22개 테스트와 최대 3개 시나리오입니다.
- `docs/research/market-counterfactual-comparison.md`: 입력 wrapper, 결과 delta-only 계약과 운영 경계를 기록했습니다.

## 문서·계약 영향

- 사용자 문서: `docs/research/market-counterfactual-comparison.md`에 새 오프라인 비교 계약을 기록했습니다.
- 운영 문서: 해당 없음. provider·서비스·주문·DB·설정은 변경하지 않았습니다.
- API·설정·데이터 계약: 새 파일 기반 비교 schema만 추가했으며 기존 loss report schema와 회계 함수는 호출·수정하지 않았습니다.

## 검증

- `backend/.venv/bin/python -m pytest tests/test_market_counterfactual_comparison.py tests/test_market_loss_accounting.py -q` — 통과, 43 tests (새 비교 테스트 22개 포함).
- `backend/.venv/bin/python -m ruff check jusik/market_counterfactual_comparison.py tests/test_market_counterfactual_comparison.py` — 통과.
- `backend/.venv/bin/python -m ruff format --check jusik/market_counterfactual_comparison.py tests/test_market_counterfactual_comparison.py` — 통과.
- `backend/.venv/bin/python -m mypy --strict jusik/market_counterfactual_comparison.py tests/test_market_counterfactual_comparison.py` — 통과.
- 실행하지 않은 검사: network/provider/engine/replay/GPU와 frontend 검사는 작업 경계 밖입니다.

## 안전·운영 상태

- CPU 합성 fixture만 사용했습니다. network/provider/engine/replay/GPU, PAPER/live, 실제 주문, 운영 원장·DB·서비스·remote push 변경은 없습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260917-r2-06-474fb22d`; manifest: 구현 검증 후 기록 예정; hash: 원본 준비 report별 SHA를 결과에 보존합니다.
- 남은 작업·차단 조건: 독립 Terra review와 부모의 local main 통합 검증이 남았습니다. 전체 R2-06 checkbox와 경제 평가는 미완료·not-evaluated입니다.
- 다음 시작: 독립 review가 모듈·테스트·계약을 읽고 metadata와 delta 경계를 재검증합니다.

## 제한 재시도 보완 (2026-09-17)

- `_leaf_differences`에서 container/scalar 및 mapping/list 유형 교체를 atomic leaf 변경으로 허용하던 우회를 거절하도록 보완했습니다. `_change_record`는 검증된 실제 단일 leaf에서 `atomic_path`와 `before`·`after`를 파생해 최상위 scalar 변경도 `cost`처럼 정확히 기록합니다.
- 관련 합성 회귀 검사를 추가하고 문서 입력 예시의 기준 `fee_rate`를 시나리오 변경과 일치시켰습니다. CPU seed 0, 준비된 오프라인 fixture만 사용하며 실제 acceptance·경제 평가는 여전히 미평가입니다.
- 제한 재검증: comparison/loss accounting pytest 45개 통과, Ruff check·format 및 `pyproject.toml` strict mypy 통과, `git diff --check` 통과. 로그는 retry audit의 `logs/`에 보존했습니다.
