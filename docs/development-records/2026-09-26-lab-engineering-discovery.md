# 빈 큐의 자동 공학 과제 발굴 복구

- 상태: local main 통합·독립 검토·통합 검사 완료. 운영의 실제 후속 작업 검증 진행 중.
- 작업 slug: `lab-engineering-discovery`
- 기준: `491349c`; 구현: `050dd0e`; 병합 직전 main: `08428fb`; 통합: `9cb75fc`.
- 범위: 기존 READY·독립 구현 검토를 우선하는 자동 실행기에 제한된 오프라인 과제 발굴을 연결한다. 실거래·투자 검증·credential·권한 경계는 변경하지 않는다.

## 원인과 근거

2026-09-25 21:25 KST 이후 journal에 `fixed_engineering_backlog_exhausted`가 166회 기록되었다. timer는 실행됐지만 새로운 제품 attempt나 commit은 없었다. 고정 공학 목록 소진 뒤 일반 planner보다 먼저 반환하며, 기존 planner도 연구 과제만 등록하고 동적 공학 spec을 저장할 경로가 없었다. 단순한 service 재시작이나 고정 과제 한 건 추가로는 원인이 해결되지 않는다.

## 변경과 결정

`automatic_engineering_discovery`를 기본 `false`로 추가한다. 승인된 설치에서는 고정 목록 소진 후 읽기 전용 발굴, 별도 읽기 전용 범위 검토, 결정적 등록, 기존 구현·독립 코드 검토를 이어간다. 정확히 한 개의 허용된 소스·테스트 쌍만 소유하며, 범위 검토 PASS는 개발 허용일 뿐 공학 완료나 투자 검증이 아니다.

기존 task·attempt를 변경하지 않는 추가 테이블에 발굴 단계와 frozen spec을 저장한다. 제안·검토는 main HEAD, 소스 증거 hash, mandate, task snapshot에 결속한다. 같은 의미 입력에서는 서로 다른 후보를 최대 세 건 검토하며, 거절 사유는 다음 발굴에 전달한다. `no_work`나 후보 소진 뒤에는 시각 경과만으로 LLM을 반복 호출하지 않는다. READY 작업이 있으면 이 대기 상태보다 먼저 실행한다.

## 문서·계약 영향

- 운영 계약: `docs/development-runner.md`, `docs/continuous-development-session.md`.
- 구조·역할 경계: `docs/architecture.md`, `docs/autonomous-trading-lab.md`.
- 이전 중단 판단: `2026-09-25-lab-runner-backlog-exhaustion-audit.md`를 역사적 기록으로 보존하고 새 요청의 후속 구현을 연결한다.
- 사용자 API·프런트엔드·브로커 계약은 변경하지 않는다.

## 검증

고정 backlog 소진 상태에서 발굴 dispatch가 누락되는 RED를 먼저 확인했다. 구현 담당자의 관련 runner pytest 164개와 최종 커밋의 발굴 pytest 17개가 통과했다. 변경 파일 Ruff check/format, 소스 3개 strict mypy, `git diff --check`가 통과했다. 변경 테스트의 strict mypy는 기존 imported test의 타입 오류를 분리하기 위해 `--follow-imports=silent`를 사용했다. 최종 통합 검사와 별도 Sol review 결과는 별도로 추가한다. fake CLI 검증과 실제 설치의 Codex 실행 검증은 분리한다.

운영 DB 사전 백업의 별도 복사본 `runner-migration-dry-run.db`에 새 `RunnerStore`를 적용했다. 기존 6개 테이블의 973개 행이 값과 순서까지 동일하고, 새 테이블 4개만 추가됐으며 `PRAGMA integrity_check`는 `ok`다. 원본 운영 DB에 대한 테스트 쓰기는 하지 않았다. 구현 agent의 사전·사후 routing audit는 `code/gpt-6-sol/high`의 실제 child 기록으로 통과했다.

별도 `review/gpt-6-sol/high` 검토에서 확인된 P1/P2 지적은 없었다. reviewer의 실제 child routing audit도 통과했다. 통합 `9cb75fc`에서 discovery/backlog/planning/roadmap/review/recovery pytest **164 passed (41.38s)**, 변경 파일 Ruff check/format, 소스 strict mypy와 변경 테스트의 제한된 import strict mypy가 모두 통과했다. 이 작업에는 프런트엔드 변경이 없어 프런트엔드 build는 실행하지 않았다.

## 안전·운영 상태

수동 수정 전에 roadmap runner를 pause하고 service를 정지했다. timer는 유지한다. tracked main이 깨끗하고 통합 검증이 통과한 뒤 새 설정을 활성화하고 재개한다. 사용자 미추적 `HANDOFF.md`, 기존 실패 시도와 관련 없는 워크트리는 보존한다. 원격 push·실주문·PAPER/live 활성화·추가 결제·Windows 종료는 수행하지 않는다.

2026-09-25T21:30Z 통합 검증 후 설치의 `automatic_engineering_discovery=true`를 적용했다. 기존 `daily_launches=null`, timeout·cooldown·credential·권한 설정은 그대로 유지했다. 이 설정은 사용자 승인된 기존 Codex 개발 호출을 연결하며 추가 유료 서비스를 설치하지 않는다.

## 증거와 복구

- 운영 DB 사전 백업: `/home/kwl/.local/share/jusik/portfolio-audit/20260926-engineering-discovery/runner-before-discovery.db`.
- 백업 integrity: `ok`; SHA-256: `ec3e16f0d05e34eaae3262e53bf64c14c5454c9c19469cdea9722bfc0d1d6fd1`.
- 설정 사전 백업: 같은 audit 디렉터리의 `runner-config-before-discovery.json`; SHA-256: `7a8ecd2c24d8b4581db00a1a54012507259717cae3a37ec1fef1bdb76aa4c211`.
- 구현 워크트리: `/home/kwl/projects/jusik-lab-engineering-discovery`, 브랜치 `feat/lab-engineering-discovery`.
- 복구: 먼저 pause하고 service를 정지한다. 새 발굴만 막으려면 `automatic_engineering_discovery=false`로 되돌린다. 이미 승인된 동적 작업의 spec은 보존하므로 모든 실행 중단에는 pause가 필요하다. DB 전체를 과거 백업으로 덮어써 새 작업 이력을 지우지 않는다. 이전 코드로 되돌리려면 동적 작업을 실행하지 않는 paused 상태를 유지하고 별도 호환성 판단을 한다.
- 남은 수용 조건: 독립 검토, local main 통합, 운영 DB 보존 확인, 실제 자동 발굴·범위 검토·개발 및 다음 발굴의 자동 연결.
