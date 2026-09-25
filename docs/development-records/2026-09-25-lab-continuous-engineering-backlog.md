# 유한 공학 backlog 자동 진행

- 상태: 코드 통합 완료, 운영 dispatch 확인 중
- 기록 시각: 2026-09-25T04:32:14Z
- 작업 slug: `lab-continuous-engineering-backlog`
- 기준/통합: `626303f` / `c62d512`
- 범위: 투자 자료 대기와 기존 BLOCKED 공학 시도를 보존하면서 독립 오프라인 공학 작업을 자동 등록·선택한다. 투자 승격과 주문 경계는 변경하지 않는다.

## 변경과 결정

- `backend/jusik/development_runner_contract.py`에 기존 paper spec을 보존하고 전략 버전 증거 영수증과 paper 계약 재시작 중복 방지의 고정 spec 두 개를 등록했다. 제품 구현은 각각 후속 child의 별도 작업이다.
- `backend/jusik/development_runner.py`는 roadmap scope의 명시적 opt-in에서만 기존 READY·review 후보를 우선 처리하고, 없으면 미생성 spec 하나를 같은 주기에 선택한다. spec별 정확한 변경 파일·evidence hash·독립 review 계약을 강제한다.
- `backend/jusik/development_runner_store.py`는 등록·소진 판정·idle 기록을 SQLite 트랜잭션으로 관리한다. 재시도·대기 해제로 READY가 되면 오래된 idle 기록을 같은 트랜잭션에서 지운다. 과거 BLOCKED attempt는 재실행·소급 승인하지 않는다.
- 독립 검토에서 READY 복귀 후 stale idle과 소진 판정/기록 사이 경합을 발견해 재현 테스트와 함께 수정했다. 최종 Sol 재검토에서 P1/P2 없음.

## 문서·계약 영향

- 사용자·운영 문서: `docs/development-runner.md`에 opt-in, 유한 backlog, 진행·중지 명령과 소진 동작을 설명한다. `docs/autonomous-trading-lab.md`에는 투자 검증과의 경계를 반영한다.
- 설정: `/home/kwl/.config/jusik/roadmap-development-runner.json` 원본을 private audit에 백업한 후 `automatic_engineering_backlog=true`만 추가했다. 기본값은 `false`; research scope에는 적용되지 않는다. 백업 SHA-256은 `0296bbef34d59ffec6b64ea906c76163ebc3acb00141bfdfb623884bfc6efb5a`다.
- API·데이터 계약: 공학 spec별 소유 파일·검토 receipt를 일반화한다. 투자 validation과 strategy lifecycle 전이는 변경하지 않는다.

## 검증

- 로컬 `main`: runner 관련 pytest 161개 통과, Ruff check·format 통과, 변경 source 4개 strict mypy 통과.
- 신규 회귀는 기존 BLOCKED 뒤 첫/둘째 독립 task의 same-cycle 선택, opt-in 기본 off, pause·quota·cooldown·governance, spec별 evidence/review, READY 복귀 idle 삭제와 retry 경합을 임시 Git/SQLite·fake child로 검증했다.
- 독립 Sol 검토: 두 P2 수정 후 PASS. 실제 운영 child·reviewer dispatch와 systemd 동시 실행은 이 시점에는 미검증이다.
- 프런트엔드 변경이 없어 build는 실행하지 않았다.

## 안전·운영 상태

- 기록 시점 roadmap runner는 paused, service inactive, timer active다. 설정만 활성화했으며 실제 dispatch는 tracked `main`을 깨끗하게 만든 뒤 재개·확인한다.
- 실주문, PAPER/live activation, 운영 투자 원장 변경, 원격 push, 추가 결제, credential/권한 변경 없음. 사용자 미추적 `HANDOFF.md`와 다른 worktree는 보존한다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260925-continuous-engineering-backlog/`; 설정 원본은 `roadmap-development-runner.before.json`.
- 남은 작업: 문서 커밋·tracked clean 확인 후 runner resume와 실제 새 task 등록·실행 여부 확인, handoff 저장, 통합 worktree 정리.
- 다음 시작: roadmap runner를 재개하기 전 local main 상태와 서비스 inactive를 확인한다.
