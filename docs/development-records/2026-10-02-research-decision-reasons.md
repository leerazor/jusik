# 기록된 포트폴리오 거래 보류 사유 요약

- 상태: 개발·운영 배포 완료. 사용자의 운영 적용 요청으로 기존 서비스에 반영하고 실제 화면을 확인했습니다.
- 기록 시각: 2026-10-01T22:43:48.769163+00:00
- 작업 slug: `research-decision-reasons`
- 기준/통합: `554ad542f9f39081783a4e28f6c68182dd9075a4` / `7ce3142d74d42bd94d2912a3f37ef131e375b3d9`.
- 구현: `7606f2e56a5cad8a5d97ed2d3536f366989a4fb3`, 화면 보완 `8a6fe26046dae32383539a4c901b8761a9200ffe`. 병합 직전 main `3f78b2f`.

## 변경과 결정

- `/research/portfolio`의 정책 비교에 이유별 기록 요약과 정책별 원문 펼침을 추가했습니다. `frontend/lib/portfolio-decision-reasons.ts`는 각 비교의 `base.policy_events`에서 세 종류만 집계합니다.
- `frequency_skip`은 재배분 평가 횟수, `band_skip`은 종목별 기록 수, `cap_constraint_deferred`는 상한 초과 처리 보류 기록 수입니다. 단위가 달라 합산한 비율·기간·금액·거래 수로 표현하지 않습니다. 반복 사건도 보존합니다.
- `frontend/app/research/portfolio/decision-reasons.tsx`는 한국어 사건명과 원문 시각·종류·설명·값을 연결합니다. 상한 처리 보류를 전체 매매 중단으로 해석하지 않습니다. 원문 주기 문구만으로 실제 간격을 확정하지 않으며 기존의 고정된 4주·2%p 집계 라벨을 제거했습니다.
- 기록이 없으면 원인을 알 수 없다고 표시합니다. 미기록 신호·전체 현금 대기 원인을 추정하거나 다른 연구·비용 스트레스 실행의 기록을 섞지 않습니다. 정책 비교가 없는 기존 결과에는 새 요약을 만들지 않습니다.
- 독립 화면 검토의 모바일 읽기 문제를 보완했습니다. 요약 정책 열을 고정하고 가로 스크롤 안내를 추가했으며 원문은 모바일에서 사건별 항목으로 줄바꿈합니다. 스타일은 해당 표에만 적용됩니다.

## 문서·계약 영향

- 사용자 문서: [화면 설계 기준](../investor-web-design.md)에 요약 의미·원문·모바일 표시를 추가했습니다.
- API·설정·연구 데이터 계약·운영 문서: 변경 없음. 기존 typed 응답과 저장된 이벤트를 읽으며 백엔드·전략·성과 계산·동결 결과는 보존했습니다.
- 집중 검사는 `frontend/scripts/verify-portfolio-decision-reasons.ts`, 실행 명령은 `npm run verify:portfolio-decision-reasons`입니다.

## 검증

- 구현 worktree와 통합 main에서 `npm run verify:portfolio-decision-reasons`, `npm run lint`, `npm run typecheck`, `npm run build`, `git diff --check` 모두 통과했습니다.
- 집중 검사: 혼합 단위·반복 사건·비대상 사건·정책별 분리·빈 기록·안전한 원문 escape·한국어 원문 연결·표시 안내를 확인했습니다.
- 독립 코드 검토: 최초 diff와 후속 변경 모두 PASS, P1/P2 없음. 검토한 diff·파일 해시와 구현 commit이 일치합니다. 중앙 모델 라우팅 사전검사와 child 모델/effort 사후 감사도 통과했습니다.
- 브라우저: 합성 normal/empty/nonreason-only/missing-policy-experiment 네 상태 모두 HTTP 200. 빈 기록은 원인 미확인, 정책 비교 부재는 요약 미생성을 확인했습니다. 390px에서 문서 너비도 390px이며 PC·모바일 원문 접근을 확인했습니다.
- 구현 문맥을 주지 않은 독립 초보자 화면 재검토 PASS. 목적·행동 주체·사건 단위·해석 한계·다음 확인 경로를 화면 문구와 URL로 확인했습니다. agent 시뮬레이션이며 실제 참가자 연구는 아닙니다.
- main 빌드는 기존 서비스 `.next`와 분리한 `.next-build-decision-reasons`에서 수행했습니다. 전용 3353 서버의 요약·원문 링크·모바일 표시도 확인하고 종료했습니다.
- 백테스트와 백엔드 테스트는 실행하지 않았습니다. 금융 계산·백엔드 변경이 없는 표시 기능이며 합성 자료로 검증했습니다. 투자 성과 개선을 검증한 작업이 아닙니다.

## 안전·운영 상태

- 시작 시 runner paused=false, service/timer active였습니다. 수동 작업 전 pause·service stop·inactive/MainPID=0을 확인했습니다.
- 병행 `us-data-shortage-alpaca-sip-20261002`의 문서 커밋을 보존한 채 main에 통합했습니다. 해당 작업 종료를 등록부에서 확인했습니다. 이 기록 commit 뒤 기존 runner를 resume하며 실제 복원 결과는 audit의 `runtime-after.json`을 따릅니다.
- 운영 웹 서비스 배포·실주문·PAPER 승격·운영 연구 데이터 변경·원격 push 없음. 기존 사용자 `HANDOFF.md` 보존.
- 전용 3352/3353/8352 서버와 브라우저 종료 확인, 증거 보존 후 전용 worktree·병합된 브랜치·분리 빌드 출력 정리 완료.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20261002-research-decision-reasons/`. `verification.json`, `routing-audit.json`, `main-build.log`, `implementation.patch`, 합성 fixture, 화면 캡처와 `manifest.json`을 보존했습니다. 후속 runtime 파일을 제외한 최초 manifest SHA-256은 `32cf772c5733b9d789d77d0b8c85353858c9c48fe8f297b6e9d44da64e0c3ced`입니다.
- [인계](../handoffs/2026-10-02-research-decision-reasons.md)를 다음 시작점으로 사용합니다. 현재 작업의 개발·배포 잔여 없음. 아래 사용자 승인 후 배포 기록을 따릅니다.
- workflow 판단: 도움 됨 — 원천 이벤트의 서로 다른 단위와 모바일 이해 장애를 조사·독립 검토로 확인했습니다.
- 근거: 기존 이벤트/API 재사용, 단일 구현자 보완, 집중·통합 검증 PASS. 시간·호출·수익 개선은 미측정입니다.
- 다음 조정: 유지 — 기록되지 않은 원인은 추정하지 않고 추가 연구 없이 표시 범위에서 종료합니다.

## 사용자 승인 후 운영 배포

- 배포 시각: 2026-10-02T01:08:16.506654+00:00
- 배포 기준: `a460407`; 검증한 제품 통합 이후 제품 변경 없음. `./start.sh`가 고유 빌드 출력으로 production build한 뒤 3000/8000/8001 서비스를 기동했습니다. 기존 외부 인증 정책과 터널을 재사용했습니다.
- 두 백엔드 health와 `/research`, `/research/portfolio` 모두 HTTP 200이며 운영 결과에서 새 사유 요약이 확인됩니다. 브라우저에서 실제 원문 펼침과 1440px/390px 문서 너비 일치를 확인했습니다.
- 인증 없는 외부 HTTPS 요청은 401과 Basic challenge를 반환합니다. credential·인증 설정·연구 데이터·전략·주문 기능 변경 없음.
- 시작 당시 runner unpaused/timer active/service inactive였고 배포 동안만 pause했습니다. 이 기록 commit 뒤 기존 unpaused 상태를 복원하며 실제 결과는 `deployment/runner-after.json`에 보존합니다.
- 배포 로그·health.json·browser.log·PC/모바일 캡처는 기존 audit의 `deployment/`에 있습니다. 실행한 운영 서비스는 계속 유지하며 검증용 브라우저만 종료했습니다. 운영 적용 잔여 없음.
