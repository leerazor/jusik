# Autonomous lab 독립 검토와 오프라인 실행 계약

- 상태: 로컬 main 통합·focused 검증 완료; 실제 reviewer 운영 smoke와 투자 검증은 미완료
- 기록 시각: 2026-09-25 UTC
- 작업 slug: `lab-independent-review-receipt`
- 기준/통합: `3a9ec25` / `d7e7c7c`
- 범위: 공학 후보의 독립 검토·완료 판정과 이미 생성된 fake-broker 계약의 독립 수정·통합. 실제 주문, PAPER activation, 투자 성과 판정은 제외한다.

## 변경과 결정

- `development_runner.py`, `development_runner_store.py`, `development_runner_review.py`, `development_runner_contract.py`: 구현 child의 자기 보고 PASS를 공학 완료로 수용하지 않는다. 새 후보는 `WAITING_EXTERNAL`에 기록한 뒤 별도 읽기 전용·network-disabled reviewer attempt를 최대 2회 실행한다. task/구현 attempt/시작 HEAD/현재 main HEAD/두 소유 파일 hash가 맞는 PASS receipt만 같은 DB transaction에서 `DONE + ENGINEERING_COMPLETE + NOT_EVALUATED`로 확정한다. 과거 후보/차단 attempt는 소급 승격하지 않는다.
- 재시작 시 reviewer PID·PGID·Linux `/proc` 시작 시각을 대조한다. 정체 불명 또는 종료 확인 실패는 무관 프로세스에 signal을 보내지 않고 해당 review만 `quarantined`로 기록하며 독립 READY는 진행한다. reviewer 자식 환경은 허용 목록과 전용 cache/tmp로 제한한다. 실제 동일 사용자 권한의 완전한 비밀 격리를 보장하지는 않는다.
- `paper_execution_contract.py`와 테스트: 오프라인 fake-broker 계약을 통합했다. 첫 독립 검토에서 취소 후 늦은 체결, Decimal 반올림 과체결, 취소 응답 손실 중복 호출을 발견했다. 두 번째 검토의 취소 후 전량 체결·상태 회귀도 수정했고 최종 Sol 검토 PASS를 받았다. 재시작 간 원장 영속성·실제 브로커 호출은 이 코드의 보장 범위가 아니다.
- 통합 SHA: reviewer 경로 `f954568`, 오프라인 계약 merge `d7e7c7c`. 사용자 소유 미추적 `HANDOFF.md`와 다른 worktree는 보존했다.

## 문서·계약 영향

- 운영 문서 `docs/development-runner.md`와 설계 `docs/autonomous-trading-lab.md`에 구현/미검증 경계를 반영했다. 구조 단위 추가는 기존 runner 내부 모듈이므로 `docs/architecture.md` 지도는 유지한다.
- API·연구 mandate·투자 로드맵·PAPER/live 설정은 변경하지 않았다.

## 검증

- reviewer 작업 브랜치: 신규 RED 5건 확인 후 관련 pytest 145 passed, Ruff check/format, strict mypy, diff check 통과. 별도 Sol 검토는 초기 P1/P2를 재현·수정시킨 뒤 최신 `f954568`에 PASS.
- 오프라인 계약 브랜치: 최종 pytest 18 passed, Ruff check/format, strict mypy, diff check 통과. 별도 Sol 검토 PASS.
- local main 통합: 관련 runner·paper·lifecycle pytest 179 passed; 변경 Python Ruff check/format, strict mypy 5개 source, diff check 통과.
- 운영 DB 추가형 적용 전 private SQLite backup을 만들고 적용 후 기존 `tasks` 134행·`attempts` 190행의 ID/상태/시도 횟수·최근 시도 및 실패 코드가 동일함을 확인했다. `review_attempts` 테이블 존재를 확인했다. 백업은 `/home/kwl/.local/share/jusik/portfolio-audit/20260925-review-migration-dZEK3P/runner-before.db`이며 mode 0600이다. 롤백이 필요하면 runner를 pause·service inactive로 만든 뒤 이 백업을 기준으로 검토한다. 자동 복원이나 데이터 삭제는 하지 않았다.
- 실제 Codex reviewer 호출, 장시간 살아 있는 프로세스/PGID 재사용 운영 실험, 전체 backend suite, 실측 자료 투자 검증은 수행하지 않았다. 기존 전체 suite의 frozen replay 실패 2건이 해결됐다고 주장하지 않는다.

## 안전·운영 상태

- 수동 변경 전에 roadmap runner를 pause하고 service inactive를 확인했다. timer는 active로 유지했다. 운영 DB·실제 주문·외부 서비스·원격 push·Windows 종료는 변경하지 않았다.
- 기존 `lab-paper-execution-contract-v1` 운영 task는 `independent_review_unavailable` 차단 상태다. 그 attempt는 새 reviewer 후보 형식이 아니므로 자동 완료하지 않는다. 코드의 수동 통합 완료와 운영 task 완료 판정은 분리한다.

## 증거와 재개

- 독립 review 두 개의 보고와 구현 커밋은 이 작업의 Git/worktree 기록을 따른다. 큰 원시 로그나 비밀값은 문서에 복사하지 않는다.
- 다음: 문서 커밋과 clean main 확인 뒤 roadmap runner를 재개하고 서비스/timer 상태를 확인한다. 실제 Codex reviewer 운영 smoke는 별도 새 후보와 격리된 조건에서만 수행한다. lifecycle receipt adapter는 다음 독립 READY 개발 과제로 등록한다.
