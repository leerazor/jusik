# 선정 KR 네 arm 합성 비교

- 상태: 구현·로컬 검증 완료 — 독립 검토·main 통합 대기
- 기록 시각: 2026-10-03T19:38:35Z
- 작업 slug: `selected-kr-comparison-20261004`
- 기준/통합: `67a5cd40bf83b3e395fbd7823358f3b016bf96af` / 없음
- 범위: 동일 KR 합성 입력으로 기존 순수 보유, cap-control, 두 고정 후보 위험 경로를 각 한 번 실행하고 기존 Decimal 지표로 비교한다. raw 원장·후보 정책·설정은 변경하지 않는다.

## 변경과 결정

- `backend/jusik/selected_kr_comparison.py`: 전체 raw·signal 내용, 별도 가격 pin, 등록/cohort/기간, 비용·달력·평가일·무위험률 근거, 설정 및 지표/어댑터 소스 해시를 묶은 호출자 동결 manifest를 요구한다. 불일치는 네 arm 실행 전에 거부한다. 네 원장 결과와 첫 결정/체결 시각을 그대로 반환한다.
- 지표는 공통 명시 UTC 날짜의 마지막 실제 NAV로 수익률/CAGR/Sharpe를 평가하고 모든 phase 순서점을 MDD/Calmar/20% 필터에 사용한다. 없는 날짜를 메우지 않고 5,000점 경계를 지킨다. 무위험률 근거가 없으면 Sharpe만 unavailable이다.
- `market_performance_metrics.py`의 직접 호출에만 동일 순간의 순서 있는 NAV와 `risk_free=None`을 허용하는 선택지를 추가했다. 기본 JSON/저장형 입력 검사는 바꾸지 않는다.
- Supervisor가 필수 pin 연동 범위를 추가 승인했다. `market_performance_calculation_policy_v1.json`의 evaluator SHA를 `d99382b0…`에서 `98b91b80…`으로, `market_performance_policy.py`의 artifact SHA를 `87385ecb…`에서 `f7d1ae4b…`으로 바꿨다. artifact의 다른 모든 필드는 byte 동일하며 정책 수식·상수·Context·안전·historical 범위는 그대로다.

## 문서·계약 영향

- 비교 규약에 네 arm 합성 단계와 manifest, 공통 날짜/전체 chronology, 원천·투자 판정 한계를 기록했다.
- 지표 문서에 직접 호출 선택지와 기본 저장형 계약, source/artifact pin의 동시 갱신을 기록했다.
- 설정 JSON, 실제 원천/비용 승인, API·서비스 계약은 변경하지 않았다.

## 검증

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend backend/.venv/bin/python -m pytest -q -p no:cacheprovider` + 기존 raw·후보·legacy 관련 12파일: 268 통과.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend:backend/tests backend/.venv/bin/python -m pytest -q -p no:cacheprovider` + 새 비교·기존 지표·정책 pin/변조 방어·투영·readiness 5파일: 132 통과. 이전 `evaluator_source_sha_mismatch` 3건이 정상 통과하고 artifact/평가기 변조가 여전히 fail-closed인지 검증했다.
- baseline 3·cap 3·single target 3·batch KR/US 2·KR sequence 전체 직렬화가 `/tmp/selected-kr-policy-code/*-final.json`과 byte 동일. 이전 위험 없는 두 후보 전체 경제 출력은 과거 설정 SHA metadata만 제외하고 동일하다. 현재 full-risk 두 후보 전체 직렬화는 `/tmp/selected-kr-risk-p2-code/risk-fixtures.json`과 동일하다. raw/policy/signal/config SHA는 기준과 동일.
- 신규 네 arm 전체 합성 출력 `/tmp/selected-kr-comparison-code/synthetic-four-arm.json` SHA-256 `d3d18656e792d49818597f3e23ccd5c03c105789271984a45ddffcfe8e396b46`.
- 변경 Python Ruff check·format, strict mypy, `git diff --check` 통과. 실행 명령은 Python 5파일에 scoped Ruff, 모듈 3파일에 `mypy --strict`이다.

## 안전·운영 상태

- 네 arm 검사는 합성 fixture만 사용했다. 네트워크·DB·서비스·credential·주문·PAPER/live·실자료 성과·원격 push 변경 없음. `execution_allowed=false`, `results_observed=false`, `candidate_execution_code_hash=null` 유지. 실제 READY cohort/수익률/투자 적격 판단 없음.

## 증거와 재개

- audit: `/tmp/selected-kr-comparison-code/`; 기존 출력 `/tmp/selected-kr-policy-code/`.
- 남은 작업: 독립 검토·main 통합, 실제 원천/비용·기간 수용과 투자 검증은 별도 단계.
- 다음 시작: 비교 manifest의 실행 전 불일치 거부, 동일 시각 MDD, 정책 pin 연동을 독립 검토한다.

## workflow 평가

- workflow 판단: 도움 됨 — 기존 계획과 원장/지표 계약을 먼저 읽어 비교 어댑터로 변경을 제한했다.
- 근거: 기존 268검사·baseline/cap 직렬화를 재사용했고 평가기 source pin의 추가 경계를 발견했다. 시간·호출 절감은 미측정이다.
- 다음 조정: 수정 — 의미 소스가 고정된 평가기 변경은 계획에서 정책 artifact pin의 소유 범위를 함께 명시한다.
