# 공학 실패 출력의 실패 시점 해시

- 상태: 완료
- 기록 시각: 2026-09-25T09:02:26Z
- 작업 slug: `lab-failed-output-digest`
- 기준/통합: `f2cf7be` / `c85a1a5`
- 범위: 향후 `completion_invalid` 공학 시도의 출력 SHA-256을 실패 처리와 함께 기록한다. 기존 legacy 시도는 소급 변경하지 않고 제품·주문·투자 게이트를 보존한다.

## 변경과 결정

- `backend/jusik/development_runner.py`는 새 공학 완료 형식 오류에서 출력 SHA-256을 계산해 실패 기록에 전달한다. 출력이 없거나 읽을 수 없으면 명시적 null marker를 남겨 복구를 거부한다.
- `backend/jusik/development_runner_store.py`는 marker와 첫 새 시도 rowid 경계를 같은 SQLite transaction에 기록한다. 경계 이후 기록을 SQL NULL로 지워도 legacy로 취급하지 않는다. 경계 자체가 누락됐고 새 marker가 존재하면 보수적으로 거부한다.
- 복구 후보 생성, reviewer 전후와 최종 PASS 전이가 동일한 원본 marker identity를 확인한다. `backend/tests/test_development_runner_recovery.py`에 실제 실패 기록과 사후 출력·transcript 변경, marker 삭제, 경계 누락, 기존 legacy 복구를 추가했다.

## 문서·계약 영향

- `docs/development-runner.md`에 신규 실패 해시와 legacy 구분, 한계를 추가했다. DB 테이블 schema migration과 설정 변경은 없다.
- 직접 DB 임의 쓰기로 경계와 모든 marker를 함께 제거하는 공격은 이 범위에서 탐지하지 못한다. DB 자체는 신뢰 경계다.

## 검증

- 구현 워크트리의 runner 인접 pytest 185개 통과, Ruff check/format, 소스 strict mypy 통과. 별도 Sol 검토에서 marker→NULL 우회를 재현해 rowid 경계로 수정한 뒤 최종 PASS, P1/P2 없음.
- local main의 runner·제품 관련 pytest 141개, Ruff check/format, 변경 소스 strict mypy, diff check 통과. 테스트 파일 전체 mypy에는 기존 import된 review 테스트의 타입 오류가 있어 소스 범위 strict 검사를 사용했다.
- 실제 운영에 새 실패를 의도적으로 만들지 않았다. 임시 Git/SQLite로만 검증했다.

## 안전·운영 상태

- 실주문·PAPER/live activation·원격 push·추가 결제·credential/권한 변경 없음. 기록 중 roadmap runner pause·service inactive, timer active이며 tracked main 정리 후 재개한다.
- 기존 복구 완료 운영 DB, 사용자 미추적 `HANDOFF.md`와 다른 worktree를 보존한다.

## 증거와 재개

- 구현 커밋 `cd36e6c`, 경계 보강 `c85a1a5`; 최종 코드의 적용은 이후 새 실패 시도부터다.
- 다음 시작: runner를 재개해 READY/idle 상태를 확인한다. 기존 legacy 시도의 과거 출력 불변성은 여전히 증명하지 않는다.
