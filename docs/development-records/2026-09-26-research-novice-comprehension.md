# 처음 방문한 사람을 위한 연구 화면 재설계

- 상태: 완료
- 기록 시각: 2026-09-26T09:47:42.200789+00:00
- 작업 slug: `research-novice-comprehension`
- 기준/통합: `b887db7f998542362f1d08f1929d4f60436cfef2` / `d8539d3708db6e070b6bb4d878a408576e7bbc6e`; 마지막 종목 메모 수정 통합 `02a51a8e7f1217ef928412165842e649c5cd371e`
- 범위: 연구 홈·결과·모의 관찰·웹 보고서 소개와 종목 메모의 설명, 읽기 순서, 반응형 표시, 지속 검수 기준. 수치·원문·전략·인증·서버 액션 계약은 보존했습니다.

## 변경과 결정

연구자가 만든 두 시험을 사용자의 이전 투자 방식으로 오해하지 않도록 목적과 비교 출처를 먼저 설명합니다. 화면은 질문, 두 시험의 실제 행동, 가상 금액 예시, 관측 결과와 한계, 독자의 다음 행동 순서입니다. 4주·8주는 프로그램이 종목과 투자 금액을 다시 계산하는 간격이며 투자기간이나 매번 거래한다는 뜻이 아님을 조건부 거래 예시로 풉니다.

`comparison-settings.tsx`와 새 `comparison-results.tsx`가 홈·결과의 설명을 공유합니다. 기본 수치는 기간 전체 수익, 최대 하락 폭, 남긴 현금의 비율 세 가지로 줄이고 전문 설정과 거래 세부는 펼쳐 읽습니다. 위험·비용이 불리해진 결과는 기본 해석에 남깁니다. 여러 규칙을 함께 바꾼 시험을 주기 하나의 효과로 설명하지 않습니다.

`research-narrative.ts`의 연구별 질문·행동·예시는 기존 ID와 source/result/report hash가 모두 맞을 때만 사용합니다. 독립 코드 검토에서 전체 연구 요약이 특정 짧은 기간의 개선 결과와 모순되는 문제를 확인했습니다. `ae6b69a`에서 기존 Decimal 비교를 이용해 현재 표시된 비교의 수익·낙폭·현금·비용 방향을 설명하도록 고쳤습니다. 연구 전체 요약은 연구 단위 소개에만 둡니다.

모의 관찰은 새 가격으로 프로그램의 판단과 가상 매매를 기록하는 별도 경로임을 설명합니다. 자료 응답 실패·검증 형식 실패·계좌 불일치 등 확인 가능한 상태와 사용자의 다음 읽기를 안내하며 제공되지 않은 복구 시각을 만들지 않습니다.

보고서는 전체 원문을 웹에서 읽습니다. 검증된 연구 문맥이 있으면 목적과 읽는 법을 위에 표시하고, 문맥 조회 실패에도 안전하게 확인한 원문은 읽을 수 있습니다. 참고 보고서에는 무관한 연구 설명을 붙이지 않습니다. 원문의 표현과 값, 안전한 링크·HTML 처리, 해시 검증은 유지합니다. 표의 좌우 이동과 요약 절삭/원문 반올림 차이를 안내합니다.

`/investor`는 직접 종목을 찾아 개인 메모를 남기는 선택 도구입니다. 마지막 실제 화면 검수에서 필수 입력과 두 관심 이유의 의미가 불명확했습니다. `66a2873`에서 최소 기록 안내와 필수/선택 표기, 가치 진입·초기 추세 진입의 뜻, 모를 때 연구 설명으로 돌아가는 경로를 추가했습니다. EPS·PER의 선택 입력은 예시와 함께 펼쳐 읽습니다. 폼 이름·속성·기본값·검증·서버 액션은 변경하지 않았습니다. `/invester`의 `/investor` 이동도 확인했습니다.

## 독립 검토와 수행 경계

Luna explore와 Sol plan 뒤 native code spawn 및 기존 code agent 재개가 `agent thread limit reached`로 거절됐습니다. 완료 agent 중단으로도 해소되지 않아 root가 격리 worktree의 단일 구현 소유자를 맡았습니다. 별도 Sol 코드 reviewer와 새 문맥의 Sol 화면 reviewer를 유지했고 외부 CLI 우회 위임은 하지 않았습니다. 이 예외는 `delegation-limit.json`에 남겼습니다.

화면 reviewer는 구현 코드·계획·API 자료나 정답을 받지 않았습니다. 실제 화면과 일반 탐색만으로 목적, 비교의 출처, 행동과 간격, 결과의 한계, 다음 행동을 자기 말로 설명하고 근거 문구를 남겼습니다. 초기 행동/다음 행동의 공백과 마지막 메모 입력 공백을 수정한 뒤 재검수하여 모두 PASS했습니다. PC 1440px·모바일 390px를 확인했습니다. 이는 agent의 초보 관점 검수이며 실제 초보 참여자 시험은 아닙니다.

## 문서·계약 영향

- 사용자 문서: `docs/investor-web-design.md`에 목적 중심 읽기 흐름, 선택 도구의 역할, 보고서 안내와 검수 기준을 반영했습니다.
- 개발 규칙: `frontend/AGENTS.md`에 구현 문맥 없는 화면 reviewer, 보이는 근거에 따른 평가, 추측 지점 수정·재검수와 웹 보고서 보존을 명시했습니다.
- 운영 문서: 배포 방식 변경은 없습니다. 현재 서비스 재시작과 runner pause의 소유 경계는 이 기록과 task handoff에 남깁니다.
- API·설정·데이터 계약: 변경 없음. 연구 catalog·원문·금융 계산·전략·인증·주문 경계를 보존했습니다.

## 검증

- `npm --prefix frontend run lint`, `npm --prefix frontend run typecheck`, `npm --prefix frontend run build` — 작업 worktree와 마지막 main 통합 모두 PASS. `investor-*.log`, `main-final-*.log` 참조.
- `npm --prefix frontend run verify:research-reports -- /home/kwl/.local/share/jusik/ui-comprehension-20260926/fixture` — 원문 보고서 12개, 파서·링크·식별 guard와 비교 방향 회귀 검사 PASS. `main-reports.log` 참조. 마지막 수정은 메모 안내 문구만이므로 보고서 검사는 반복하지 않았습니다.
- 읽기 전용 fixture의 정상 12화면, 누락·불일치·오프라인 등 14상태 — PASS. 잘못된 문맥을 숨기며 안전한 원문 읽기를 유지하고, 누락/변조 원문은 오류로 표시함을 확인했습니다.
- 키보드 목차, 접힌 영역의 자동 갱신 후 상태 유지, 보고서 이동, PC/모바일 넘침과 다운로드 발생 없음 — PASS. 최초 URL 확인 타이밍 문제와 소수점 후행 0 기대값 오류는 검증 도구를 바로잡아 재확인했으며 원래 증거도 보존했습니다.
- 배포 후 연구 8화면·종목 메모 2화면, 오타 경로 이동, 세 서비스 상태, 외부 미인증 401 — PASS. `deployment/browser.json`, `browser-investor-final.json`, `health-final.json`, `auth-final.json` 참조.
- 독립 코드 검토·화면 이해도 검수 — 수정 후 PASS. 폼 속성 보존, 보고서와 backend 변경 없음, 사용자 루트 handoff 해시 보존도 확인했습니다.
- 실행하지 않은 검사: 실제 주문·메모 저장을 실행하지 않았습니다. frontend 변경이므로 backend 전체 suite를 반복하지 않았습니다. 실제 초보 참여자 시험은 하지 않았습니다.

## 안전·운영 상태

기존 적용·재시작 승인에 따라 `./start.sh`로 현재 서비스에 적용했습니다. 3000 웹·8000 API·8001 연구 API와 기존 보호된 ngrok 연결은 실행 중입니다. 인증 설정 변경, 실주문, 모의 주문 실행, 연구 원장 수정, 원격 push는 하지 않았습니다.

runner는 시작과 마지막 확인 모두 paused=1·running attempt=0입니다. 병행 수동 성능 개선과 `lab-scope-review-transport-retry`의 소유 경계를 보존하며 이 UI 작업만으로 재개하지 않았습니다. 해당 작업 supervisor가 현재 상태를 확인해 재개합니다. 사용자 미추적 `HANDOFF.md`는 수정·커밋하지 않았습니다.

전용 preview 3339·fixture 8339와 검수 브라우저는 종료했습니다. 필요한 결과·최종 diff·환경 버전·로그·화면을 audit에 보존한 뒤 main ancestry와 clean 상태를 확인하고 작업 worktree와 branch를 정상 제거했습니다. 다른 worktree는 보존했습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/ui-comprehension-20260926/`
- manifest: 같은 경로 `manifest.json`; SHA-256 `1515a8bb27c05f2f719a715e4365efa356d0fb28a2acae4900077f6542d7be62`. 실행 중 launcher 로그는 고정 snapshot을 해시로 보존했습니다.
- 전체 검증 요약은 `verification.json`, 독립 검토 근거는 `novice-review-final.md`와 `code-review-final.md`, 통합·정리 근거는 `integration*.json`과 `cleanup.json`입니다.
- handoff: `/home/kwl/.local/share/jusik/ui-comprehension-20260926/HANDOFF.md`. 현재 서비스와 runner 재개 소유권을 확인할 때 읽습니다.
- 남은 필수 작업: 없음.
- 다음 시작: 작업 등록부와 현재 Git·서비스·runner 상태를 대조하고, 신규 화면 변경에도 구현 문맥 없는 검수와 지적 수정·재검수를 적용합니다.
