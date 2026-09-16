# R3-02 시장 연구 상세 coverage 표시

- 상태: 구현 완료·독립 검토 전
- 기록 시각: 2026-09-16T05:53:37Z
- 작업 slug: `r3-market-detail-coverage`
- 기준/통합: `c33178ec2229589a4aea63438506d3d93368b146` / 없음
- 범위: 시장 연구 상세 화면과 표시 helper, 오프라인 계약 검사, 시장 연구 계약 문서

## 변경과 결정

- `frontend/app/research/market/[id]/page.tsx`에서 결과가 `ready`, `insufficient`, `approximate`인 모든 경우에 기존 metrics와 coverage를 표시하고, 값이 없거나 malformed이면 확인 불가로 남깁니다.
- `frontend/lib/marketResearch.ts`에 결과 상태·완전성·자료 등급·자료 성격·capability 상태와 coverage 카운터 표시 helper를 추가했습니다. coverage 비율은 양의 분모가 있을 때만 계산하고 clamp하지 않습니다.
- readiness capability의 status·detail·missing range 및 배열 항목 수를 표시합니다. missing range 항목 수는 영향받은 세션·종목 수가 아닙니다. 보유 결측의 마지막 가격·경과일은 limitations 문구에 남깁니다.
- status·completeness·readiness에서 도출한 잠정 설명은 자료 확정성·최종 승격 가능성을 판단하지 않습니다. 등급과 `simulated` 자료 성격은 독립 필드로 표시합니다.
- 결과가 존재할 때 실행 request·결과 request·result·readiness의 `research_grade` 불일치를 표시 전에 차단하고, 등급·metrics·성공 상태를 `결과 확인 불가`로 숨깁니다. `result=null` 상태의 기존 안내는 유지합니다.
- 모바일 결과 화면의 overflow 원인은 입력·정책 SHA 문단에 기존 `.hashes` 줄바꿈 클래스가 빠진 것이었습니다. 상세 페이지의 해당 문단에 `basis hashes`를 적용해 기존 CSS의 `overflow-wrap:anywhere`를 사용합니다.

## 문서·계약 영향

- 사용자 계약 문서: `docs/market-research-contract.md`에 상세 coverage, unknown/zero/분모, capability 및 잠정 표시 규칙을 기록했습니다.
- 운영 문서: 해당 없음. 서비스·설정·PAPER·주문·데이터베이스를 변경하지 않았습니다.
- API·설정·데이터 계약: 기존 result metrics, completeness, readiness, limitations를 소비하며 schema와 backend 생산 경로는 변경하지 않았습니다.

## 검증

- `npm ci --no-audit --no-fund` — 통과; 대상 worktree `frontend/node_modules`에 lockfile 의존성을 격리 설치했습니다(약 6.0초).
- `npm run verify:market-research-contract` — 통과(0.21초); strict/approximate 자료·상태, legacy 누락, zero/분모0/malformed 카운터와 held-missing caveat fixture를 검사했습니다.
- `marketResearchGradeIsConsistent` 회귀 fixture — 네 등급 필드 각각의 불일치와 `result=null` 보존을 검사합니다.
- `npm run lint` — 통과(2.41초).
- `npm run typecheck` — 통과(2.27초).
- `npm run build` — 통과(2.78초); Next.js production build와 route generation을 완료했습니다.
- P2 후속 `run-checks.py ... p2 120` — 계약 검사 0.264초, lint 2.368초, typecheck 1.015초, build 2.273초 모두 통과; 실제 stdout과 route 목록은 audit `p2-*.log`에 보존했습니다.
- 모바일 overflow 수정 후 `npm run lint` — 통과(2.819초), `npm run typecheck` — 통과(0.841초), `npm run build` — 통과(3.722초); 실제 stdout과 route 목록은 부모 검증 기록과 함께 확인했습니다.
- 브라우저·fixture 서버 — 감독 agent가 담당하므로 실행하지 않습니다.

## 안전·운영 상태

- 오프라인 frontend 계약 fixture와 정적 검증만 사용합니다. provider 수집, 운영 API·DB, 서비스, PAPER/live 상태, 주문, 원격 push는 수행하지 않았습니다.
- 비밀정보·자격증명·계좌 식별자는 기록하거나 변경하지 않았습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260916-r3-02-981ad0a5`; code-check 로그는 `code-checks/`에 보존했습니다.
- 남은 작업·차단 조건: 독립 review, main 통합 검증, audit 증거와 handoff 보관은 감독 범위입니다.
- 다음 시작: 계약 검사와 lint/typecheck/build 결과를 기록한 뒤 변경 diff를 독립 검토합니다.
