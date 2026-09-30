# 미국 v4 캐시 결손 점검

- 작업: `us-v4-cache-gaps-20260930`; 기준 `b44d895`; 구현 `f8cb6a1`, 독립 review PASS, main 통합 `67526fe7c153a6ac1079321828d977bb58f0f7dd`.
- [고정 범위](../../../../.local/share/jusik/portfolio-audit/20260930-us-v4-cache-gaps/scope.json)의 24개 보호 원본과 ICUI 작업의 140개 캐시를 확인하고, marker 없이 전용 캐시로 복사했다. [오프라인 진단](../../../../.local/share/jusik/portfolio-audit/20260930-us-v4-cache-gaps/result.json)은 deny-all 수집기 한 번의 결과다. v4 가상 miss는 24개로 v3의 25개보다 하나 적다. GPACW는 후보에서 빠졌고, ICUI는 기존 캐시를 재사용했으며, EPRX가 누적 선정에 추가됐다. 새 exact Yahoo 키는 EPRX 한 건뿐이다. 이 수치는 누적 진단 목록 비교이고 전체 checkpoint 명단의 복원이나 데이터 완전성을 뜻하지 않는다.
- 오프라인 출력 `offline-UNTRUSTED-v4.json`은 연구 입력이 아니다. 생성된 v4 완료 marker를 즉시 격리하고 `collect-status.ready=false`를 확인했다. 별도 `gap-cache-copy`에서 [고정 GET 조건](../../../../.local/share/jusik/portfolio-audit/20260930-us-v4-cache-gaps/get-scope.json)을 검증했다. Alpha 원문 두 곳 모두 EPRX를 `Eupraxia Pharmaceuticals Inc`·NASDAQ·Stock·Active로 표시하며, 해당 키는 과거 frozen/live/v3/ICUI sentinel/140 캐시에 없었다.
- 단일 Yahoo GET은 사전 sentinel을 기록하고 30초 요청·60초 전체 제한, 재시도·리다이렉트 0, 스트리밍 10 MiB 상한으로 수행했다. [조회 결과](../../../../.local/share/jusik/portfolio-audit/20260930-us-v4-cache-gaps/gap-result.json)는 HTTP 200, 29,490바이트, NAS/USD와 OHLCV 검증 통과, 거래소 세션 272개 중 일봉 272개, 사건 0개다. 검증된 원문만 별도 캐시에 저장되어 140→141개가 되었고 새 완료 marker는 없다. 오프라인 출력이나 기존 캐시·준비 자료는 수정하지 않았다.
- 오프라인 시점의 가상 miss 24개는 기존 실패 23개와 EPRX 1개다. 조회 후 후속 재사용 기준은 `gap-cache-copy/manifest.json`(SHA `b352ea91287a5c77296874b4bbc7e803919fee80e42d315faceecf4276becf15`, 141개)이다. collector를 다시 실행하지 않았으므로 최종 v4 prepared·universe coverage는 검증되지 않았다.
- [결속 기록](../../../../.local/share/jusik/portfolio-audit/20260930-us-v4-cache-gaps/verification.json)은 스크립트·결과·원문·sentinel 해시, 원본 24개 재확인, 전후 캐시 상태를 연결한다. 두 audit 스크립트의 Ruff check/format과 strict mypy가 통과했다. 기존 v4 회귀 54개는 코드 hash가 그대로여서 반복하지 않았다. 시장 요청은 조건부 1회뿐이며 전략·NAV·금융 실험·주문은 0회다.
- 두 실행 스크립트가 같은 `binding.json` 경로를 사용해 GET 단계에서 오프라인 binding이 덮였다. 실행 결과와 스크립트는 변경하지 않고 GET binding bytes를 `gap-binding.json`에 보존했으며, 오프라인 script/result/baseline 해시로 `binding.json`을 사후 재구성했다. 최종 결속 기록은 이 증거 경로 교정을 명시한다.
- EPRX 원문 성공은 v4 prepared 자료 인수나 전체 24개 miss 해결, 사건 관측시각·PIT·비용 차감 수익률 검증을 뜻하지 않는다. 동일 요청 재시도 없이 다른 결손의 원천 근거를 별도 범위에서 검토한다.
- workflow 판단: 도움 됨 — 실제 선정 경로를 재사용해 새 EPRX 요청만 발견·보완했고 독립 검토로 단계별 binding 충돌을 발견했다.
- 근거: 오프라인 실행 1회·실제 GET 1회·272세션 확보, 증거 경로 교정 1건. 시간·호출 절감 비교값은 미측정이다.
- 다음 조정: 수정 — 여러 단계를 같은 audit에서 재사용할 때 실행 전에 출력 파일명을 분리한다. 계산·요청은 근거 변화 없이 반복하지 않는다.

## 통합과 인계

- main 통합 후 backend tree 불변, 감사 산출물 15개·문서 2개·보호 원본 24개 SHA, 문서 링크 7개, 단계별 binding 3개/4개 결속과 완료 marker 부재를 확인했다. `integration.json`, `review-final.json`, `routing-code-review.json`에 검증을 보존했다. 실제 요청·수집·기존 54개 검사는 추가 실행하지 않았다.
- 환경 버전은 `verification.json`, 정리 점검은 `cleanup-preflight.json`에 남겼다. 전용 worktree/branch는 제거했고 사용자 루트 HANDOFF·다른 작업은 보존했다. runner paused/running0 및 service/timer inactive 유지; 주문·PAPER/live·추가 결제·권한·자격증명·원격 push 변경 없음.
- 남은 차단은 이번 v4 감사의 기존 요청 결손 23건 및 기존 사건125 관측시각 결손, 배당 회계 연결·비용/FX/NAV 인수 조건이다. EPRX 성공이나 cache141을 최종 v4 prepared·PIT·비용 성과 인수로 해석하지 않는다. 동일 EPRX/ICUI 조회와 같은 선정 검사를 반복하지 않는다.
- 다음 시작은 이번 `gap-cache-copy` 141개와 이미 기록된 결손·재개 조건이다. 신규 외부 근거가 실제 남은 결손을 해소할 수 있는 범위만 독립 심사하며, 더 이상 새 결손이 없는 상태에서 이전 요청을 되풀이하지 않는다.
