# 선정 후보 KR 목표 결정열의 합성 재조정

- 상태: 구현 완료, 독립 검토·main 통합 전
- 기록 시각: 2026-10-03T17:02:29Z
- 작업 slug: `selected-rebalance-sequence-20261004`
- 기준/통합: `eb56a4f42610ffa79b2767e12cd8dfeeac2ccaa1` / `74a55817fbe31b483035142b04d10dbd9c2a201b`
- 범위: 등록 revision 1의 KR 전체 cohort에 명시적으로 주입한 유한 목표 결정열을 기존 raw 회계 사건 루프에서 체결한다. 실제 후보 일정·신호 연결·성과 실행은 포함하지 않는다.

## 변경과 결정

- `backend/jusik/approved_universe_buy_hold.py`: `run_kr_target_sequence_reference`를 추가했다. 전체 등록 identity와 종목 20%·총액 60%·leveraged 20%, 엄격히 다음 공통 KRX 개장, 증가하는 결정과 겹치지 않는 pending batch를 검증한다. 분할→배당락→지급→모든 시가 mark 뒤 매도 전 위험점을 남기고 정렬된 매도 후 매수를 같은 원장에서 수행한다.
- 기존 `_sell_state`의 비례 원가 차감 및 배당 권리·미수 보존을 재사용한다. 기존 매수 전이가 보유 수량·원가에 더하도록 수정했다. 지급 배당 현금과 매도대금은 매도 후 공유 KRW 현금으로 정확히 한 번 옮기고 NAV 불변을 검사한다. 전량 매도된 상태의 후속 분할은 수량에 적용하지 않으며, 새 매수는 raw 시가를 쓴다.
- `Nref` 상계와 비용 포함 최소 정수 매도, 공유 현금 비례 내림 매수를 체결 전 전체 벡터로 계산한다. 매도 종목은 같은 batch에서 다시 사지 않는다. 정수 매도 반복은 보유 수량의 비트 길이에 따른 한도로 제한하고 한도 안에 수렴하지 않으면 거부한다. 분수 산술과 실제 Decimal 원장의 비용·현금·NAV·종목·gross·leveraged 노출을 대사하며 반올림 차이는 거부한다.
- `backend/tests/test_approved_universe_rebalance_sequence.py`: 자본 1,000의 작은 정수 완전열거, 비용·공유현금, 3결정 분할/배당 권리/지급, 추가 매수, 전량 현금, 매도 후 분할, 개장 갭 위반 이력, 순열 및 잘못된 입력을 검증한다.

## 문서·계약 영향

- 사용자 연구 규약: `docs/research/approved-universe-comparison-protocol-v1.md`의 여섯 번째 합성 단계와 미구현 범위를 갱신했다.
- 설정 계약: `docs/research/selected-candidate-config-v1.json`의 raw core 의미 source SHA-256만 `84e2898ab39f16bf5748e532fb35aebed0d490c1fc7a814702266a079f5f584d`에서 `c2855b2338a80e4536f1eb0ada3abe8c046fe806e03cc30e77bf4780558a74e4`로 갱신했다. 나머지 네 source hash와 숫자·시각은 유지했다. 설정 SHA-256은 `f44294b0e6acd915ec22bfc5c7e85ad4f561656606d8ce4249d96f59a2c3e1ab`이다. `candidate_execution_code_hash=null`, `execution_allowed=false`, `results_observed=false`를 유지했다.
- API·서비스·운영 계약: 변경 없음.

## 검증

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend backend/.venv/bin/python -m pytest -q -p no:cacheprovider backend/tests/test_approved_universe_rebalance_sequence.py backend/tests/test_approved_universe_multi_target.py backend/tests/test_selected_candidate_signals.py backend/tests/test_approved_universe_target_bridge.py backend/tests/test_approved_universe_buy_hold.py backend/tests/test_approved_universe_cap_control.py backend/tests/test_market_history_action_accounting.py backend/tests/test_research_portfolio.py backend/tests/test_research_portfolio_time_evidence.py backend/tests/test_research_portfolio_volatility_target_sensitivity.py` — 기존 200개와 신규 8개, 총 208개 통과.
- `backend/.venv/bin/ruff check` 및 `ruff format --check` (소스·신규 테스트), `PYTHONPATH=backend backend/.venv/bin/python -m mypy --strict` (동일 파일) — 통과.
- `/tmp/selected-rebalance-code/oracle.py` — 독립 작은 정수 완전열거 125개 조합 중 가능한 32개. A 3주·B 1주 매도, C 3주 매수, NAV 950·현금 550 대조.
- `/tmp/buyhold-baseline-compat.py`, `/tmp/selected-target-bridge-code/cap_compat.py`, `/tmp/selected-multi-target-code/target_compat.py` 및 KR/US 초기 batch fixture — 기존 baseline 3·cap-control 3·단일 target 3 및 KR/US batch 전체 직렬화 출력이 변경 전과 byte 동일. SHA-256: baseline `930b79ab749421fad20bc220e5eeef7c114ef9e7a923e9e5d4a7286dde72d9fc`, cap `90a70498db03492a0ba91a47aeeecbe5e75552d89b9e64938fc01e81c4b535ee`, target `bc7ff1c2b0fa18594fcc7d26a41dce045836f3a5c46e711c460c2b5f10817d0d`, KR/US batch `071036f645442d6da67ec74a494eae5d0337accedfc9089a6f756d4f17f6a3df`.
- 다섯 의미 source hash와 세 실행 차단 값 검사, `git diff --check` — 통과.
- 실행하지 않은 검사: 실제 원천 인수·후보 전체 전략·비용 차감 성과·서비스/주문 경로. 이 단계의 입력과 권한 범위 밖이다.

## 안전·운영 상태

- 운영 DB·원천/API·네트워크·runner·서비스·PAPER/실주문·성과 실험·원격 push 변경 없음. 합성 계산은 실제 투자 적격 또는 수익성 검증이 아니다.

## 증거와 재개

- 재현 경로: `/tmp/selected-rebalance-code/`의 사전/사후 전체 직렬화 JSON과 독립 oracle 코드·결과.
- 남은 작업: supervisor의 독립 코드 검토·main 통합 및 실제 자료/후보 연결은 별도 승인 단계다.
- 다음 시작: 이 커밋을 독립 검토하고 기존 출력 동일성·208개 회귀를 재확인한다.

## workflow 평가

- workflow 판단: 도움 됨 — 고정 계획과 이전 직렬화 호환 스크립트를 재사용해 같은 회계 루프 안에서 범위를 제한했다.
- 근거: 작은 정수 완전열거, 기존 전체 출력 바이트 비교, 회귀 검사를 수행했다. 시간·호출 절감량은 미측정이다.
- 다음 조정: 유지 — 감독 독립 검토 전 합성 결과를 투자 적격으로 승격하지 않는다.

## supervisor 통합

- 구현022e67f 독립 Sol/high review PASS. 별도 소규모 3,870건 수량/현금/상한 검증. main74a5581에서 208개 검사(6.36초)·Ruff·strict mypy PASS.
- 독립 100MKRW 3결정 산술, 입력 순열 전체 동일, 매도/추가매수 전후 배당 권리·지급 단회성 PASS. probe는 pre_rebalance/open·accrual/payment를 구분해 대사했다.
- 영구 audit `/home/kwl/.local/share/jusik/portfolio-audit/20261004-selected-rebalance/`, manifest SHA `c1c270edc2f890486577710f46b36050bbb7e358b3a579a2d6671f0151443877`.
- 남은 전략 연결: 고정 신호·4주 일정·2%p band·episode/cooldown/재진입. 실제자료 적격과 실제 수익성은 미검증. codewriter 종료, 동일 관리형 checkout은 다음 승인된 작업 재사용 위해 보존한다.
