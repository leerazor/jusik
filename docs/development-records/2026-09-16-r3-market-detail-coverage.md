# R3-02 시장 연구 상세 coverage 표시

- 상태: 완료; R3-02 기술 acceptance 충족, 경제 평가 not-evaluated
- 기록 시각: 2026-09-16T05:53:37Z
- 작업 slug: `r3-market-detail-coverage`
- 기준/통합: `c33178ec2229589a4aea63438506d3d93368b146` / `c8cb6e29b038d3724fd3b76d04788270e9221e0a`
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

## Astra 최종 통합 검증과 정리

- local main 통합: `c8cb6e29b038d3724fd3b76d04788270e9221e0a`. Terra 최종 검토는 `2bb2df73a5e02b36c9ac517a9909b4e6d44718ac` 전체에 대해 P1/P2 없음으로 통과했습니다.
- main에서 contract, lint, typecheck, build를 다시 실행해 모두 통과했습니다. 실제 stdout은 audit `integrated-*.log`, 명령·wall 시간은 `integrated-checks.json`에 있습니다. 초기 code-checks와 mobile 수정 시간은 작업자 보고이며, 독립 stdout 증거는 owner/p2/integrated 로그가 기준입니다.
- 정적 GET fixture8개, 각 최대2심볼·3세션, seed0. 최초 desktop/mobile16개는 모든 내용 검사가 통과했지만 mobile7개에서 기존 SHA 문단의 overflow가 발생했습니다. `.hashes` 재사용으로 수정하고 통합 main에서 허용된 재검증16개를 통과했습니다. 최종 overflow0·외부요청0, strict loading 두 화면 통과입니다.
- 브라우저 시작 전 cache 권한·daemon 유지·스크립트 URL 오류는 별도 실패 파일에 보존했습니다. 화면 순회 전 실패이며 fixture 추가나 연구 실행은 없었습니다. 측정·보고된 검증 시간에 추가60초 여유를 포함한 보수적 합계는132초 이내로1200초 제한 안입니다.
- 초기 model-only plaintext 감사 실패를 보존한 뒤 같은 워크트리의 구현 소유권을 Luna에 순차 인계했습니다. opaque-mode adapter pre/post와 Terra 감사는 통과했으며 원문 메시지 무결성·native role sandbox 적용을 주장하지 않습니다.
- 증거115개·SHA와 handoff를 durable audit에 먼저 보관하고 검증한 뒤, 소유 loopback 서버를 종료하고 해당 worktree·branch를 정상 제거했습니다. 기존 worktree6개와 루트 HANDOFF.md는 보존했습니다.
- R3-02 checkbox만 완료했습니다. R3 단계나 R3-03/04 등 다른 checklist는 변경하지 않았습니다. benchmark·미래 관측은 이 UI acceptance의 입력이 아니며 경제적 성공은 평가하지 않았습니다. 성과 catalog·웹 배포는 해당 없고 서비스·설정·DB·PAPER/live·주문·remote 변경은 없습니다.
- 최종 증거: `/home/kwl/.local/share/jusik/portfolio-audit/20260916-r3-02-981ad0a5/integration-verification.json`, SHA-256 `0fe76bcc80d5e141151c887ab23ffa84e8e22520b42183f9d907454f45cec550`. 전체 목록·hash는 `manifest.json`, 재개 정보는 `HANDOFF.md`입니다.
- 남은 작업: 이 slice에는 없습니다. 후속 연구나 격리 작업은 별도 위임 조건에서 판단합니다.
