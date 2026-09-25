# Lifecycle receipt 현재 revision DB guard

- 상태: 완료
- 기록 시각: 2026-09-25T12:19:51Z
- 작업 slug: `lab-lifecycle-receipt-revision-guard-v1`
- 기준/통합: `891cfdc` / `9926ebb`
- 범위: 오프라인 receipt 신규 SQL INSERT의 현재 전략 revision 일치를 DB에서 강제한다. 기존 receipt·전략 전이·투자 검증·주문 게이트는 유지한다.

## 변경과 결정

- 조사에서 `record()`는 현재 revision을 검사하지만 직접 SQL INSERT는 과거·미래 revision을 넣을 수 있음을 확인했다. receipt는 증거 identity만 담아 수명주기 전이의 충분조건이 아니므로 `RESEARCHING → BACKTESTED` 같은 전이는 추가하지 않았다.
- `backend/jusik/development_runner_contract.py`에 다섯 번째 고정 공학 spec을 등록했다(`c6d848c`). 별도 Sol spec review PASS 후 자동 runner가 `backend/jusik/strategy_lifecycle_receipt.py`에 `BEFORE INSERT` guard를 추가했다(`c8ef92c`). 존재하는 strategy ID·version의 현재 revision과 정확히 일치해야 하며 외래키 설정을 끈 연결에도 적용된다.
- `backend/tests/test_strategy_lifecycle_receipt.py`는 누락·잘못된 버전·과거·미래 revision의 직접 삽입 거부, 현재 revision 허용, 기존 행 보존, 실패 후 receipt/state/event 불변, API 회귀와 writer-lock 충돌을 검사한다. 자동 reviewer PASS 뒤 서식만 수정한 `9926ebb`는 AST 동일을 확인했고 최종 파일도 별도 Sol 검토 PASS를 받았다.

## 문서·계약 영향

- `docs/development-runner.md`의 고정 backlog 수를 다섯으로 갱신했다. `docs/autonomous-trading-lab.md`는 receipt가 identity만 증명하고 전이를 승인하지 않는 경계를 명시했다.
- 기존 DB는 receipt store 초기화 시 `CREATE TRIGGER IF NOT EXISTS`로 guard가 설치된다. 기존 행은 수정·삭제·소급 검증하지 않는다. 동일 DB의 구버전 코드로 돌아가도 트리거는 남아 신규 직접 INSERT를 계속 제한한다. DDL 권한을 가진 동일 사용자나 증거 출처·진위는 이 guard의 범위 밖이다.

## 검증

- 자동 spec: backlog pytest 33개, Ruff 및 지정 파일 strict mypy 통과. 일반 strict mypy가 import하는 변경되지 않은 roadmap 테스트의 기존 타입 오류 8개는 별개다.
- 최종 main: `PYTHONDONTWRITEBYTECODE=1 backend/.venv/bin/python -m pytest -q -p no:cacheprovider backend/tests/test_strategy_lifecycle_receipt.py backend/tests/test_strategy_lifecycle.py` — 35 passed. 제품 두 파일 Ruff check/format과 strict mypy 통과; `git diff --check` 및 독립 Sol 최종 검토 PASS.
- 실제 브로커·KIS 모의투자·투자 수익률 검증은 실행하지 않았다.

## 안전·운영 상태

- 실주문·PAPER/live activation·추가 결제·권한/credential 변경·원격 push 없음. runner는 tracked main 문서 편집 중 pause, service inactive, timer active이며 문서 커밋 후 resume한다. 사용자 미추적 `HANDOFF.md`는 보존했다.

## 증거와 재개

- 운영 task `lab-lifecycle-receipt-revision-guard-v1`은 첫 자동 시도 후 reviewer PASS로 `DONE/ENGINEERING_COMPLETE/NOT_EVALUATED`; 투자 판정은 여전히 미평가다.
- 남은 작업: 실제 전이에는 category·provenance·검증 결과·원자적 정책이 필요하다. 이를 정하지 않고 현재 receipt 존재만으로 전이를 열지 않는다. 다음 독립 공학 작업은 READY 상태와 기존 코드의 재현 가능한 갭을 먼저 확인한다.
