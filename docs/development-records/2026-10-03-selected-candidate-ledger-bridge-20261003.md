# 선정 후보 단일 target 합성 회계 연결

- 상태: 단일 target 합성 단계 구현·로컬 검증 완료, 독립 검토·supervisor 통합 대기
- 기록 시각: 2026-10-03T15:09:49Z
- 작업 slug: `selected-candidate-ledger-bridge-20261003`
- 기준/통합: `c20c31161a24642ebe40c84293083fbda7ab54a4` / 없음
- 범위: 하나의 외부 주입 목표를 동일 raw 회계 코어의 최초 매수 한 건에만 연결했다. 후보 신호·전체 실행·실제 성과·주문은 포함하지 않는다.

## 변경과 결정

- `backend/jusik/approved_universe_buy_hold.py`: `TargetInstruction`의 등록 identity, 결정시각, 0~20% 목표를 검증하고 `run_target_bridge_reference`를 추가했다. 기존 사건 루프에서 결정 후 첫 공식 시가만 대상이며 동시 시가에서는 사지 않는다. 기존 매수 비용·FX·현금·원가 전이를 작은 비공개 함수로 공유하고 NAV 차감 후 목표 비중을 재검증한다. 목표 0, 한 주 불가, 기간 종료까지 적격 개장 부재는 명시 상태다. 미보유 종목의 기업행동·가격 이벤트는 보유·권리를 만들지 않는다.
- `backend/tests/test_approved_universe_target_bridge.py`: KR 독립 손계산 199,600주·현금 79,840,400원·NAV 99,800,400원, 1주 추가 초과, 동시 시가 제외, 다른 미보유 종목 사건, 매수 전 ex, 보유 후 분할→ex→지급·원천징수, US 환전 spread로 정수 수량이 달라지는 경계·미래 FX 배제, 명시 미체결과 identity·비용·raw basis 거부를 검증한다.
- 기존 순수 보유·cap-control 공개 dataclass와 함수 시그니처, 평가 결과·위반 이력은 변경하지 않았다.

## 문서·계약 영향

- `docs/research/approved-universe-comparison-protocol-v1.md`: 합성 단일 target 단계의 범위와 SMA·두 후보 전체 실행이 아직 없는 점을 명시했다.
- `docs/research/selected-candidate-config-v1.json`: raw 코어 semantic SHA-256만 `6a03e12948c079d7353d6099e9a338cf80c300e82074ece54981a1ed5f317bbd`에서 `50eaac00df0f3a213f1beb1d5616e07d88876f2ba68299583d8721fae0a54b53`로 갱신했다. 다른 세 source hash 및 `candidate_execution_code_hash=null`, `execution_allowed=false`, `results_observed=false`는 유지했다. 과거 관측 결과를 재결속하지 않았다.
- 운영·서비스 계약: 변경 없음.

## 검증

- 변경 전 `/tmp/buyhold-baseline-compat.py`의 기존 기준선 세 fixture 전체 직렬화 SHA-256 `930b79ab749421fad20bc220e5eeef7c114ef9e7a923e9e5d4a7286dde72d9fc`; `/tmp/cap-control-before-target.json`의 KR1%·KR2%·US 세 사례 SHA-256 `90a70498db03492a0ba91a47aeeecbe5e75552d89b9e64938fc01e81c4b535ee`. 매수 전이 추출 직후와 target 연결 후에도 전부 바이트 동일했다.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend backend/.venv/bin/python -m pytest -q -p no:cacheprovider backend/tests/test_approved_universe_target_bridge.py backend/tests/test_approved_universe_buy_hold.py backend/tests/test_approved_universe_cap_control.py backend/tests/test_market_history_action_accounting.py` — 기존 83개와 신규 15개, 총 98개 통과.
- 구현·신규 테스트 Ruff check/format 및 strict mypy — 통과.
- `/tmp/selected-target-bridge-code/independent_oracle.py` — 별도 합성 fixture로 199,600주·현금 79,840,400원·NAV 99,800,400원과 1주 추가 초과를 대조했다.
- 실행하지 않은 검사: 실제 자료 수용, 후보 전체 실행·성과, 서비스·주문 경로는 이 단계의 대상이 아니다.

## 안전·운영 상태

- 운영 DB, 네트워크, runner, 서비스, PAPER/실주문, 원천 파일, 실제 성과 실험, 원격 push 변경 없음. 비교 JSON·테스트는 합성 전용이다.

## 증거와 재개

- 재현 산출물: `/tmp/selected-target-bridge-code/`에 기준선·cap-control 직렬화 비교와 독립 oracle 스크립트를 보관한다.
- 남은 작업: 독립 코드 검토, supervisor의 로컬 통합·검증. 그 다음 단계에서만 provenance가 확인된 완료 조정종가 신호를 순수 target planner로 계산하고, 다종목·재조정과 위험 episode를 별도로 검증한다.
- 다음 시작: 이 브랜치 diff, 98개 검사, 사전 고정 출력 비교 및 설정 hash를 재확인한다.

## workflow 평가

- workflow 판단: 도움 됨 — 기존 원장과 사건 루프를 재사용하고 첫 단일 체결에서 멈춰 중복 원장과 조기 성과 주장을 피했다.
- 근거: 구조 변경 직후 83개 회귀와 전체 출력 비교를 먼저 통과한 뒤 기능 테스트를 추가했다. 호출·비용 절감량은 미측정이다.
- 비용 절감 효과: 비교 자료가 없어 미측정.
