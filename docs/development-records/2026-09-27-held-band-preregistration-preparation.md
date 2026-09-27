# Held-band 후속 사전등록 준비

- 상태: 완료 (문서 준비만; 실행 가능한 사전등록은 차단)
- 기록 시각: 2026-09-27T00:05:14Z
- 작업 slug: `portfolio-held-band-preregistration-draft-v2`
- 기준/통합: `10e092a55ab50d96b09fe8c15b2a535530a9f8ad` / `f375f822b53ae591a23d8631c991629189ca73a7` (local `main` fast-forward)
- 범위: held-band 후속 연구의 실행 불가 사전등록 초안 두 파일을 만들고 기존 v1 evidence를 보존했습니다.

## 변경과 결정

- `docs/research/portfolio-held-band-preregistration-draft-v2.md`는 제안된 4%p 후보와 2%p 대조군의 미래 전용 비교를 설명합니다. v1 기간은 후향 근거이며 untouched OOS가 될 수 없다고 분리합니다.
- `docs/research/portfolio-held-band-preregistration-draft-v2.json`은 `execution_allowed=false`를 고정하고, 확인되지 않은 자료·기간·요구수익률·예산 및 hash identity를 `null`로 남깁니다. 현재 mandate의 독립 검증 단계, MDD hard filter, 최대 세 후보, 자동 승자/승격·holdout 재튜닝 금지를 반영합니다.
- 최종 독립 문서 검토에서 v1 preregistration SHA 오기가 발견되어 두 초안에서 수정했습니다. 기존 자료는 변경하지 않았습니다. 확인된 v1 SHA는 preregistration `fa5065df2ae70d024656209b0a33b755071c1441ecfa3406db99973fda49277e`, hash manifest `bba3822f08a648462c8a2634c9402b545c833ad854bcb924fac96adb75d366a2`, results `6c20c79552964182d52e5a9ce8571747ddf97a21a9c7b5c46b2dc827e167479b`입니다.
- 현재 mandate 파일 SHA는 `22efba4714bc0baf65c56bdfd84dcdee91184a760a13d4d30c5a94486c264ab1`입니다. 준비 조사에서는 2026-09-08 뒤의 새 held-band 호환 관측을 찾지 못했습니다. 다른 범위의 달력·R0·KOFR 자료로 이를 대신하지 않았습니다.

## 문서·계약 영향

- 사용자 문서: 위 두 연구 초안을 새로 추가했습니다. 사용자 흐름이나 투자 결과를 바꾸지 않습니다.
- 운영 문서: `docs/worktree-tasks.md`를 완료 상태와 통합·검증 결과로 갱신했습니다. runner 정책·설정은 바꾸지 않았습니다.
- API·설정·데이터 계약: 변경 없음.

## 검증

- `python -m json.tool docs/research/portfolio-held-band-preregistration-draft-v2.json` — 통과.
- `git diff --check 10e092a55ab50d96b09fe8c15b2a535530a9f8ad..f375f822b53ae591a23d8631c991629189ca73a7` — 통과; 작업 브랜치의 변경 경로는 초안 두 파일뿐.
- `sha256sum` — v1 preregistration·hash manifest·results가 등록된 기존 SHA와 일치.
- 별도 Sol 문서 review — 오기 수정 후 전체 재검토 PASS.
- 제품 테스트·실험·benchmark·자료 수집·network 호출 — 문서 전용 준비 단계여서 실행하지 않았습니다. 수익성이나 자료의 PIT 적격성을 검증했다고 주장하지 않습니다.

## 안전·운영 상태

- service의 실제 설정은 `~/.config/jusik/roadmap-development-runner.json` (`investment-roadmap`)입니다. 수동 편집 전에 확인한 이 큐는 `paused=false`였고 timer는 active였습니다. 편집 도중 timer cycle은 7회 `idle`, 1회 `blocked` (`tracked worktree is dirty`)였으며 task 상태 수는 181개 중 completed 156, blocked 9, failed 15, waiting_external 1로 전후 같고 running task는 0개였습니다. 서비스 결과와 task 상태에서 실행된 task attempt는 없었습니다.
- 통합 때 roadmap 큐를 pause하고 one-shot service를 정지했습니다. tracked worktree를 깨끗하게 만든 뒤 기존 `paused=false`로 복원했습니다. 운영 기록 정정 중 짧은 maintenance pause를 한 번 더 적용했고, 이 기록을 커밋한 뒤 같은 상태로 복원합니다. 최종 목표 상태는 timer active, queue unpaused, 실행 중 task 0개, one-shot service inactive입니다. 별도 `~/.config/jusik/development-runner.json` 큐는 원래 `paused=true`인 상태로 변경하지 않았습니다.
- 실주문, PAPER/DB 변경, service 설정 변경, 원격 push, 새 자료 수집은 없습니다. 사용자 소유 루트 `HANDOFF.md`를 보존했습니다.
- 소유 worktree `/home/kwl/projects/jusik-portfolio-held-band-preregistration-draft-v2`는 clean 상태에서 제거했습니다. 작업 브랜치와 두 작업 커밋은 보존했습니다.

## 증거와 재개

- audit: 기존 v1 자료 `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-held-band-interaction-v1-cce0cdf0e5ea43e4a088f2dfe5c2fa74/experiment/`; 변경하지 않음.
- 남은 차단: 신규 source/universe/PIT 등급·기간, IS/validation/walk-forward/OOS 경계와 최소 표본, 후보별 비용 기준 요구수익률 지표·기간·값, 실행/계산 예산을 정해야 합니다. 미래 자료 수령 후 실행 전에 입력 manifest와 최종 코드 identity/hash를 고정해야 합니다.
- 다음 시작: 이 초안과 최신 `docs/research-mandate.json`을 읽고 필요한 결정·미래 자료의 적격성을 확정한 뒤, 모든 필수 필드와 budget/hash를 고정하기 전까지는 실행하지 않습니다.
