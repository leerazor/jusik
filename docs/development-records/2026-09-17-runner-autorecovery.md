# 2026-09-17 runner auto-recovery

지속 개발 실행기의 재시작 정체와 scope별 planning cap을 보완했다. `RunnerConfig.automatic_recovery`는 기본적으로 꺼져 있으며 설치 설정이 켠 경우에만 명시된 recovery marker를 처리한다.

## 변경

- roadmap planning enqueue cap은 `queued`와 `running`만 계산한다. research scope의 기존 pending 계산은 보존한다.
- planner와 child Popen은 다섯 개 cache 변수를 현재 private attempt 하위로 제한한다. `HOME`, `CODEX_HOME`, 전역 설정은 변경하지 않는다.
- completion의 nullable `recovery_kind`는 legacy 생략을 `None`으로 읽는다. `environment`의 고정 환경 label 또는 고정 implementation defect/review label만 최대 두 번(60/120초) 자동 재시도한다.
- terminal attempt, retry 예약, previous attempt 연결, history outbox를 하나의 SQLite transaction으로 기록해 재시작 crash window를 없앴다. 과거 attempt와 실패 label은 보존한다.
- planner의 correctable output/schema/length failure만 안전한 label로 다음 prompt에 전달한다. 종료 코드, identity/hash/stale, missing data, policy와 permission 변경은 자동 재시도 대상이 아니다.

## 검증

격리된 `backend/.venv-r2`의 Python 3.13에서 fake child와 임시 SQLite를 사용해 runner, planning, roadmap focused tests를 실행했다. 실제 Codex, service, network data collection, brokerage order는 실행하지 않았다. 자동 recovery attempt는 매번 completion의 tests/review 계약을 다시 검증한다.
