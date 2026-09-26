# R2-02 비용 계약 market 유일성 검증

- 상태: 코드·독립 검토·local main 통합 검증 완료. 운영 DB의 기존 task는 별도 명시적 retry 전까지 BLOCKED를 보존한다.
- 작업 slug: `r2-02-cost-market-uniqueness`
- 원 task: `roadmap-r2-02-cost-market-uniqueness-v1`
- 기존 worktree 기준: `e61df2fc8c2b2d56f09a6c6ee627900dc2524625`; 구현 `196f8e3`, 통합 `b125389`.

## 범위와 근거

기존 scope reviewer는 `broker_cost_profiles.py`의 빈·중복 market 계약을 거부하는
오프라인 코드 수정만 승인했다. 실제 요율·계좌 비용·성과 계산·R2-02 완료 승인은 아니다.
현재 main과 기존 worktree source SHA가 승인 당시
`42bc99abab5ae585b5753b5f20fd565267d2aca95127c719096910c2aa4f8f2f`와 같다.

builder는 빈 market tuple 및 중복 market을 받아 계약을 만들고, manifest 검증도
중복 profile을 정상 builder로 재계산한 hash와 함께 받아들일 수 있다. 단일 구현자가
소스와 대응 테스트 두 파일만 수정하며 요율·정상 시장 선정·기존 유효 계약은 유지한다.

## 검증과 복구 조건

빈·중복 입력 및 hash를 다시 계산한 중복 manifest의 RED 4건, 기존 PASS 8건을
확인했다. `196f8e3`은 두 파일에만 검사와 회귀를 추가하며 pytest 12개·Ruff check/format·
두 파일 strict mypy를 통과했다. 별도 Sol/high reviewer가 고정된 diff를 검토했고,
유효한 순서 포함 부분집합 15개를 기준 코드와 독립 비교하여 모든 비용·manifest·hash·ID
보존과 기존 manifest roundtrip을 확인했다. 최종 판정은 PASS, 발견한 문제는 없다.

main `b125389`에서 같은 pytest 12개(0.03초), Ruff check/format, 두 파일 strict mypy를
다시 통과했다. 구현자 Luna/high의 fresh pre/post routing helper도 PASS다.
reviewer 최신 child-owned turn은 `gpt-6-sol/high`로 확인했다. 프런트엔드 변경이나 금융
실험이 없어 해당 build/경제 평가는 실행하지 않았다.

실제 독립 review 기록은 audit의 `cost-market-independent-review.json`에 있다. 원 task,
기준·검토·통합 commit, reviewer/turn 식별, 검사와 다음 파일 hash에 결속한다.

- source: `a5ec09c100409a477fcba9ec9b8879ff75150da3d0e976c3cb9cad3fa16fbba4`
- test: `8df3aa3538babb2c1629a949bf475f84534eb8396bf6937e4844fa645a888948`

마지막으로 관측한 기존 원 task의 상태는 `blocked`다. 과거 attempt `1934a7bed2034f0fb815052823c2091f`,
scope receipt 및 실패 근거는 불변으로 보존한다. 실제 구현·외부 독립 review 완료 후
기존 명시적 retry를 사용하며, 새 attempt는 새 변경이나 하위 agent 없이 실제 완료
증거를 검증·보고한다. 증거가 불충분하거나 수정이 추가되면 자체 승인하지 않는다.
원 `r2-01` FAILED는 이 작업에서 변경하지 않는다.

재시도 child의 작업은 위 commit의 main ancestry, 두 파일 hash, 실제 독립 review와
이 개발 기록을 확인하여 이미 끝난 구현을 보고하는 것이다. 또 다른 구현자·reviewer를
중첩 호출하거나 같은 변경을 다시 만들지 않는다. 과거 승인·출력은 수정하지 않는다.

## 안전·기록

자동 runner는 별도 runner 수리 동안 pause 상태다. 데이터·금융 실험·실주문·PAPER/LIVE·
권한·credential·비용 정책·원격 push·Windows 종료는 변경하지 않는다.
사용자 `HANDOFF.md`는 보존하고 결과는 완료 시 date-specific handoff에 연결한다.
audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260926-roadmap-completion-review/`.
