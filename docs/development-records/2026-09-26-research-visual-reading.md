# 연구 화면의 글을 표와 비교 그래프로 정리

- 상태: 완료
- 기록 시각: 2026-09-26T10:53:06.746599+00:00
- 작업 slug: `research-visual-reading`
- 기준/제품/통합: `d89ac20769d4e0f07d6b2bf7913f5444a15d2aae` / `84a361fc1d68ad48518e3805adb1b97001ce7c5d` / `758dd811939261c670c822fa7947df48748fc984`
- 범위: `/research`와 `/research/progress`의 비교 설명·표·그래프·점검 도식, 표시 helper와 집중 검사, 설계·검수 규칙. 원문·금융 값·API·전략·인증·운영 데이터는 보존했습니다.

## 자체 평가와 변경

직전 화면은 설명을 끝까지 읽으면 이해할 수 있었지만 첫 화면에 결론이 없고 두 시험의 차이가 문장 두 묶음에 흩어져 있었습니다. root의 실제 모바일 측정에서 결과 제목은 문서 위에서 2,112px, 기본 텍스트는 2,658자였습니다. 별도 화면 reviewer도 한눈에 비교하기 어렵고 수익과 하락의 같은 초록색이 득실을 혼동시킬 수 있다고 판단했습니다.

연구 목적 다음, 질문 바로 아래에 현재 비교의 네 가지 변화 결론을 두었습니다. 설정은 의미별 행과 두 시험 열이 있는 표로 대응합니다. 수익·중간 하락·총 비용·현금을 각각 두 가로막대로 비교하며, 비용도 기본 화면에 노출합니다. 색은 두 시험을 구분하고 숫자와 변화 방향을 직접 표시합니다. 점검 행동은 결과 뒤의 세 단계 도식으로, 상세 설정·용어·계산 예시는 펼쳐 읽도록 옮겼습니다.

그래프는 항목별로 두 값에 같은 0선·눈금을 씁니다. 음수는 왼쪽, 0은 길이 0, 누락은 막대 없음으로 처리하고 작은 값을 임의로 늘리지 않습니다. 큰 값은 먼저 정규화하여 좌표 계산의 overflow를 막습니다. 길이만 근사하며 기존 Decimal 문자열의 수치 표시와 대소 비교는 유지합니다. 시계열이나 새로운 금융 성과는 만들지 않았습니다.

독립 코드 검토에서 기존 `candidateRuleForComparison`이 core10 ID의 c1/c2를 후보 A/B로 잘못 추론하던 오류를 발견했습니다. c2는 후보 B가 아니라 비용 2배인 후보 A입니다. 실제 catalog와 원문 보고서를 대조해, 기존 연구 ID·hash 검증과 비교 소속 확인 뒤 등록된 네 comparison ID를 후보 A·밴드 2%p로 연결했습니다. 실제 비용 2배 fixture 회귀 검사를 추가했습니다. catalog 자체는 정확했으므로 성과 catalog나 원문을 변경하지 않았습니다. [성과 공개 절차](../research-progress-publication.md)의 새 성과 비교 없는 기술 오류 수정에 해당합니다.

## 검수 결과

구현 문맥 없는 별도 Sol reviewer가 PC 1440px·모바일 390px의 실제 렌더링 화면만 봤습니다. 목적·변경점·득실·주기 행동·다음 읽기를 긴 글을 모두 읽지 않고 설명했고 중요한 새 추측 지점이 없어 PASS했습니다. 각 그래프에 이름·수치·변화 방향이 있어 모바일에서도 앞의 값을 기억하는 부담이 작다고 평가했습니다. 실제 초보 참여자 시험은 아닙니다.

배포 후 390×844 화면에서 개요의 결론은 487~643px, 첫 그래프는 1,168px에 보였습니다. 성과 화면의 결론은 479~635px, 첫 그래프는 1,198px입니다. 개요 기본 텍스트는 1,903자로 약 28% 줄었습니다. 이 수치는 브라우저의 기본 표시 상태에서 측정한 화면 특성이며 투자 성과나 실제 사용자의 이해도 점수가 아닙니다.

## 수행·문서·계약 경계

직전 native code dispatch의 thread 제한을 유지하여 반복 spawn이나 외부 CLI 우회를 하지 않았습니다. root가 관련 탐색 근거와 현재 소스를 조사하고 재사용 Sol plan의 제한된 계획을 받아 격리 worktree의 단일 구현을 맡았습니다. 별도 코드·화면 reviewer는 유지했고 routing 검사를 통과했습니다.

`docs/investor-web-design.md`와 `frontend/AGENTS.md`에 읽기 부담 평가, 표·짝 막대·행동 도식, 원래 수치·0선·음수·누락·색상 기준을 반영했습니다. 새 의존성은 없고 `verify:research-charts` 검사 명령만 추가했습니다. 보고서 전체의 웹 읽기와 안전한 링크·원문·식별 guard를 보존했습니다. `/investor`의 폼·서버 액션과 backend는 변경하지 않았습니다.

## 검증

- worktree 및 main: `npm --prefix frontend run lint`, `typecheck`, `build` — PASS.
- `npm --prefix frontend run verify:research-charts` — 양수·음수·0·동률·작은 값·극단값·누락의 축과 막대 검사 PASS.
- `npm --prefix frontend run verify:research-reports -- /home/kwl/.local/share/jusik/ui-visual-reading-20260926/fixture` — 원문 12개·파서/링크/식별 guard·실제 c2 매핑 회귀 검사 PASS.
- 정상 4화면, 오류·누락·불일치 14상태, 실제 c2 화면의 후보 A·2%p·111.06%, 키보드 펼침 및 자동 갱신 후 상태 유지 — PASS.
- 배포 후 두 페이지 × 두 화면 폭, 웹 보고서 이동, 브라우저 오류·가로 넘침·다운로드 없음, API 상태와 외부 미인증 401 — PASS.
- 독립 코드 검토의 P2와 화면 읽기 부담 지적을 수정한 후 재검수 — PASS.
- 초기 chart -0 검사와 새 테스트의 null narrowing 실패를 고쳤습니다. 잘못된 로딩 시점 측정과 실제 후보 B가 없던 fixture 시나리오도 검증 도구에서 정정했습니다. 이전 실패 증거는 `review-evidence.md`와 audit에 보존합니다.
- 실행하지 않은 검사: 실제 주문·메모 저장·연구 실행, backend 전체 suite, 실제 초보 참여자 및 스크린리더 도구 시험은 수행하지 않았습니다. frontend 변경에 필요한 검증으로 한정했습니다.

## 안전·운영 상태

승인된 `./start.sh`로 현재 서비스에 적용·재시작했습니다. 웹 3000·API 8000/8001과 기존 보호된 ngrok 연결은 실행 중입니다. 실주문·모의 주문 실행·원장 수정·인증 설정 변경·원격 push는 하지 않았습니다. 사용자 미추적 루트 `HANDOFF.md`는 해시까지 보존했습니다.

작업 시작 runner는 paused=0·running attempt=0이었습니다. 수동 변경 동안 pause와 service inactive를 확인했습니다. 기록·통합·정리 후 시작 전 자동 실행 상태로 복원하며, 실제 복원 결과는 audit의 `runner-restored.json`이 기준입니다. 다른 작업의 자동 실행을 위한 설정·큐·권한을 바꾸지 않습니다.

전용 preview 3340·fixture 8340과 검수 브라우저를 종료했습니다. 로그·최종 diff·환경 버전·화면을 보존한 뒤 main ancestry와 clean 상태를 확인하고 `/home/kwl/projects/jusik-research-visual-reading` 및 `feat/research-visual-reading`를 정상 제거했습니다. 다른 worktree는 보존했습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/ui-visual-reading-20260926/`; `manifest.json`에 고정 증거 파일의 SHA-256을 저장합니다. 실행 중 launcher 로그는 snapshot으로 보존합니다.
- 자체 평가와 원인 수정은 `review-evidence.md`, 별도 화면 검수는 `novice-review-final.md`와 `review-final/`, 실제 서비스는 `deployment/`에서 확인합니다.
- handoff: 같은 audit의 `HANDOFF.md`. 서비스와 자동 개발의 최종 상태, 통합 SHA와 다음 시작점을 확인할 때 읽습니다.
- 남은 UI 필수 작업: 없음. 새 화면 변경은 문장 이해와 함께 비교의 쉬움·첫 화면 결론·실제 데이터 시각화를 검수합니다.
