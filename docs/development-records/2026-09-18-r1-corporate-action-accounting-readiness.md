# R1 기업행사 회계 준비도

- 상태: 차단
- 기록 시각: 2026-09-17T19:25:00Z
- 작업 slug: `r1-corporate-action-accounting-readiness`
- 기준/통합: `0977adf10da4720b63fdc574647988c729efd5bc` / 없음
- 범위: 현재 고정 action 자료, 공통 모델, 수집기, 순수 회계 엔진과 기존 artifact adapter를 읽기 전용으로 대조했습니다. 코드·테스트·운영 상태는 변경하지 않았습니다.

## 변경과 결정

- 공통 action 모델은 split/delisting/halt만 표현하며 dividend, ex/effective/pay 경계와 권리수량이 없습니다.
- 별도 action collector는 dividend amount/currency와 vendor date를 보존하지만 지급일·권리경계·확정 보유수량을 제공하지 않습니다.
- 기존 `market_history_action_accounting.py`는 split ratio/currency와 dividend effective/payment/amount/currency/entitled quantity, raw basis, action identity·semantic hash를 명시적으로 요구하고 누락·중복·충돌을 fail-closed 처리합니다.
- 기존 artifact adapter도 coverage incomplete와 economic not-evaluated를 고정합니다. 추가 wrapper는 사실을 늘리지 않으므로 구현하지 않습니다.

## 문서·계약 영향

- 사용자·운영·API 문서 변경 없음. 이 개발 기록과 작업 등록부에 차단 결정만 남깁니다.
- `R1-04` checkbox, frozen R0 artifact, strategy/result/readiness 계약은 변경하지 않았습니다.

## 검증

- 관련 모델·collector·accounting·artifact·frozen readiness를 `rg`, `nl`, JSON 구조 확인으로 읽었습니다.
- 테스트·lint·mypy는 코드 변경이 없어 실행하지 않았습니다.
- network·research·DB·service·runner·PAPER/live·주문은 실행하지 않았습니다.

## 안전·운영 상태

- 실제 action 금액·지급일·권리수량을 합성하지 않았고 provider vendor date를 지급일로 재해석하지 않았습니다.

## 증거와 재개

- 기존 기술 근거: `docs/market-history-action-artifact.md`, `backend/jusik/market_history_action_accounting.py`, `backend/jusik/market_history_action_artifact.py`.
- 재개 조건: 원문 SHA·관측시각과 연결된 stable action identity, split ratio/raw 전후 가격, dividend 금액·통화·유효/지급 UTC, 권리 경계의 확정 보유수량과 체결 순서.
- 다음 시작: 이후 추가된 R0 session/cost evidence를 기존 R2 NAV reconciliation에 canonical 한정으로 연결합니다.
