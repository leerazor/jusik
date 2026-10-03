# 선정 후보 KR 신호·정책의 합성 raw 원장 연결

- 상태: 구현 완료, 독립 검토·main 통합 전
- 기록 시각: 2026-10-03T17:49:41Z
- 작업 slug: `selected-kr-candidate-policy-20261004`
- 기준/통합: `9c43580944bd8530cc54a5841a5e95a340f7117f` / 없음
- 범위: 동결된 두 신호 방법을 각각 명시적 합성 KR 원장에서 4주 결정·밴드·엄격히 다음 공식 개장 체결로 연결한다. 위험 사건을 처리할 규칙이나 실제 자료 적격·성과 실행은 추가하지 않는다.

## 변경과 결정

- `backend/jusik/selected_candidate_kr_policy.py`: `run_kr_selected_candidate_reference`가 raw·신호 등록 revision/hash, 전체 identity/cohort, 공식 달력, 설정 SHA 및 별개 의미 source hash를 대조한다. 첫 Monday 00:00 UTC부터 28일 간격으로 `plan_selected_candidate`를 실제 호출하고 `incomplete`는 실패로 처리한다. 결정 시 직전 완료 원장 상태에서 엄격한 2%p 미만 밴드를 판정하고 양의 목표·당시 hard cap 정상인 경우만 실제 수량을 `hold_quantity`로 기록한다. 신호 원천 hash와 raw 가격 원천 hash는 합치지 않는다.
- `backend/jusik/approved_universe_buy_hold.py`: 같은 사건 루프에 결정 전 hook과 완료 종가 hook, 수량 유지 지시를 좁게 추가했다. 기존 `execute_kr_batch`의 매도·매수·현금 sweep·기업행동 전이를 공유한다. 밴드 지시에는 계산용 가짜 목표를 주지 않고 매도·매수를 건너뛴다. 다른 거래 비용 후 보유 수량의 종목/총액/leveraged hard cap이 깨지면 수리 거래를 꾸미지 않고 거부한다. 결정과 같은 시각의 개장은 체결에서 제외하며 pending 결정이 겹치면 거부한다.
- 완료 종가의 별도 episode 고점 대비 하락이 10%에 닿으면 `RiskPolicyRequired` (`risk_policy_required`)로 결과 전체를 실패 처리한다. raw lifetime 최고점·MDD 20% 관측은 별도로 보존하며 재진입 시점 재설정은 구현하지 않았다. 성공 결과는 `synthetic_reference_only`, `investment_qualification=not_evaluated`이고 신호 계획·밴드 수량·raw ledger·episode/lifetime 고점을 함께 노출한다.
- `backend/tests/test_selected_candidate_kr_policy.py`: 두 고정 방법의 실제 planner→raw 원장 두 결정과 독립 분수 산술, strict band, 비용 후 유지 수량, unsupported hard cap, 0목표, 배당 권리, late revision, 위험 중단·lifetime 구분, identity/hash·pending·불완전 입력을 검증한다.

## 문서·계약 영향

- `docs/research/approved-universe-comparison-protocol-v1.md`: 일곱 번째 합성 단계와 위험·실자료 차단 경계를 추가했다. 공식 배당 검토 24/111은 전체 자료 준비율이 아니고 실제 READY cohort는 없다.
- `docs/research/selected-candidate-config-v1.json`: raw 의미 source hash `c2855b2338a80e4536f1eb0ada3abe8c046fe806e03cc30e77bf4780558a74e4`→`fc7014caaeaebb83ded93fac439339b5b274f645003b82680c47d722c956e81a`, 신규 정책 module hash `8f9ad87aa7057a1b039418ad3999107a68315e8e3f9cb19c469a63d4aa0fa411`만 반영했다. 다른 의미 hash·숫자·시점은 유지했다. 설정 SHA-256 `f56bda3e69b6d65b1785dcb6cb0f4698515064a888aa6daf7f6fd40bf743dc3d`; `candidate_execution_code_hash=null`, `execution_allowed=false`, `results_observed=false` 유지.
- API·서비스·운영 계약: 변경 없음.

## 검증

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend backend/.venv/bin/python -m pytest -q -p no:cacheprovider backend/tests/test_selected_candidate_kr_policy.py backend/tests/test_approved_universe_rebalance_sequence.py backend/tests/test_approved_universe_multi_target.py backend/tests/test_selected_candidate_signals.py backend/tests/test_approved_universe_target_bridge.py backend/tests/test_approved_universe_buy_hold.py backend/tests/test_approved_universe_cap_control.py backend/tests/test_market_history_action_accounting.py backend/tests/test_research_portfolio.py backend/tests/test_research_portfolio_time_evidence.py backend/tests/test_research_portfolio_volatility_target_sensitivity.py` — 기존 208개와 신규 10개, 총 218개 통과.
- 소유 코드·신규 테스트 `backend/.venv/bin/ruff check`, `ruff format --check`, `PYTHONPATH=backend backend/.venv/bin/python -m mypy --strict` — 모두 통과. `git diff --check` 통과.
- `/tmp/selected-kr-policy-code/policy-fixtures.json` — 양 방법의 두 번의 28일 결정·체결 전체 출력 SHA-256 `b75c647b55e18323580789df3557e47cecd5e32e7afcf82b66833b343f7a0e74`; 신규 테스트에서 각각 독립 분수식으로 첫·두 번째 수량, 비용 후 현금과 NAV를 대조했다.
- `/tmp/selected-kr-policy-code/`: 수정 전후 baseline 3·cap 3·단일 target 3·초기 batch KR/US 2의 전체 직렬화와 KR 3결정 전체 출력, 독립 probe가 byte 동일. SHA-256 baseline `930b79ab749421fad20bc220e5eeef7c114ef9e7a923e9e5d4a7286dde72d9fc`, cap `90a70498db03492a0ba91a47aeeecbe5e75552d89b9e64938fc01e81c4b535ee`, target `bc7ff1c2b0fa18594fcc7d26a41dce045836f3a5c46e711c460c2b5f10817d0d`, batch `071036f645442d6da67ec74a494eae5d0337accedfc9089a6f756d4f17f6a3df`, KR sequence `306383eeace492a109f827199bca221093099ed935d82cff857ca717820e8bd3`, probe `55d9a49e07fde4cbb7f6da1eafa4c7ff212a93f6d65b786ae061b384afe57a73`.
- 실제 원천 인수·후보 성과·주문·서비스 검사는 이 단계에서 실행하지 않았다.

## 안전·운영 상태

- 운영 DB·원천/API·네트워크·runner·서비스·PAPER/실주문·성과 실험·원격 push 변경 없음. 합성 NAV를 실제 수익률로 해석하지 않는다.

## 증거와 재개

- 작업 전후 전체 출력 및 독립 probe: `/tmp/selected-kr-policy-code/`.
- 남은 작업: supervisor 독립 검토·main 통합. 위험 청산 pending 우선순위, 28일 cooldown·주간 회복·재진입과 비용 후 cap 수리는 미구현이다. 실제 등록 16종목 revision 1의 원천 적격은 별도 인수가 필요하다.
- 다음 시작: 정책 결정 hook·밴드 수량 유지·위험 경계의 독립 검토 후 동결 합성 검사를 재현한다.

## workflow 평가

- workflow 판단: 도움 됨 — 기존 신호 planner와 단일 raw 사건 루프를 직접 연결하고 위험 미구현 사건을 실패로 제한했다.
- 근거: 이전 전체 출력 및 독립 probe를 재사용해 원장 회귀를 대조했다. 시간·호출 절감량은 미측정이다.
- 다음 조정: 유지 — full risk·실자료 적격을 별도 완료 조건으로 다룬다.

## 독립 검토 P2 수정 (2026-10-03T18:03:01Z)

- 검토에서 설정의 의미 소스 해시 6개 중 3개만 검사하던 누락을 확인했다. 정책 입력은 동결된 6개 경로 집합과 소문자 SHA-256 형식을 먼저 검사하고, 이 6개 파일의 실제 바이트 해시를 모두 대조한다. 임의 추가 경로는 읽지 않고 거부한다. 고정된 후보·위험 플래그·합성 단계 범위는 그대로다.
- 등록된 6개 경로 각각을 누락하거나 잘못된 해시·형식 오류로 바꾼 뒤 설정 SHA를 다시 계산하는 회귀 검사를 추가했다. 임의 추가 경로와 대문자·짧은 문자열·숫자 해시도 거부한다. 검토의 `market_history_action_accounting.py` 변조는 수정 전 수락, 수정 후 거부를 확인했다.
- 정책 소스 해시만 `8f9ad87aa7057a1b039418ad3999107a68315e8e3f9cb19c469a63d4aa0fa411`→`b482a5707656b7b8f678603b27c6b38bcf1ddda3180d56e31dcd7191d59c72cc`로 갱신했다. 설정 SHA-256은 `546446d6557095a0bba4811b785fa54a65557405669a519c4b9fcdd645d85ee2`; 다른 5개 소스 해시와 `candidate_execution_code_hash=null`, `execution_allowed=false`, `results_observed=false`를 확인했다.
- 정책 집중 검사 32개, 기존 관련 검사 포함 총 240개 통과. 소유 Python 2개 파일 Ruff check·format 및 strict mypy 통과. `/tmp/selected-kr-policy-code/`의 baseline·cap·single target·batch·KR sequence 전체 직렬화와 독립 probe는 이전 `*-final.json`과 바이트 동일하다. 설정 SHA가 달라져 정책 출력의 입력 결속 값은 새 SHA를 사용한다.
- 남은 작업: 독립 재검토와 supervisor의 통합. 실제 원천 적격·성과·위험 청산 정책은 여전히 미완료다.
