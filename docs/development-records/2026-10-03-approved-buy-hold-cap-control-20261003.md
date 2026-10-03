# 승인 종목 cap-control 합성 회계 기준선

- 상태: 구현·로컬 검증 완료, 독립 검토·supervisor 통합 대기
- 기록 시각: 2026-10-03T13:21:29Z
- 작업 slug: `approved-buy-hold-cap-control-20261003`
- 기준/통합: `5b3cab0` / 없음
- 범위: 순수 보유의 공개 입력·출력·실패 계약을 보존하고 동일 회계 사건 코어에 합성 cap-control만 추가했다. 실제 자료 인수, 성과 비교, 주문·서비스 연결은 하지 않았다.

## 변경과 결정

- `backend/jusik/approved_universe_buy_hold.py`: 기존 공개 함수를 비공개 공유 코어의 래퍼로 분리했다. 이전 출력의 전체 dataclass 직렬화 SHA-256은 `15202e55dad65a04637efe619cb524823f74f5003a14d6253cfc728833f102fd`이며 리팩터링 직후·최종 상태에서 같은 fixture의 전체 출력이 일치했다.
- 새 `run_cap_control_reference`와 `SellCostAssumptions`, `CapControlReference`, 매도·조정 시도 기록을 추가했다. 관측된 과거 위반만 다음 적격 공식 시가에서 조정한다. 동시 기업행동과 전 종목 가격 갱신을 먼저 반영하고, 외부 평가점은 조정 뒤 하나만 기록한다. 개장 갭의 조정 전후 노출은 매도·시도에 별도로 남긴다.
- 매도는 최소 정수 수량, KR/US별 명시 비용과 명목금액 세금 가정, 비례 원가 감소, 기존 배당 권리 보존, USD 현금 유지로 제한했다. 자연 회복·부분 해소·기간 종료 미체결을 구분한다.
- `backend/tests/test_approved_universe_cap_control.py`: 독립 1%/2% 손계산 oracle, 1주 적은 수량 실패, 엄격한 다음 개장, 동시 종가, 분할·배당, FX 가용시각, 다종목 순서, 미체결·부분 해소 및 비용 거부를 합성 fixture로 검증했다.

## 문서·계약 영향

- 사용자·연구 문서: `docs/research.md`의 입력·산식·출력 계약과 `docs/research/approved-universe-comparison-protocol-v1.md`의 현재 구현 단계를 갱신했다.
- 운영 문서: 해당 없음. 서비스·DB·실행기 계약 변경이 없다.
- API·설정·데이터 계약: Python 순수 함수의 신규 입력·결과형만 추가했고 기존 공개 dataclass와 함수 시그니처는 보존했다.

## 검증

- 변경 전 `pytest` 기존 buy-hold 및 기업행동 67개 통과. 공유 코어 추출 직후 같은 67개 및 전체 직렬화 동일성 통과.
- 최종 `PYTHONPATH=backend backend/.venv/bin/python -m pytest -q backend/tests/test_approved_universe_cap_control.py backend/tests/test_approved_universe_buy_hold.py backend/tests/test_market_history_action_accounting.py` — 81개 통과.
- `backend/.venv/bin/ruff check`와 `ruff format --check` 대상 구현·신규 테스트 — 통과.
- `PYTHONPATH=backend backend/.venv/bin/python -m mypy --strict` 대상 구현·신규 테스트 — 통과.
- 최종 기존 fixture의 전체 직렬화 출력 — 원본과 바이트 동일. `git diff --check` — 통과.
- 실행하지 않은 검사: 실제 원천 자료 acceptance·성과·주문·서비스 테스트는 이 작업 범위가 아니다.

## 안전·운영 상태

- PAPER/실주문, 서비스, DB, 외부 네트워크, 배포, 원격 push와 권한 변경 없음.

## 증거와 재개

- 독립 손계산 입력: `/tmp/buyhold-cap-independent-expected.json`; 이전 전체 출력: `/tmp/buyhold-cap-old-output.json`. 둘 다 합성 자료이며 저장소 외부 보조 근거다.
- 남은 작업: 독립 검토 및 supervisor의 로컬 `main` 통합·통합 검증·등록부와 handoff 갱신. 투자 적격성은 `not_evaluated`다.
- 다음 시작: 현재 작업 브랜치의 diff와 위 검증 근거를 독립 검토한 뒤 supervisor가 통합 여부를 결정한다.

## workflow 평가

- workflow 판단: 도움 됨 — 기존 탐색·계획 결과와 67개 검사를 재사용해 구조 변경과 기능 변경의 회귀 범위를 분리했다.
- 근거: 이전 출력 전체 비교 2회, 기존 67개 및 신규 14개 통과. 첫 신규 검사에서 손계산 기대 수량과 합성 부분 해소 fixture 설정 오류를 발견해 바로 수정했다.
- 비용 절감 효과: 비교 자료가 없어 미측정.
