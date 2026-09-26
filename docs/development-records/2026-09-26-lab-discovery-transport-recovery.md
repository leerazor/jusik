# 자동 발굴 호출 장애 복구와 지침 검증

- 상태: 구현·독립 검토·local main 통합 검증 완료. 운영 재개 결과는 아래 외부 RUNTIME에 기록한다.
- 작업 slug: `lab-discovery-transport-recovery`
- 기준/통합: `9562a63` / `0578faf`.
- 범위: discovery/scope 호출 실패의 분류와 지속 가능한 예약 재시도, 관련 지침과 회귀 테스트. 제품 전략·투자 검증·주문은 바꾸지 않는다.

## 원인과 확인한 사실

자동개발은 전혀 실행되지 않은 것이 아니다. 제품 `7a65b6f`의 구현과 독립 review가
완료된 뒤 capacity 오류와 401을 동일한 infra 실패로 두 번 누적하여 discovery cycle을
terminal로 처리했다. 이 상태에서는 같은 source fingerprint로 재개하지 않아 공급자
호출이 복구되어도 발굴이 멈췄다. 호출 실패는 작업 소진의 증거가 아니다.

저장된 ChatGPT 로그인 상태와 동일한 Sol/high·읽기 전용 설정으로 보낸 제한된
실제 Codex probe가 성공했다. 현재 인증 변경이 필요하다는 근거는 없다. 과거 401의
공급자 내부 원인은 확인하지 못했으며 잘못된 사용자 API key라고 단정하지 않는다.
비밀값·인증 파일 본문·원시 오류는 이 기록에 저장하지 않는다.

## 지침 감사와 결정

`AGENTS.md`와 연속 개발 정책에는 독립 READY 진행 규칙이 있었지만, 호출 오류와
정상적인 `no_work`의 재개 조건이 구분되지 않았다. 실행 코드의 두 번 실패 후 영구
종료가 지속 개발 의도와 충돌했다. 단순히 “계속하라”는 문구를 추가하는 대신 다음을
구현·테스트한다.

- 알려진 일시 오류만 5분→15분→60분 간격, 401은 6시간 간격으로 예약한다.
- 원문 대신 제한된 오류 종류·횟수·UTC 재시도 시각을 저장한다.
- pause·quota·identity·process ownership 검사를 유지하고 READY와 구현 review를 우선한다.
- 명시적인 no_work, 무효 결과, 미분류 오류, 무결성 문제의 기존 유한 종료를 보존한다.
- 과거 terminal·attempt·승인된 frozen spec을 수정하지 않는다. 새 코드 fingerprint로 재개한다.

모델 역할 설정은 조사 Luna/medium, 계획·복잡한 구현·독립 검토 Sol/high이며 이번 수정에
새 상주 agent나 Astra는 필요하지 않다. planner 포함 active 최대 4명과 단일 코드 소유를
유지한다. 구현은 별도 worktree, root는 문서와 운영 통합을 담당한다.

## 문서·계약 영향

- `AGENTS.md`: 대기 진단 시 읽을 canonical 정책과 실행 증명 의무를 연결한다.
- `docs/continuous-development-session.md`: 호출 실패와 작업 소진을 구별한다.
- `docs/development-runner.md`: discovery 전용 지연 재시도와 기존 실패 종료의 경계를 설명한다.
- SQLite: discovery cycle에 nullable retry 정보와 기본값이 있는 횟수 필드를 가산한다.
  기존 데이터 보존과 새 버전 재시작을 테스트한다. rollback은 runner를 pause한 뒤 코드
  revert와 검증으로 처리하며 운영 DB를 과거 백업으로 덮어쓰지 않는다.

## 검증

- 같은 설정의 실제 읽기 전용 Codex probe: exit 0, 유효한 `{"ok":true}` 응답.
- 수정 커밋 `2befc7a`에서 discovery pytest 37개, runner 관련 7개 파일 pytest 254개,
  Ruff check·format, 소스 3개와 테스트 1개의 strict mypy, diff check를 통과했다.
  후속 `6a4cca2`의 독립 review PASS와 main 통합 검증을 완료했다.
- 독립 code review는 pause·invalid-output 경로에서도 잔존 process group을 확인하도록
  P2를 제기했다. 동일 구현 담당자가 `6a4cca2`에서 수정하고 두 RED/GREEN 회귀를 추가했다.
  별도 reviewer의 최종 discovery 39개·Ruff 검사와 P2 closure는 PASS다.
- main `0578faf`에서 `python -m pytest tests/test_development_runner*.py -q`에 해당하는
  7개 명시 파일 검사: **256 passed (64.99s)**. 수정 세 파일 Ruff check·format, 소스
  runner/store/discovery의 `mypy --strict`, 수정 테스트의
  `mypy --strict --follow-imports=silent`가 통과했다.
- 제한: 테스트 import까지 포함한 일반 strict mypy는 변경하지 않은
  `test_development_runner_roadmap.py`의 기존 오류 8개로 실패했다. 이전 개발 기록과 같은
  focused import 정책을 적용했으며 전체 타입 검사 통과로 주장하지 않는다.
- 실제 운영 백업의 전용 복사본 `migration-validation.db`에 새 RunnerStore migration을
  적용했다. 기존 10개 테이블의 모든 기존 열·행이 동일하고 새 retry 필드 3개가 생성됐으며
  integrity `ok`다. 운영 원본 DB에는 이 검증을 수행하지 않았다.
- 새 회귀는 기존 cycle에 `transient_failures`가 없어 실패했다(RED). 문서 독립 검토에서
  일반 idle timeout과 discovery 예외의 모호함을 지적하여 `9e20f05`에서 적용 범위를 명확히 했다.
- 구현 agent의 현재 turn metadata는 `gpt-6-sol/high`다. 전체 이력용 routing helper는
  과거 turn의 context 위치 문제로 FAIL을 반환했다. 원본 metadata에는 해당 과거 turn과
  현재 turn의 Sol/high가 모두 존재함을 별도로 확인했으며 helper PASS로 보고하지 않는다.
- 프런트엔드·금융 수익률 검증: 이번 범위 밖이다. 공학 복구가 투자 검증을 의미하지 않는다.

## 안전·운영 상태

수동 수정 동안 runner pause·service inactive, timer active를 유지했다. 최종 기록 commit 뒤
기존 설치 설정 그대로 resume하며 실제 시도 증거는 외부 `RUNTIME.md`에서 확인한다. 실주문·PAPER/live 활성화,
원격 push·결제·credential·모델·권한·Windows 종료는 수행하지 않았다. 사용자 미추적
`HANDOFF.md`, 다른 worktree, 과거 실패와 완료 제품은 보존한다.
작업 worktree는 미병합·미커밋·사용자 산출물 부재를 확인한 뒤 정상 제거했다. 소스·테스트는
Git에 보존됐으며 재생성 가능한 전용 venv와 검사 캐시만 함께 제거됐다.

## 증거와 다음 단계

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260926-lab-discovery-recovery/`.
- SQLite online backup: `runner-before-recovery.db`, integrity `ok`, SHA-256
  `f408dd8c299bd273761694fec589a62f264f43fa0f4842ed62494ecb1cad48a9`.
- 구현 중 read-only 비교: tasks 142개, attempts 202개, discovery cycles 3개,
  discovery attempts 7개, proposals 3개는 백업과 동일했고 DB integrity는 `ok`다.
- 운영 결과·확인 시각: 위 audit의 `RUNTIME.md`. live discovery는 HEAD에 결속되므로
  재개 뒤 기록만을 위해 root 문서를 다시 commit해 진행 중 identity를 바꾸지 않는다.
- 다음: 현재 DB와 RUNTIME의 최신 attempt·retry_after를 대조한다. timer active만으로
  개발 중이라고 판단하지 않는다. 원격 push·투자 검증 완료는 별도 범위다.
