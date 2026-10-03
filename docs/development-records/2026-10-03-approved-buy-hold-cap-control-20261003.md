# 승인 종목 cap-control 합성 회계 기준선

- 상태: 독립 검토 P1 수정·로컬 재검증 완료, 재검토·supervisor 통합 대기
- 기록 시각: 2026-10-03T13:35:50Z
- 작업 slug: `approved-buy-hold-cap-control-20261003`
- 기준/통합: `5b3cab0` / `de9153d`
- 범위: 순수 보유의 공개 입력·출력·실패 계약을 보존하고 동일 회계 사건 코어에 합성 cap-control만 추가했다. 실제 자료 인수, 성과 비교, 주문·서비스 연결은 하지 않았다.

## 변경과 결정

- `backend/jusik/approved_universe_buy_hold.py`: 기존 공개 함수를 비공개 공유 코어의 래퍼로 분리했다. 이전 출력의 전체 dataclass 직렬화 SHA-256은 `15202e55dad65a04637efe619cb524823f74f5003a14d6253cfc728833f102fd`이며 리팩터링 직후·최종 상태에서 같은 fixture의 전체 출력이 일치했다.
- 새 `run_cap_control_reference`와 `SellCostAssumptions`, `CapControlReference`, 매도·조정 시도 기록을 추가했다. 관측된 과거 위반만 다음 적격 공식 시가에서 조정한다. 동시 기업행동과 전 종목 가격 갱신을 먼저 반영하고, 외부 평가점은 조정 뒤 하나만 기록한다. 개장 갭의 조정 전후 노출은 매도·시도에 별도로 남긴다.
- 매도는 최소 정수 수량, KR/US별 명시 비용과 명목금액 세금 가정, 비례 원가 감소, 기존 배당 권리 보존, USD 현금 유지로 제한했다. 자연 회복·부분 해소·기간 종료 미체결을 구분한다.
- `backend/tests/test_approved_universe_cap_control.py`: 독립 1%/2% 손계산 oracle, 1주 적은 수량 실패, 엄격한 다음 개장, 동시 종가, 분할·배당, FX 가용시각, 다종목 순서, 미체결·부분 해소 및 비용 거부를 합성 fixture로 검증했다.
- 동결 커밋 `c5054e7`의 독립 검토에서 적격 개장 없는 평가점의 자연 회복 뒤에도 옛 매도 대기가 남는 P1을 확인했다. 모든 최종 평가점과 평가 종료점에서 비중이 상한 이내면 `natural_recovery`로 대기를 종료한다. 이후 새 초과는 새 관측시각부터 대기한다. 상한 20%, 기존 매도 산식과 과거 위반 이력은 변경하지 않았다.

## 문서·계약 영향

- 사용자·연구 문서: `docs/research.md`와 `docs/research/approved-universe-comparison-protocol-v1.md`에 적격 개장 없는 회복·새 위반 대기·종료시각의 상태 계약을 명시했다.
- 운영 문서: 해당 없음. 서비스·DB·실행기 계약 변경이 없다.
- API·설정·데이터 계약: Python 순수 함수의 신규 입력·결과형만 추가했고 기존 공개 dataclass와 함수 시그니처는 보존했다.

## 검증

- 변경 전 `pytest` 기존 buy-hold 및 기업행동 67개 통과. 공유 코어 추출 직후 같은 67개 및 전체 직렬화 동일성 통과.
- 리뷰 P1 재현: 수정 전 새 집중 테스트 2개 실패. 비개장 회복 뒤 다음 개장의 새 위반을 같은 시각에 매도했고, 회복한 종료 상태를 미체결로 기록했다.
- 최종 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend backend/.venv/bin/python -m pytest -q -p no:cacheprovider backend/tests/test_approved_universe_cap_control.py backend/tests/test_approved_universe_buy_hold.py backend/tests/test_market_history_action_accounting.py` — 83개 통과.
- `backend/.venv/bin/ruff check`와 `ruff format --check` 대상 구현·신규 테스트 — 통과.
- `PYTHONPATH=backend backend/.venv/bin/python -m mypy --strict` 대상 구현·신규 테스트 — 통과.
- 독립 `/tmp/buyhold-cap-independent-oracle.py backend` — KR 1% 매도 80,161주·NAV 119,839,678원, US 매도 81주·USD 현금 16,038 및 NAV 119,838,000원 일치.
- `/tmp/buyhold-baseline-compat.py . /tmp/buyhold-cap-recovery-baseline-after.json` — 기존 세 fixture 전체 직렬화 출력 SHA-256 `930b79ab749421fad20bc220e5eeef7c114ef9e7a923e9e5d4a7286dde72d9fc`로 리뷰 전과 동일. `git diff --check` — 통과.
- 실행하지 않은 검사: 실제 원천 자료 acceptance·성과·주문·서비스 테스트는 이 작업 범위가 아니다.

## 안전·운영 상태

- PAPER/실주문, 서비스, DB, 외부 네트워크, 배포, 원격 push와 권한 변경 없음.

## 증거와 재개

- 독립 손계산 입력: `/tmp/buyhold-cap-independent-expected.json`; 이전 전체 출력: `/tmp/buyhold-cap-old-output.json`; 독립 리뷰: `/tmp/buyhold-cap-review-result.txt`. 모두 합성 자료이며 저장소 외부 보조 근거다.
- 남은 작업: P1 수정의 독립 재검토 및 supervisor의 로컬 `main` 통합·통합 검증·등록부와 handoff 갱신. 투자 적격성은 `not_evaluated`다.
- 다음 시작: 현재 작업 브랜치의 diff와 위 검증 근거를 독립 검토한 뒤 supervisor가 통합 여부를 결정한다.

## workflow 평가

- workflow 판단: 도움 됨 — 기존 탐색·계획 결과와 67개 검사를 재사용해 구조 변경과 기능 변경의 회귀 범위를 분리했다.
- 근거: 이전 출력 전체 비교, 기존 67개 및 신규 16개 통과. 독립 검토에서 발견한 대기 상태 결함을 새 회귀 2개로 재현하고 수정했다.
- 비용 절감 효과: 비교 자료가 없어 미측정.

## 독립 검토·통합 결과

- 최초 c5054e7의 P1: 적격 개장이 없는 평가점에서 비중이 회복해도 이전 대기가 남았다. 7fab35e에서 모든 최종 평가점의 자연 회복으로 대기를 종료하고, 새 위반은 새 시각부터 대기하도록 수정했다. 종료시각 FX 회복도 검증했다. 과거 위반 이력과20% 상한은 보존했다.
- 독립 Sol/high 재검토 PASS 후 main `de9153d` 통합. main83개 pytest·Ruff check/format·strict mypy·KR/US 독립 oracle PASS. baseline3입력 전체출력 SHA `930b79ab749421fad20bc220e5eeef7c114ef9e7a923e9e5d4a7286dde72d9fc` 동일. 위 초기 개발 완료 당시의 통합 대기는 이 결과로 해소됐다.
- 영구 audit `/home/kwl/.local/share/jusik/portfolio-audit/20261003-buyhold-cap-control/`: 최초/최종 검토, 독립 산식, 전체출력과 status/manifest 보존. native agent 세션 한도 때문에 중앙 선택을 명시한 기존 단일 CLI 구현/검토 세션을 재개했으며, 실제 turn_context Sol/high 확인. native helper parent-link 검증으로 보고하지 않는다.
- 서비스·DB·주문·PAPER/live·원격push 변경 없음. 실제 투자 성과는 `not_evaluated`. 다음은 등록종목 실제 원주가 자료 인수와 비용/배당 보완.
