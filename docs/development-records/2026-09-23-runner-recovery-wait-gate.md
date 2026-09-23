# 로드맵 실행기 자동 복구와 반복 대기 억제

- 상태: 완료
- 기록 시각: 2026-09-23T03:24:00Z
- 작업 slug: `runner-recovery-wait-gate`
- 기준/통합: `11de6f8` / `f55a762`
- 범위: 로드맵 planner의 재판단 입력과 완료된 대기 결과의 명시적 재시도, 기존 제한적 자동 복구의 전용 설치 활성화. 연구 scope, 금융 mandate, PAPER/live 및 주문 경계는 보존한다.

## 변경과 결정

- 로드맵 planner fingerprint는 task snapshot, roadmap SHA, 검증된 mandate digest 및 `main:backend/jusik` tree에 결속한다. UTC 날짜와 무관한 문서 커밋만으로 같은 대기를 다시 호출하지 않는다. 일반 연구 scope의 fingerprint는 유지한다.
- 제안 결과에는 시작 시점 `main` HEAD 검사를 별도로 적용한다. task/attempt/fingerprint identity, task snapshot 및 governance 검증은 유지한다.
- `retry --planning-wait`는 현재 fingerprint와 일치하는 완료된 로드맵 `planning_waiting`만 재큐잉한다. 이전 attempt를 연결하며, 오래된 planner ID와 일반 완료 작업은 거절한다. 외부 근거 변화는 자동 추정하지 않고 근거 확인 후 명시적으로 재시도한다.
- 설치된 roadmap 전용 설정에서 `automatic_recovery=true`로 전환했다. 허용 label과 task당 2회·60/120초 대기 계약은 변경하지 않았다. 이전 설정은 외부 audit에 보존했다.

## 문서·계약 영향

- 운영 문서: `docs/development-runner.md`, `docs/roadmap-automation.md`에 planner 입력·재시도 명령과 자동 복구 범위를 반영했다.
- 사용자 문서·금융 데이터 계약: 해당 없음. UI, 금융 정책 및 데이터 해석을 변경하지 않았다.

## 검증

- 작업 워크트리: runner focused pytest 111 passed, 후속 수정 planning/roadmap 47 passed; Ruff check/format, 변경 모듈 mypy, diff check 통과.
- 독립 Sol 검토: 오래된 waiting planner ID의 거짓 재시도 성공 1건 지적. 후속 수정 `f55a762`와 재검토에서 해결 확인.
- local `main`: runner focused pytest 112 passed, Ruff check/format, 변경 모듈 mypy, diff check 통과.
- 전체 backend mypy: 기존 범위 밖 오류 3건(미사용 `type: ignore` 2건, `torch` stub 누락)으로 미통과. 이번 변경 모듈 검사에는 오류가 없다.

## 안전·운영 상태

- 수동 수정 전 roadmap runner를 pause하고 service inactive, running attempt 0을 확인했다. 전용 설정 이외의 운영 DB·서비스·금융 상태는 변경하지 않았다.
- 통합 후 runner를 재개했다. 최종 `paused=0`, running attempt 0, queued task 0, service inactive, timer active/enabled를 확인했다. 통합된 worktree/branch와 재생성 가능한 환경·캐시는 근거 보존 후 정상 정리했다.
- 실제 주문, PAPER/live 승격, 원격 push, Windows 종료는 수행하지 않았다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260923-runner-recovery-wait`; 설치 설정 이전 사본, `integration-summary.json`, `HANDOFF.md` 참조.
- 남은 작업: 기술 동작의 운영 재현에는 새로운 실제 환경 오류 또는 새 외부 근거가 필요하다. 이를 만들기 위한 인위적 운영 실패는 실행하지 않는다.
- 다음 시작: audit `HANDOFF.md`와 운영 DB의 최신 planner 상태를 읽고, 같은 자료 부족을 재시도하지 말고 다음 독립 작업을 고른다.
