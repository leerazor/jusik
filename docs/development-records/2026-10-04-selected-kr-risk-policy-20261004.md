# 선정 KR 후보의 합성 위험 청산·회복 경로

- 상태: 완료 — 독립 P2 수정·재검토·로컬 main 통합 검증 PASS
- 기록 시각: 2026-10-03T18:31:27Z
- 작업 slug: `selected-kr-risk-policy-20261004`
- 기준/통합: `32e9d9ad8320e40d1af32fd4f7274bbd1274fc41` / `7cc20002cb43bfae1256b581c3871f419db16fd1`
- 범위: 동결된 두 KR 후보를 같은 raw 사건·회계 루프에서 합성 위험 사건, 전량청산, 28일 cooldown, 주간 2회 확인, 다음 4주 재진입까지 연결한다. 기존 위험 없는 함수의 실패 계약과 모든 이전 원장 출력을 보존한다.

## 변경과 결정

- `selected_candidate_kr_policy.py`: 별도 `run_kr_selected_candidate_risk_reference`와 위험·cap 사건 기록을 추가했다. 완료 종가의 episode 낙폭이 10% 이상이면 정상 pending을 취소하고 0목표를 대기한다. 실제 전량 체결 또는 기존 전량 현금만 청산 완료로 인정한다. 완료 UTC 날짜+28일 뒤 Monday 00:00 UTC마다 실제 `plan_selected_candidate`로 회복을 확인하며, 불완전·양의 목표 2개 미만이면 연속 횟수와 준비 상태를 초기화한다. 두 번째 확인이 예정일과 겹쳐도 다음 예정 4주 결정까지 기다린다. 재진입 결정 직전 raw NAV로 episode 최고점만 재설정한다.
- `approved_universe_buy_hold.py`: 기존 단일 사건 루프와 `execute_kr_batch`, `_sell_state`, 배당 미수·지급 전이를 그대로 쓰는 동적 KR 지시·체결·cap 관측 훅을 추가했다. 완료 종가 위험 청산이 이전 cap 수리·정상 목표보다 앞선다. 이전 시각에 관측된 cap 위반은 전체 공통 개장 mark 뒤 자연 회복 여부를 확인하고, 정상 목표가 대기 중이면 밴드를 풀어 한 batch만 실행한다. 목표가 없으면 정렬된 보유분에서 비용 반영 최소 정수 매도만 수행하고 공유 원화 현금으로 한 번 sweep한다. 첫 관측이 그 시가인 갭 위반은 그 시가에 별도 수리하지 않는다. 종료까지 미체결·미수리면 명시적으로 실패한다.
- 기존 `run_kr_selected_candidate_reference`는 위험 사건에서 `RiskPolicyRequired`를 내는 계약을 유지한다. 새 결과도 `synthetic_reference_only`, `investment_qualification=not_evaluated`이며 lifetime 최고점·MDD와 과거 cap 위반 기록을 초기화하지 않는다.

## 문서·계약 영향

- `approved-universe-comparison-protocol-v1.md`에 합성 여덟 번째 단계와 주간 시각, 청산 완료일+28 calendar days, 같은 예정일의 두 번째 확인 보류, 위험·cap·정상 지시 우선순위를 구현 전에 명시했다.
- `selected-candidate-config-v1.json`은 변경된 raw core·정책 모듈의 의미 소스 해시만 갱신했다. 다른 4개 의미 해시와 모든 숫자·가설·시각, `candidate_execution_code_hash=null`, `execution_allowed=false`, `results_observed=false`는 유지했다. 최종 설정 SHA-256은 `40122bdb5978149fdedbdbb89fe18fcb836bb844583a64203f27c3eabb4f86e0`이며 실제 6개 파일 바이트 해시와 일치한다.
- API·서비스·운영 설정은 변경하지 않았다.

## 검증

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend backend/.venv/bin/python -m pytest -q -p no:cacheprovider`에 새 위험 정책·기존 정책·raw 원장·신호·legacy 관련 12개 테스트 파일을 지정해 총 262개 통과(기존 240개 + 신규 22개).
- `backend/.venv/bin/ruff check`와 `ruff format --check`를 변경 Python 3개 파일에 실행, `PYTHONPATH=backend backend/.venv/bin/python -m mypy --strict`를 같은 3개 파일에 실행해 모두 통과. `git diff --check`도 확인한다.
- 신규 실제 planner→raw 합성 검사는 두 방법의 정확히 10% 종가 latch, 정수 전량청산과 1% 매도비용 독립 산술, 같은 시각 개장 배제, 배당락 권리·지급, 분할 후 수량, cooldown 이전/해당일, 두 번째 확인의 4주 예정일 지연, 한 종목 적격·불완전 신호 reset, 정상 pending 취소, cap 자연 회복·새 갭·목표 중복 방지·위험 우선, lifetime MDD 이력을 확인했다. 작은 정수 상태 전부 열거로 비용 반영 cap 최소 매도 수량도 대조했다.
- `/tmp/selected-kr-risk-code/`: 이전 baseline 3·cap 3·단일 target 3·batch KR/US 2 및 KR sequence 전체 직렬화가 수정 전과 이전 동결 출력에 바이트 동일하다. 기존 정책의 두 방법 전체 경제 출력은 설정 SHA 필드만 제외하고 동일하다. 새 두 방법 위험 경로의 전체 직렬화 SHA-256은 `dc3ebd6857c9f9dad6f122750e1e4933d3fc6e3ad2870cf12557090d03063d5d`다.
- 실제 원천·기간·비용 인수, 후보 성과, 주문과 서비스 실행은 하지 않았다.

## 안전·운영 상태

- 운영 DB·네트워크·외부 원천/API·서비스·credential·PAPER/실주문·성과 실험·원격 push 변경 없음. 합성 수치를 실제 수익률이나 투자 적격으로 간주하지 않는다. 등록 revision 1의 실제 16종목은 READY cohort가 아니며 공식 배당 24/111은 배당 검토 분율에만 해당한다.

## 증거와 재개

- audit: `/tmp/selected-kr-risk-code/`; 기존 고정 출력: `/tmp/selected-kr-policy-code/`.
- 남은 작업: 이 단계의 독립 검토와 main 통합은 완료. 실제 등록·원주가·배당·FX·달력·비용·기간·수익률 조건 인수와 운영 정책은 별도 단계다.
- 다음 시작: 동적 결정/종가 우선순위, cap 최소 정수 수리, 엄격한 후속 공통 개장의 독립 검토 뒤 합성 전체 출력과 설정 해시를 재확인한다.

## workflow 평가

- workflow 판단: 도움 됨 — 확정 계획과 이전 동결 출력을 먼저 읽어 기존 함수 계약과 단일 원장 경계를 유지했다.
- 근거: 이전 11개 직렬화와 KR sequence를 재사용했고 새 합성 경로를 22개 사례 및 작은 전부 열거로 검증했다. 시간·호출 절감량은 미측정이다.
- 다음 조정: 유지 — 독립 검토 뒤 자료 인수·투자 검증으로 넘어간다.

## 독립 검토 P2 두 건 수정 (2026-10-03T18:47:09Z)

- 비용 후 cap 수리는 종목을 한 번 순회한 뒤 앞선 종목이 새로 초과되는 결함이 있었다. 전체 정수 보유수량이 매 반복마다 엄격히 감소하는 유한 가상 매도 계획으로 모든 종목·총액·레버리지 cap을 다시 확인한다. 각 단계는 비용 포함 정확한 분수식으로 필요한 수량을 한 번에 계산하며, 수렴 후 기존 원장에 종목당 매도를 한 번만 적용한다. 수렴 불가능·비양수 NAV·실제/가상 산술 불일치는 실패 처리한다. 검토 사례의 시가 A 101.25원/B 105원, 각 200,000주, NAV 101,250,000원은 B 7,158주와 A 15주 매도로 해결하며 한 주 적게 팔면 상한을 넘는다.
- full-risk 동적 지시만 결정시각보다 엄격히 늦은 **전체 cohort 개장시각 교집합의 첫 시각**을 선택한다. 다음 날 A만 열리고 그다음 날 A·B가 함께 열리면 두 번째 날 청산한다. 정상 진입과 cap 대기도 같은 공통 개장을 사용하고, 교집합이 없으면 미체결 실패다. 기존 위험 없는 정책 훅과 공개 KR 시퀀스의 개별 첫 개장 일치 제한은 그대로다.
- `test_selected_candidate_kr_risk_policy.py`에 결합 cap·독립 Fraction 사후 NAV/한 주 부족 계산·한 종목당 한 매도·입력 순서 불변, 위험청산/초기진입/cap 대기의 엇갈린 개장, 예정 목표와 cap 대기의 공통 개장, 교집합 부재 실패를 추가했다. 해당 테스트 파일 28개, 기존 관련 240개 포함 총 268개 통과. 변경 Python 2개 파일 Ruff check·format, strict mypy, `git diff --check` 통과.
- `/tmp/selected-kr-risk-p2-code/`의 baseline·cap·single target·batch·KR sequence 직렬화는 수정 전과 바이트 동일하다. 기존 위험 없는 정책과 이전 full-risk 2방법의 전체 경제 출력도 설정 SHA 필드만 제외하고 동일하다. 독립 Fraction probe의 두 방법×배당 유무 4건 및 입력 순서 불변 4건은 PASS다.
- 설정은 raw core 의미 해시만 `f63f86e97fe2728e09c11595cba935e27c18f08b3626b38d75c61cf8942a0ca8`로 갱신했다. 설정 SHA-256은 `670bfcd77a6fd02a40c5e3123f2e1b3f1591e811f709ea5a61f099f3c752ba15`; 6개 실제 소스와 일치하며 숫자·가설·차단 플래그는 그대로다. 새 full-risk 직렬화 SHA-256은 `7dc0f5aae710e905bc441c0eaacba4cf3630a8119ad768b1b6b907b72c0ca7c7`이다.
- 남은 작업: 수정분 독립 재검토와 supervisor main 통합. 실제 자료·성과·주문 검증은 수행하지 않았다.

## supervisor 통합 검증

- 구현8efee89의 P2 두 건(비용 연쇄 cap 재평가·최초 공통 개장 선택)을 동일 구현자cf1c8ac에서 수정, 독립 재검토PASS. 병합 전main1b27203, 통합7cc20002.
- main 관련268검사 6.67초 PASS, Ruff·strict mypy·diff check PASS. 두 후보×배당 유무4사례에서 사전 손계산한 청산/회복/재진입시각·정수수량·현금·NAV·episode/lifetime고점 및 입력순서반전 대사 PASS.
- audit `/home/kwl/.local/share/jusik/portfolio-audit/20261004-selected-kr-risk-policy/`, manifest SHA256 `7597cdc43ca614c155af3e853c57809605d26460642892bc4824fefd8721cd4a`. 과거출력보존·두 오류재현/수정·독립결과 보존.
- 현재 등록16/revision1. 최신 읽기전용 배당집계 matched24/mismatched13/partial6/unreviewed68(총111) 확인, 투자자료 인수와 다르다. 별도 KIS 달력조회 HTTP500은 해당 자료 인계 재사용.
- 다음은 기존지표를 재사용하는 동일 입력 KR 기준선·2후보 합성 비교 연결 조사/계획. 이 checkout 재사용 예정. 실제원천/수익성/미래OOS 완료·주문·원격push 없음.
