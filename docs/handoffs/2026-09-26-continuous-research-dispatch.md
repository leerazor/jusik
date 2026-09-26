# 지속 연구 dispatch 재설계 인계

- 검증 시각: 2026-09-26T01:29:36Z. 저장소 `/home/kwl/projects/jusik`, local `main`.
- 구현 통합 `9fae842`, 타입 보완 통합 `5b86cb0`. 최종 기록 commit 뒤 runner를 재개한다.
- 목표: 사용자 반복 지시 없이 의미 있는 연구 준비·공학 작업을 선택한다. 수익률·가동률을
  보장하거나 투자 검증·실주문·추가 결제·권한·credential 기준을 완화하지 않는다.

## 완료한 첫 구현

공학 discovery의 조기 반환 때문에 적격 연구 planner가 호출되지 않는 원인을 재현·수정했다.
기존 READY/구현 review 다음에 bounded 연구 제안을 평가하며, pending→별도 read-only scope
PASS→현재 입력 재검증→단일 원자 등록을 거친다. WAIT/REJECT/무효 계획은 공학 fallback을
막지 않는다. DB-bound scope 직접 등록·승인 task followup 우회·불확실 orphan을 차단한다.

설계 정본은 [autonomous-trading-lab 17절](../autonomous-trading-lab.md#17-목표-기반-지속-운영),
변경과 근거는 [개발 기록](../development-records/2026-09-26-lab-continuous-research-dispatch.md)이다.
AGENTS·구조 안내·runner/session 운영 문서·작업 등록부를 최소 병합했다.
기존 8개 프로필, planner 포함 active 최대 4개와 단일 코드 소유 원칙을 유지했다.

## 검증·작업 공간

- 독립 Sol review PASS. 등록 우회 P1 두 건을 RED로 재현해 보완했다.
- 최종 main pytest 292개 PASS; 변경 파일 Ruff와 소스 3개/테스트 4개 strict mypy PASS.
- 운영 backup 복사본: 기존 10개 테이블·1,039개 행과 기존 열 값 보존, 반복 초기화·integrity PASS.
- 전체-history routing helper는 이전 turn context 누락으로 검증 불가. 실제 최신 code/review
  turn context `gpt-6-sol/high`는 확인했으며 helper PASS로 과장하지 않는다.
- 전용 worktree 정상 제거, 브랜치·커밋 보존. 사용자 미추적 `HANDOFF.md`와 다른 worktree 보존.
- API·실계좌 주문·PAPER 활성화·원격 push·Windows 종료 없음. 새로운 수익성 검증 결과 없음.

## 운영 상태와 다음 순서

수동 개발 동안 runner는 pause, timer는 active였다. 최종 문서 commit 뒤 기존
`/home/kwl/.config/jusik/roadmap-development-runner.json`으로 재개한다. 코드/설정은
추가 변경하지 않고 실제 task·child·단계는 아래 외부 `RUNTIME.md`에 기록한다.
이는 HEAD가 고정된 실행 중 문서 commit으로 제안을 무효화하지 않기 위한 분리다.

audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260926-continuous-research-dispatch/`.
`VALIDATION.md`는 검사 근거, `RUNTIME.md`는 마지막 재개 관측이다. 서비스 상태는 시간에 따라
달라지므로 다음 세션에서 다시 확인한다. 기존 연구 universe와 prospective monitor는 유지했다.

다음 우선 과제는 새 roadmap 산출물의 독립 완료 reviewer 자동 연결이다. scope PASS를
완료 review로 사용하지 않는다. 이어서 reviewer의 transient retry, 증거 기반 no_work와
외부 readiness 재평가를 다룬다. 현재 prospective 계약은 새 mandate와 완전히 호환되지
않는다. 기존 관찰 창/OOS를 건드리지 않는 계약·자료 준비가 선행하며 새 실험은 별도 gate를 따른다.

재개 프롬프트: “이 handoff와 외부 RUNTIME, 실제 Git·runner 상태를 확인하라. 자동 child가
실행 중이면 main을 수정하지 말고 관측하라. 수동 변경이 필요하면 기존 pause 절차로 충돌을
막고 독립 완료 reviewer 연결의 최소 범위를 설계·검증하라. 실주문·투자 기준은 변경하지 마라.”
