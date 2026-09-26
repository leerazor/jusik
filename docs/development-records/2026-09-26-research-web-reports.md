# 웹 보고서와 연구 비교 설명 개선

- 상태: 완료. 구현·독립 검토·main 통합·검증과 기존 3000 포트 배포를 마쳤습니다.
- 기록 시각: 2026-09-26T08:26:39Z.
- 작업 slug: `research-web-reports`
- 조사/구현 기준: `a4194781be2655c398d85e493622626781bfc269` / `c299dbb603c7a2d51521e960f98b06748064247e`.
- 구현: `539a4967869475908d1f8da842b0d6ddd831d45b`, 각주 보완 `f465e1178323b4c743a50eb82fc2e21f00220744`. 병합 직전 main `02f6c4cea3351ddcc3e10d3e7fa0eabfa156d56a`, 통합 `422452ead8d55c62c75f655919c9eea0c601b613`.
- 범위: 프런트엔드 보고서 읽기·링크·비교 설명과 관련 문서. 백엔드·금융 계산·원문 보고서·성과 catalog·전략·인증·거래 정책은 변경하지 않습니다.

## 변경과 결정

- 사용자는 보고서를 Markdown 파일로 내려받아 읽도록 하지 말고 웹에서 보여 달라고 명시했습니다. 기존 공개 연구 5개와 모의 관찰의 기준 보고서 링크가 모두 attachment 응답임을 확인했습니다.
- ‘기존 방식’은 사용자의 투자 이력으로 오해할 수 있어 연구용 비교 설정과 변경 설정으로 설명합니다. 두 설정이 같은 과거 자료로 계산한 가상 연구라는 맥락을 먼저 제공합니다.
- 4주·8주는 정상 목표 투자 비중을 다시 계산하는 간격입니다. 과거 엔진은 기간의 첫 월요일 UTC를 기준으로 28일·56일 간격을 판별합니다. 실제 거래는 비중 차이 등 조건에 따르며 위험 대응 매도는 사이에도 발생할 수 있습니다. 투자 만기나 매번 주문을 한다는 뜻으로 표현하지 않습니다.
- 보고서는 기존 허용된 backend endpoint에서 읽는 프런트엔드 서버 페이지로 표시합니다. 공개 이력·포트폴리오 실행·배당·고정 참고 보고서를 포함합니다. 기존 Markdown URL도 웹 페이지로 연결하고 CSV·JSON 자료 내보내기는 보존합니다.
- Markdown은 `react-markdown`·`remark-gfm`으로 제목·목차·표·목록·본문을 렌더링합니다. 원문을 요약으로 대체하거나 전체 코드를 그대로 노출하지 않습니다. 실행 가능한 HTML·임의 로컬 파일·위험한 링크·자동 외부 이미지 요청을 허용하지 않습니다.
- 알려진 연구의 설명은 기존 ID·source/result/report hash 검증이 일치할 때만 연결합니다. 보고서가 없거나 연결·본문 검증에 실패해도 파일 다운로드를 대안으로 안내하지 않습니다.
- `frontend/lib/research-reports.ts`가 보고서 종류와 허용 경로·본문 검증·링크 변환을 담당하며, `frontend/app/research/reports/[...report]/page.tsx`와 같은 디렉터리의 렌더러·CSS가 웹 읽기를 담당합니다. 기존 Markdown proxy 세 종류와 개요·연구 결과·이력·모의 관찰·포트폴리오·배당 화면의 링크를 전환했습니다.
- `research-narrative.ts`와 `comparison-settings.tsx`가 검증된 연구의 조건을 수치 앞에 표시합니다. 최대 투자 비중·흔들림 목표·28일/56일 점검 간격을 구분하며, 여러 조건을 함께 바꾼 결과를 주기 하나의 효과로 표현하지 않습니다.
- 독립 검토에서 GFM 각주 참조의 ID·접근성 속성이 빠지는 P2를 재현했습니다. 같은 구현자가 속성 보존과 중복 각주 왕복 검사를 추가했고 재검토를 통과했습니다.

## 문서·계약 영향

- 사용자 문서: `docs/investor-web-design.md`에 웹 보고서 읽기와 비교 설정·주기의 설명 기준을 반영합니다.
- 지속 지침: `frontend/AGENTS.md`에 보고서의 웹 읽기 원칙을 추가합니다.
- API·금융·데이터 계약: 변경 없음. 기존 공개 아티팩트 검증과 허용 목록을 재사용합니다. 웹 Markdown 다운로드 URL의 응답은 독자 화면으로 이동하도록 변경합니다.
- 기존 1년 immutable 다운로드 응답이 이미 사용자 브라우저에 캐시돼 있으면 서버에서 회수할 수 없습니다. 화면 링크는 새 canonical URL로 교체하고, 이전 주소 호환은 새 브라우저에서 검증합니다.

## 검증

- 읽기 전용 explore·plan 완료. cadence 근거는 `research_portfolio_engine.py`와 `test_research_portfolio_volatility15_cadence_cost_tradeoff.py`의 일정·주기 사이 위험 대응 검사에서 확인했습니다.
- 원본 공개 보고서 12개를 읽기 전용 fixture로 보존했습니다. 이력 보고서 5개의 본문 SHA-256과 artifact ID가 일치합니다.
- worker와 통합 main에서 `npm run verify:research-reports -- /home/kwl/.local/share/jusik/ui-web-reports-20260926`, `npm run lint`, `npm run typecheck`, `npm run build` 모두 통과했습니다. 원문 12개의 전체 문자열·hash·숫자, 허용 경로·기존 주소 이동·안전한 링크·각주·목차·설명 식별 가드를 검사합니다. main 로그는 audit의 `main-*.log`입니다.
- 1440px·390px에서 주요 화면 6개를 확인했습니다. 실제 보고서 12개를 두 폭에서 읽고 표 행·목차 대상·본문을 확인했으며 이전 주소 12개도 웹으로 이동합니다. 브라우저 다운로드·페이지 오류·문서 가로 넘침은 0건입니다.
- 누락·연결 실패·빈 본문·변조된 이력 보고서, 미등록·식별 불일치 연구, 진행 API 실패를 구분했습니다. XSS fixture에서 실행·위험 링크·외부 이미지 요청이 없고 정상 표·목록·마지막 본문·각주가 표시됩니다. CSV·JSON 자료 내보내기는 HTTP 200과 attachment를 유지합니다.
- 각주 참조·복귀, 목차의 Enter 이동과 11초 경과 후 위치 보존을 실제 브라우저에서 확인했습니다. 초기 검사기는 한글 fragment와 인코딩된 URL을 비교했고 새 페이지 준비 전에 focus를 주어 실패했습니다. 준비 완료 뒤 focus·URL·scrollY를 함께 측정한 `browser-final.json`에서 통과했습니다. 보고서 페이지에 자동 갱신이 있다고 주장하지 않습니다.
- 별도 Sol 검토는 각주 P2 보완 뒤 필수 지적 없음입니다. explore·plan·code·review의 routing 감사도 통과했습니다.
- 배포 후 두 API health·연구 주요 화면을 확인하고 보고서 12개의 canonical/기존 주소 총 24개가 HTML 본문을 반환하는 것을 확인했습니다. 실제 3000 브라우저의 8개 화면 검사와 보고서 클릭도 통과했으며 다운로드·오류·넘침이 없습니다. 외부 터널의 기존 인증 검사도 통과했습니다.
- 백엔드 테스트는 실행하지 않았습니다. 이 작업의 backend·계산·원문 자료 diff는 없습니다. 실제 초보자 참여 시험과 스크린리더 실사용 시험은 수행하지 않았습니다.

## 안전·운영 상태

- 시작 당시 자동 개발은 unpaused·service inactive·timer active·running attempt 0이었습니다. 수동 변경 전에 pause·service stop으로 격리했습니다. 종료 후 MainPID 0이며 service의 실패 종료 상태는 운영 증거로 보존합니다.
- 구현 환경은 전용 worktree·의존성·Next 출력으로 분리하고 프런트 3338·읽기 전용 fixture 8338을 사용합니다. 운영 DB·계좌·주문 API를 테스트에 사용하지 않습니다.
- 사용자 소유 미추적 루트 `HANDOFF.md`와 다른 작업을 보존했습니다. 기존 적용·재시작 승인을 이어 받아 `./start.sh`로 기존 서비스를 교체했습니다. 첫 배포 빌드는 page data 수집 중 worker `SIGSEGV`로 종료됐고 기존 서비스를 유지했습니다. 당시 가용 메모리는 약 10GB였으며 원인은 확정하지 않았습니다. 검증용 서버를 종료한 뒤 같은 코드·설정으로 다시 실행해 빌드·서비스 기동을 통과했습니다. `start.sh`·인증 설정은 변경하지 않았습니다.
- 현재 주소는 `http://localhost:3000/research`이며 배포 실행 세션은 `84791`입니다. 기존 별도 인증 터널 세션 `25201`을 재사용했습니다. 3338·8338 검증 서버와 전용 worktree·브랜치는 증거 보존 뒤 정상 정리했습니다. 원격 push·실주문·운영 자료 직접 수정은 수행하지 않았습니다.
- 진행 중 별도 수동 작업 `performance-sprint-20260926-1656`가 등록됐습니다. 해당 기록·변경을 보존했으며 frontend·시작 스크립트에 충돌이 없음을 확인했습니다. 동시에 수동 개발과 runner가 저장소를 바꾸지 않도록 자동 실행의 pause를 유지합니다. 이 작업이 runner를 재개하지 않으며, 병행 수동 작업을 마친 감독자가 전체 상태를 확인하고 기존 설정으로 재개해야 합니다. 실제 최종 상태는 audit의 `deployment/runtime.json`에 기록합니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/ui-web-reports-20260926/`. `baseline-links.json`·`baseline-reports.json`은 기존 다운로드 문제, `report-fixtures.json`은 전체 보고서 유형의 원본 hash, `plan.json`은 확정 범위와 검증 계획입니다.
- `browser-reports.json`·`browser-states-final.json`·`browser-final.json`은 화면·실패·최종 각주와 목차 검사입니다. `deployment/health-final.json`·`deployment/browser.json`·`deployment/auth-final.json`은 실제 서비스 확인, `implementation.patch`·`preservation.json`·`manifest.json`은 변경 범위와 파일 무결성 증거입니다.
- handoff: 같은 audit의 `HANDOFF.md`. 단일 구현자는 `/root/ui_code`, root는 문서·검증·통합을 담당했습니다. 전용 worktree·브랜치는 정리했고 통합 commit과 산출물은 보존했습니다.
- 남은 필수 작업·승인 대기: 없음. 자동 실행 재개는 별도 진행 중인 성능 개선 작업의 운영 경계입니다.
- 다음 시작: 이 기록과 audit의 `HANDOFF.md`·`deployment/runtime.json`을 읽고 현재 3000 화면·Git·병행 작업의 상태를 확인합니다.
