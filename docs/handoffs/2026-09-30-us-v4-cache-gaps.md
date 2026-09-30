# 미국 v4 캐시 결손 인계

- 작업 `us-v4-cache-gaps-20260930`; [개발 기록](../development-records/2026-09-30-us-v4-cache-gaps.md)과 [결속 기록](../../../../.local/share/jusik/portfolio-audit/20260930-us-v4-cache-gaps/verification.json)이 최종 읽기 진입점이다. main 병합 `67526fe7c153a6ac1079321828d977bb58f0f7dd`.
- 오프라인 수집기 1회: 140개 캐시에서 가상 miss 24개, v3 대비 GPACW 제거·ICUI 캐시 재사용·EPRX 추가. 오프라인 출력은 영구 `UNTRUSTED`; v4 marker 격리 후 ready=false다.
- 조건부 EPRX GET 1회: 기존 미시도 exact 키, HTTP 200, 검증된 NAS/USD 일봉 272/272 세션과 사건 0개. 별도 조회 캐시 141개와 사전 sentinel·원문 hash를 보존했다. 원본 24개 해시와 audit 크기 정책 확인. 전략·NAV·성과·주문·원격 push 없음.
- 오프라인 miss 24개는 기존 실패 23개+EPRX 1개였다. EPRX 검증 후 재사용 기준은 `gap-cache-copy/manifest.json` SHA `b352ea91287a5c77296874b4bbc7e803919fee80e42d315faceecf4276becf15`의 141개 캐시다. 이후 collector를 재실행하지 않아 최종 v4 prepared·universe coverage는 미검증이다.
- 두 스크립트의 `binding.json` 경로 충돌 후 GET binding을 `gap-binding.json`으로 byte 보존하고 오프라인 binding을 고정 산출물의 해시로 사후 재구성했다. 재실행은 하지 않았다. 단계별 binding과 교정 이력은 최종 결속 기록에서 확인한다.
- v4 collector를 조회 후 재실행하지 않았다. 단일 원문은 전체 준비 자료 적격성 또는 PIT 증거가 아니다. 24개 가상 miss 중 이전 실패 키와 사건 관측 근거는 별도 범위의 차단 조건으로 남는다. 같은 EPRX 키 재조회는 하지 않는다.
- workflow: 확정 scope의 단일 probe와 단일 조회만 수행했다. 결과별 캐시를 분리해 증거 해석을 보존했다. 다음 작업은 실제 차단 원인을 줄이는 새 근거가 있을 때만 시작한다.
- 2026-09-30T10:37Z 완료: 구현 `f8cb6a1`, main `67526fe7c153a6ac1079321828d977bb58f0f7dd`. 독립 review의 binding 충돌 지적은 교정 후 해시 검증으로 해결했다. 통합 검증 PASS, 환경/audit 보존, 전용 worktree/branch 정리. 사용자 HANDOFF·다른 작업 보존, runner paused/inactive 유지.
- 다음 시작: 새 캐시141개와 이 기록을 재사용한다. 이미 보완한 EPRX/ICUI 또는 같은 선정 입력을 반복하지 않고, 기존 요청 결손23·사건125 관측시각 문제를 실제 해결할 새 근거의 독립 scope를 검토한다. 최종 v4 prepared/비용·FX·NAV 비교는 아직 미검증이다. 후속 다단계 감사는 실행 전에 binding 경로를 분리한다.
