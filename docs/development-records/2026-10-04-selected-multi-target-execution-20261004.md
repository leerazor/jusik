# 선정 후보 최초 다종목 target 합성 체결

- 상태: 완료: 독립 검토 PASS·로컬 main 통합·200개 통합 검사 PASS
- 기록 시각: 2026-10-03T16:31:47Z
- 작업 slug: `selected-multi-target-execution-20261004`
- 기준/통합: `59fe312095c30ffe8e64dae68a2482cdcf44baf6` / `42214b8af0f693f0ea8dc5c53d2f5453d961184d`
- 범위: 기존 raw 사건 루프에서 같은 통화·같은 다음 공식 시가에 도달하는 전체 cohort의 최초 목표 벡터 한 건만 합성 체결했다. 신호 모듈·legacy 원장·API·scheduler·재조정·매도는 변경하지 않았다.

## 변경과 결정

- `backend/jusik/approved_universe_buy_hold.py`: 공개 `run_multi_target_reference`와 합성 결과·종목별 체결 시도 상태를 추가했다. 전체 등록 identity를 정확히 한 번씩, 공통 결정시각, 종목 20%·총액 60%·등록 leveraged 합계 20%를 검증한다. 양의 목표가 있으면 cohort 전부 같은 통화·같은 엄격히 후속 첫 공식 개장이어야 한다. 전부 0은 거래 없는 `all_cash`다.
- 같은 시각 분할→배당락→지급→전 종목 공식 시가 mark 뒤에 기존 `buy_terms`와 `buy_at_open`을 사용한다. 비공개 순수 수량 함수는 `uᵢ=⌊wᵢN₀/Vᵢ⌋`, `Nmin=N₀−Σuᵢ(Cᵢ−Vᵢ)`, `qᵢ=⌊wᵢNmin/Vᵢ⌋`를 계산한다. 공유 원화 현금 부족·비양수 `Nmin`은 거부하며 잔여 현금을 재배분하지 않는다.
- Decimal 비용·평가액·입력 합계의 경계는 정확한 분수로 계산하고 기존 Decimal 원장 전이가 반올림되어 일치하지 않으면 명시적으로 거부한다. 체결 뒤 cash·NAV·종목별 목표·gross·leveraged 한도를 재확인한다. `filled`는 주식 한 주 이상이며 실제 달성 비중과 목표 미달을 별도 기록한다. `one_share_not_feasible`과 배치 `no_feasible_share`는 거래 없는 시도와 구분한다.
- 기존 `run_buy_hold_reference`, `run_cap_control_reference`, `run_target_bridge_reference`의 공개 dataclass·시그니처·전체 출력은 유지했다.

## 문서·계약 영향

- `docs/research/approved-universe-comparison-protocol-v1.md`: 다섯 번째 합성 단계의 단일 시가·통화 조건, 보수적 동시 수량, 미구현 범위를 명시했다.
- `docs/research/selected-candidate-config-v1.json`: raw 코어 의미 source SHA-256만 `50eaac00df0f3a213f1beb1d5616e07d88876f2ba68299583d8721fae0a54b53`에서 `84e2898ab39f16bf5748e532fb35aebed0d490c1fc7a814702266a079f5f584d`로 갱신했다. 나머지 네 hash, 수치·시점, `candidate_execution_code_hash=null`, `execution_allowed=false`, `results_observed=false`를 유지했다. 설정 파일 SHA-256은 `5e46bdfa7d99a352ac384f33466d647e0f8e0995e65162f85e19ee431391f1ed`다.
- API·운영·서비스 계약: 변경 없음.

## 검증

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend backend/.venv/bin/python -m pytest -q -p no:cacheprovider backend/tests/test_approved_universe_multi_target.py backend/tests/test_selected_candidate_signals.py backend/tests/test_approved_universe_target_bridge.py backend/tests/test_approved_universe_buy_hold.py backend/tests/test_approved_universe_cap_control.py backend/tests/test_market_history_action_accounting.py backend/tests/test_research_portfolio.py backend/tests/test_research_portfolio_time_evidence.py backend/tests/test_research_portfolio_volatility_target_sensitivity.py` — 기존 189개와 신규 11개, 총 200개 통과.
- 소유 코드·신규 테스트 `backend/.venv/bin/ruff check`, `ruff format --check`, `PYTHONPATH=backend backend/.venv/bin/python -m mypy --strict` — 통과.
- `/tmp/selected-multi-target-code/independent_oracle.py` — 자본 1,000, 가격 100/50, 비용 10%, 목표 각 20%의 작은 정수 공간을 완전 열거했다. `u=(2,4)`, `Nmin=960`, `q=(1,3)`, 현금 725·NAV 975. 동일 산술의 KR 192,000/384,000주와 USD FX spread 192/384주도 대조했다.
- `/tmp/buyhold-baseline-compat.py`, `/tmp/selected-target-bridge-code/cap_compat.py`, `/tmp/selected-multi-target-code/target_compat.py` — 기존 baseline 3·cap-control 3·단일 target 3사례의 **전체 직렬화 출력이 변경 전과 byte 동일**. SHA-256: baseline `930b79ab749421fad20bc220e5eeef7c114ef9e7a923e9e5d4a7286dde72d9fc`, cap-control `90a70498db03492a0ba91a47aeeecbe5e75552d89b9e64938fc01e81c4b535ee`, 단일 target `bc7ff1c2b0fa18594fcc7d26a41dce045836f3a5c46e711c460c2b5f10817d0d`.
- 다섯 의미 source hash와 실행 차단 flags 대조·`git diff --check` — 통과. 실행하지 않은 검사: 실제 원천 인수, 후보 전체 전략, 비용 차감 성과, 서비스·주문 경로는 이 단계 밖이다.

## 안전·운영 상태

- 운영 DB·원천/API·네트워크·runner·서비스·PAPER/실주문·성과 실험·원격 push 변경 없음. 합성 검증은 투자 적격이나 실제 수익성 결과가 아니다.

## 증거와 재개

- 재현 경로: `/tmp/selected-multi-target-code/`에 사전·사후 전체 직렬화 JSON, 독립 oracle 및 결과 JSON을 보관했다.
- 남은 작업: 독립 코드 검토와 로컬 main 통합은 완료했다. 이후 신호 목표와 raw 체결 연결, 혼합 시장·여러 개장, 재조정·위험 episode·실제 자료 적격은 별도 단계다.
- 다음 시작: selected-rebalance-sequence 작업의 기존 매도·일정·밴드 재사용 조사 결과로 계획을 확정한다.

## workflow 평가

- workflow 판단: 도움 됨 — 고정 계획과 기존 코어를 재사용해 한 번의 초기 동시 체결로 범위를 제한했다.
- 근거: 순수 산술과 원장 경계를 독립 열거·200개 검사·전체 출력 비교로 확인했다. 시간·호출 절감량은 미측정이다.
- 다음 조정: 유지 — 독립 검토 후 다음 실행 단계를 별도 소유 작업으로 다룬다.

## supervisor 통합

- 구현9ed4b1e 독립 Sol/high review PASS. main42214b8에서 200개 검사(6.58초)·Ruff·strict mypy·독립 KR1%/US수수료+환전 Fraction oracle·전체 결과 순열불변 PASS.
- 영구 audit `/home/kwl/.local/share/jusik/portfolio-audit/20261004-selected-multi-target/`, manifest SHA `31efda9c8496796133ce45055c5b815b8a03ff629c4bb571cb13a69d1d56b75f`.
- 다음 재조정 단계의 읽기 전용 explore가 진행 중이다. 관리형 checkout은 후속 작업 재사용을 위해 유지한다. root 사용자 HANDOFF.md 보존.
